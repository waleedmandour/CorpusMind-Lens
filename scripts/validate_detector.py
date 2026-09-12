"""§16 detector/embedding validation harness (crash-resilient driver form).

Benchmarks the engine's OWN detection stack — ``OWLViTDetector``,
``SceneClassifier`` (CLIP zero-shot) and the ``clip-ViT-B-32`` embedding
backend — against a small hand-annotated sample (``validation-sample.json``).

Subcommands (each is a short-lived process — OWL-ViT's CPU activations can
hit small boxes' RAM ceilings, so no long-lived orchestrator is trusted):

    detect-one NAME CACHE_DIR FRAG_DIR   one image × all thresholds → fragment
    scenes CACHE_DIR FRAG_DIR            CLIP zero-shot scene labels → fragment
    embed  CACHE_DIR FRAG_DIR            clip-ViT-B-32 zero-shot → fragment
    aggregate CACHE_DIR FRAG_DIR OUT     merge fragments + GT → metrics JSON

Matching policy: greedy by confidence, same category, IoU >= 0.5
(recorded in validation-sample.json's ``policy``). Results are an honest
smoke-level benchmark on a deliberately small sample — NOT a claim of
parity with fine-tuned, task-specific models.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import pathlib
import platform
import sys
import time

import numpy as np

from PIL import Image
import urllib.request

SAMPLE = pathlib.Path(__file__).resolve().parent / "validation-sample.json"
ENGINE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "lens-engine"
UA = "CorpusMindLens-validation/0.1 (research benchmark)"

THRESHOLDS = [0.40, 0.25, 0.15]  # 0.15 = engine default


def fetch_image(url: str, cache: pathlib.Path, name: str) -> bytes:
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / name
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    last: Exception | None = None
    for attempt in range(4):  # image hosts throw transient 502/429s
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                dest.write_bytes(r.read())
            return dest.read_bytes()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last}")


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def match(detections: list[dict], gt: list[dict], iou_thresh: float = 0.5):
    """Greedy same-category matching. Returns (tp, fp, fn)."""
    used = [False] * len(gt)
    tp = 0
    for det in sorted(detections, key=lambda d: -d["confidence"]):
        best, best_iou = None, iou_thresh
        for i, g in enumerate(gt):
            if used[i] or g["category"] != det["label"]:
                continue
            v = iou(det["bbox"], g["bbox"])
            if v >= best_iou:
                best, best_iou = i, v
        if best is not None:
            used[best] = True
            tp += 1
    fp = len(detections) - tp
    fn = sum(1 for u in used if not u)
    return tp, fp, fn


def square_pad(raw: bytes, max_side: int = 800):
    """Pad to square on the shorter axis, then cap the side at max_side.

    Returns (jpeg_bytes, (fx, fy, fw, fh)) so a GT box maps into padded
    space as x' = fx + x*fw, y' = fy + y*fh (normalized throughout).
    Square input keeps OWL-ViT's token grid constant, bounding activation
    memory on small machines.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    W, H = img.size
    S = max(W, H)
    px, py = (S - W) // 2, (S - H) // 2
    canvas = Image.new("RGB", (S, S), (128, 128, 128))
    canvas.paste(img, (px, py))
    if S > max_side:
        canvas = canvas.resize((max_side, max_side))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    return buf.getvalue(), (px / S, py / S, W / S, H / S)


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text())


def object_images(sample: dict) -> dict:
    return {k: v for k, v in sample["images"].items() if v["boxes"]}


def scene_images(sample: dict) -> dict:
    return {k: v for k, v in sample["images"].items() if v.get("scene")}


# ── subcommands ──────────────────────────────────────────────────────────

