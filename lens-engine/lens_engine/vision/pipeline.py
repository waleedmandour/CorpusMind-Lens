"""The full per-image analysis pipeline (§9.2–9.4, 9.7).

Orchestrates, for one image: metadata extraction (GPS excluded by design),
OCR (with per-word boxes), colour analysis, geometric composition analysis —
writing everything into ``Image.meta``. Detection (§9.5), embeddings (§9.11)
and typography (§9.8) are separate opt-in-lazy subsystems that piggyback on
the same meta column via their own endpoints.

All steps are deterministic and re-runnable; each result block records the
engine/version that produced it (reproducibility principle §4-6).
"""
from __future__ import annotations

from ..logging import get_logger
from ..storage.models import Image
from . import colours as colours_mod
from . import ingest, meta as meta_mod, ocr as ocr_mod

log = get_logger(__name__)

ENGINE_VERSION = "lens-engine 0.1.0"


async def analyse_image_full(img: Image, *, ocr_language: str | None = None,
                             set_language: str | None = None) -> dict:
    """Run the full deterministic pipeline for one stored image.

    Runs in the background worker (never on the request thread — §13). The
    language override is applied at re-analysis time; set-level language
    resolution follows §9.4 (an Arabic-tagged set OCRs with ara+eng).
    """
    import asyncio

    from ..config import get_settings

    raw = await asyncio.to_thread(
        ingest.read_image_bytes, img.storage_path, get_settings().encryption_key
    )
    meta = dict(img.meta or {})
    meta.setdefault("user", {})
    meta["exif_xmp"] = meta_mod.extract_metadata(raw)

    lang = ocr_mod.resolve_language(ocr_language, set_language)
    ocr = await asyncio.to_thread(ocr_mod.run_ocr, raw, language=lang)
    meta["ocr"] = ocr.to_dict()

    pil = ingest.load_image(raw)
    ca = await asyncio.to_thread(colours_mod.analyse_colours, pil)
    comp = await asyncio.to_thread(colours_mod.analyse_composition, pil)
    meta["colour"] = {
        "dominant_colours": ca.dominant_colours,
        "warm_cold_balance": ca.warm_cold_balance,
        "brightness": ca.brightness,
        "contrast": ca.contrast,
        "saturation": ca.saturation,
        "colour_symbolism_notes": ca.colour_symbolism_notes,
        "engine": ENGINE_VERSION,
    }
    meta["composition"] = {
        "information_value": comp.information_value,
        "rule_of_thirds_intersections": comp.rule_of_thirds_intersections,
        "salience_centre": list(comp.salience_centre),
        "visual_balance": comp.visual_balance,
        "framing_balance": comp.framing_balance,
        "golden_ratio_offset": comp.golden_ratio_offset,
        "vectors": comp.vectors,
        "engine": ENGINE_VERSION,
    }

    meta.setdefault("annotations", {})   # §9.9 schema lands empty; filled by the annotation API
    meta.setdefault("tags", [])
    meta.setdefault("detections", [])    # §9.5 — populated by the detection endpoints
    meta.setdefault("typography", {})    # §9.8 — populated by the typography endpoint
    meta.setdefault("vlm_description", {})  # §10 — populated by the describe endpoint

    info = ingest.get_image_info(raw, img.filename)
    log.info("image_analysed", extra={
        "image": img.id, "size": f"{info.width}x{info.height}",
        "ocr_engine": ocr.engine, "ocr_words": ocr.word_count,
    })
    return {
        "width": info.width,
        "height": info.height,
        "format": info.format,
        "size_bytes": info.size_bytes,
        "meta": meta,
    }
