"""Social-tab analytics over ``Post`` corpora (v0.2).

Platform-aware corpus linguistics: lexical frequency/diversity/ngrams reuse
the same :mod:`lens_engine.stats.measures` battery as the visual side, plus
social-native measures: emoji frequency, hashtag frequency and co-occurrence
networks, engagement statistics, engagement-weighted keyness, text KWIC and
a posting time series. Everything is deterministic and offline.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from . import textutils
from ..stats import measures as M
from ..storage.models import Post


def _texts(posts: list[Post]) -> list[str]:
    return [p.text for p in posts if p.text]


def _tok(posts: list[Post]) -> list[str]:
    out: list[str] = []
    for t in _texts(posts):
        out.extend(textutils.tokens(t))
    return out


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 2) if total else 0.0


# --------------------------------------------------------------------------- #
# Lexical battery (text-side counterpart of the visual annotation battery)
# --------------------------------------------------------------------------- #


def text_frequency(posts: list[Post], min_count: int = 1, limit: int = 500) -> dict:
    toks = _tok(posts)
    counts = Counter(toks)
    rows = [
        {"word": w, "count": c, "percent": _pct(c, len(toks))}
        for w, c in counts.most_common()
        if c >= max(1, min_count)
    ][:limit]
    return {
        "tokens": len(toks),
        "types": len(counts),
        "posts": len(posts),
        "profile": rows,
    }


def text_diversity(posts: list[Post], *, mattr_window: int = 50, sttr_chunk: int = 1000) -> dict:
    toks = _tok(posts)
    return {
        "posts": len(posts),
        "tokens": len(toks),
        "types": len(set(toks)),
        "ttr": round(M.type_token_ratio(toks), 4),
        "guiraud_r": round(M.guiraud(toks), 4),
        "mattr": round(M.mattr(toks, window=mattr_window), 4),
        "sttr": round(M.sttr(toks, chunk_size=sttr_chunk), 4),
    }


def text_ngrams(posts: list[Post], *, n: int = 2, min_count: int = 2, limit: int = 300) -> dict:
    """N-grams over the chronological text stream (reading order = post time)."""
    if not 1 <= n <= 5:
        raise ValueError("n must be 1-5")
    toks = _tok(posts)
    grams = [tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)]
    counts = Counter(" ".join(g) for g in grams)
    return {
        "n": n,
        "tokens": len(toks),
        "distinct_grams": len(counts),
        "profile": [
            {"ngram": g, "count": c, "percent": _pct(c, len(grams))}
            for g, c in counts.most_common()
            if c >= max(1, min_count)
        ][:limit],
    }


def text_kwic(posts: list[Post], query: str, context: int = 6, limit: int = 200) -> dict:
    """Concordance over post text (word-level window, chronological)."""
    q = query.strip().lower()
    if not q:
        return {"query": query, "hits": 0, "lines": []}
    lines: list[dict] = []
    for p in posts:
        toks = textutils.tokens(p.text)
        for i, t in enumerate(toks):
            if t == q or (len(q) > 3 and q in t):
                lo, hi = max(0, i - context), min(len(toks), i + context + 1)
                lines.append(
                    {
                        "post_id": p.id,
                        "platform": p.platform,
                        "created_at": p.created_at,
                        "left": " ".join(toks[lo:i]),
                        "node": toks[i],
                        "right": " ".join(toks[i + 1 : hi]),
                    }
                )
                if len(lines) >= limit:
                    break
        if len(lines) >= limit:
            break
    return {"query": q, "hits": len(lines), "lines": lines}


# --------------------------------------------------------------------------- #
# Social-native measures
# --------------------------------------------------------------------------- #


def emoji_stats(posts: list[Post], limit: int = 200) -> dict:
    per_post: list[int] = []
    counts: Counter = Counter()
    with_emoji = 0
    for p in posts:
        found = textutils.extract_emoji(p.text)
        per_post.append(len(found))
        if found:
            with_emoji += 1
        counts.update(found)
    total = sum(counts.values())
    return {
        "posts": len(posts),
        "posts_with_emoji": with_emoji,
        "coverage": _pct(with_emoji, len(posts)),
        "total_emoji": total,
        "types": len(counts),
        "per_post_mean": round(statistics.fmean(per_post), 3) if per_post else 0.0,
        "profile": [
            {"emoji": e, "count": c, "percent": _pct(c, total)}
            for e, c in counts.most_common()[:limit]
        ],
    }


def hashtag_stats(posts: list[Post], limit: int = 300) -> dict:
    counts: Counter = Counter()
    for p in posts:
        counts.update((p.meta or {}).get("hashtags") or [])
    norm = Counter({(k or "").lower(): v for k, v in counts.items()})
    total = sum(norm.values())
    return {
        "posts": len(posts),
        "posts_with_hashtags": sum(1 for p in posts if (p.meta or {}).get("hashtags")),
        "total_hashtags": total,
        "unique_hashtags": len(norm),
        "per_post_mean": round(total / len(posts), 3) if posts else 0.0,
        "profile": [
            {"hashtag": f"#{h}", "count": c, "percent": _pct(c, total)}
            for h, c in norm.most_common()[:limit]
        ],
    }


def hashtag_cooccurrence(posts: list[Post], min_joint: int = 2, limit: int = 300) -> dict:
    pair_counts: Counter = Counter()
    node_counts: Counter = Counter()
    for p in posts:
        tags = sorted({(h or "").lower() for h in ((p.meta or {}).get("hashtags") or []) if h})
        node_counts.update(tags)
        for i, a in enumerate(tags):
            for b in tags[i + 1 :]:
                pair_counts[(a, b)] += 1
    pairs = [
        {"a": f"#{a}", "b": f"#{b}", "joint": c}
        for (a, b), c in pair_counts.most_common()
        if c >= max(1, min_joint)
    ][:limit]
    return {
        "nodes": len(node_counts),
        "pairs": len(pair_counts),
        "edges": pairs,
        "top_nodes": [{"hashtag": f"#{h}", "count": c} for h, c in node_counts.most_common(50)],
    }


def engagement_stats(posts: list[Post], top: int = 20) -> dict:
    def _vals(get) -> list[int]:
        return [get(p) for p in posts]

    def _block(name: str, vals: list[int]) -> dict:
        return {
            "total": sum(vals),
            "mean": round(statistics.fmean(vals), 2) if vals else 0.0,
            "median": statistics.median(vals) if vals else 0,
            "max": max(vals) if vals else 0,
        }

    likes, comments, shares = _vals(lambda p: p.likes), _vals(lambda p: p.comments), _vals(lambda p: p.shares)
    def _total(p: Post) -> int:
        return p.likes + p.comments + p.shares

    ranked = sorted(posts, key=_total, reverse=True)[:top]
    by_platform: dict[str, dict] = {}
    for plat in sorted({p.platform for p in posts}):
        sub = [p for p in posts if p.platform == plat]
        by_platform[plat] = {
            "posts": len(sub),
            "mean_engagement": round(statistics.fmean([_total(p) for p in sub]), 2) if sub else 0.0,
            "mean_likes": round(statistics.fmean([p.likes for p in sub]), 2) if sub else 0.0,
        }
    return {
        "posts": len(posts),
        "likes": _block("likes", likes),
        "comments": _block("comments", comments),
        "shares": _block("shares", shares),
        "by_platform": by_platform,
        "top_posts": [
            {
                "id": p.id,
                "platform": p.platform,
                "author": p.author,
                "text": p.text[:160],
                "likes": p.likes,
                "comments": p.comments,
                "shares": p.shares,
                "engagement": _total(p),
                "created_at": p.created_at,
            }
            for p in ranked
        ],
    }


def engagement_weighted_frequency(
    posts: list[Post], *, min_count: int = 1, limit: int = 300
) -> dict:
    """Term frequency weighted by engagement: weight = 1 + ln(1 + likes).

    Surfaces the lexis of high-reach posts instead of treating every post
    equally; pairs with plain :func:`text_frequency` for comparison.
    """
    plain: Counter = Counter()
    weighted: dict[str, float] = defaultdict(float)
    for p in posts:
        toks = textutils.tokens(p.text)
        plain.update(toks)
        w = 1.0 + __import__("math").log(1 + max(0, p.likes))
        for t in toks:
            weighted[t] += w
    rows = sorted(weighted.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return {
        "posts": len(posts),
        "note": "weight = 1 + ln(1 + likes)",
        "profile": [
            {"word": w, "weighted": round(v, 3), "count": plain.get(w, 0)} for w, v in rows
        ],
    }


def keyness_tokens(target: list[Post], reference: list[Post], *, min_freq: int = 2, limit: int = 200) -> dict:
    """Target-vs-reference keyness over token frequency (same battery as §11)."""
    t_counts, r_counts = Counter(_tok(target)), Counter(_tok(reference))
    n1, n2 = sum(t_counts.values()), sum(r_counts.values())
    rows = []
    for w, f1 in t_counts.items():
        if f1 < min_freq:
            continue
        row = M.compute_keyness_row(w, f1, r_counts.get(w, 0), n1, n2)
        rows.append(
            {
                "word": row.term,
                "f_target": row.f1,
                "f_reference": row.f2,
                "log_likelihood": round(row.measures["log_likelihood"], 4),
                "log_ratio": round(row.measures["log_ratio"], 4),
                "pct_diff": round(row.measures["pct_diff"], 2),
                "odds_ratio": round(row.measures["odds_ratio"], 4),
            }
        )
    rows.sort(key=lambda r: r["log_likelihood"], reverse=True)
    return {
        "target_tokens": n1,
        "reference_tokens": n2,
        "rows": rows[:limit],
    }


def time_series(posts: list[Post], bucket: str = "month") -> dict:
    """Post counts and mean engagement per time bucket (chronological)."""
    if bucket not in ("day", "week", "month", "year"):
        raise ValueError("bucket must be one of: day, week, month, year")
    bins: dict[str, list[int]] = defaultdict(list)
    for p in posts:
        t = (p.created_at or "")[: {"day": 10, "week": 10, "month": 7, "year": 4}[bucket]]
        if t:
            bins[t].append(p.likes + p.comments + p.shares)
    points = [
        {
            "bucket": k,
            "posts": len(v),
            "engagement_total": sum(v),
            "engagement_mean": round(statistics.fmean(v), 2) if v else 0.0,
        }
        for k, v in sorted(bins.items())
    ]
    return {"bucket": bucket, "points": points, "span": [points[0]["bucket"], points[-1]["bucket"]] if points else None}