def cmd_detect_one(args) -> int:
    sample = load_sample()
    items = object_images(sample)
    name = args.name if args.name in items else f"{args.name}.jpg"
    if name not in items:
        print(f"unknown object image {args.name}")
        return 2
    sys.path.insert(0, str(ENGINE_ROOT))
    from lens_engine.detection.detector import OWLViTDetector

    det = OWLViTDetector()
    padded, (fx, fy, fw, fh) = square_pad(fetch_image(items[name]["source"]["image_url"],
                                                      pathlib.Path(args.cache_dir), name))
    out = {"gt_padded": [
        {**g, "bbox": [fx + g["bbox"][0] * fw, fy + g["bbox"][1] * fh,
                        g["bbox"][2] * fw, g["bbox"][3] * fh]}
        for g in items[name]["boxes"]
    ], "thresholds": {}}
    for t in THRESHOLDS:
        t0 = time.time()
        dets = asyncio_run(det.detect(padded, threshold=t))
        out["thresholds"][str(t)] = {"dets": [d.to_dict() for d in dets],
                                     "latency_s": round(time.time() - t0, 2)}
        print(f"{name} @ {t}: {len(dets)} dets ({out['thresholds'][str(t)]['latency_s']}s)", flush=True)
    frag = pathlib.Path(args.frag_dir)
    frag.mkdir(parents=True, exist_ok=True)
    (frag / f"det-{name}.json").write_text(json.dumps(out))
    return 0


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def cmd_scenes(args) -> int:
    sample = load_sample()
    items = scene_images(sample)
    sys.path.insert(0, str(ENGINE_ROOT))
    from lens_engine.detection.detector import SceneClassifier

    sc = SceneClassifier()
    detail, top1, top3 = [], 0, 0
    for name, item in items.items():
        raw = fetch_image(item["source"]["image_url"], pathlib.Path(args.cache_dir), name)
        res = asyncio_run(sc.classify(raw, top_k=3))
        got = [r["scene"] for r in res]
        top1 += got and item["scene"] == got[0]
        top3 += item["scene"] in got
        detail.append({"image": name, "expected": item["scene"], "got": got})
        print(f"{name}: expected {item['scene']}, got {got}", flush=True)
    frag = pathlib.Path(args.frag_dir)
    frag.mkdir(parents=True, exist_ok=True)
    (frag / "scenes.json").write_text(json.dumps(
        {"top1": f"{top1}/{len(items)}", "top3": f"{top3}/{len(items)}", "detail": detail}))
    print(f"scenes: top1 {top1}/{len(items)}, top3 {top3}/{len(items)}")
    return 0


def cmd_embed(args) -> int:
    sample = load_sample()
    items = object_images(sample)
    sys.path.insert(0, str(ENGINE_ROOT))
    from lens_engine.detection.detector import DEFAULT_QUERY_CATEGORIES

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("sentence-transformers/clip-ViT-B-32")
    prompts = [f"a photo of {c}" for c in DEFAULT_QUERY_CATEGORIES]
    t_emb = model.encode(prompts, normalize_embeddings=True)
    detail, top1, top3 = [], 0, 0
    for name, item in items.items():
        raw = fetch_image(item["source"]["image_url"], pathlib.Path(args.cache_dir), name)
        img = Image.open(io.BytesIO(raw)).convert("RGB")  # ST >= 5 rejects BytesIO
        i_emb = model.encode(img, normalize_embeddings=True)
        sims = (np.atleast_2d(i_emb) @ np.atleast_2d(t_emb).T).ravel()
        ranked = [c for _, c in sorted(zip(sims.tolist(), DEFAULT_QUERY_CATEGORIES), reverse=True)]
        top1 += ranked[0] == item["primary"]
        top3 += item["primary"] in ranked[:3]
        detail.append({"image": name, "expected": item["primary"], "top3": ranked[:3]})
        print(f"{name}: expected {item['primary']}, top3 {ranked[:3]}", flush=True)
    frag = pathlib.Path(args.frag_dir)
    frag.mkdir(parents=True, exist_ok=True)
    (frag / "embeddings.json").write_text(json.dumps(
        {"model": "sentence-transformers/clip-ViT-B-32",
         "zero_shot_category_top1": f"{top1}/{len(items)}",
         "top3": f"{top3}/{len(items)}", "detail": detail}))
    print(f"embeddings zero-shot: top1 {top1}/{len(items)}, top3 {top3}/{len(items)}")
    return 0


