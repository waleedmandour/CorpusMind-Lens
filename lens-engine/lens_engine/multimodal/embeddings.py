"""Text-embedding backend over local Ollama (v0.2) + semantic search.

Why: the packaged (PyInstaller) build ships WITHOUT torch — the CLIP stack
in ``alignment.py`` honestly degrades to the grid heuristic there. Ollama's
``/api/embed`` closes the text-side semantic gap for every installation
that has a local Ollama (which the Setup screen makes the default):

* default model ``bge-m3`` — multilingual (100+ languages, strong Arabic),
  small (1.2 GB), runs on CPU.
* vectors are cached in the image's ``meta["semantic"]["embeddings"]`` so a
  re-search is pure numpy.

Honesty rules (same as everywhere in Lens):

* The response always names ``model`` + ``provider`` + ``coverage`` (how
  many images in the set are actually embedded vs skipped).
* No Ollama → 409 with a setup hint, never a fake result.
* Cosine similarity is reported raw; no fake confidence rescaling.
"""
from __future__ import annotations

import asyncio
import math

from ..ai.providers import OllamaProvider
from ..logging import get_logger
from ..models_defaults import effective_model

log = get_logger(__name__)


class SemanticUnavailableError(RuntimeError):
    """Local AI backend or embedding model missing — the API layer turns
    this into HTTP 409 with a setup hint; the UI opens the Setup flow."""


def _ocr_text(meta: dict) -> str:
    ocr = (meta or {}).get("ocr") or {}
    text = ocr.get("text") or ""
    caption = ((meta or {}).get("user") or {}).get("caption") or ""
    return f"{text} {caption}".strip()


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


async def embed_text(text: str, *, model: str | None = None) -> list[float]:
    model = model or effective_model("embed")
    resp = await OllamaProvider().embed(text, model=model)
    return resp.vector


async def _ensure_model(model: str) -> None:
    """Raise a clear error if Ollama or the embedding model is missing —
    the UI turns this into the Setup flow, never a silent empty result."""
    provider = OllamaProvider()
    if not await provider.health():
        raise SemanticUnavailableError(
            "Ollama is not reachable on 127.0.0.1:11434. Start it (or use "
            "Settings → AI Backend → Start/Install) and pull the embedding "
            f"model '{model}' — see the Setup screen."
        )
    models = await provider.list_models()
    if models and not any(m == model or m.split(":")[0] == model.split(":")[0] for m in models):
        raise SemanticUnavailableError(
            f"Embedding model '{model}' is not pulled yet. Run: ollama pull {model} "
            "(or pick another embedding model in Settings → AI Backend)."
        )


async def ensure_embeddings(set_images: list, *, force: bool = False) -> dict:
    """Embed OCR+caption text for every image missing a cached vector.

    Mutates each image's ``meta["semantic"]`` via ``store.update_image``.
    Returns coverage stats. Images without any text are skipped (and
    reported) — there is nothing to embed.
    """
    from ..main import get_store

    
    model = effective_model("embed")
    await _ensure_model(model)

    store = get_store()
    embedded = skipped_no_text = cached = 0
    for img in set_images:
        text = _ocr_text(img.meta)
        sem = (img.meta or {}).get("semantic") or {}
        if not force and sem.get("embeddings", {}).get("vector") and \
                sem.get("embeddings", {}).get("model") == model:
            cached += 1
            continue
        if not text:
            skipped_no_text += 1
            continue
        vec = await embed_text(text, model=model)
        sem["embeddings"] = {"model": model, "provider": "ollama", "vector": vec}
        merged = dict(img.meta or {})
        merged["semantic"] = sem
        store.update_image(img.id, meta=merged)
        embedded += 1
    return {"model": model, "embedded": embedded, "cached": cached,
            "skipped_no_text": skipped_no_text, "total": len(set_images)}


async def semantic_search(set_images: list, query: str, *, top_k: int = 20) -> dict:
    """Rank the set's images by cosine(query, ocr+caption embedding)."""
    
    model = effective_model("embed")
    qvec = await embed_text(query, model=model)
    hits = []
    missed = 0
    for img in set_images:
        sem = (img.meta or {}).get("semantic") or {}
        emb = sem.get("embeddings") or {}
        vec = emb.get("vector")
        if not vec or len(vec) != len(qvec):
            missed += 1
            continue
        hits.append({
            "image_id": img.id,
            "filename": img.filename,
            "similarity": round(_cos(qvec, vec), 4),
            "snippet": _ocr_text(img.meta)[:180],
        })
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return {"query": query, "model": model, "provider": "ollama",
            "hits": hits[:top_k], "scored": len(hits), "unscored_no_embedding": missed}
