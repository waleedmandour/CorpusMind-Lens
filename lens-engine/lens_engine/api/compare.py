"""Bilingual / comparative sets (§9.17): generic set-vs-set comparison across
every applicable §9.14 metric — the 'compare A vs B' workflow (before/after,
campaign A/B, country A/B, publication A/B), not per-category bespoke code."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..main import get_store
from ..stats import service
from ..vision.annotations import DIMENSION_IDS

router = APIRouter(tags=["compare"])


@router.get("/compare/{set_a}/{set_b}")
async def compare_sets(set_a: str, set_b: str, dims: str | None = None) -> dict:
    store = get_store()
    sa, sb = store.get_image_set(set_a), store.get_image_set(set_b)
    if not sa or not sb:
        raise HTTPException(404, "One or both image sets not found")
    images_a, images_b = store.list_images(set_a), store.list_images(set_b)
    dimensions = [d.strip() for d in dims.split(",")] if dims else list(DIMENSION_IDS)
    dimensions = [d for d in dimensions if d in DIMENSION_IDS]

    per_dim = {}
    for dim in dimensions:
        per_dim[dim] = {
            "frequency_a": service.frequency_profile(images_a, dim),
            "frequency_b": service.frequency_profile(images_b, dim),
            "diversity_a": service.diversity_battery(images_a, dim),
            "diversity_b": service.diversity_battery(images_b, dim),
            "keyness_a_vs_b": service.keyness(images_a, images_b, dim),
            "dispersion_a": service.dispersion(images_a, dim),
            "dispersion_b": service.dispersion(images_b, dim),
        }
    return {
        "set_a": {"id": set_a, "name": sa.name, "images": len(images_a)},
        "set_b": {"id": set_b, "name": sb.name, "images": len(images_b)},
        "dimensions": per_dim,
        "note": "Generic comparison: every metric is the standard §9.14 battery "
                "computed per set plus the keyness battery between them.",
    }
