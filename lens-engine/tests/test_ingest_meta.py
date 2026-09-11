"""Ingestion hardening (§9.2): magic-byte sniffing, caps, mislabeled files
fail clearly. Also: EXIF/XMP extraction with GPS permanently excluded."""
from __future__ import annotations

import pytest

from lens_engine.vision.ingest import detect_image_format, sniff_image_format, validate_upload
from lens_engine.vision.meta import extract_metadata, merge_user_fields
from tests.conftest import make_png


def test_sniff_real_png():
    raw = make_png()
    assert sniff_image_format(raw) == "png"


def test_sniff_rejects_text_file():
    assert sniff_image_format(b"hello world this is not an image at all!!") is None


def test_sniff_jpeg_magic():
    assert sniff_image_format(b"\xff\xd8\xff\xe0" + b"x" * 20) == "jpg"
    assert sniff_image_format(b"RIFF1234WEBPVP8 " + b"x" * 10) == "webp"
    assert sniff_image_format(b"II*\x00" + b"x" * 10) == "tif"
    assert sniff_image_format(b"BM" + b"x" * 12) == "bmp"


def test_validate_rejects_mislabeled_file():
    with pytest.raises(ValueError, match="magic-byte check failed"):
        validate_upload(b"not an image", "fake.png")


def test_validate_rejects_svg():
    with pytest.raises(ValueError, match="Unsupported image format"):
        validate_upload(b"<svg></svg>", "vector.svg")  # deliberately unsupported


def test_validate_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_upload(b"", "x.png")


def test_validate_rejects_wrong_extension_vs_bytes():
    raw = make_png()
    with pytest.raises(ValueError, match="bytes are PNG"):
        validate_upload(raw, "actually-png.jpg")


def test_detect_format_normalises_jpeg():
    assert detect_image_format("photo.jpeg") == "jpg"


def test_metadata_never_contains_gps():
    raw = make_png()
    meta = extract_metadata(raw)
    assert meta["gps"]["extracted"] is False
    assert "GPS is never extracted" in meta["gps"]["reason"]
    # even if XMP EXIF contains GPS namespace fragments, none are surfaced
    xmp = meta["xmp"]
    for key in xmp:
        assert "gps" not in key.lower()
        assert "latitude" not in str(xmp[key]).lower()


def test_user_fields_merge_is_nondestructive():
    meta = {"exif": {"make": "X"}, "xmp": {"creator": "Y"}}
    merged = merge_user_fields(meta, {"source": "Newspaper archive", "hacked": "nope"})
    assert merged["user"]["source"] == "Newspaper archive"
    assert "hacked" not in merged["user"]
    assert merged["exif"] == {"make": "X"}      # machine blocks untouched
    assert merged["xmp"]["creator"] == "Y"
