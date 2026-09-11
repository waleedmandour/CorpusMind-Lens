"""Worked-example tests for every §11 formula (CONTRIBUTING rule 4: the
statistics are frozen contracts — a wrong constant is a silent validity bug
in a published result). Hand-computed values, independent of the parent's
test suite (build brief §16)."""
from __future__ import annotations

import math

import pytest

from lens_engine.stats import measures as M


# --- Collocation measures ---------------------------------------------------

def test_expected_joint():
    assert M.expected_joint(R=10, C=20, N=100) == 2.0


def test_mutual_information():
    # O=E → MI = 0
    assert M.mutual_information(2.0, 10, 20, 100) == 0.0
    # O=8, E=2 → log2(4) = 2
    assert M.mutual_information(8.0, 10, 20, 100) == pytest.approx(2.0)
    assert M.mutual_information(0, 10, 20, 100) == float("-inf")


def test_t_score():
    # (8 − 2) / sqrt(8) = 6 / 2.8284… = 2.1213…
    assert M.t_score(8.0, 10, 20, 100) == pytest.approx(2.1213203, rel=1e-5)


def test_dice_and_logdice():
    assert M.dice_coefficient(6, 10, 14) == pytest.approx(0.5)
    # LogDice = 14 + log2(0.5) = 13
    assert M.log_dice(6, 10, 14) == pytest.approx(13.0)


def test_log_likelihood_2x2_classic():
    # small hand-computable table: a=8,b=2,c=2,d=8 → all marginals 10, E=5 per cell
    # G² = 2·(8·ln(8/5) + 2·ln(2/5) + 2·ln(2/5) + 8·ln(8/5)) = 7.7098…
    assert M.log_likelihood_2x2(8, 2, 2, 8) == pytest.approx(7.709820, abs=1e-4)
    # uniform table → 0
    assert M.log_likelihood_2x2(1, 1, 1, 1) == pytest.approx(0.0)
    # cross-check against an independent formulation on a larger table:
    a, b, c, d = 110, 2440, 44, 29114
    ll = M.log_likelihood_2x2(a, b, c, d)
    total = a + b + c + d
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d
    expected = 0.0
    for o, r, cc in ((a, r1, c1), (b, r1, c2), (c, r2, c1), (d, r2, c2)):
        e = r * cc / total
        expected += o * math.log(o / e)
    assert ll == pytest.approx(2 * expected, rel=1e-9)


def test_chi_square_2x2():
    # a=110,b=2440,c=44,d=29114: hand-computable Pearson χ²
    a, b, c, d = 110, 2440, 44, 29114
    total = a + b + c + d
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d
    chi = sum(((o - r * cc / total) ** 2) / (r * cc / total)
              for o, r, cc in ((a, r1, c1), (b, r1, c2), (c, r2, c1), (d, r2, c2)))
    assert M.chi_square_2x2(a, b, c, d) == pytest.approx(chi, rel=1e-9)


def test_delta_p():
    # joint=5, fx=10, fy=20, N=100
    # P(y|x)=0.5, P(y|¬x)=15/90=0.1667 → ΔP(y|x)=0.3333
    # P(x|y)=0.25, P(x|¬y)=5/80=0.0625 → ΔP(x|y)=0.1875
    dp_xy, dp_yx = M.delta_p(5, 10, 20, 100)
    assert dp_xy == pytest.approx(1 / 3, abs=1e-4)
    assert dp_yx == pytest.approx(0.1875, abs=1e-4)


# --- Keyness ------------------------------------------------------------------

def test_keyness_ll_is_2x2_ll():
    # signature (f1, f2, N1, N2): a=f1, b=N1−f1, c=f2, d=N2−f2
    assert M.keyness_ll(50, 10, 1000, 1000) == M.log_likelihood_2x2(50, 950, 10, 990)


def test_log_ratio():
    # (50/1000)/(10/1000) = 5 → log2(5)
    assert M.log_ratio(50, 10, 1000, 1000) == pytest.approx(math.log2(5))
    assert M.log_ratio(0, 10, 1000, 1000) == float("-inf")
    assert M.log_ratio(10, 0, 1000, 1000) == float("inf")


