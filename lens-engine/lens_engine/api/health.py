"""Health + engine-identity endpoints (desktop sidecar polls /health)."""
from __future__ import annotations

from fastapi import APIRouter

from .. import __version__, API_VERSION, PRODUCT_NAME
from ..ai.providers import OllamaProvider, LMStudioProvider
from ..config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "product": PRODUCT_NAME,
        "version": __version__,
        "api_version": API_VERSION,
        "facial_analysis": s.facial_analysis,
        "cloud_enabled": s.cloud_enabled,
        "encryption": bool(s.encryption_key),
    }


@router.get("/providers/status")
async def providers_status() -> dict:
    """Which AI backends are reachable right now (used by the UI provider picker)."""
    ollama = OllamaProvider()
    lmstudio = LMStudioProvider()
    return {
        "ollama": {"reachable": await ollama.health(), "models": await ollama.list_models()},
        "lmstudio": {"reachable": await lmstudio.health(), "models": await lmstudio.list_models()},
        "cloud": {"enabled": get_settings().cloud_enabled},
    }
