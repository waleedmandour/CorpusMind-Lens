"""Default AI model resolution (v0.3 default-model picker).

Order of authority for every pluggable model slot:

1. Explicit per-call argument (the caller passes ``model=...``)
2. DB override   — ``app_settings["models"]``, set from
   Settings, AI backend & models (PUT /settings/models)
3. Environment   — LENS_VISION_OCR_MODEL / LENS_EMBED_MODEL (v0.2 behaviour)
4. Built-in defaults — qwen2.5vl:3b (vision OCR), bge-m3 (embeddings),
   llama3.1 (assistant chat)

The DB override makes the picker visible in the UI and persistent across
restarts without env-var surgery; the env vars keep working for Docker and
headless setups (documented in the settings route response).
"""
from __future__ import annotations

from .config import get_settings
from .logging import get_logger

log = get_logger(__name__)

_MODELS_KEY = "models"
_KINDS = ("vision_ocr", "embed", "chat")
_ENV_FIELDS = {
    "vision_ocr": "vision_ocr_model",
    "embed": "default_embedding_model",
}
_DEFAULTS = {
    "vision_ocr": "qwen2.5vl:3b",
    "embed": "bge-m3",
    "chat": "llama3.1",
}


def _overrides() -> dict:
    try:
        from .main import get_store

        value = get_store().get_setting(_MODELS_KEY)
        return value if isinstance(value, dict) else {}
    except Exception:  # store unavailable (early startup) → env defaults
        return {}


def effective_model(kind: str) -> str:
    """Resolve one model slot. Unknown kinds fall back to 'chat'."""
    if kind not in _KINDS:
        kind = "chat"
    override = _overrides().get(kind)
    if isinstance(override, str) and override.strip():
        return override.strip()
    if kind in _ENV_FIELDS:
        return getattr(get_settings(), _ENV_FIELDS[kind])
    return _DEFAULTS[kind]


def model_settings_snapshot() -> dict:
    """Full state for the Settings card: effective values + where they came from."""
    overrides = _overrides()
    out: dict = {"overrides": {}, "env_defaults": {}, "defaults": _DEFAULTS}
    for kind in _KINDS:
        eff = effective_model(kind)
        out[kind + "_model"] = eff
        if isinstance(overrides.get(kind), str) and overrides[kind].strip():
            out["overrides"][kind] = overrides[kind]
        if kind in _ENV_FIELDS:
            out["env_defaults"][kind] = getattr(get_settings(), _ENV_FIELDS[kind])
        else:
            out["env_defaults"][kind] = _DEFAULTS[kind]
    return out


def set_model_overrides(updates: dict, clear: list[str] | None = None) -> None:
    """Persist overrides atomically (merged into the existing mapping)."""
    from .main import get_store

    merged = {k: v for k, v in _overrides().items() if k in _KINDS}
    for kind, value in (updates or {}).items():
        if kind not in _KINDS:
            continue
        if isinstance(value, str) and value.strip():
            merged[kind] = value.strip()
    for kind in clear or []:
        merged.pop(kind, None)
    get_store().set_setting(_MODELS_KEY, merged)
