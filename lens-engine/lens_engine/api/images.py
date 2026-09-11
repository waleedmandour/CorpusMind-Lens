"""Image upload / retrieval / re-analysis routes (§9.2–9.4).

Uploads are validated (magic bytes, caps), persisted (optionally encrypted),
and queued for BACKGROUND analysis — the request thread never runs
Pillow/Tesseract/numpy analysis (§13; the parent's documented regression).
"""
from __future__ import annotations

from datetime import UTC, datetime

from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..config import get_settings
from ..main import enqueue_ingest, get_store
from ..storage.models import Image
from ..storage.store import new_id
from ..vision import ingest as ingest_mod
from ..vision.meta import merge_user_fields

router = APIRouter(tags=["images"])


@router.post("/imagesets/{set_id}/images", status_code=202)
async def upload_images(
    set_id: str,
    files: list[UploadFile] = File(...),
    ocr_language: str | None = Form(None),
) -> dict:
    """Batch upload. Returns 202 immediately; analysis proceeds in the
    background with per-image status on the image objects (§13)."""
    settings = get_settings()
    store = get_store()
    s = store.get_image_set(set_id)
    if not s:
        raise HTTPException(404, "Image set not found")
    if len(files) > settings.max_batch_images:
        raise HTTPException(413, f"Batch cap is {settings.max_batch_images} images.")

    accepted, rejected = [], []
    for f in files:
        try:
            raw = await f.read()
            fmt = ingest_mod.validate_upload(raw, f.filename or "unnamed")
        except ValueError as e:
            rejected.append({"filename": f.filename, "error": str(e)})
            continue
        except Exception as e:  # unreadable upload stream
            rejected.append({"filename": f.filename, "error": f"unreadable upload: {e}"})
            continue

        img = Image(
            id=new_id(),
            image_set_id=set_id,
            filename=f.filename or f"{new_id()}.{fmt}",
            storage_path="",
            format=fmt,
            size_bytes=len(raw),
            status="pending",
        )
        storage_path, thumb_path = ingest_mod.persist_image_bytes(img, raw, settings=settings)
        img.storage_path = storage_path
        img.thumb_path = thumb_path
        store.add_image(img)
        enqueue_ingest(img.id)
        accepted.append(img.id)

    if ocr_language:
        store.update_image_set(set_id, meta={**(s.meta or {}), "ocr_language": ocr_language})
    return {"accepted": accepted, "rejected": rejected, "queued": len(accepted)}


@router.get("/imagesets/{set_id}/images")
async def list_images(set_id: str) -> list[dict]:
    return [asdict(i) for i in get_store().list_images(set_id)]


@router.get("/images/{image_id}")
async def get_image(image_id: str) -> dict:
    img = get_store().get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    d = asdict(img)
    d.pop("storage_path", None)  # internal path stays internal
    return d


@router.get("/images/{image_id}/thumbnail")
async def image_thumbnail(image_id: str) -> Response:
    from ..storage.encryption import decrypt_bytes

    img = get_store().get_image(image_id)
    if not img or not img.thumb_path:
        raise HTTPException(404, "Image not found")
    blob = decrypt_bytes(open(img.thumb_path, "rb").read(), get_settings().encryption_key)
    return Response(content=blob, media_type="image/png")


@router.delete("/images/{image_id}")
async def delete_image(image_id: str) -> dict:
    img = get_store().delete_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    import contextlib
    import pathlib

    for p in (img.storage_path, img.thumb_path):
        with contextlib.suppress(OSError):
            pathlib.Path(p).unlink(missing_ok=True)
    return {"deleted": image_id}


@router.post("/images/{image_id}/reanalyze")
async def reanalyze_image(image_id: str, ocr_language: str | None = None) -> dict:
    """Re-run the deterministic pipeline (e.g. after installing a missing
    OCR language pack — a missing pack at ingest time is not permanent, §9.4)."""
    store = get_store()
    img = store.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    set_language = None
    parent = store.get_image_set(img.image_set_id)
    if parent:
        set_language = (parent.meta or {}).get("ocr_language")
    enqueue_ingest(image_id)
    return {"queued": image_id, "ocr_language": ocr_language or set_language or "english"}


@router.post("/images/{image_id}/user-fields")
async def set_user_fields(image_id: str, fields: dict) -> dict:
    """User-editable IPTC fields (source/publication/licence/genre/language-
    of-embedded-text), merged non-destructively; machine blocks are never
    user-overwritable (§9.3)."""
    from ..vision.meta import USER_FIELD_IDS

    store = get_store()
    img = store.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    unknown = set(fields) - set(USER_FIELD_IDS)
    if unknown:
        raise HTTPException(422, f"Unknown user fields: {sorted(unknown)}")
    meta = merge_user_fields(dict(img.meta or {}), fields)
    img = store.update_image(image_id, meta=meta, updated_at=datetime.now(UTC).isoformat())
    return {"user": meta.get("user", {})}
