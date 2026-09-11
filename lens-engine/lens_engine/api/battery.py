"""The corpus-linguistics battery over visual annotations (§9.14) — routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..main import get_store
from ..stats import service

router = APIRouter(tags=["battery"])


def _set_images(set_id: str):
    store = get_store()
    if not store.get_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    return store.list_images(set_id)


@router.get("/imagesets/{set_id}/battery/frequency/{dim}")
async def frequency(set_id: str, dim: str) -> dict:
    return service.frequency_profile(_set_images(set_id), dim)


@router.get("/imagesets/{set_id}/battery/diversity/{dim}")
async def diversity(set_id: str, dim: str) -> dict:
    return service.diversity_battery(_set_images(set_id), dim)


@router.get("/imagesets/{set_id}/battery/ngrams/{dim}")
async def ngrams(set_id: str, dim: str, n: int = 2, min_count: int = 2,
                 include_gaps: bool = True) -> dict:
    if not 1 <= n <= 5:
        raise HTTPException(422, "n must be 1–5")
    return service.ngrams(_set_images(set_id), dim, n=n, min_count=min_count,
                          include_gaps=include_gaps)


@router.get("/imagesets/{set_id}/battery/cooccurrence/{dim_a}/{dim_b}")
async def cooccurrence(set_id: str, dim_a: str, dim_b: str, min_joint: int = 2) -> dict:
    return service.cooccurrence(_set_images(set_id), dim_a, dim_b, min_joint=min_joint)


@router.get("/imagesets/{set_id}/battery/keyness/{dim}")
async def keyness(set_id: str, dim: str, reference_set_id: str) -> dict:
    """Set-vs-set keyness: target = this set, reference = reference_set_id."""
    target = _set_images(set_id)
    ref = _set_images(reference_set_id)
    return service.keyness(target, ref, dim)


@router.get("/imagesets/{set_id}/battery/dispersion/{dim}")
async def dispersion(set_id: str, dim: str, bins: int = 10) -> dict:
    if not 2 <= bins <= 50:
        raise HTTPException(422, "bins must be 2–50")
    return service.dispersion(_set_images(set_id), dim, bins=bins)


@router.get("/imagesets/{set_id}/battery/kwic/{dim}")
async def kwic(set_id: str, dim: str, category: str, context: int = 2) -> dict:
    if not 1 <= context <= 5:
        raise HTTPException(422, "context must be 1–5")
    return service.visual_kwic(_set_images(set_id), dim, category, context=context)


@router.get("/imagesets/{set_id}/battery/full")
async def full_battery(set_id: str, dim: str) -> dict:
    """The complete battery for one dimension in a single call (workbench 'Measures' tab)."""
    images = _set_images(set_id)
    return {
        "dimension": dim,
        "frequency": service.frequency_profile(images, dim),
        "diversity": service.diversity_battery(images, dim),
        "ngrams": service.ngrams(images, dim, n=2, min_count=1),
        "dispersion": service.dispersion(images, dim),
    }