def test_pct_diff():
    # norm1 = 50/1000*1e6 = 50000 ; norm2 = 10/1000*1e6 = 10000
    assert M.pct_diff(50, 10, 1000, 1000) == pytest.approx(400.0)


def test_simple_maths():
    # (50000+1)/(10000+1) ≈ 4.9997
    assert M.simple_maths(50, 10, 1000, 1000) == pytest.approx(50001 / 10001, rel=1e-4)


def test_odds_ratio_haldane():
    assert M.odds_ratio_haldane(50, 10, 1000, 1000) == pytest.approx(
        (50 * 990) / (10 * 950), rel=1e-9)
    # zero cell → Haldane–Anscombe 0.5 correction, finite value
    v = M.odds_ratio_haldane(0, 10, 1000, 1000)
    assert math.isfinite(v) and v > 0


def test_fisher_exact_sparse():
    # sparse table where χ² would mislead: Fisher must return a valid p in [0,1]
    p = M.fisher_exact_2x2(3, 10, 0, 20)
    assert 0.0 <= p <= 1.0
    assert M.fisher_exact_2x2(1, 1, 1, 1) == pytest.approx(1.0)  # maximally uninformative


def test_chi2_min_expected():
    assert M.chi2_min_expected(110, 2440, 44, 29114) == pytest.approx(154 * 2550 / 31708, rel=1e-6)


def test_keyness_row_has_significance_and_effect_sizes():
    row = M.compute_keyness_row("x", 50, 10, 1000, 1000)
    for key in ("log_likelihood", "chi_square", "fisher_exact", "log_ratio",
                "pct_diff", "simple_maths", "odds_ratio", "chi2_min_expected"):
        assert key in row.measures  # significance AND effect size, always together


# --- Dispersion -----------------------------------------------------------------

def test_juillands_d():
    # perfectly even → D = 1
    assert M.juillands_d([5, 5, 5, 5]) == pytest.approx(1.0)
    # all in one part → D = 0 (max CV → 1 − CV/√(n−1) ≤ 0 clamped)
    assert M.juillands_d([20, 0, 0, 0]) == pytest.approx(0.0)


def test_gries_dp():
    # uniform observed over uniform bins → DP = 0
    assert M.gries_dp([5, 5, 5, 5]) == pytest.approx(0.0)
    # all tokens in bin 1 of 4 uniform bins → DP = 0.5*(|1−0.25|+3*0.25) = 0.75
    assert M.gries_dp([20, 0, 0, 0]) == pytest.approx(0.75)
    # unequal bins: 2 bins sized 3:1, all 4 tokens in the size-3 bin → expected .75/.25
    assert M.gries_dp([4, 0], sizes=[3, 1]) == pytest.approx(0.5 * (0.25 + 0.25))


def test_gries_dp_norm():
    assert M.gries_dp_norm([20, 0, 0, 0]) == pytest.approx(0.75 * 4 / 3)


# --- Categorical variation --------------------------------------------------------

def test_ttr_guiraud():
    assert M.type_token_ratio(["a", "a", "b"]) == pytest.approx(2 / 3)
    assert M.guiraud(["a", "a", "b", "c", "c"]) == pytest.approx(3 / math.sqrt(5))


def test_mattr():
    # window=2 over "a b a b": windows ab, ba, ab → TTRs 1,1,1 → 1.0
    assert M.mattr(["a", "b", "a", "b"], window=2) == pytest.approx(1.0)
    # shorter than window → raw TTR
    assert M.mattr(["a", "b", "b"], window=10) == pytest.approx(2 / 3)


def test_sttr():
    # 2 chunks of 4: "a b c d" TTR=1 ; "a b c d" TTR=1 → 1.0
    assert M.sttr(["a", "b", "c", "d", "a", "b", "c", "d"], chunk_size=4) == pytest.approx(1.0)
    # trailing short chunk is dropped: 4 + 2 tokens
    assert M.sttr(["a", "b", "c", "d", "e", "e"], chunk_size=4) == pytest.approx(1.0)


def test_errors():
    with pytest.raises(ValueError):
        M.expected_joint(1, 1, 0)
