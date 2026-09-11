"""Facial & body analysis (§9.6) — opt-in, off by default, descriptive-first.

Scope guardrails (§17):
  - Age group, gender presentation, expression/emotion, gaze, head
    direction, posture/gesture, dominance/submission cues — always output
    as a DESCRIBED VISUAL CUE FIRST ("figure occupies more vertical frame
    space, direct frontal gaze") with an optional, clearly labelled
    interpretive gloss.
  - Never identity recognition or re-identification. No face embedding,
    no matching against any gallery, no naming.
  - Ships behind Settings → Ethics → Facial Analysis; the backend consent
    gate is enforced server-side regardless of what the UI sends.
  - Aggregate/descriptive use only; every response carries a fixed notice.
"""

from ..config import get_settings
from ..logging import get_logger

log = get_logger(__name__)

ETHICS_NOTICE = (
    "Facial/body analysis is opt-in and off by default. It produces aggregate, "
    "descriptive visual cues only. It never performs identity recognition or "
    "re-identification, and no real, identifiable individual is ever named."
)

_CUE_KEYWORDS = {
    "gaze": ["looking at the camera", "direct gaze", "averted gaze", "gaze directed",
             "eyes toward viewer", "eyes away"],
    "head_direction": ["head turned", "profile view", "frontal", "tilted head", "head facing"],
    "posture": ["standing", "seated", "leaning", "arms crossed", "hands raised",
                "occupies more vertical frame space", "occupies less vertical frame space"],
    "expression": ["smiling", "frowning", "neutral expression", "open mouth", "closed eyes"],
    "social_distance": ["close to the camera", "far from the camera", "fills the frame",
                        "small within the frame"],
}

_GLOSS_HINTS = {
    "direct gaze": "direct frontal gaze may construct viewer address / demand",
    "occupies more vertical frame space": "greater vertical occupancy may read as higher salience or dominance",
    "arms crossed": "crossed arms may read as guardedness",
}


def facial_analysis_enabled() -> bool:
    return get_settings().facial_analysis


def extract_visual_cues(description: str) -> dict:
    """Deterministic cue extraction from a vision-LM description.

    Returns described cues (with bbox-free, image-level phrasing) plus
    optional interpretive glosses, each clearly labelled. Runs at any time;
    what varies with consent is whether the *description* is allowed to
    contain person-descriptive content at all (see consent_gate) and
    whether this route may be called.
    """
    text = (description or "").lower()
    cues: list[dict] = []
    for cue_type, phrases in _CUE_KEYWORDS.items():
        for p in phrases:
            if p in text:
                cues.append({"type": cue_type, "cue": p})
                break
    glosses = [
        {"cue": c["cue"], "gloss": hint, "label": "interpretive — framework-relative hypothesis"}
        for c in cues
        for hint in [_GLOSS_HINTS.get(c["cue"], "")]
        if hint
    ]
    return {
        "cues": cues,
        "interpretive_glosses": glosses,
        "notice": ETHICS_NOTICE,
    }


def enforce_consent_or_raise() -> None:
    """Backend consent gate — raises unless the user opted in server-side."""
    if not facial_analysis_enabled():
        from ..api.errors import ConsentRequiredError

        raise ConsentRequiredError(
            "Facial analysis is off (Settings → Ethics). It ships opt-in and never "
            "performs identity recognition."
        )
