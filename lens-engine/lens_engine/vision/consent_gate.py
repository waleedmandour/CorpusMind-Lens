"""Consent-gate filter for vision-LM output (§9.6, §17).

A vision-LM asked to describe a photo will volunteer age/emotion/gender-
presentation commentary about people in it whether or not anyone asked.
While the dedicated facial-analysis module is gated by Settings, the
/describe route and the discourse routes' LLM mode have no gate of their
own — this module is the response-shaping filter every person-descriptive
output passes through:

  - Detection is keyword-based, not model-based (documented limitation:
    not a perfect filter, but it catches the common case and provides a
    clear audit trail via ``person_descriptive_redacted``).
  - When the gate is CLOSED (the default, per §17) and person-descriptive
    content is detected, filtered segments are replaced with a redaction
    marker. The rest of the response passes through unchanged.
  - When the gate is OPEN (user explicitly opted in via Settings → Ethics,
    backed by LENS_FACIAL_ANALYSIS=1), no filtering happens and the
    response notes that person-descriptive content was returned.
  - The filter is enforced at RESPONSE-SHAPING time: you can't stop the
    LLM generating person-descriptive text, but you can post-process its
    output before returning it. The gate is server-side and enforced
    regardless of what the UI sends (§9.6).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..config import get_settings
from ..logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Person-descriptive vocabulary (conservative; false negatives are worse
# than false positives — the redaction flag makes filtering visible).
# ---------------------------------------------------------------------------

_AGE_KEYWORDS = [
    "child", "young adult", "young-adult", "adult", "senior", "elderly",
    "middle-aged", "middle aged", "teenager", "teen", "toddler",
    "baby", "infant", "old man", "old woman", "old person",
    "young man", "young woman", "young person", "young boy", "young girl",
]

_GENDER_KEYWORDS = [
    "masculine", "feminine",
    "male", "female", "man", "woman", "men", "women",
    "boy", "girl", "boys", "girls", "guy", "lady", "ladies",
    "gentleman", "gentlemen",
    "gender presentation", "gender expression",
]

_EXPRESSION_KEYWORDS = [
    "smiling", "smile", "smiles", "smiled",
    "frowning", "frown", "frowns",
    "serious expression", "serious face",
    "surprised expression", "surprised face",
    "neutral expression", "neutral face",
    "facial expression", "expression on",
    "grinning", "grin", "smirking", "smirk",
    "laughing", "laugh", "laughed",
    "crying", "cry", "tears",
    "angry expression", "angry face", "angry look",
    "sad expression", "sad face", "sad look",
    "happy expression", "happy face", "happy look",
]

_APPEARANCE_KEYWORDS = [
    "attractive", "beautiful", "handsome", "good-looking", "good looking",
    "pretty", "ugly", "plain-looking", "plain looking",
    "tall", "short", "slim", "slender", "stocky", "muscular",
    "blonde", "blond", "brunette", "redhead", "dark-haired", "dark haired",
    "bald", "balding", "curly hair", "straight hair", "long hair", "short hair",
    "beard", "mustache", "moustache", "goatee", "stubble",
    "blue eyes", "brown eyes", "green eyes", "dark eyes", "light eyes",
    "skin tone", "skin color", "skin colour", "pale skin", "dark skin",
    "fair skin", "olive skin",
]

_ETHNICITY_KEYWORDS = [
    "asian", "african", "european", "middle eastern", "middle-eastern",
    "hispanic", "latino", "latina", "latin american", "native american",
    "indigenous", "south asian", "east asian", "southeast asian",
    "caucasian", "white person", "white man", "white woman", "white people",
    "black person", "black man", "black woman", "black people",
    "brown person", "brown man", "brown woman",
    "person of color", "person of colour", "racial", "ethnicity",
    "ethnic background", "ethnic appearance",
    "african american", "afro",
    "mediterranean", "nordic", "scandinavian",
]

_RELIGIOUS_KEYWORDS = [
    "hijab", "niqab", "burqa", "chador", "abaya", "khimar",
    "turban", "dastar", "pagri",
    "kippah", "yarmulke", "kipa",
    "cross necklace", "crucifix", "rosary",
    "veil", "head covering", "headscarf", "head scarf",
    "religious attire", "religious garment", "religious dress",
    "prayer shawl", "tallit", "tzitzit",
    "clerical collar", "habit", "cassock",
    "sikh", "muslim", "jewish", "christian", "buddhist", "hindu",
    "orthodox", "fundamentalist",
    "religious", "devout", "practicing",
]

_SOCIOECONOMIC_KEYWORDS = [
    "wealthy", "rich", "poor", "impoverished", "destitute",
    "affluent", "privileged", "underprivileged",
    "working class", "middle class", "upper class", "lower class",
    "homeless", "beggar", "panhandler",
    "socioeconomic", "social class", "economic status",
    "luxury", "designer clothes", "expensive clothing",
    "ragged", "unkempt", "shabby",
    "professional-looking", "business attire",
    "blue-collar", "white-collar",
]

_ALL_KEYWORDS = (
    _AGE_KEYWORDS + _GENDER_KEYWORDS + _EXPRESSION_KEYWORDS + _APPEARANCE_KEYWORDS
    + _ETHNICITY_KEYWORDS + _RELIGIOUS_KEYWORDS + _SOCIOECONOMIC_KEYWORDS
)

# Single alternation regex, longest-first so "young adult" matches before
# "young" / "adult" individually. Word boundaries avoid "adult" inside
# "adulthood"; compound over-matching is accepted.
_ALL_KEYWORDS_SORTED = sorted(_ALL_KEYWORDS, key=len, reverse=True)
_KEYWORD_REGEX = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _ALL_KEYWORDS_SORTED) + r")\b",
    re.IGNORECASE,
)

_REDACTION_MARKER = "[redacted: person-descriptive content — enable facial analysis in Settings → Ethics to view]"


@dataclass(frozen=True, slots=True)
class FilterResult:
    filtered_text: str
    was_filtered: bool
    matched_keywords: list[str]


def is_facial_analysis_enabled() -> bool:
    return get_settings().facial_analysis


def _redact_segment(text: str) -> str:
    """Redact at SENTENCE level — replacing just the keyword would leave a
    broken sentence that might still convey the meaning through context."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(
        _REDACTION_MARKER if _KEYWORD_REGEX.search(s) else s for s in sentences
    )


