"""Image ingestion with upload hardening (§9.2).

Formats: JPG, PNG, TIFF, WebP, BMP. **Not SVG** — it is a vector/XML format;
the raster analysis path and OCR need pixels. The parent's docstring once
claimed SVG support and was flagged wrong: we drop the claim, not fix the
claim.

Hardening (v1.2.0 lesson carried forward): per-file size cap, batch cap, and
magic-byte sniffing so a mislabeled file fails clearly instead of crashing
the image library deep inside a batch.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..logging import get_logger
from ..storage.encryption import decrypt_bytes, encrypt_bytes
from ..storage.models import Image

log = get_logger(__name__)

SUPPORTED_IMAGE_FORMATS = {"jpg", "jpeg", "png", "tif", "tiff", "webp", "bmp"}


def detect_image_format(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "jpeg":
        ext = "jpg"
    if ext not in SUPPORTED_IMAGE_FORMATS:
        raise ValueError(
            f"Unsupported image format: .{ext} (supported: {sorted(SUPPORTED_IMAGE_FORMATS)})"
        )
    return ext


def sniff_image_format(raw: bytes) -> str | None:
    """Detect the real image format from magic bytes.

    Uploads must not trust the filename extension alone — a text file named
    .png would crash the analysis pipeline inside Pillow with a confusing
    error. Returns a SUPPORTED_IMAGE_FORMATS value, or None when the bytes
    don't match any known raster image header (§9.2: "a mislabeled file
    fails clearly instead of crashing the image library").
    """
    if len(raw) < 12:
        return None
    if raw[:3] == b"\xff\xd8\xff":
        return "jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:4] == b"GIF8":
        return None  # GIF moved out of scope for Lens 0.1.0 (rare in research sets; document)
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    if raw[:4] in (b"II*\x00", b"MM\x00*"):
        return "tif"
    if raw[:2] == b"BM":
        return "bmp"
    return None


def validate_upload(raw: bytes, filename: str) -> str:
    """Validate one uploaded file; returns the canonical format id.

    Raises ``ValueError`` with a user-actionable message on any failure.
    """
    settings = get_settings()
    ext_fmt = detect_image_format(filename)  # extension must be a supported type
    if len(raw) == 0:
        raise ValueError(f"'{filename}' is empty.")
    max_bytes = settings.max_file_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise ValueError(
            f"'{filename}' is {len(raw) / 1048576:.1f} MB — the per-file cap is "
            f"{settings.max_file_mb} MB."
        )
    sniffed = sniff_image_format(raw)
    if sniffed is None:
        raise ValueError(
            f"'{filename}' does not look like a real {ext_fmt.upper()} file "
            f"(magic-byte check failed). A mislabeled file would crash analysis later; "
            f"re-export it as a raster image and retry."
        )
    if sniffed != ext_fmt and not (sniffed, ext_fmt) in {("tif", "tif"), ("jpg", "jpg")}:
        # TIF/TIFF and JPG/JPEG share magic bytes; everything else must agree.
        if not {sniffed, ext_fmt} <= {"tif"} and not {sniffed, ext_fmt} <= {"jpg"}:
            raise ValueError(
                f"'{filename}' is labelled .{ext_fmt} but its bytes are {sniffed.upper()}. "
                f"Rename it to match its real format and retry."
            )
    return ext_fmt


def load_image(raw: bytes) -> Any:
    """Load image bytes into an RGB PIL Image (decryption-aware callers pass
    decrypted bytes; see :func:`read_image_bytes`)."""
    from PIL import Image as PILImage

    img = PILImage.open(io.BytesIO(raw))
    return img.convert("RGB")


def read_image_bytes(storage_path: str | Path, encryption_key: str | None = None) -> bytes:
    """Every image-bytes read in the engine must go through this helper so
    at-rest encryption is transparent (the v1.2.0 lesson: one route decrypted
    and the others sent ciphertext to the vision model)."""
    blob = Path(storage_path).read_bytes()
    if encryption_key is None:
        from ..config import get_settings

        encryption_key = get_settings().encryption_key
    return decrypt_bytes(blob, encryption_key)


def make_thumbnail(raw: bytes, *, max_side: int = 512) -> bytes:
    from PIL import Image as PILImage

    img = PILImage.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


@dataclass(frozen=True, slots=True)
class ImageInfo:
    width: int
    height: int
    format: str
    mode: str
    size_bytes: int


def get_image_info(raw: bytes, filename: str) -> ImageInfo:
    img = load_image(raw)
    return ImageInfo(
        width=img.width,
        height=img.height,
        format=detect_image_format(filename),
        mode=img.mode,
        size_bytes=len(raw),
    )


def persist_image_bytes(
    img: Image, raw: bytes, *, settings: Any | None = None
) -> tuple[str, str]:
    """Write raw bytes (+ thumbnail) under the data dir, honouring at-rest
    encryption. Returns (storage_path, thumb_path)."""
    from ..config import get_settings

    s = settings or get_settings()
    base = s.data_dir / "images" / img.image_set_id
    base.mkdir(parents=True, exist_ok=True)
    enc = encrypt_bytes(raw, s.encryption_key)
    storage_path = base / f"{img.id}_{Path(img.filename).name}"
    storage_path.write_bytes(enc)

    thumb = make_thumbnail(raw)
    tbase = s.data_dir / "thumbs" / img.image_set_id
    tbase.mkdir(parents=True, exist_ok=True)
    # Thumbnails are derived artifacts; encrypt with the same policy.
    thumb_path = tbase / f"{img.id}.png"
    thumb_path.write_bytes(encrypt_bytes(thumb, s.encryption_key))
    return str(storage_path), str(thumb_path)
