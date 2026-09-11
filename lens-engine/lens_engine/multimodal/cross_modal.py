"""Cross-modal meaning (§9.12) — relations between image and text.

Reinforcement, complementarity, contradiction, irony, mismatch,
amplification, silence, redundancy — each output labelled with which
alignment (§9.11) it is based on. Deterministic heuristics operate on the
alignment pairs + sentiment lexicons; every relation cites the alignment
backend that produced its evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

_POS = {"happy", "hope", "unity", "peace", "growth", "future", "together", "success",
        "free", "family", "love", "win", "progress", "safe"}
_NEG = {"fear", "threat", "crisis", "danger", "enemy", "war", "corrupt", "decline",
        "chaos", "victim", "loss", "fail", "broken", "alone", "hate"}


def _valence(text: str) -> int:
    t = f" {text.lower()} "
    pos = sum(1 for w in _POS if f" {w} " in t)
    neg = sum(1 for w in _NEG if f" {w} " in t)
    return pos - neg


def _image_valence(colour: dict) -> int:
    """Coarse deterministic proxy: warm + bright + saturated leans positive."""
    if not colour:
        return 0
    warm = float(colour.get("warm_cold_balance", 0))
    bright = float(colour.get("brightness", 128)) - 128
    score = warm + bright / 128.0
    if score > 0.35:
        return 1
    if score < -0.35:
        return -1
    return 0


def cross_modal_relations(alignment: dict, colour: dict, ocr_text: str,
                          *, annotations: dict | None = None) -> dict:
    """Derive cross-modal relations from an alignment result + signals.

    The alignment backend is propagated to every relation so nothing is
    presented without its provenance (§9.12).
    """
    backend = alignment.get("backend", "none")
    pairs = alignment.get("pairs", [])
    rels: list[dict] = []

    text_val = _valence(ocr_text)
    img_val = _image_valence(colour)

    if not ocr_text.strip():
        rels.append({
            "relation": "silence",
            "note": "No embedded text detected; the image carries the message alone "
                    "(or text is present but unreadable — check OCR confidence).",
            "based_on": {"ocr.word_count": 0},
            "confidence": 0.6,
        })
        return {"backend": backend, "relations": rels}

    if pairs:
        rels.append({
            "relation": "reinforcement" if text_val * img_val >= 0 else "contradiction",
            "note": ("text and image valence point the same way" if text_val * img_val >= 0
                     else "text and image valence diverge — check for irony/mismatch"),
            "based_on": {"text_valence": text_val, "image_valence": img_val,
                         "alignment_backend": backend},
            "confidence": 0.45 if abs(text_val) and img_val else 0.3,
        })

    mm = ((annotations or {}).get("multimodal_integration") or {}).get("values") or []
    if "anchorage" in mm:
        rels.append({
            "relation": "amplification",
            "note": "annotated 'anchorage': text fixes/directs the image's meaning "
                    "(Barthes 1977).",
            "based_on": {"annotations.multimodal_integration": "anchorage"},
            "confidence": 0.6,
        })
    if "relay" in mm:
        rels.append({
            "relation": "complementarity",
            "note": "annotated 'relay': text and image advance meaning together.",
            "based_on": {"annotations.multimodal_integration": "relay"},
            "confidence": 0.6,
        })
    if "contradiction" in mm:
        rels.append({
            "relation": "irony",
            "note": "annotated 'contradiction': text-image tension flagged by the "
                    "researcher; treat as a strong candidate reading.",
            "based_on": {"annotations.multimodal_integration": "contradiction"},
            "confidence": 0.7,
        })

    if not pairs and rels == []:
        rels.append({
            "relation": "mismatch",
            "note": "no alignment pairs available to ground a relation; the alignment "
                    "backend may be unavailable (grid fallback returns geometry only).",
            "based_on": {"alignment_backend": backend},
            "confidence": 0.2,
        })

    return {"backend": backend, "relations": rels}