def filter_person_descriptive(text: str) -> FilterResult:
    """Filter person-descriptive content from a text string.

    Gate OPEN (explicit opt-in) → returned unchanged, ``was_filtered=False``.
    Gate CLOSED (default) → sentences containing person-descriptive keywords
    are replaced with the redaction marker.
    """
    if not text:
        return FilterResult(filtered_text=text, was_filtered=False, matched_keywords=[])

    if is_facial_analysis_enabled():
        return FilterResult(filtered_text=text, was_filtered=False, matched_keywords=[])

    matches = _KEYWORD_REGEX.findall(text)
    if not matches:
        return FilterResult(filtered_text=text, was_filtered=False, matched_keywords=[])

    matched_keywords = sorted({m.lower() for m in matches})
    filtered = _redact_segment(text)
    log.info("person_descriptive_filtered", extra={
        "keyword_count": len(matched_keywords), "keywords": matched_keywords[:5],
    })
    return FilterResult(filtered_text=filtered, was_filtered=True, matched_keywords=matched_keywords)


# ---------------------------------------------------------------------------
# Route-level helpers
# ---------------------------------------------------------------------------


def filter_describe_response(description: str) -> dict[str, Any]:
    result = filter_person_descriptive(description)
    return {
        "description": result.filtered_text,
        "person_descriptive_redacted": result.was_filtered,
    }


def filter_discourse_claims(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Filter person-descriptive content from discourse claim dicts.

    Both ``claim`` and ``summary`` are filtered independently (filtering
    only the claim text is a latent bypass — the parent's issue-6 lesson).
    ``evidence`` lists reference feature names, not person descriptions,
    and are not filtered.
    """
    any_filtered = False
    filtered_claims: list[dict[str, Any]] = []
    for c in claims:
        claim_result = filter_person_descriptive(c.get("claim", ""))
        summary_result = filter_person_descriptive(c.get("summary", ""))
        if claim_result.was_filtered or summary_result.was_filtered:
            any_filtered = True
        filtered_claims.append({
            **c,
            "claim": claim_result.filtered_text,
            "summary": summary_result.filtered_text,
        })
    return {
        "claims": filtered_claims,
        "person_descriptive_redacted": any_filtered,
    }
