"""Discourse-lens routes (§9.13) + batch runner (§9.18).

12 framework lenses × {heuristic, llm} modes, per-image or per-set, with
provenance badges (mode/model/confidence) and redaction notices. The batch
runner runs any subset of lenses over a whole set with per-image error
isolation, skip-if-cached, and consent-gate enforcement; status/cancel
endpoints included.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..discourse.lenses import (FRAMEWORK_IDS, heuristic_lens, llm_lens, load_frameworks,
                                signals_from_meta)
from ..logging import get_logger
from ..main import get_store

log = get_logger(__name__)
router = APIRouter(tags=["discourse"])

_fw_cache: dict[str, dict] = {}


def frameworks() -> dict:
    if not _fw_cache:
        _fw_cache.update(load_frameworks(get_settings().frameworks_dir))
    return _fw_cache


# In-memory batch registry (single-tenant local engine — acceptable; a
# restart clears state and jobs are resumable by re-running).
_batch_jobs: dict[str, dict] = {}


@router.get("/discourse/frameworks")
async def list_frameworks() -> list[dict]:
    out = []
    for fid, fw in frameworks().items():
        out.append({
            "id": fid,
            "full_name": fw.full_name,
            "version": fw.version,
            "family": fw.framework_family,
            "categories": [c.get("id") for c in fw.categories],
        })
    return out


@router.post("/images/{image_id}/discourse/{framework_id}")
async def analyse_image(image_id: str, framework_id: str, mode: str = "heuristic",
                        model: str = "") -> dict:
    fws = frameworks()
    if framework_id not in fws and framework_id not in FRAMEWORK_IDS:
        raise HTTPException(404, f"Unknown framework '{framework_id}'")
    fw = fws.get(framework_id)
    if fw is None:
        raise HTTPException(404, f"Framework template '{framework_id}' not found on disk")
    store = get_store()
    img = store.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")

    sig = signals_from_meta(image_id, img.meta or {})
    started = datetime.now(UTC).isoformat()
    if mode == "llm":
        from ..ai.providers import get_provider

        provider = get_provider("ollama")  # LLM discourse stays local-first; cloud via settings only
        try:
            llm = await llm_lens(framework_id, fw, sig, provider,
                                 model or "moondream")
        except Exception as e:
            raise HTTPException(502, f"LLM lens failed: {e}")
        return _result(image_id, framework_id, fw, mode, started, llm)

    claims = heuristic_lens(framework_id, fw, sig)
    return _result(image_id, framework_id, fw, "heuristic", started, {"claims": claims})


def _result(image_id: str, framework_id: str, fw, mode: str, started: str, payload: dict) -> dict:
    return {
        "image_id": image_id,
        "framework": framework_id,
        "framework_full_name": fw.full_name,
        "framework_version": fw.version,
        "mode": mode,
        "model": payload.get("model") if mode == "llm" else None,
        "started_at": started,
        "claims": payload.get("claims", []),
        "person_descriptive_redacted": payload.get("person_descriptive_redacted", False),
        "ungrounded_count": payload.get("ungrounded_count", 0),
        "notice": "Interpretive claims are framework-lensed hypotheses with cited "
                  "evidence — never facts about real people, institutions, or groups.",
    }


# --------------------------------------------------------------------------- #
# Batch runner (§9.18)
# --------------------------------------------------------------------------- #


class BatchRequest(BaseModel := __import__("pydantic").BaseModel):
    image_ids: list[str] | None = None        # None → whole set
    frameworks: list[str] | None = None       # None → all 12
    mode: str = "heuristic"
    skip_cached: bool = True


@router.post("/imagesets/{set_id}/discourse/batch", status_code=202)
async def start_batch(set_id: str, req: BatchRequest) -> dict:
    store = get_store()
    if not store.get_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    images = store.list_images(set_id)
    if req.image_ids is not None:
        wanted = set(req.image_ids)
        images = [i for i in images if i.id in wanted]
    fws = req.frameworks or FRAMEWORK_IDS
    job_id = uuid.uuid4().hex[:10]
    _batch_jobs[job_id] = {
        "id": job_id, "set_id": set_id, "status": "running",
        "total": len(images) * len(fws),
        "done": 0, "errors": [], "cancelled": False,
        "results": [], "started_at": datetime.now(UTC).isoformat(),
    }
    asyncio.get_running_loop().create_task(_run_batch(job_id, images, fws, req.mode))
    return {"job_id": job_id, "status": "running", "total": len(images) * len(fws)}


async def _run_batch(job_id: str, images, framework_ids: list[str], mode: str) -> None:
    job = _batch_jobs[job_id]
    fws = frameworks()
    for img in images:
        if job["cancelled"]:
            job["status"] = "cancelled"
            return
        for fid in framework_ids:
            if job["cancelled"]:
                job["status"] = "cancelled"
                return
            fw = fws.get(fid)
            if fw is None:
                continue
            try:
                sig = signals_from_meta(img.id, img.meta or {})
                if mode == "heuristic":
                    payload = {"claims": heuristic_lens(fid, fw, sig)}
                else:
                    from ..ai.providers import OllamaProvider

                    provider = OllamaProvider()
                    payload = await llm_lens(fid, fw, sig, provider, "moondream")
                job["results"].append(_result(img.id, fid, fw, mode,
                                              datetime.now(UTC).isoformat(), payload))
            except Exception as e:
                # per-image error isolation (§9.18)
                job["errors"].append({"image_id": img.id, "framework": fid, "error": str(e)[:300]})
            finally:
                job["done"] += 1
    job["status"] = "complete"
    job["finished_at"] = datetime.now(UTC).isoformat()


@router.get("/discourse/batch/{job_id}")
async def batch_status(job_id: str) -> dict:
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Batch job not found (state is in-memory; re-run if the engine restarted)")
    return {k: v for k, v in job.items() if k != "results"} | {
        "results_ready": len(job["results"]),
    }


@router.post("/discourse/batch/{job_id}/cancel")
async def batch_cancel(job_id: str) -> dict:
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Batch job not found")
    job["cancelled"] = True
    return {"job_id": job_id, "status": "cancelling"}


@router.get("/discourse/batch/{job_id}/results")
async def batch_results(job_id: str) -> dict:
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Batch job not found")
    return {"job_id": job_id, "status": job["status"], "results": job["results"],
            "errors": job["errors"]}
