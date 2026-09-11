"""The AI Assistant tool surface (§10).

Grounded tool-calling ONLY (§4 Principle 2): every claim the Assistant makes
must resolve to a real tool call — a computed statistic, an image region, an
OCR span, or a cited framework template. Every call + result is written to
the audit trail; tool results are returned with evidence ids the UI renders
as badges. With Companion Mode on, ``get_text_corpus_overview`` joins the
surface (§5); without it, the tool is simply absent (graceful degradation).

Tools: list_image_sets, get_image_set_summary, get_image_analysis,
describe_image_region, get_detections, get_alignment, get_visual_profile,
get_visual_ngrams, get_visual_collocations, get_visual_keyness,
get_visual_dispersion, visual_kwic, get_framework_template,
[get_text_corpus_overview — Companion Mode only].
"""
from __future__ import annotations

import json
from typing import Any

from ..config import get_settings
from ..logging import get_logger
from ..main import get_store
from ..stats import service
from ..vision.annotations import SCHEMA, dimension

log = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Tool implementations — return {"summary": str, "evidence": {...}, "data": ...}
# --------------------------------------------------------------------------- #


def _ok(summary: str, data: Any, evidence: dict | None = None) -> dict:
    return {"grounded": True, "summary": summary, "evidence": evidence or {},
            "data": _jsonable(data)}


def _err(msg: str) -> dict:
    return {"grounded": False, "error": msg, "data": None}


def _jsonable(obj: Any) -> Any:
    try:
        json.dumps(obj, ensure_ascii=False, default=str)
        return obj
    except Exception:
        return str(obj)[:2000]


def list_image_sets() -> dict:
    store = get_store()
    sets = store.list_image_sets()
    return _ok(
        f"{len(sets)} image sets available.",
        [{"id": s.id, "name": s.name, "project_id": s.project_id} for s in sets],
        evidence={"tool": "list_image_sets"},
    )


def get_image_set_summary(set_id: str) -> dict:
    store = get_store()
    s = store.get_image_set(set_id)
    if not s:
        return _err(f"Image set '{set_id}' not found.")
    images = store.list_images(set_id)
    coverage = {
        "ocr": sum(1 for i in images if (i.meta or {}).get("ocr", {}).get("text")),
        "detections": sum(1 for i in images if (i.meta or {}).get("detections")),
        "annotated": sum(1 for i in images if (i.meta or {}).get("annotations")),
    }
    return _ok(
        f"Image set '{s.name}': {len(images)} images; OCR on {coverage['ocr']}, "
        f"detections on {coverage['detections']}, annotations on {coverage['annotated']}.",
        {"name": s.name, "description": s.description, "provenance_notes": s.provenance_notes,
         "tags": s.tags, "image_count": len(images), "coverage": coverage},
        evidence={"tool": "get_image_set_summary", "set_id": set_id},
    )


def get_image_analysis(image_id: str) -> dict:
    img = get_store().get_image(image_id)
    if not img:
        return _err(f"Image '{image_id}' not found.")
    meta = img.meta or {}
    return _ok(
        f"Analysis for '{img.filename}': OCR {meta.get('ocr', {}).get('word_count', 0)} words "
        f"(conf {meta.get('ocr', {}).get('confidence', 0)}), "
        f"{len(meta.get('detections', []))} detections, "
        f"{len((meta.get('colour') or {}).get('dominant_colours', []))} dominant colours.",
        {"ocr": meta.get("ocr"), "colour": meta.get("colour"),
         "composition": meta.get("composition"), "detections": meta.get("detections"),
         "annotations": meta.get("annotations"), "typography": meta.get("typography"),
         "vlm_description": (meta.get("vlm_description") or {}).get("text", "")},
        evidence={"tool": "get_image_analysis", "image_id": image_id},
    )


