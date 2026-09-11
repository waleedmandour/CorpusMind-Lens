"""Annotation schema validation (§9.9): unknown category ids are rejected
server-side — a typo never silently corrupts a corpus."""
from __future__ import annotations

import pytest

from lens_engine.vision.annotations import (DIMENSION_IDS, SCHEMA, is_valid_category,
                                            normalise_annotations, read_annotations)


def test_schema_shape():
    assert len(SCHEMA) == 5
    assert DIMENSION_IDS == ("visual_morphology", "attentional_framing", "shot_scale",
                             "path_transition", "multimodal_integration")
    # every dimension has multi-select + ≥ 8 categories, each with EN+AR labels
    for d in SCHEMA:
        assert d["multi"] is True
        assert len(d["categories"]) >= 8
        for c in d["categories"]:
            assert c["label_en"] and c["label_ar"] and c["id"]


def test_valid_payload_roundtrip():
    payload = {
        "dimensions": {
            "shot_scale": {"values": ["medium_shot", "close_up"], "note": "waist-up"},
            "visual_morphology": {"values": ["emblem"], "note": ""},
        },
        "tags": ["Press Photo", "press photo", "election"],
    }
    clean = normalise_annotations(payload)
    assert clean["dimensions"]["shot_scale"]["values"] == ["medium_shot", "close_up"]
    # tags dedupe case-insensitively
    assert clean["tags"] == ["Press Photo", "election"]
    read = read_annotations({"tags": clean["tags"],
                             "annotations": clean["dimensions"]})
    assert read["dimensions"]["shot_scale"]["values"] == ["medium_shot", "close_up"]


def test_unknown_category_rejected():
    with pytest.raises(ValueError, match="Unknown category 'medium_shoot'"):
        normalise_annotations({"dimensions": {"shot_scale": {"values": ["medium_shoot"],
                                                             "note": ""}}})


def test_unknown_dimension_dropped_forward_compatible():
    clean = normalise_annotations({"dimensions": {"not_a_dimension": {"values": ["x"], "note": ""}}})
    assert clean["dimensions"] == {}


def test_non_string_values_rejected():
    with pytest.raises(ValueError, match="must be strings"):
        normalise_annotations({"dimensions": {"shot_scale": {"values": [42], "note": ""}}})


def test_is_valid_category():
    assert is_valid_category("shot_scale", "close_up")
    assert not is_valid_category("shot_scale", "emblem")   # belongs to visual_morphology
    assert not is_valid_category("nonexistent", "close_up")
