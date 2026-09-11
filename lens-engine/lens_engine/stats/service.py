"""The corpus-linguistics measurement battery applied to visual annotation
sequences (§9.14). This is what makes Lens a corpus tool and not just an
image annotator.

Reading order (§7): images ordered by ``created_at`` ASC within a set; the
sequence for a dimension is each image's annotation values for that
dimension, with ``<gap>`` surfacing where an image carries no value for the
dimension (gaps are data — they measure annotation coverage — and are
excluded from category statistics but reported).

All measures come from :mod:`lens_engine.stats.measures` — the forked §11
definitions, no ad-hoc math here. Keyness rows always pair significance
with effect size (Hardie's discipline).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from . import measures as M
from ..storage.models import Image


# --------------------------------------------------------------------------- #
# Sequence construction
# --------------------------------------------------------------------------- #


def dimension_sequence(images: list[Image], dim: str, *, which: str = "first") -> list[str]:
    """One token per image (reading order) for the given dimension.

    ``which="first"`` takes the first selected category value; ``"all"``
    explodes multi-select values into consecutive tokens. Images with no
    value for the dimension surface ``<gap>`` — measurement of annotation
    coverage, not silent omission.
    """
    seq: list[str] = []
    for img in images:
        block = (img.meta or {}).get("annotations", {}).get(dim) or {}
        values = [v for v in (block.get("values") or []) if isinstance(v, str) and v]
        if not values:
            seq.append("<gap>")
        elif which == "all":
            seq.extend(values)
        else:
            seq.append(values[0])
    return seq


# --------------------------------------------------------------------------- #
# Frequency + diversity
# --------------------------------------------------------------------------- #


def frequency_profile(images: list[Image], dim: str) -> dict:
    seq = dimension_sequence(images, dim, which="all")
    cats = [t for t in seq if t != "<gap>"]
    counts = Counter(cats)
    n = len(cats)
    return {
        "dimension": dim,
        "total_observations": n,
        "gaps": seq.count("<gap>"),
        "coverage": round(n / len(seq), 4) if seq else 0.0,
        "profile": [{"category": c, "count": k, "percent": round(k / n * 100, 2) if n else 0.0}
                    for c, k in counts.most_common()],
    }


def diversity_battery(images: list[Image], dim: str, *, mattr_window: int = 50,
                      sttr_chunk: int = 1000) -> dict:
    """The diversity battery over a dimension's category sequence:
    TTR, Guiraud's R, MATTR, STTR (§11)."""
    seq = dimension_sequence(images, dim, which="first")
    cats = [t for t in seq if t != "<gap>"]
    return {
        "dimension": dim,
        "tokens": len(cats),
        "types": len(set(cats)),
        "ttr": round(M.type_token_ratio(cats), 4),
        "guiraud_r": round(M.guiraud(cats), 4),
        "mattr": round(M.mattr(cats, window=mattr_window), 4),
        "sttr": round(M.sttr(cats, chunk_size=sttr_chunk), 4),
    }


# --------------------------------------------------------------------------- #
# Sequence n-grams (over reading order, with <gap> surfacing)
# --------------------------------------------------------------------------- #


def ngrams(images: list[Image], dim: str, *, n: int = 2, min_count: int = 2,
           include_gaps: bool = True) -> dict:
    """Sequence n-grams over the set's reading order. ``<gap>`` tokens are
    kept (unless ``include_gaps=False``) so annotation holes are visible in
    the transition chains rather than papered over."""
    seq = dimension_sequence(images, dim, which="first")
    if not include_gaps:
        seq = [t for t in seq if t != "<gap>"]
    grams = [tuple(seq[i: i + n]) for i in range(len(seq) - n + 1)]
    counts = Counter(grams)
    return {
        "dimension": dim,
        "n": n,
        "total": len(grams),
        "grams": [{"gram": list(g), "count": c} for g, c in counts.most_common() if c >= min_count],
    }


# --------------------------------------------------------------------------- #
# Co-occurrence association between dimensions
# --------------------------------------------------------------------------- #


def cooccurrence(images: list[Image], dim_a: str, dim_b: str, *, min_joint: int = 2) -> dict:
    """Association between the values of two dimensions over the same images.

    For every (category_a, category_b) pair with joint ≥ min_joint, computes
    MI (Church & Hanks 1990), T-score, Dice, LogDice (Rychlý 2008),
    ΔP (Gries 2013), and G² (Dunning 1993) from the 2×2 table of the pair
    against everything else. N = number of images where both dimensions are
    annotated (the honest denominator for cross-dimension claims).
    """
    pairs: Counter = Counter()
    fa: Counter = Counter()
    fb: Counter = Counter()
    n = 0
    for img in images:
        ann = (img.meta or {}).get("annotations", {})
        va = [v for v in (ann.get(dim_a) or {}).get("values") or []]
        vb = [v for v in (ann.get(dim_b) or {}).get("values") or []]
        if not va or not vb:
            continue
        n += 1
        for a in va:
            fa[a] += 1
        for b in vb:
            fb[b] += 1
        for a in va:
            for b in vb:
                pairs[(a, b)] += 1

    rows = []
    for (a, b), joint in pairs.items():
        if joint < min_joint:
            continue
        fx, fy = fa[a], fb[b]
        ll = M.log_likelihood_2x2(a=joint, b=fx - joint, c=fy - joint, d=max(0, n - fx - fy + joint))
        dp_xy, dp_yx = M.delta_p(joint, fx, fy, n)
        rows.append({
            "a": a, "b": b,
            "joint": joint, "f_a": fx, "f_b": fy, "N": n,
            "mi": round(M.mutual_information(joint, fx, fy, n), 4),
            "t_score": round(M.t_score(joint, fx, fy, n), 4),
            "dice": round(M.dice_coefficient(joint, fx, fy), 4),
            "log_dice": round(M.log_dice(joint, fx, fy), 4),
            "delta_p_a_given_b": round(dp_yx, 4),
            "delta_p_b_given_a": round(dp_xy, 4),
            "g2": round(ll, 4),
        })
    rows.sort(key=lambda r: r["g2"], reverse=True)
    return {"dim_a": dim_a, "dim_b": dim_b, "N": n, "pairs": rows}


