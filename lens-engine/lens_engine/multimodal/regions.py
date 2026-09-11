"""Region-merging helper for alignment (kept separate for testability)."""
from __future__ import annotations


def merge_boxes(boxes: list[list[int]], *, gap_px: int = 12) -> list[list[int]]:
    """Greedy horizontal merge of word boxes into phrase-region candidates."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    merged: list[list[int]] = []
    for x, y, w, h in boxes:
        placed = False
        for m in merged:
            mx, my, mw, mh = m
            same_line = abs((y + h / 2) - (my + mh / 2)) < max(h, mh) * 0.6
            adjacent = x <= mx + mw + gap_px and mx <= x + w + gap_px
            if same_line and adjacent:
                nx, ny = min(mx, x), min(my, y)
                nw = max(mx + mw, x + w) - nx
                nh = max(my + mh, y + h) - ny
                m[0], m[1], m[2], m[3] = nx, ny, nw, nh
                placed = True
                break
        if not placed:
            merged.append([x, y, w, h])
    return merged


def regions_from_words(words: list[dict], W: int, H: int, *,
                       max_regions: int = 12) -> list[list[float]]:
    """Merge OCR word boxes into normalized candidate regions (largest first)."""
    boxes = []
    for w in words:
        try:
            boxes.append([int(v) for v in w["box"]])
        except Exception:
            continue
    merged = merge_boxes(boxes)
    merged.sort(key=lambda b: b[2] * b[3], reverse=True)
    out = []
    for x, y, w, h in merged[:max_regions]:
        out.append([max(0.0, x / W), max(0.0, y / H), min(1.0, w / W), min(1.0, h / H)])
    if not out:
        out = [[0.0, 0.0, 1.0, 1.0]]
    return out
