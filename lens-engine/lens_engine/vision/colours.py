"""Colour & composition analysis (§9.7) — geometric, not impressionistic.

Colour symbolism output is always framework/culture-relative, labelled as
such, never universal (§4 Principle 4). Composition metrics — information
value (left/right, top/bottom, centre/margin), salience, framing, rule of
thirds, visual balance — are computed from saliency maps + bounding-box
centroids so results are numeric and reproducible.
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass

from ..logging import get_logger

log = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Colour analysis
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ColourAnalysis:
    dominant_colours: list[dict]     # [{hex, rgb, percent}]
    warm_cold_balance: float         # -1 (cold) to +1 (warm)
    brightness: float                # 0–255 mean luminance
    contrast: float                  # 0–255 std of luminance
    saturation: float                # 0–1 mean saturation
    colour_symbolism_notes: list[str]  # culture-relative hints, labelled


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _is_warm(hue: float) -> bool:
    """Hue 0–60 (red-yellow) and 300–360 (magenta-red) = warm."""
    return hue < 60 or hue >= 300


def analyse_colours(img, *, max_colours: int = 5) -> ColourAnalysis:
    """Analyse colour distribution of an image (§9.7)."""
    import numpy as np

    if img.width > 200:
        ratio = 200 / img.width
        img_small = img.resize((200, max(1, int(img.height * ratio))))
    else:
        img_small = img

    arr = np.array(img_small)
    quantized = (arr // 32) * 32
    pixels = quantized.reshape(-1, 3)

    from collections import Counter

    colour_counts = Counter(tuple(int(p) for p in pix) for pix in pixels)
    total = sum(colour_counts.values())
    dominant = []
    for rgb, count in colour_counts.most_common(max_colours):
        dominant.append({
            "hex": _rgb_to_hex(rgb),
            "rgb": [int(c) for c in rgb],
            "percent": round(count / total * 100, 2),
        })

    warm_count = cold_count = 0
    saturations: list[float] = []
    for rgb, count in colour_counts.items():
        r, g, b = [x / 255.0 for x in rgb]
        h, s, _v = colorsys.rgb_to_hsv(r, g, b)
        if s > 0.1:  # ignore near-grey pixels
            if _is_warm(h * 360):
                warm_count += count
            else:
                cold_count += count
            saturations.append(s * count)
    warm_cold = (warm_count - cold_count) / total if total else 0.0

    grey = np.array(img_small.convert("L"))
    brightness = float(grey.mean())
    contrast = float(grey.std())
    saturation = sum(saturations) / total if total else 0.0

    # Culture-relative notes — explicitly labelled framework/culture-relative
    # in the phrasing itself, per §4 Principle 4.
    notes = []
    top_r, top_g, top_b = dominant[0]["rgb"] if dominant else [128, 128, 128]
    if top_r > 150 and top_g < 100 and top_b < 100:
        notes.append(
            "Red-dominant. Framework/culture-relative (not universal): in many Western "
            "contexts passion/danger; in many East Asian contexts luck/celebration."
        )
    elif top_r > 200 and top_g > 200 and top_b < 100:
        notes.append(
            "Yellow-dominant. Framework/culture-relative: commonly warmth/caution; "
            "in some contexts sacred/royal."
        )
    elif top_g > 120 and top_r < 120 and top_b < 120:
        notes.append(
            "Green-dominant. Framework/culture-relative: commonly nature/growth; "
            "in some Islamic contexts religious significance."
        )
    elif top_b > 120 and top_r < 100 and top_g < 100:
        notes.append(
            "Blue-dominant. Framework/culture-relative: commonly calm/trust; "
            "in some contexts melancholy."
        )
    elif top_r > 150 and top_g < 100 and top_b > 150:
        notes.append(
            "Magenta/purple-dominant. Framework/culture-relative: commonly luxury/spirituality."
        )
    if brightness > 200:
        notes.append(
            "High-key (very bright). Framework-relative reading: often connotes openness/optimism."
        )
    elif brightness < 60:
        notes.append(
            "Low-key (very dark). Framework-relative reading: often connotes gravity/mystery."
        )

    return ColourAnalysis(
        dominant_colours=dominant,
        warm_cold_balance=round(warm_cold, 3),
        brightness=round(brightness, 1),
        contrast=round(contrast, 1),
        saturation=round(saturation, 3),
        colour_symbolism_notes=notes,
    )


# --------------------------------------------------------------------------- #
# Composition analysis (geometric)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CompositionAnalysis:
    information_value: dict[str, float]       # {left, right, top, bottom, centre, margin}
    rule_of_thirds_intersections: list[dict]  # 4 intersection points + salience
    salience_centre: tuple[float, float]      # (x, y) normalized 0–1
    visual_balance: float                     # -1 (left-heavy) to +1 (right-heavy)
    framing_balance: float                    # 0 (centred) to 1 (edge-weighted)
    golden_ratio_offset: float                # distance of salience centre from φ point
    vectors: list[dict]                       # dominant directional vectors (edge-based)


def analyse_composition(img) -> CompositionAnalysis:
    """Geometric composition analysis (§9.7)."""
    import numpy as np
    from PIL import ImageFilter

    if img.width > 400:
        ratio = 400 / img.width
        img_small = img.resize((400, max(1, int(img.height * ratio))))
    else:
        img_small = img

    arr = np.array(img_small.convert("L"), dtype=float)
    h, w = arr.shape

    blurred = img_small.convert("L").filter(ImageFilter.GaussianBlur(radius=5))
    blurred_arr = np.array(blurred, dtype=float)
    saliency = np.abs(arr - blurred_arr)
    saliency_norm = saliency / (saliency.max() + 1e-8)
    total_salience = saliency_norm.sum()

    if total_salience > 0:
        ys, xs = np.indices(saliency_norm.shape)
        cx = float((xs * saliency_norm).sum() / total_salience / w)
        cy = float((ys * saliency_norm).sum() / total_salience / h)
    else:
        cx, cy = 0.5, 0.5

    left = float(saliency_norm[:, : w // 2].sum() / total_salience) if total_salience else 0.5
    right = float(saliency_norm[:, w // 2:].sum() / total_salience) if total_salience else 0.5
    top = float(saliency_norm[: h // 2, :].sum() / total_salience) if total_salience else 0.5
    bottom = float(saliency_norm[h // 2:, :].sum() / total_salience) if total_salience else 0.5
    centre = float(
        saliency_norm[h // 4: 3 * h // 4, w // 4: 3 * w // 4].sum() / total_salience
    ) if total_salience else 0.5
    margin = 1.0 - centre

    visual_balance = right - left
    framing_balance = float(margin)

    thirds_points = []
    for tx in [w / 3, 2 * w / 3]:
        for ty in [h / 3, 2 * h / 3]:
            x0, x1 = max(0, int(tx - 10)), min(w, int(tx + 10))
            y0, y1 = max(0, int(ty - 10)), min(h, int(ty + 10))
            local = float(saliency_norm[y0:y1, x0:x1].sum() / (total_salience + 1e-8))
            thirds_points.append({"x": round(tx / w, 3), "y": round(ty / h, 3), "salience": round(local, 4)})

    # Golden-ratio offset: distance from the nearest φ intersection (0.382/0.618 grid)
    phi_xs = [0.382, 0.618]
    phi_ys = [0.382, 0.618]
    d = min(((cx - px) ** 2 + (cy - py) ** 2) ** 0.5 for px in phi_xs for py in phi_ys)

    # Dominant directional vectors via image gradient orientation histogram
    gy, gx = np.gradient(arr)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    theta = (np.degrees(np.arctan2(gy, gx)) + 360) % 180  # 0–180 orientation bins
    hist, edges = np.histogram(theta, bins=12, range=(0, 180), weights=mag)
    vectors = []
    top_idx = hist.argsort()[::-1][:3]
    for i in top_idx:
        if hist[i] <= 0 or mag.sum() <= 0:
            continue
        vectors.append({
            "angle_deg": round(float((edges[i] + edges[i + 1]) / 2), 1),
            "strength": round(float(hist[i] / hist.sum()), 3) if hist.sum() else 0.0,
        })

    return CompositionAnalysis(
        information_value={
            "left": round(left, 3), "right": round(right, 3),
            "top": round(top, 3), "bottom": round(bottom, 3),
            "centre": round(centre, 3), "margin": round(margin, 3),
        },
        rule_of_thirds_intersections=thirds_points,
        salience_centre=(round(cx, 3), round(cy, 3)),
        visual_balance=round(visual_balance, 3),
        framing_balance=round(framing_balance, 3),
        golden_ratio_offset=round(d, 3),
        vectors=vectors,
    )
