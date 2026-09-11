"""Discourse lens battery tests: 12 frameworks, heuristic mode, grounding,
hedged phrasing, consent-gate integration."""
from __future__ import annotations

import pytest

from lens_engine.config import get_settings
from lens_engine.discourse.lenses import (FRAMEWORK_IDS, heuristic_lens, load_frameworks,
                                          signals_from_meta)


@pytest.fixture(scope="module")
def frameworks():
    return load_frameworks(get_settings().frameworks_dir)


def test_all_12_templates_load(frameworks):
    assert len(frameworks) == 12
    for fid in FRAMEWORK_IDS:
        assert fid in frameworks, f"missing template: {fid}"
        fw = frameworks[fid]
        assert fw.full_name and fw.categories and fw.guardrails


def _rich_signals() -> dict:
    return {
        "colour": {
            "dominant_colours": [{"hex": "#aa2222", "rgb": [170, 34, 34], "percent": 40}],
            "warm_cold_balance": 0.6, "brightness": 90, "contrast": 60, "saturation": 0.5,
            "colour_symbolism_notes": [
                "Red-dominant. Framework/culture-relative (not universal): in many Western "
                "contexts passion/danger; in many East Asian contexts luck/celebration."],
        },
        "composition": {
            "information_value": {"left": 0.2, "right": 0.8, "top": 0.7, "bottom": 0.3,
                                  "centre": 0.65, "margin": 0.35},
            "visual_balance": 0.6, "framing_balance": 0.35,
        },
        "ocr": {"text": "We must stand together NOW against the threat. Our nation demands action.",
                "confidence": 0.9, "word_count": 12},
        "detections": [
            {"label": "person", "confidence": 0.8, "bbox": [0.1, 0.1, 0.3, 0.5],
             "model": "google/owlvit-base-patch32", "revision": "main"},
            {"label": "flag", "confidence": 0.7, "bbox": [0.6, 0.1, 0.2, 0.2],
             "model": "google/owlvit-base-patch32", "revision": "main"},
        ],
        "annotations": {"shot_scale": {"values": ["medium_shot"], "note": ""},
                        "multimodal_integration": {"values": ["anchorage"], "note": ""}},
    }


def test_every_framework_produces_grounded_hedged_claims(frameworks):
    sig = signals_from_meta("img1", _rich_signals())
    for fid in FRAMEWORK_IDS:
        claims = heuristic_lens(fid, frameworks[fid], sig)
        assert isinstance(claims, list) and claims, f"{fid} produced no claims"
        for c in claims:
            assert c["evidence"], f"{fid} claim without evidence: {c}"
            assert c["mode"] == "heuristic"
            assert c["framework"] == frameworks[fid].full_name
            # hedged phrasing discipline (§4 P4)
            low = c["claim"].lower()
            assert any(h in low for h in ("may", "reads as", "metrics", "hypothesis")), (
                f"{fid} claim lacks hedging: {c['claim']}")


def test_cda_family_flags_power_and_polarisation(frameworks):
    sig = signals_from_meta("img1", _rich_signals())
    claims = heuristic_lens("fairclough-cda", frameworks["fairclough-cda"], sig)
    cats = {c["category"] for c in claims}
    assert "power_and_solidarity" in cats
    text_claim = [c for c in claims if c["category"] == "power_and_solidarity"][0]
    assert "ocr.text" in text_claim["evidence"]


def test_kvl_information_value_zones(frameworks):
    sig = signals_from_meta("img1", _rich_signals())
    claims = heuristic_lens("kress-van-leeuwen", frameworks["kress-van-leeuwen"], sig)
    subs = {c["subcategory"] for c in claims}
    assert "given_new" in subs or "ideal_real" in subs
    assert "centre_margin" in subs


def test_barthes_anchorage_requires_text(frameworks):
    rich = _rich_signals()
    rich["ocr"] = {"text": "", "confidence": 0.0, "word_count": 0}
    sig = signals_from_meta("img1", rich)
    claims = heuristic_lens("barthes-semiotics", frameworks["barthes-semiotics"], sig)
    cats = {c["category"] for c in claims}
    assert "anchorage_relay" not in cats  # no text → no anchorage claim
    assert "denotation" in cats           # falls to the pure-image reading


def test_metaphor_candidates_require_verification_gate(frameworks):
    sig = signals_from_meta("img1", _rich_signals())
    claims = heuristic_lens("lakoff-johnson-cmt", frameworks["lakoff-johnson-cmt"], sig)
    strong = [c for c in claims if c["category"] == "conceptual_metaphor" and c["confidence"] > 0.3]
    if strong:
        assert "human verification" in strong[0]["claim"] or "candidate" in strong[0]["claim"]
    # low-signal branch stays visibly low-confidence
    weak = [c for c in claims if c["confidence"] <= 0.3]
    assert weak or strong


def test_low_signal_frameworks_stay_honest(frameworks):
    empty = signals_from_meta("img1", {})
    for fid in ("wodak-dha", "aristotle-rhetoric", "martin-white-appraisal"):
        claims = heuristic_lens(fid, frameworks[fid], empty)
        for c in claims:
            assert c["confidence"] <= 0.6  # weak signal ⇒ visibly weak confidence
