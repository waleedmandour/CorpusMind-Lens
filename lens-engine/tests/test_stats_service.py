"""The §9.14 battery over synthetic annotation sequences (reading order,
gaps, keyness pairing, dispersion bins, KWIC)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lens_engine.stats import service
from lens_engine.storage.models import Image


def _img(set_id: str, i: int, annotations: dict | None) -> Image:
    t = (datetime.now(UTC) + timedelta(seconds=i)).isoformat()
    return Image(id=f"img{i:02d}", image_set_id=set_id, filename=f"{i}.png",
                 storage_path="/tmp/x", created_at=t,
                 meta={"annotations": annotations or {}})


def _set(n: int = 6, pattern: dict[int, dict] | None = None) -> list[Image]:
    pattern = pattern or {}
    return [_img("s", i, pattern.get(i, {
        "shot_scale": {"values": ["close_up"] if i % 2 == 0 else ["long_shot"], "note": ""},
        "visual_morphology": {"values": ["emblem"], "note": ""},
    })) for i in range(n)]


def test_reading_order_and_gap_surfacing():
    images = _set(4, {1: {}})  # image 1 has no annotations → <gap>
    seq = service.dimension_sequence(images, "shot_scale")
    # i=0 close (even), i=1 gap, i=2 close (even), i=3 long (odd)
    assert seq == ["close_up", "<gap>", "close_up", "long_shot"]
    freq = service.frequency_profile(images, "shot_scale")
    assert freq["gaps"] == 1
    assert freq["coverage"] == 0.75


def test_frequency_profile_counts():
    images = _set(6)
    freq = service.frequency_profile(images, "shot_scale")
    counts = {r["category"]: r["count"] for r in freq["profile"]}
    assert counts == {"close_up": 3, "long_shot": 3}


def test_diversity_battery_fields():
    d = service.diversity_battery(_set(6), "shot_scale")
    assert set(d) >= {"ttr", "guiraud_r", "mattr", "sttr", "tokens", "types"}
    assert 0 <= d["ttr"] <= 1


def test_ngrams_respect_reading_order():
    images = _set(6)
    g = service.ngrams(images, "shot_scale", n=2, min_count=1)
    grams = {tuple(r["gram"]): r["count"] for r in g["grams"]}
    # sequence: close, long, close, long, close, long → 3× (close_up, long_shot)
    assert grams.get(("close_up", "long_shot")) == 3
    assert grams.get(("long_shot", "close_up")) == 2


def test_cooccurrence_between_dimensions():
    images = _set(6)
    co = service.cooccurrence(images, "shot_scale", "visual_morphology", min_joint=1)
    assert co["N"] == 6
    top = co["pairs"][0]
    assert top["a"] in ("close_up", "long_shot") and top["b"] == "emblem"
    # all measures present per §11
    for k in ("mi", "t_score", "dice", "log_dice", "delta_p_a_given_b", "delta_p_b_given_a", "g2"):
        assert k in top


def test_keyness_pairs_significance_with_effect_size():
    a = _set(6)  # alternating close/long
    b = _set(6, pattern={i: {"shot_scale": {"values": ["long_shot"], "note": ""},
                             "visual_morphology": {"values": ["emblem"], "note": ""}}
                          for i in range(6)})
    k = service.keyness(a, b, "shot_scale")
    rows = {r["category"]: r for r in k["rows"]}
    assert rows["close_up"]["f1"] == 3 and rows["close_up"]["f2"] == 0
    # every row carries significance AND effect sizes together
    for r in rows.values():
        assert {"log_likelihood", "chi_square", "fisher_exact", "log_ratio",
                "pct_diff", "simple_maths", "odds_ratio"} <= set(r)
    assert rows["close_up"]["log_ratio"] > 0   # more in target


def test_dispersion_bins():
    images = _set(8, pattern={
        i: {"shot_scale": {"values": ["close_up" if i < 4 else "long_shot"], "note": ""},
            "visual_morphology": {"values": ["emblem"], "note": ""}} for i in range(8)})
    disp = service.dispersion(images, "shot_scale", bins=4)
    rows = {r["category"]: r for r in disp["rows"]}
    # 8 tokens → 4 bins of 2: close_up = [2,2,0,0] → DP = 0.5·(|.5−.25|·2 + |0−.25|·2) = 0.5
    assert rows["close_up"]["per_bin"] == [2, 2, 0, 0]
    assert rows["close_up"]["gries_dp"] == pytest.approx(0.5)
    # long_shot the mirror → same DP
    assert rows["long_shot"]["gries_dp"] == pytest.approx(rows["close_up"]["gries_dp"])


def test_visual_kwic_context():
    images = _set(6)
    kw = service.visual_kwic(images, "shot_scale", "long_shot", context=1)
    assert kw["total_occurrences"] == 3
    hit = kw["hits"][0]
    assert hit["node"] == "long_shot"
    assert hit["left"] == ["close_up"]
    assert hit["right"] == ["close_up"]
    assert hit["image_id"] == "img01"  # position 1 in reading order
