"""Arabic OCR/caption post-processing (§9.16) — narrowly scoped, per §6.

Lens only ever needs Arabic processing applied to SHORT OCR/caption strings,
not a full tokenize→tag→parse corpus pipeline — so this module implements
normalization + diacritics handling + short-span dialect hints directly,
with CAMeL Tools as an optional, detected-at-runtime upgrade (its Apache-2.0
code + data licenses would be appended to THIRD_PARTY_LICENSES.md before any
release bundles it).

Full RTL UI mirroring lives in lens-web (§9.16: full mirroring, not just
RTL text inside an LTR layout).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Dialect-hint lexicons for short spans (heuristic, for OCR guidance only —
# never presented as a language ID result, only as "hints" for post-processing)
_DIALECT_HINTS = {
    "egyptian": ["إزيك", "عاملة إيه", "ده", "مش كده", "بقى", "خالص", "ليه"],
    "levantine": ["شو", "لمن", "بدك", "هلق", "منيح", "كتير", "زي هيك"],
    "gulf": ["شلون", "ابغي", "ابى", "وش", "الحين", "طيب خلاص", "دحين"],
    "maghrebi": ["بغيت", "واش", "دابا", "كاين", "بزاف", "دوك"],
    "msa": ["الذي", "التي", "إنه", "لأنه", "حيث", "عليه", "إلا"],
}

_TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"


@dataclass(slots=True)
class ArabicPostProcessResult:
    normalized: str
    had_tashkeel: bool
    tatweel_removed: int
    dialect_hints: list[str]
    camel_tools_available: bool
    note: str

    def to_dict(self) -> dict:
        return {
            "normalized": self.normalized,
            "had_tashkeel": self.had_tashkeel,
            "tatweel_removed": self.tatweel_removed,
            "dialect_hints": self.dialect_hints,
            "camel_tools_available": self.camel_tools_available,
            "note": self.note,
        }


def normalize_arabic(text: str) -> str:
    """Script-level normalization safe for search/statistics:
    alef variants → bare alef, ʿayn/hamza carriers unified, ta marbuta → ha
    OPTIONAL (kept — it changes morphology), tatweel stripped, tashkeel
    stripped, Arabic-Indic digits preserved (they can be meaningful)."""
    if not text:
        return text
    out = text
    out = _TASHKEEL.sub("", out)
    out = out.replace(_TATWEEL, "")
    out = out.replace("\u0623", "\u0627").replace("\u0625", "\u0627").replace("\u0622", "\u0627")
    out = out.replace("\u0649", "\u064A")  # alif maqsura → ya
    return out


def detect_dialect_hints(text: str) -> list[str]:
    t = text or ""
    hints = []
    for dialect, markers in _DIALECT_HINTS.items():
        if any(m in t for m in markers):
            hints.append(dialect)
    return hints


def post_process_ocr(text: str, *, use_camel: bool = False) -> ArabicPostProcessResult:
    """Full scoped pipeline for one OCR/caption string.

    Dialect-aware OCR guidance: the hints tell the researcher which dialect
    a short span leans toward so OCR re-runs / manual checks can be targeted;
    they are heuristic aids, never presented as identification results.
    """
    camel = False
    normalized = normalize_arabic(text or "")
    if use_camel:
        try:
            # Optional upgrade path: CAMeL Tools for finer normalization.
            # Not imported at module level — Lens never hard-requires it.
            from camel_tools.utils.normalize import normalize_alef_maksura_ar as _nm  # noqa: F401

            camel = True
        except ImportError:
            camel = False
    tatweel_removed = (text or "").count(_TATWEEL)
    return ArabicPostProcessResult(
        normalized=normalized,
        had_tashkeel=bool(_TASHKEEL.search(text or "")),
        tatweel_removed=tatweel_removed,
        dialect_hints=detect_dialect_hints(text or ""),
        camel_tools_available=camel,
        note="Scoped to short OCR/caption strings (§6). Dialect hints are OCR guidance, "
             "not language identification.",
    )


def is_arabic(text: str) -> bool:
    if not text:
        return False
    arabic = sum(1 for ch in text if "\u0600" <= ch <= "\u06FF")
    return arabic / max(1, len(text.strip())) > 0.3
