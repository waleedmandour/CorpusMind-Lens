"""Image-set CRUD + set-level statistics (§9.1).

ImageSet is the top-level corpus unit — Lens's own concept, replacing the
inherited Project → Corpus → {Documents, ImageSets} hierarchy (§7). The UI
vocabulary is "image sets"; there is no text-corpus-shaped affordance here.
``companion_link`` is the only place a CorpusMind (Text) identifier is ever
stored, and it is nullable and inert unless Companion Mode is on (§5).
"""
from __future__ import annotations

from collections import Counter

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..main import get_store

router = APIRouter(tags=["imagesets"])


class ImageSetIn(BaseModel):
    project_id: str
    name: str
    description: str = ""
    provenance_notes: str = ""
    meta: dict = Field(default_factory=dict)       # genre/source/date-range etc. (user-definable)
    tags: list[str] = Field(default_factory=list)


class ImageSetPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    provenance_notes: str | None = None
    meta: dict | None = None
    tags: list[str] | None = None
    companion_link: dict | None = None


@router.get("/projects/{project_id}/imagesets")
async def list_image_sets(project_id: str) -> list[dict]:
    return [asdict(s) for s in get_store().list_image_sets(project_id)]


@router.post("/imagesets", status_code=201)
async def create_image_set(payload: ImageSetIn) -> dict:
    store = get_store()
    if not store.get_project(payload.project_id):
        raise HTTPException(404, "Project not found")
    s = store.create_image_set(
        payload.project_id, payload.name, payload.description,
        payload.provenance_notes, payload.meta, payload.tags,
    )
    return asdict(s)


@router.get("/imagesets/{set_id}")
async def get_image_set(set_id: str) -> dict:
    s = get_store().get_image_set(set_id)
    if not s:
        raise HTTPException(404, "Image set not found")
    return asdict(s)


@router.patch("/imagesets/{set_id}")
async def patch_image_set(set_id: str, payload: ImageSetPatch) -> dict:
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    s = get_store().update_image_set(set_id, **fields)
    if not s:
        raise HTTPException(404, "Image set not found")
    return asdict(s)


@router.delete("/imagesets/{set_id}")
async def delete_image_set(set_id: str) -> dict:
    if not get_store().delete_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    return {"deleted": set_id}


@router.get("/imagesets/{set_id}/stats")
async def image_set_stats(set_id: str) -> dict:
    """Set-level statistics: format mix, orientation mix, resolution/date
    ranges, OCR/caption/VLM/annotation coverage (§9.1)."""
    store = get_store()
    s = store.get_image_set(set_id)
    if not s:
        raise HTTPException(404, "Image set not found")
    images = store.list_images(set_id)

    fmt_mix = Counter(i.format for i in images)
    orient = Counter(
        ("landscape" if i.width > i.height else "portrait" if i.height > i.width else "square")
        for i in images if i.width
    )
    widths = [i.width for i in images if i.width]
    heights = [i.height for i in images if i.height]
    dates = sorted(
        (i.meta.get("exif_xmp", {}).get("exif", {}).get("date_time_original") or "")
        for i in images
    )
    dates = [d for d in dates if d]

    def coverage(pred) -> float:
        return round(sum(1 for i in images if pred(i)) / len(images), 4) if images else 0.0

    ann_dims = ["visual_morphology", "attentional_framing", "shot_scale", "path_transition",
                "multimodal_integration"]
    return {
        "image_count": len(images),
        "format_mix": dict(fmt_mix),
        "orientation_mix": dict(orient),
        "resolution_range": {"min_w": min(widths) if widths else 0,
                             "max_w": max(widths) if widths else 0,
                             "min_h": min(heights) if heights else 0,
                             "max_h": max(heights) if heights else 0},
        "capture_date_range": {"from": dates[0] if dates else None,
                               "to": dates[-1] if dates else None},
        "coverage": {
            "ocr": coverage(lambda i: bool((i.meta.get("ocr") or {}).get("text"))),
            "vlm_description": coverage(lambda i: bool(i.meta.get("vlm_description"))),
            "detections": coverage(lambda i: bool(i.meta.get("detections"))),
            **{
                f"annotations:{d}": coverage(
                    lambda i, d=d: bool((i.meta.get("annotations", {}).get(d) or {}).get("values"))
                ) for d in ann_dims
            },
        },
    }
