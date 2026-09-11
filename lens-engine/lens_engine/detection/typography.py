"""Typography-in-image profiling (§9.8) — derived from OCR bounding-box
geometry, deterministic and reproducible.

For text embedded in images (posters, ads, memes): font weight/size proxies,
capitalization, spacing, alignment, and hierarchy, derived from the per-word
boxes captured by the OCR stage (§9.4). This is legitimate media/propaganda-
studies analysis of existing published content.

Logo/institution/symbol detection is deliberately NOT here — it rides the
ordinary object-detection classes on top of §9.5's detector, exactly as the
brief specifies.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from ..logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class TypographyProfile:
    word_count: int
    size_distribution: dict       # px-height quartiles → small/medium/large bands
    dominant_case: str            # lower | upper | title | mixed
    upper_ratio: float
    alignment: str                # left | centre | right | justified-ish | unknown
    line_count_estimate: int
    hierarchy: list[dict]         # distinct size bands with their words
    emphasis_signals: list[str]   # e.g. "shouty-caps", "very large display text"
    engine: str

    def to_dict(self) -> dict:
        return {
            "word_count": self.word_count,
            "size_distribution": self.size_distribution,
            "dominant_case": self.dominant_case,
            "upper_ratio": round(self.upper_ratio, 3),
            "alignment": self.alignment,
            "line_count_estimate": self.line_count_estimate,
            "hierarchy": self.hierarchy,
            "emphasis_signals": self.emphasis_signals,
            "engine": self.engine,
            "note": "Derived from OCR box geometry (pixel-height proxies, not font "
                    "identification). Numeric and reproducible.",
        }


def profile_typography(words: list[dict], image_width: int, image_height: int,
                       *, engine: str = "ocr-geometry v1") -> TypographyProfile:
    """Compute the typography profile from OCR per-word boxes.

    ``words``: [{"text": str, "conf": float, "box": [x, y, w, h]}, ...]
    """
    if not words:
        return TypographyProfile(0, {}, "unknown", 0.0, "unknown", 0, [], [], engine)

    boxes = []
    for w in words:
        try:
            x, y, bw, bh = (int(v) for v in w["box"])
        except Exception:
            continue
        text = (w.get("text") or "").strip()
        if not text or bh <= 1:
            continue
        boxes.append({"text": text, "x": x, "y": y, "w": bw, "h": bh})

    if not boxes:
        return TypographyProfile(0, {}, "unknown", 0.0, "unknown", 0, [], [], engine)

    heights = sorted(b["h"] for b in boxes)
    q1, q2, q3 = heights[len(heights) // 4], heights[len(heights) // 2], heights[3 * len(heights) // 4]

    def band(h: int) -> str:
        if h <= q1:
            return "small"
        if h <= q3:
            return "medium"
        return "large"

    size_bands = Counter(band(b["h"]) for b in boxes)
    size_distribution = {
        "q1_px": q1, "median_px": q2, "q3_px": q3,
        "bands": dict(size_bands),
        "relative_median": round(q2 / max(1, image_height), 4),
    }

    upper = sum(1 for b in boxes if b["text"].isupper() and len(b["text"]) > 1)
    title = sum(1 for b in boxes if b["text"][:1].isupper() and not b["text"].isupper())
    lower = sum(1 for b in boxes if b["text"].islower())
    upper_ratio = upper / len(boxes)
    if upper_ratio > 0.6:
        dominant_case = "upper"
    elif title / len(boxes) > 0.5:
        dominant_case = "title"
    elif lower / len(boxes) > 0.6:
        dominant_case = "lower"
    else:
        dominant_case = "mixed"

    # Alignment: cluster word left/right edges against image margins
    W = max(1, image_width)
    left_edges = [b["x"] / W for b in boxes]
    right_edges = [(b["x"] + b["w"]) / W for b in boxes]
    mean_left = sum(left_edges) / len(left_edges)
    mean_right = sum(right_edges) / len(right_edges)
    span = mean_right - mean_left
    if abs(mean_left - (1 - mean_right)) < 0.06 and span < 0.7:
        alignment = "centre"
    elif mean_left < 0.15:
        alignment = "left"
    elif mean_right > 0.85:
        alignment = "right"
    elif span > 0.85:
        alignment = "full-width (justified-ish)"
    else:
        alignment = "unknown"

    # Line estimate: group words whose vertical centres are close
    vcs = sorted((b["y"] + b["h"] / 2) for b in boxes)
    lines = 1
    for a, b in zip(vcs, vcs[1:]):
        if b - a > max(8, q2 * 0.8):
            lines += 1

    # Hierarchy: distinct size bands with representative words
    hierarchy = []
    for band_name in ("large", "medium", "small"):
        members = [b["text"] for b in boxes if band(b["h"]) == band_name]
        if members:
            hierarchy.append({
                "band": band_name,
                "words": members[:8],
                "median_height_px": sorted(b["h"] for b in boxes if band(b["h"]) == band_name)[
                    len(members) // 2
                ] if members else 0,
            })

    emphasis: list[str] = []
    if upper_ratio > 0.6 and len(boxes) > 3:
        emphasis.append("shouty-caps (majority uppercase)")
    if q2 > image_height * 0.08:
        emphasis.append("very large display text (median height > 8% of image height)")
    if re.search(r"!{2,}", " ".join(b["text"] for b in boxes)):
        emphasis.append("repeated exclamation marks")
    if size_bands.get("large", 0) > 0 and size_bands.get("small", 0) > 0:
        big = max(b["h"] for b in boxes if band(b["h"]) == "large")
        small = min(b["h"] for b in boxes if band(b["h"]) == "small")
        if small > 0 and big / small >= 3:
            emphasis.append(f"strong size hierarchy (largest/smallest ≈ {big / small:.1f}×)")

    return TypographyProfile(
        word_count=len(boxes),
        size_distribution=size_distribution,
        dominant_case=dominant_case,
        upper_ratio=upper_ratio,
        alignment=alignment,
        line_count_estimate=lines,
        hierarchy=hierarchy,
        emphasis_signals=emphasis,
        engine=engine,
    )