# --------------------------------------------------------------------------- #
# Set-vs-set keyness (significance + effect size, always together)
# --------------------------------------------------------------------------- #


def keyness(images_target: list[Image], images_ref: list[Image], dim: str) -> dict:
    """Full-battery, LL-ranked keyness between two image sets on one
    dimension. Every row carries log-likelihood (significance) AND Log
    Ratio / %DIFF / Simple Maths / Odds Ratio (effect size) plus the Cochran
    min-expected diagnostic for χ² validity."""
    seq_t = dimension_sequence(images_target, dim, which="all")
    seq_r = dimension_sequence(images_ref, dim, which="all")
    ct = Counter(t for t in seq_t if t != "<gap>")
    cr = Counter(t for t in seq_r if t != "<gap>")
    N1, N2 = sum(ct.values()), sum(cr.values())
    vocab = set(ct) | set(cr)
    rows = []
    for term in vocab:
        row = M.compute_keyness_row(term, ct[term], cr[term], N1, N2)
        rows.append({
            "category": row.term,
            "f1": row.f1, "f2": row.f2,
            "norm_f1_pm": round(M._norm_freq(row.f1, N1), 2) if N1 else 0.0,
            "norm_f2_pm": round(M._norm_freq(row.f2, N2), 2) if N2 else 0.0,
            **{k: (round(v, 4) if abs(v) != float("inf") else v) for k, v in row.measures.items()},
        })
    rows.sort(key=lambda r: r["log_likelihood"], reverse=True)
    return {
        "dimension": dim,
        "N1": N1, "N2": N2,
        "note": "Keyness = significance (log_likelihood, chi_square, fisher_exact) "
                "+ effect size (log_ratio, pct_diff, simple_maths, odds_ratio), always together. "
                "chi2_min_expected < 5 flags χ² as unreliable on that row (use LL/Fisher instead).",
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# Dispersion
# --------------------------------------------------------------------------- #


def dispersion(images: list[Image], dim: str, *, bins: int = 10) -> dict:
    """Juilland's D and Gries' DP (+ DP-norm) per category, with per-bin
    histograms. Bins are consecutive slices of the reading order; expected
    proportions for DP are the bin *token* sizes (unequal-bin-correct)."""
    seq = dimension_sequence(images, dim, which="all")
    cats = [t for t in seq if t != "<gap>"]
    n_bins = max(1, min(bins, len(cats) or 1))
    size = max(1, len(cats) // n_bins)
    parts = [cats[i * size:(i + 1) * size] for i in range(n_bins - 1)]
    parts.append(cats[(n_bins - 1) * size:])  # last bin takes the remainder
    parts = [p for p in parts if p]
    bin_sizes = [len(p) for p in parts]
    vocab = set(cats)
    out = []
    for term in vocab:
        observed = [p.count(term) for p in parts]
        if sum(observed) == 0:
            continue
        out.append({
            "category": term,
            "total": sum(observed),
            "juillands_d": round(M.juillands_d(observed), 4),
            "gries_dp": round(M.gries_dp(observed, bin_sizes), 4),
            "gries_dp_norm": round(M.gries_dp_norm(observed, bin_sizes), 4),
            "per_bin": observed,
            "bin_sizes": bin_sizes,
        })
    out.sort(key=lambda r: r["gries_dp"])  # most even (lowest DP) first
    return {"dimension": dim, "bins": len(parts), "rows": out}


# --------------------------------------------------------------------------- #
# Visual KWIC (sequence concordance with left/right context)
# --------------------------------------------------------------------------- #


def visual_kwic(images: list[Image], dim: str, category: str, *, context: int = 2,
                limit: int = 200) -> dict:
    """Visual KWIC: every occurrence of ``category`` in the set's reading-
    order sequence for ``dim``, with ``context`` tokens of left/right
    co-annotation context and the anchor image's position + id."""
    seq = dimension_sequence(images, dim, which="first")
    hits = []
    for i, tok in enumerate(seq):
        if tok != category:
            continue
        left = seq[max(0, i - context): i]
        right = seq[i + 1: i + 1 + context]
        hits.append({
            "position": i,
            "image_id": images[i].id if i < len(images) and tok == seq[i] else None,
            "left": left,
            "node": tok,
            "right": right,
        })
        if len(hits) >= limit:
            break
    return {"dimension": dim, "category": category, "hits": hits, "total_occurrences": len(hits)}
