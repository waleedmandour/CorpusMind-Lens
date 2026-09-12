"""OCR corpus tools (§9.15): KWIC over OCR text + captions, word-frequency
lists with shared EN/AR stopword handling, set-vs-set keyness on extracted
text, and export as a <doc>-marked corpus file or structured JSON — so the
extracted text can flow into any standard text-analysis tool (including a
Companion-linked CorpusMind Text instance, §5).
"""
from __future__ import annotations

import re
from collections import Counter

from fastapi import APIRouter, HTTPException

from ..main import get_store
from ..config import get_settings
from ..nlp_ar.normalize import is_arabic, normalize_arabic
from ..stats import measures as M

router = APIRouter(tags=["ocrtools"])

EN_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "by", "from", "is", "are", "was", "were", "be", "been", "it", "its",
    "this", "that", "these", "those", "as", "at", "so", "if", "then", "than",
}
AR_STOPWORDS = {
    "في", "من", "على", "إلى", "عن", "أن", "إن", "التي", "الذي", "هذا", "هذه",
    "ذلك", "كان", "كانت", "ما", "لا", "لم", "لن", "قد", "كل", "بين", "عند",
}
STOPWORDS = EN_STOPWORDS | AR_STOPWORDS

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


def _tokens(text: str, *, remove_stopwords: bool = True) -> list[str]:
    toks = [t.lower() for t in _TOKEN_RE.findall(text or "")]
    if remove_stopwords:
        toks = [t for t in toks if t not in STOPWORDS]
    return toks


def _set_text(set_id: str, include_captions: bool = True) -> list[tuple[str, str]]:
    """(image_id, text) pairs in reading order."""
    store = get_store()
    if not store.get_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    out = []
    for img in store.list_images(set_id):
        meta = img.meta or {}
        text = (meta.get("ocr") or {}).get("text", "") or ""
        if include_captions:
            caption = (meta.get("user") or {}).get("caption", "")
            if caption:
                text = (text + " " + caption).strip()
        if text.strip():
            out.append((img.id, text))
    return out


@router.get("/imagesets/{set_id}/ocrtools/wordlist")
async def wordlist(set_id: str, stopwords: bool = True, normalize_ar: bool = True) -> dict:
    docs = _set_text(set_id)
    counts: Counter = Counter()
    for _iid, text in docs:
        if normalize_ar and is_arabic(text):
            text = normalize_arabic(text)
        counts.update(_tokens(text, remove_stopwords=stopwords))
    n = sum(counts.values())
    return {
        "tokens": n,
        "types": len(counts),
        "ttr": round(M.type_token_ratio([t for t, c in counts.items() for _ in range(c)]), 4) if n else 0.0,
        "items": [{"word": w, "count": c, "freq_pm": round(c / n * 1_000_000, 2) if n else 0}
                  for w, c in counts.most_common()],
    }


@router.get("/imagesets/{set_id}/ocrtools/kwic")
async def kwic(set_id: str, query: str, context_words: int = 6) -> dict:
    docs = _set_text(set_id)
    q = query.lower()
    hits = []
    for iid, text in docs:
        toks = _tokens(text, remove_stopwords=False)
        for i, tok in enumerate(toks):
            if q in tok:
                hits.append({
                    "image_id": iid,
                    "left": toks[max(0, i - context_words): i],
                    "node": tok,
                    "right": toks[i + 1: i + 1 + context_words],
                })
    return {"query": query, "hits": hits[:200], "total": len(hits)}


@router.get("/imagesets/{set_id}/ocrtools/keyness")
async def keyness(set_id: str, reference_set_id: str, stopwords: bool = True) -> dict:
    target = _set_text(set_id)
    ref = _set_text(reference_set_id)
    ct: Counter = Counter()
    cr: Counter = Counter()
    for _iid, text in target:
        ct.update(_tokens(text, remove_stopwords=stopwords))
    for _iid, text in ref:
        cr.update(_tokens(text, remove_stopwords=stopwords))
    N1, N2 = sum(ct.values()), sum(cr.values())
    rows = []
    for term in set(ct) | set(cr):
        row = M.compute_keyness_row(term, ct[term], cr[term], N1, N2)
        rows.append({
            "term": row.term, "f1": row.f1, "f2": row.f2,
            **{k: (round(v, 4) if abs(v) != float("inf") else v)
               for k, v in row.measures.items()},
        })
    rows.sort(key=lambda r: r["log_likelihood"], reverse=True)
    return {"N1": N1, "N2": N2, "rows": rows,
            "note": "Significance + effect size always together (Hardie's discipline)."}


@router.get("/imagesets/{set_id}/ocrtools/export-corpus")
async def export_corpus(set_id: str, format: str = "txt") -> dict:
    """Export the extracted text as a <doc>-marked corpus file (flows into
    AntConc/WordSmith/CorpusMind Text) or structured JSON (§9.15)."""
    docs = _set_text(set_id)
    if format == "json":
        return {"docs": [{"image_id": iid, "text": text} for iid, text in docs]}
    body = "\n\n".join(f"<doc id=\"{iid}\">\n{text}\n</doc>" for iid, text in docs)
    return {"format": "txt", "body": body}


@router.post("/images/{image_id}/ocr/vision")
async def ocr_via_vision_model(image_id: str, model: str | None = None) -> dict:
    """Re-extract text with a local Ollama vision model (v0.2).

    For packaged builds (no Tesseract) or low-confidence pages. Overwrites
    the stored OCR **text**; per-word boxes are NOT produced (a VLM returns
    text only), so typography/word-geometry features stay tied to Tesseract
    results. The engine label in the response is always explicit.
    """
    from fastapi import HTTPException

    from ..main import get_store
    from ..vision.ingest import read_image_bytes
    from ..vision.ocr import run_vision_ocr

    store = get_store()
    img = store.get_image(image_id)
    if img is None:
        raise HTTPException(404, "Image not found")
    raw = read_image_bytes(img.storage_path, get_settings().encryption_key)
    result = await run_vision_ocr(raw, model=model)
    if result.text:
        meta = dict(img.meta or {})
        meta["ocr"] = result.to_dict()
        store.update_image(image_id, meta=meta)
    return {"image_id": image_id, **result.to_dict(),
            "note": "Vision-model OCR has no per-word boxes; tesseract remains "
                    "the engine of record for typography/word geometry."}
