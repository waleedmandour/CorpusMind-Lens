"""Semantic search over an image set's OCR + caption text (v0.2).

``POST /imagesets/{set_id}/semantic-search  { query, force? }``

Embeddings come from the local Ollama (default ``bge-m3``, multilingual
EN+AR). Vectors are cached per image in ``meta.semantic``; the first search
on a set embeds everything (progress is implicit — small sets embed in
seconds on CPU). Every response names the model/provider and its coverage.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..main import get_store
from ..logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["semantic"])


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 20
    force: bool = False   # re-embed even when a cached vector exists


@router.post("/imagesets/{set_id}/semantic-search")
async def semantic_search(set_id: str, body: SemanticSearchRequest) -> dict:
    from ..multimodal import embeddings as E
    from ..multimodal.embeddings import SemanticUnavailableError

    store = get_store()
    if not store.get_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    if not body.query.strip():
        raise HTTPException(422, "query must not be empty")
    images = store.list_images(set_id)

    try:
        coverage = await E.ensure_embeddings(images, force=body.force)
        # Re-fetch: ensure_embeddings persisted vectors via the store, but
        # the in-memory objects above still lack them (stale meta) — the
        # scorer must read the fresh rows.
        images = store.list_images(set_id)
        result = await E.semantic_search(images, body.query.strip(), top_k=body.top_k)
    except SemanticUnavailableError as e:
        raise HTTPException(409, str(e)) from e
    return {**result, "coverage": coverage,
            "note": "Text-side semantics over OCR+captions via the local Ollama "
                    f"({result['model']}). This is not CLIP joint-space image "
                    "similarity — image crops are not embedded."}
