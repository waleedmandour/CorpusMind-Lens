"""Visual Grammar module (§9.10) — structured Kress & van Leeuwen scoring.

Every claim cites exactly which sub-analysis (colour, composition, detection,
OCR) produced it; the AI-generated natural-language explanation is a second,
clearly-labelled layer. Phrased per §4 Principle 4.
"""
from __future__ import annotations

from ..discourse.lenses import ImageSignals, claim, hedge


def visual_grammar_score(sig: ImageSignals) -> dict:
    """Structured breakdown across Representational / Interactional /
    Compositional metafunctions, grounded in the computed sub-analyses."""
    iv = sig.info_value
    detections = sig.detection_labels()
    people = [d for d in detections if any(k in d for k in
              ("person", "man", "woman", "child", "face", "crowd"))]
    objects = [d for d in detections if d not in people]
    annotations = sig.annotations or {}
    shot = ((annotations.get("shot_scale") or {}).get("values") or [])
    salience = sig.composition.get("framing_balance", 0.0)
    balance = sig.composition.get("visual_balance", 0.0)

    claims = []

    # Representational — what is depicted (now detection-fed, §9.5/§9.10)
    if people or objects:
        claims.append(claim(
            "Kress & van Leeuwen (2006)", "representational",
            hedge("Kress & van Leeuwen (2006)",
                  f"the detected participants/objects ({', '.join((people + objects)[:4])}) "
                  f"ground the Representational metafunction in open-vocabulary "
                  f"detection rather than a placeholder."),
            ["detections.labels"], 0.65 if people or objects else 0.3,
            subcategory="participants"))
    else:
        claims.append(claim(
            "Kress & van Leeuwen (2006)", "representational",
            hedge("Kress & van Leeuwen (2006)",
                  "no detector output is available for this image; the Representational "
                  "metafunction falls back to colour/composition signals only."),
            ["detections.available=false"], 0.25, subcategory="participants"))
    for note in ((sig.colour or {}).get("colour_symbolism_notes") or [])[:1]:
        claims.append(claim(
            "Kress & van Leeuwen (2006)", "representational",
            hedge("Kress & van Leeuwen (2006)", f"colour may function as a symbolic "
                  f"attribute: {note}"),
            ["colour.colour_symbolism_notes"], 0.45, subcategory="symbolic_attribute"))

    # Interactional — contact, social distance, attitude, modality
    contact = "demand" if people and _gazing(sig) else "offer"
    claims.append(claim(
        "Kress & van Leeuwen (2006)", "interactional",
        hedge("Kress & van Leeuwen (2006)",
              f"the image act reads as a {contact}: " + (
                  "depicted participants make eye contact with the viewer." if contact == "demand"
                  else "no direct address toward the viewer was detected; participants "
                       "are offered as items of contemplation.")),
        ["detections.labels", "annotations.shot_scale"], 0.5 if people else 0.35,
        subcategory="image_act"))
    if shot:
        claims.append(claim(
            "Kress & van Leeuwen (2006)", "interactional",
            hedge("Kress & van Leeuwen (2006)",
                  f"the annotated shot scale '{shot[0]}' realizes a specific social "
                  f"distance between viewer and represented participants."),
            ["annotations.shot_scale"], 0.6, subcategory="social_distance"))

    # Compositional — information value, salience, framing
    if iv:
        top_iv = max(iv.items(), key=lambda kv: kv[1])
        claims.append(claim(
            "Kress & van Leeuwen (2006)", "compositional",
            hedge("Kress & van Leeuwen (2006)",
                  f"information value concentrates in the '{top_iv[0]}' zone "
                  f"({top_iv[1]:.2f} of measured salience), suggesting that zone carries "
                  f"the composition's dominant informational load."),
            ["composition.information_value"], 0.55, subcategory="information_value"))
    claims.append(claim(
        "Kress & van Leeuwen (2006)", "compositional",
        hedge("Kress & van Leeuwen (2006)",
              f"framing/balance metrics: framing_balance={salience:.2f} "
              f"(0=centred, 1=edge-weighted), visual_balance={balance:+.2f} "
              f"(negative=left-heavy, positive=right-heavy)."),
        ["composition.framing_balance", "composition.visual_balance"], 0.5,
        subcategory="framing"))

    explanation = (
        "This structured score is computed from deterministic sub-analyses "
        "(colour, geometric composition, open-vocabulary detection, annotations). "
        "Under a Kress & van Leeuwen reading, these numbers may indicate the "
        "metafunctional emphases above — they are framework-lensed hypotheses, "
        "not measurements of meaning itself."
    )
    return {
        "metafunctions": {
            "representational": [c for c in claims if c["category"] == "representational"],
            "interactional": [c for c in claims if c["category"] == "interactional"],
            "compositional": [c for c in claims if c["category"] == "compositional"],
        },
        "explanation": explanation,
        "explanation_layer": "interpretive narrative — clearly separated from the numeric score",
    }


def _gazing(sig: ImageSignals) -> bool:
    """Direct gaze detection is available only from detections/VLM cues; absent
    evidence defaults to 'offer' (the conservative reading)."""
    desc = ((sig.annotations or {}).get("vlm_description") or {})
    return "looking at the camera" in str(desc).lower() or "direct gaze" in str(desc).lower()
