"""Detection + typography routes (§9.5, §9.8) — Phase-2 gap closures."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..detection.detector import DEFAULT_QUERY_CATEGORIES, get_detector, validate_detections
from ..detection.detector import SceneClassifier
from ..detection.typography import profile_typography
from ..logging import get_logger
from ..main import get_store
from ..storage.encryption import decrypt_bytes

log = get_logger(__name__)
router = APIRouter(tags=["detection"])
_scene = SceneClassifier()


async def _image_bytes(img) -> bytes:
    from ..vision.ingest import read_image_bytes

    return await asyncio.to_thread(read_image_bytes, img.storage_path,
                                   get_settings().encryption_key)


@router.get("/detection/status")
async def detection_status() -> dict:
    det = get_detector()
    st = await det.status()
    return {
        "available": st.available,
        "model": st.model,
        "revision": st.revision,
        "reason": st.reason,
        "default_categories": DEFAULT_QUERY_CATEGORIES,
        "scene_classifier_available": _scene.available(),
        "note": "Detection runs locally; no cloud vision API without the cloud opt-in.",
    }


@router.post("/images/{image_id}/detect")
async def detect_image(image_id: str, categories: list[str] | None = None,
                       threshold: float = 0.15) -> dict:
    store = get_store()
    img = store.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    det = get_detector()
    raw = await _image_bytes(img)
    detections = await det.detect(raw, categories=categories, threshold=threshold)
    scenes = await _scene.classify(raw) if _scene.available() else []
    meta = dict(img.meta or {})
    meta["detections"] = [d.to_dict() for d in detections]
    if scenes:
        meta["scenes"] = scenes
    store.update_image(image_id, meta=meta)
    return {
        "image_id": image_id,
        "detections": meta["detections"],
        "scenes": scenes,
        "model": det.name,
        "note": "Numeric, reproducible bounding boxes. The vision-LM's prose "
                "description is stored separately and never merged into this measurement.",
    }


@router.post("/imagesets/{set_id}/detect")
async def detect_set(set_id: str, categories: list[str] | None = None,
                     threshold: float = 0.15) -> dict:
    store = get_store()
    if not store.get_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    det = get_detector()
    st = await det.status()
    queued = []
    for img in store.list_images(set_id):
        queued.append(img.id)
    # Reuse the ingest queue so detection never blocks the request thread.
    from ..main import enqueue_ingest

    for image_id in queued:
        enqueue_ingest(image_id)
    return {
        "queued": queued,
        "detector_available": st.available,
        "model": st.model,
        "note": "Detections run via the background pipeline; per-image status on "
                "/images/{id}. When the detector is unavailable the queue still refreshes "
                "OCR/colour/composition but detections remain empty.",
    }


@router.get("/images/{image_id}/detections")
async def get_detections(image_id: str) -> dict:
    img = get_store().get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    return {"image_id": image_id, "detections": validate_detections(
        [d for d in (img.meta or {}).get("detections", [])])}


@router.post("/images/{image_id}/typography")
async def typography(image_id: str) -> dict:
    """Typography-in-image profile from OCR box geometry (§9.8)."""
    store = get_store()
    img = store.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    ocr = (img.meta or {}).get("ocr") or {}
    if not ocr.get("words"):
        raise HTTPException(409, "No OCR word boxes available — run/re-run OCR first.")
    profile = profile_typography(ocr["words"], img.width or 1, img.height or 1)
    meta = dict(img.meta or {})
    meta["typography"] = profile.to_dict()
    store.update_image(image_id, meta=meta)
    return profile.to_dict()
