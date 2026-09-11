"""Alignment, visual-grammar, and cross-modal routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..discourse.lenses import signals_from_meta
from ..logging import get_logger
from ..main import get_store
from ..multimodal.alignment import ClipEmbeddings, align_image_text
from ..multimodal.cross_modal import cross_modal_relations
from ..multimodal.visual_grammar import visual_grammar_score
from ..storage.encryption import decrypt_bytes

log = get_logger(__name__)

alignment_router = APIRouter(tags=["alignment"])
visual_grammar_router = APIRouter(tags=["visual-grammar"])
discourse_router = APIRouter(tags=["cross-modal"])


def _require_image(image_id: str):
    img = get_store().get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    return img


@alignment_router.post("/images/{image_id}/align")
async def align(image_id: str) -> dict:
    """Embedding-backed image–text alignment (§9.11), grid fallback labelled."""
    img = _require_image(image_id)
    ocr = (img.meta or {}).get("ocr") or {}
    from ..vision.ingest import read_image_bytes

    raw = read_image_bytes(img.storage_path, get_settings().encryption_key)
    be = ClipEmbeddings()
    result = await align_image_text(raw, ocr, backend=be)
    meta = dict(img.meta or {})
    meta["alignment"] = result
    get_store().update_image(image_id, meta=meta)
    return result


@alignment_router.get("/images/{image_id}/align")
async def get_alignment(image_id: str) -> dict:
    img = _require_image(image_id)
    alignment = (img.meta or {}).get("alignment")
    if not alignment:
        raise HTTPException(404, "No alignment computed yet — POST /images/{id}/align first.")
    return alignment


@visual_grammar_router.post("/images/{image_id}/visual-grammar")
async def run_visual_grammar(image_id: str) -> dict:
    img = _require_image(image_id)
    sig = signals_from_meta(image_id, img.meta or {})
    return visual_grammar_score(sig)


@visual_grammar_router.get("/images/{image_id}/visual-grammar")
async def get_visual_grammar(image_id: str) -> dict:
    img = _require_image(image_id)
    vg = (img.meta or {}).get("visual_grammar")
    if vg:
        return vg
    sig = signals_from_meta(image_id, img.meta or {})
    return visual_grammar_score(sig)


@discourse_router.post("/images/{image_id}/cross-modal")
async def cross_modal(image_id: str) -> dict:
    img = _require_image(image_id)
    meta = img.meta or {}
    sig = signals_from_meta(image_id, meta)
    alignment = meta.get("alignment") or {
        "backend": "none", "pairs": [],
        "note": "alignment not computed — relations are OCR/colour-grounded only",
    }
    result = cross_modal_relations(
        alignment, meta.get("colour") or {}, sig.ocr_text, annotations=sig.annotations
    )
    meta["cross_modal"] = result
    get_store().update_image(image_id, meta=meta)
    return result
