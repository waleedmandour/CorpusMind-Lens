"""Settings / Ethics / provider routes — runtime state, server-enforced."""
from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import get_settings, reset_settings
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
