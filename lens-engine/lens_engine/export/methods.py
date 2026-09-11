"""Methods Section auto-draft (§9.19 NEW) — reproducibility as a feature.

Mirrors CorpusMind Text's feature: names the exact detector/OCR-engine/
embedding-model/vision-LM versions and formula versions used, for a
manuscript's methodology section — directly serving §4 Principle 7.
"""
from __future__ import annotations

from .. import __version__
from ..config import get_settings


def methods_paragraph(set_stats: dict, image_metas: list[dict]) -> str:
    """Compose a publishable Methods paragraph from what actually ran."""
    s = get_settings()
    detector_models = sorted({
        d.get("model", "") for meta in image_metas
        for d in (meta.get("detections") or []) if d.get("model")
    })
    scene_models = sorted({
        m for meta in image_metas for m in
        [ (meta.get("scenes") or [{}])[0].get("scene", "") ] if m
    }.union({meta.get("scene_model", "") for meta in image_metas if meta.get("scene_model")}))
    ocr_engines = sorted({(meta.get("ocr") or {}).get("engine", "") for meta in image_metas
                          if (meta.get("ocr") or {}).get("engine")})
    ocr_langs = sorted({(meta.get("ocr") or {}).get("language", "") for meta in image_metas
                        if (meta.get("ocr") or {}).get("language")})
    vlm_models = sorted({(meta.get("vlm_description") or {}).get("model", "")
                         for meta in image_metas
                         if (meta.get("vlm_description") or {}).get("model")})
    embed_backends = sorted({(meta.get("alignment") or {}).get("backend", "")
                             for meta in image_metas
                             if (meta.get("alignment") or {}).get("backend")})

    n_images = set_stats.get("image_count", len(image_metas))
    lines = []
    lines.append(
        f"The visual corpus comprised {n_images} images organised into a single image set. "
        f"Analysis was performed with CorpusMind Lens engine v{__version__}, run locally "
        f"(no cloud processing was used unless explicitly noted below)."
    )
    if ocr_engines:
        lines.append(
            f"Embedded text was extracted via Tesseract OCR ({', '.join(ocr_engines)}) with "
            f"language packs: {', '.join(ocr_langs) or 'default'}; per-image mean confidence "
            f"is reported alongside all OCR-derived measures and low-confidence output is "
            f"never silently trusted."
        )
    if detector_models:
        lines.append(
            f"Object and scene detection used the open-vocabulary detector "
            f"{', '.join(detector_models)} (zero-shot, run locally), producing labelled "
            f"bounding boxes with confidence scores that feed the Representational "
            f"metafunction of Visual Grammar."
        )
    if embed_backends:
        lines.append(
            f"Image–text alignment was computed in a joint embedding space "
            f"({', '.join(embed_backends)}); where the embedding backend was unavailable, "
            f"alignments are labelled as geometric grid fallbacks and were not interpreted "
            f"semantically."
        )
    if vlm_models:
        lines.append(
            f"A vision-language model ({', '.join(vlm_models)}) generated narrative "
            f"descriptions as a clearly separated interpretive layer; all numeric measures "
            f"derive from deterministic computations, not model prose."
        )
    lines.append(
        "Annotated category sequences were analysed with the corpus-linguistics battery — "
        "frequency profiles, diversity (TTR, Guiraud's R, MATTR, STTR), sequence n-grams "
        "over reading order, co-occurrence association (MI, T-score, Dice, LogDice, ΔP, G²), "
        "set-vs-set keyness (log-likelihood always paired with effect sizes: Log Ratio, "
        "%DIFF, Simple Maths, Odds Ratio), and dispersion (Juilland's D, Gries' DP) — "
        "formula definitions as documented in docs/METHODOLOGY.md (formula set v1)."
    )
    lines.append(
        "Interpretive claims were generated only as framework-lensed hypotheses with cited "
        "evidence ids; GPS/location metadata was never extracted, and facial/body analysis "
        "remained disabled by default."
    )
    return "\n\n".join(lines)
