"""Consent-gate tests (§17): the gate stays CLOSED by default under all
code paths, redacts at sentence level, and passes non-person content."""
from __future__ import annotations

from lens_engine.vision.consent_gate import (filter_describe_response,
                                             filter_discourse_claims,
                                             filter_person_descriptive)


def test_gate_closed_by_default_redacts_person_content():
    text = ("A crowd gathers in front of a government building. "
            "A woman in the front is smiling. "
            "Banners carry large text.")
    res = filter_person_descriptive(text)
    assert res.was_filtered
    assert "smiling" not in res.filtered_text
    assert "A woman" not in res.filtered_text
    assert "government building" in res.filtered_text      # non-person content survives
    assert "Banners carry large text" in res.filtered_text
    assert any("woman" in k for k in res.matched_keywords)


def test_redaction_marker_visible():
    res = filter_person_descriptive("An elderly man frowns at the camera.")
    assert res.was_filtered
    assert "[redacted:" in res.filtered_text


def test_clean_text_untouched():
    text = "A poster with bold uppercase text over a red field; a flag flies at half mast."
    res = filter_person_descriptive(text)
    assert not res.was_filtered
    assert res.filtered_text == text


def test_describe_response_shape():
    out = filter_describe_response("A young adult is laughing.")
    assert out["person_descriptive_redacted"] is True
    assert "laughing" not in out["description"]


def test_discourse_claims_filtered_on_claim_and_summary():
    claims = [
        {"claim": "The smiling figure dominates the frame.", "summary": "Positive affect",
         "evidence": ["colour.brightness"], "confidence": 0.4},
        {"claim": "The colour field is flat.", "summary": "A man looks away.",
         "evidence": ["colour.dominant_colours"], "confidence": 0.4},
    ]
    out = filter_discourse_claims(claims)
    assert out["person_descriptive_redacted"] is True
    assert "smiling" not in out["claims"][0]["claim"]
    assert "man" not in out["claims"][1]["summary"]      # summary filtered independently
    assert out["claims"][1]["evidence"] == ["colour.dominant_colours"]  # evidence untouched


def test_gate_open_no_filtering(monkeypatch):
    from lens_engine.config import get_settings

    monkeypatch.setattr(get_settings(), "facial_analysis", True)
    text = "A woman smiles at the camera."
    res = filter_person_descriptive(text)
    assert not res.was_filtered
    assert res.filtered_text == text
