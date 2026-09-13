"""Health + engine-identity endpoints (desktop sidecar polls /health)."""
from __future__ import annotations

import importlib.util

from fastapi import APIRouter

from .. import __version__, API_VERSION, PRODUCT_NAME
from ..ai.providers import OllamaProvider, LMStudioProvider
from ..config import get_settings

router = APIRouter(tags=["health"])


def _module_available(module: str) -> bool:
    """Cheap importability probe (does not execute the module body)."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def optional_stacks() -> dict:
    """Availability of the heavyweight optional AI stacks.

    The packaged (PyInstaller) installers historically shipped WITHOUT
    torch/transformers, which silently degraded object detection and CLIP
    scene/alignment analysis to heuristics with "no visible way back"
    (v0.2.0 finding). /health now reports every optional stack honestly so
    the Settings screen can show what this installation can and cannot do,
    and what enables it.
    """
    torch = _module_available("torch")
    transformers = _module_available("transformers")
    sentence_transformers = _module_available("sentence_transformers")
    vision_stack = torch and transformers
    return {
        "vision_models": {
            "available": vision_stack,
            "packages": {"torch": torch, "transformers": transformers},
            "enables": "Open-vocabulary object detection and CLIP scene analysis",
            "enable_hint": "install the engine with the [models] extra: pip install 'lens-engine[models]'",
        },
        "alignment_embeddings": {
            "available": sentence_transformers,
            "packages": {"sentence_transformers": sentence_transformers},
            "enables": "CLIP-style image-text alignment scoring (text-side semantics also run over Ollama embeddings)",
            "enable_hint": "pip install 'lens-engine[models]'",
        },
        "tesseract_ocr": {
            "available": _module_available("pytesseract"),
            "packages": {"pytesseract": _module_available("pytesseract")},
            "enables": "Tesseract word-box OCR (vision-model OCR via Ollama still works without it)",
            "enable_hint": "pip install 'lens-engine[ocr]' plus the tesseract binary",
        },
    }


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
        "capabilities": optional_stacks(),
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
