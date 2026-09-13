"""Settings / Ethics / provider routes — runtime state, server-enforced."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import __version__
from ..config import get_settings, reset_settings
from ..models_defaults import model_settings_snapshot, set_model_overrides
from ..storage.encryption import key_fingerprint
from ..vision.facial import ETHICS_NOTICE

router = APIRouter(tags=["settings"])


@router.get("/settings")
async def get_settings_route() -> dict:
    s = get_settings()
    return {
        "version": __version__,
        "facial_analysis": s.facial_analysis,
        "facial_analysis_notice": ETHICS_NOTICE,
        "cloud_enabled": s.cloud_enabled,
        "encryption": bool(s.encryption_key),
        "encryption_fingerprint": key_fingerprint(s.encryption_key),
        "companion_enabled": s.companion_enabled,
        "companion_base_url": s.companion_base_url,
        "default_ocr_language": s.default_ocr_language,
        "max_file_mb": s.max_file_mb,
        "max_batch_images": s.max_batch_images,
        "note": "Sensitive switches are environment-backed (LENS_*); the API reports "
                "state but the server enforces the gates regardless of UI input.",
    }


@router.get("/settings/ethics")
async def ethics() -> dict:
    s = get_settings()
    return {
        "facial_analysis": s.facial_analysis,
        "gps_extraction": {"supported": False,
                           "reason": "GPS is never extracted — no setting overrides this (§4 P8)."},
        "identity_recognition": {"supported": False,
                                 "reason": "Never performs identity recognition or re-identification."},
        "interpretive_claims": "Always framework-attributed hypotheses with cited evidence.",
        "notice": ETHICS_NOTICE,
    }


# -- v0.3 default-model picker (DB-backed overrides, env vars still win) ---

class ModelDefaultsPayload(BaseModel):
    vision_ocr_model: str | None = None
    embed_model: str | None = None
    chat_model: str | None = None
    clear: list[str] = []


@router.get("/settings/models")
async def get_model_defaults() -> dict:
    snap = model_settings_snapshot()
    snap["note"] = ("Effective default models for vision OCR, semantic-search "
                    "embeddings and the Assistant. Env vars "
                    "(LENS_VISION_OCR_MODEL / LENS_EMBED_MODEL) apply when no "
                    "UI override is stored; per-request model arguments always win.")
    return snap


@router.put("/settings/models")
async def put_model_defaults(payload: ModelDefaultsPayload) -> dict:
    updates = {k: v for k, v in {
        "vision_ocr": payload.vision_ocr_model,
        "embed": payload.embed_model,
        "chat": payload.chat_model,
    }.items() if v is not None}
    set_model_overrides(updates, clear=payload.clear)
    snap = model_settings_snapshot()
    snap["saved"] = True
    return snap