def describe_image_region(image_id: str, bbox: list[float]) -> dict:
    """Region description resolves to the stored VLM narrative + the
    deterministic sub-analyses that intersect the region — never a fresh
    ungrounded generation."""
    img = get_store().get_image(image_id)
    if not img or not img.meta:
        return _err("Image not found.")
    meta = img.meta
    x, y, w, h = bbox if len(bbox) == 4 else (0, 0, 1, 1)
    inside = [
        d for d in meta.get("detections", [])
        if d.get("bbox") and not (d["bbox"][0] + d["bbox"][2] < x or d["bbox"][0] > x + w
                                  or d["bbox"][1] + d["bbox"][3] < y or d["bbox"][1] > y + h)
    ]
    words_in_region = [
        wd for wd in (meta.get("ocr") or {}).get("words", [])
        if wd.get("box") and not (wd["box"][0] + wd["box"][2] < x * (img.width or 1)
                                  or wd["box"][0] > (x + w) * (img.width or 1))
    ]
    return _ok(
        f"Region {bbox}: {len(inside)} detections, {len(words_in_region)} OCR words.",
        {"detections": inside, "ocr_words": words_in_region,
         "vlm_description": (meta.get("vlm_description") or {}).get("text", "")},
        evidence={"tool": "describe_image_region", "image_id": image_id, "bbox": bbox},
    )


def get_detections(image_id: str) -> dict:
    img = get_store().get_image(image_id)
    if not img:
        return _err("Image not found.")
    dets = img.meta.get("detections", [])
    return _ok(f"{len(dets)} detections.", dets,
               evidence={"tool": "get_detections", "image_id": image_id})


def get_alignment(image_id: str) -> dict:
    img = get_store().get_image(image_id)
    if not img:
        return _err("Image not found.")
    al = img.meta.get("alignment")
    if not al:
        return _err("No alignment computed yet (POST /images/{id}/align).")
    return _ok(f"Alignment backend {al.get('backend')}: {len(al.get('pairs', []))} pairs.",
               al, evidence={"tool": "get_alignment", "image_id": image_id})


def get_visual_profile(set_id: str, dim: str) -> dict:
    images = get_store().list_images(set_id)
    return _ok(service.frequency_profile(images, dim)["total_observations"] and
               f"Frequency profile for '{dim}' computed.",
               service.frequency_profile(images, dim),
               evidence={"tool": "get_visual_profile", "set_id": set_id, "dimension": dim})


def get_visual_ngrams(set_id: str, dim: str, n: int = 2) -> dict:
    images = get_store().list_images(set_id)
    return _ok(f"{n}-grams over reading order for '{dim}'.",
               service.ngrams(images, dim, n=n, min_count=1),
               evidence={"tool": "get_visual_ngrams", "set_id": set_id, "dimension": dim})


def get_visual_collocations(set_id: str, dim_a: str, dim_b: str) -> dict:
    images = get_store().list_images(set_id)
    return _ok(f"Co-occurrence between '{dim_a}' and '{dim_b}'.",
               service.cooccurrence(images, dim_a, dim_b, min_joint=1),
               evidence={"tool": "get_visual_collocations", "set_id": set_id})


def get_visual_keyness(set_a: str, set_b: str, dim: str) -> dict:
    store = get_store()
    return _ok("Keyness (LL + effect sizes) between the two sets.",
               service.keyness(store.list_images(set_a), store.list_images(set_b), dim),
               evidence={"tool": "get_visual_keyness", "set_a": set_a, "set_b": set_b})


def get_visual_dispersion(set_id: str, dim: str) -> dict:
    images = get_store().list_images(set_id)
    return _ok("Dispersion (Juilland's D, Gries' DP) per category.",
               service.dispersion(images, dim),
               evidence={"tool": "get_visual_dispersion", "set_id": set_id})


def visual_kwic(set_id: str, dim: str, category: str) -> dict:
    images = get_store().list_images(set_id)
    return _ok(f"Visual KWIC for '{category}' in '{dim}'.",
               service.visual_kwic(images, dim, category),
               evidence={"tool": "visual_kwic", "set_id": set_id})


def get_framework_template(name: str) -> dict:
    from ..config import get_settings
    from ..discourse.lenses import load_frameworks

    fws = load_frameworks(get_settings().frameworks_dir)
    fw = fws.get(name)
    if not fw:
        return _err(f"Framework '{name}' not found (available: {sorted(fws)}).")
    return _ok(f"Framework template '{fw.full_name}' v{fw.version}.",
               {"id": fw.id, "full_name": fw.full_name, "categories": fw.categories,
                "guardrails": fw.guardrails},
               evidence={"tool": "get_framework_template", "framework": name})


