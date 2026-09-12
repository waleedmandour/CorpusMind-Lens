"""Phase-2 module tests: typography from OCR geometry, grid-fallback
alignment honesty, Arabic post-processing, regions merge, detector honesty."""
from __future__ import annotations

from lens_engine.detection.detector import get_detector
from lens_engine.detection.typography import profile_typography
from lens_engine.multimodal.alignment import align_image_text
from lens_engine.multimodal.regions import merge_boxes, regions_from_words
from lens_engine.nlp_ar.normalize import is_arabic, normalize_arabic, post_process_ocr


# --- Typography (§9.8) --------------------------------------------------------

def _words(spec: list[tuple[str, int, int, int]], height_default=20) -> list[dict]:
    out = []
    for text, x, y, w in spec:
        h = len(text) * 3 or height_default
        out.append({"text": text, "conf": 0.9, "box": [x, y, w, h]})
    return out


def test_typography_profile_basics():
    # heights: 1 large (100), 4 medium (20), 3 small (10) → q1=10, q3=20
    words = [
        {"text": "SALE", "conf": 0.95, "box": [10, 10, 200, 100]},      # large, upper
        {"text": "SHOP", "conf": 0.9, "box": [10, 150, 80, 20]},        # medium, upper
        {"text": "NOW", "conf": 0.9, "box": [95, 150, 60, 20]},
        {"text": "GO", "conf": 0.9, "box": [160, 150, 40, 20]},
        {"text": "everything", "conf": 0.9, "box": [10, 200, 150, 20]},  # medium, lower
        {"text": "must", "conf": 0.9, "box": [10, 230, 60, 10]},        # small
        {"text": "go", "conf": 0.85, "box": [80, 230, 30, 10]},
        {"text": "a", "conf": 0.85, "box": [120, 230, 20, 10]},
    ]
    profile = profile_typography(words, 640, 480)
    assert profile.word_count == 8
    assert profile.dominant_case == "mixed"  # 4 upper / 4 lower → neither dominates
    assert profile.alignment in ("left", "centre", "right", "full-width (justified-ish)", "unknown")
    bands = [h["band"] for h in profile.hierarchy]
    assert bands[0] == "large" and "small" in bands
    assert any("hierarchy" in e or "caps" in e or "display" in e for e in profile.emphasis_signals)


def test_typography_empty():
    p = profile_typography([], 100, 100)
    assert p.word_count == 0 and p.dominant_case == "unknown"


# --- Regions / alignment fallback ----------------------------------------------

def test_merge_boxes_same_line():
    merged = merge_boxes([[10, 10, 40, 20], [60, 10, 40, 20]])
    assert len(merged) == 1
    assert merged[0][2] == 90  # 60+40-10


def test_regions_normalized():
    regions = regions_from_words(
        [{"box": [0, 0, 50, 20]}, {"box": [60, 0, 50, 20]}], 200, 100)
    assert all(0 <= v <= 1 for r in regions for v in r)


def test_grid_fallback_is_honestly_labelled():
    import io

    from PIL import Image

    img = Image.new("RGB", (100, 60), (10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    ocr_block = {"text": "big words here",
                 "words": [{"text": "big", "conf": 0.9, "box": [5, 5, 30, 20]},
                           {"text": "words", "conf": 0.9, "box": [40, 5, 40, 20]}]}
    import asyncio

    # Force the fallback deterministically (the real backend may or may not
    # be installed in a given environment): a stub whose available() is False.
    class _NoEmbeddings:
        model_id = "unavailable"

        def available(self) -> bool:
            return False

    result = asyncio.run(align_image_text(buf.getvalue(), ocr_block, backend=_NoEmbeddings()))
    assert result["backend"] == "grid-heuristic"
    assert "NOT semantic" in result["note"] or "geometric" in result["note"]
    for pair in result["pairs"]:
        assert pair["confidence"] <= 0.5  # never overclaims


# --- Arabic OCR post-processing (§9.16) -----------------------------------------

def test_normalize_strips_tashkeel_and_tatweel():
    text = "مُحَمَّــــد"
    out = normalize_arabic(text)
    assert "\u0640" not in out           # tatweel gone
    assert all(not (0x064B <= ord(ch) <= 0x065F) for ch in out)  # tashkeel gone


def test_alef_variants_unified():
    assert normalize_arabic("أإآ") == "ااا"


def test_dialect_hints():
    res = post_process_ocr("شلون الحين")
    assert "gulf" in res.dialect_hints
    res2 = post_process_ocr("الرجل الذي ذهب")
    assert "msa" in res2.dialect_hints
    assert res2.note  # hints are labelled guidance, not language ID


def test_is_arabic():
    assert is_arabic("هذا نص عربي")
    assert not is_arabic("hello world")


# --- Detector honesty (§3.2/§9.5) -------------------------------------------------

def test_detector_degrades_honestly_without_models():
    det = get_detector()
    import asyncio

    status = asyncio.run(det.status())
    if not status.available:
        assert status.reason  # says WHY it is unavailable
        assert det.name == "unavailable"