def cmd_aggregate(args) -> int:
    sample = load_sample()
    items = object_images(sample)
    frag_dir = pathlib.Path(args.frag_dir)

    per_thresh: dict[float, dict[str, list[dict]]] = {t: {} for t in THRESHOLDS}
    gt_padded: dict[str, list[dict]] = {}
    latencies = []
    for name in items:
        f = frag_dir / f"det-{name}.json"
        if not f.exists():
            print(f"MISSING fragment for {name} — aggregate incomplete")
            return 3
        data = json.loads(f.read_text())
        gt_padded[name] = data["gt_padded"]
        for t in THRESHOLDS:
            rec = data["thresholds"][str(t)]
            per_thresh[t][name] = rec["dets"]
            latencies.append({"image": name, "threshold": t, "s": rec["latency_s"]})

    results: dict = {"thresholds": {}, "per_category_at_default": {}, "latency_s": latencies,
                     "env": {"platform": platform.platform(), "python": platform.python_version()}}
    try:
        import torch, transformers  # noqa

        results["env"]["torch"] = torch.__version__
        results["env"]["transformers"] = transformers.__version__
    except Exception:  # noqa: BLE001
        pass

    for t in THRESHOLDS:
        TP = FP = FN = 0
        for name in items:
            tp, fp, fn = match(per_thresh[t][name], gt_padded[name])
            TP += tp; FP += fp; FN += fn
        p = TP / (TP + FP) if TP + FP else 0.0
        r = TP / (TP + FN) if TP + FN else 0.0
        results["thresholds"][str(t)] = {"tp": TP, "fp": FP, "fn": FN,
                                         "precision": round(p, 3), "recall": round(r, 3)}
        print(f"threshold {t}: P={p:.3f} R={r:.3f} (TP={TP} FP={FP} FN={FN})")

    cat: dict[str, dict] = {}
    for name in items:
        dets = per_thresh[0.15][name]
        gt = gt_padded[name]
        used = [False] * len(gt)
        for det_ in sorted(dets, key=lambda d: -d["confidence"]):
            hit, best = None, 0.5
            for i, g in enumerate(gt):
                if used[i] or g["category"] != det_["label"]:
                    continue
                v = iou(det_["bbox"], g["bbox"])
                if v >= best:
                    hit, best = i, v
            c = cat.setdefault(det_["label"], {"tp": 0, "fp": 0, "fn": 0})
            if hit is not None:
                used[hit] = True
                c["tp"] += 1
            else:
                c["fp"] += 1
        for i, g in enumerate(gt):
            if not used[i]:
                cat.setdefault(g["category"], {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1
    results["per_category_at_default"] = {
        k: {**v, "precision": round(v["tp"] / (v["tp"] + v["fp"]), 3) if v["tp"] + v["fp"] else 0.0,
            "recall": round(v["tp"] / (v["tp"] + v["fn"]), 3) if v["tp"] + v["fn"] else 0.0}
        for k, v in sorted(cat.items())}

    for frag, key in (("scenes.json", "scenes"), ("embeddings.json", "embeddings")):
        f = frag_dir / frag
        results[key] = json.loads(f.read_text()) if f.exists() else {"missing": True}

    pathlib.Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"wrote {args.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("detect-one")
    p1.add_argument("name")
    p1.add_argument("cache_dir")
    p1.add_argument("frag_dir")
    p1.set_defaults(fn=cmd_detect_one)

    p2 = sub.add_parser("scenes")
    p2.add_argument("cache_dir")
    p2.add_argument("frag_dir")
    p2.set_defaults(fn=cmd_scenes)

    p3 = sub.add_parser("embed")
    p3.add_argument("cache_dir")
    p3.add_argument("frag_dir")
    p3.set_defaults(fn=cmd_embed)

    p4 = sub.add_parser("aggregate")
    p4.add_argument("cache_dir")
    p4.add_argument("frag_dir")
    p4.add_argument("out")
    p4.set_defaults(fn=cmd_aggregate)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