def get_text_corpus_overview(base_url: str, corpus_id: str) -> dict:
    """Companion Mode ONLY (§5) — the tool is absent unless enabled."""
    settings = get_settings()
    if not settings.companion_enabled:
        return _err("Companion Mode is off. Enable it in Settings (it is never required).")
    from ..companion.client import CompanionClient, CompanionError

    try:
        import asyncio

        client = CompanionClient(base_url or settings.companion_base_url)
        overview = asyncio.get_event_loop().run_until_complete(
            client.get_corpus_overview(corpus_id))
    except CompanionError as e:
        return _err(f"Companion engine unreachable: {e}")
    return _ok("Companion text corpus overview retrieved.",
               overview,
               evidence={"tool": "get_text_corpus_overview", "base_url": base_url,
                         "corpus_id": corpus_id})


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

TOOLS: dict[str, dict[str, Any]] = {
    "list_image_sets": {"fn": lambda args: list_image_sets(), "args": []},
    "get_image_set_summary": {"fn": lambda a: get_image_set_summary(a["set_id"]),
                              "args": ["set_id"]},
    "get_image_analysis": {"fn": lambda a: get_image_analysis(a["image_id"]),
                           "args": ["image_id"]},
    "describe_image_region": {"fn": lambda a: describe_image_region(a["image_id"], a["bbox"]),
                              "args": ["image_id", "bbox"]},
    "get_detections": {"fn": lambda a: get_detections(a["image_id"]), "args": ["image_id"]},
    "get_alignment": {"fn": lambda a: get_alignment(a["image_id"]), "args": ["image_id"]},
    "get_visual_profile": {"fn": lambda a: get_visual_profile(a["set_id"], a["dimension"]),
                           "args": ["set_id", "dimension"]},
    "get_visual_ngrams": {"fn": lambda a: get_visual_ngrams(a["set_id"], a["dimension"],
                                                            int(a.get("n", 2))),
                          "args": ["set_id", "dimension", "n"]},
    "get_visual_collocations": {"fn": lambda a: get_visual_collocations(
        a["set_id"], a["dim_a"], a["dim_b"]), "args": ["set_id", "dim_a", "dim_b"]},
    "get_visual_keyness": {"fn": lambda a: get_visual_keyness(a["set_a"], a["set_b"],
                                                              a["dimension"]),
                           "args": ["set_a", "set_b", "dimension"]},
    "get_visual_dispersion": {"fn": lambda a: get_visual_dispersion(a["set_id"], a["dimension"]),
                              "args": ["set_id", "dimension"]},
    "visual_kwic": {"fn": lambda a: visual_kwic(a["set_id"], a["dimension"], a["category"]),
                    "args": ["set_id", "dimension", "category"]},
    "get_framework_template": {"fn": lambda a: get_framework_template(a["name"]),
                               "args": ["name"]},
    "get_text_corpus_overview": {"fn": lambda a: get_text_corpus_overview(
        a.get("base_url", ""), a["corpus_id"]), "args": ["corpus_id", "base_url"],
        "companion_only": True},
}


def tool_manifest() -> list[dict]:
    """The tool list for /assistant/tools — Companion-only tools appear in
    the surface only when Companion Mode is on (graceful degradation, §5)."""
    settings = get_settings()
    out = []
    for name, spec in TOOLS.items():
        if spec.get("companion_only") and not settings.companion_enabled:
            continue
        out.append({"name": name, "args": spec["args"]})
    return out


def run_tool(name: str, args: dict) -> dict:
    spec = TOOLS.get(name)
    if not spec:
        return _err(f"Unknown tool '{name}'")
    if spec.get("companion_only") and not get_settings().companion_enabled:
        return _err("Tool unavailable: Companion Mode is off.")
    try:
        result = spec["fn"](args)
    except Exception as e:
        result = _err(f"Tool '{name}' failed: {e}")
    from .audit import audit_event

    audit_event("tool_call", tool=name, args=args, grounded=result.get("grounded"))
    return result
