"""Annotation routes (§9.9) — the five-dimension visual annotation framework.

Multi-select values + free-text note per dimension per image; unknown
category ids are rejected server-side (a typo never silently corrupts a
corpus). Bulk-tagging across a whole set. This is Lens's most distinctive
existing asset — the schema is a frozen contract.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..main import get_store
from ..vision.annotations import (SCHEMA, normalise_annotations, read_annotations)

router = APIRouter(tags=["annotations"])


@router.get("/annotations/schema")
async def annotation_schema() -> dict:
    """The full five-dimension schema (the UI renders its pickers from this)."""
    return {"dimensions": SCHEMA}


class AnnotationPayload(BaseModel):
    dimensions: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


@router.put("/images/{image_id}/annotations")
async def set_annotations(image_id: str, payload: AnnotationPayload) -> dict:
    store = get_store()
    img = store.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    try:
        clean = normalise_annotations(payload.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    meta = dict(img.meta or {})
    meta["tags"] = clean["tags"]
    annotations = dict(meta.get("annotations") or {})
    for dim, block in clean["dimensions"].items():
        annotations[dim] = block
    meta["annotations"] = annotations
    store.update_image(image_id, meta=meta)
    return read_annotations(meta)


@router.get("/images/{image_id}/annotations")
async def get_annotations(image_id: str) -> dict:
    img = get_store().get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    return read_annotations(img.meta)


class BulkTagPayload(BaseModel):
    tags: list[str]
    image_ids: list[str] | None = None   # None → whole set


@router.post("/imagesets/{set_id}/annotations/bulk-tags")
async def bulk_tag(set_id: str, payload: BulkTagPayload) -> dict:
    """Bulk-tag across a whole set or an explicit subset (§9.9)."""
    store = get_store()
    images = store.list_images(set_id)
    if payload.image_ids is not None:
        wanted = set(payload.image_ids)
        images = [i for i in images if i.id in wanted]
    try:
        tags = normalise_annotations({"tags": payload.tags})["tags"]
    except ValueError:
        raise HTTPException(422, "Invalid tags payload")
    n = 0
    for img in images:
        meta = dict(img.meta or {})
        current = list(meta.get("tags") or [])
        merged = list(dict.fromkeys(current + tags))
        meta["tags"] = merged
        store.update_image(img.id, meta=meta)
        n += 1
    return {"tagged": n, "tags": tags}
