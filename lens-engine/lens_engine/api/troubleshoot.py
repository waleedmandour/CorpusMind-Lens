"""Smart Troubleshooting for Lens — local-model error interpretation.

The parent CorpusMind sends backend errors to Gemini for interpretation;
Lens adapts the same UX to its local-first ethics (borrow review verdict:
"ADAPT: local model"). A researcher never has to paste an error into a
cloud chatbot to understand it: the engine asks the *installed local model*
(Ollama or LM Studio) to explain the failure in plain language.

Endpoints:

* ``GET  /troubleshoot/status``    — is a local interpretation backend reachable?
* ``POST /troubleshoot/interpret`` — interpret one error, returning
  ``{available, severity, plain_language, likely_cause, suggested_fix,
  should_report, model}``.

Honest degradation: when no local model is reachable the response says so
(``available: false``) and the UI falls back to the offline rules table.
Error text is diagnostic, not corpus data, but it still never leaves the
machine — there is no cloud path here at all.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..ai.providers import LMStudioProvider, Message, ModelProviderError, OllamaProvider
from ..logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["troubleshoot"])

SYSTEM_INSTRUCTION = """You are CorpusMind Lens's Smart Troubleshooting assistant.

CorpusMind Lens is a local-first, offline research tool for multimodal corpus
linguistics. It has three parts:
  1. A Python FastAPI engine (lens-engine) on 127.0.0.1 (port 8765 or nearby)
  2. A React frontend
  3. A Tauri 2 desktop shell that supervises the engine as a sidecar

The user is a linguistics researcher, NOT a developer. Interpret the backend
error below in plain language and suggest actionable fixes.

Output EXACTLY this JSON shape (no markdown fences, no prose):
{
  "severity": "info" | "warning" | "error",
  "plain_language": "<1-2 sentence explanation a non-developer understands>",
  "likely_cause": "<1 sentence on the most probable cause>",
  "suggested_fix": "<1-3 concrete steps the user can take right now>",
  "should_report": <true if this looks like a real bug, false if it is config/environment>
}

Common Lens causes to recognize:
- Engine starting up (first launch can take up to a minute) → wait and retry
- Ollama not running (11434) → Settings, AI backend & models, Start Ollama
- Missing model (ollama pull) → Settings, AI backend & models, model catalog
- Image upload 400/413 → wrong format or too large; re-export as PNG/JPEG
- Tesseract absent → use a vision-model OCR re-run from the image panel
- 500 Internal Server Error → likely a real bug; set should_report=true

Keep plain_language and suggested_fix SHORT and ACTIONABLE."""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class InterpretRequest(BaseModel):
    error_message: str = Field(..., max_length=4000)
    error_code: str | int | None = None
    endpoint: str | None = None
    context: str | None = None
    stack_trace: str | None = Field(None, max_length=8000)


def _parse_verdict(content: str) -> dict | None:
    """Best-effort JSON extraction from a small local model's answer."""
    match = _JSON_RE.search(content or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "plain_language" not in data:
        return None
    sev = str(data.get("severity", "info")).lower()
    return {
        "severity": sev if sev in ("info", "warning", "error") else "info",
        "plain_language": str(data.get("plain_language", ""))[:1200],
        "likely_cause": str(data.get("likely_cause", ""))[:600],
        "suggested_fix": str(data.get("suggested_fix", ""))[:900],
        "should_report": bool(data.get("should_report", False)),
    }


@router.get("/troubleshoot/status")
async def status() -> dict:
    ollama = OllamaProvider()
    lmstudio = LMStudioProvider()
    try:
        ollama_ok = await ollama.health()
    except Exception:
        ollama_ok = False
    try:
        lm_ok = await lmstudio.health()
    except Exception:
        lm_ok = False
    models: list[str] = []
    backend = None
    if ollama_ok:
        try:
            models = await ollama.list_models()
            backend = "ollama"
        except Exception:
            models = []
    if not backend and lm_ok:
        try:
            models = await lmstudio.list_models()
            backend = "lmstudio"
        except Exception:
            models = []
    return {"available": backend is not None and bool(models),
            "backend": backend, "models": models[:20]}


@router.post("/troubleshoot/interpret")
async def interpret(body: InterpretRequest) -> dict:
    unavailable = {
        "available": False,
        "severity": "info",
        "plain_language": "No local AI backend is reachable, so automatic "
                          "interpretation is unavailable. The offline suggestion "
                          "below still applies.",
        "likely_cause": "Ollama or LM Studio is not running, or no text model "
                        "is installed yet.",
        "suggested_fix": "Open Settings, AI backend & models, start Ollama (or "
                         "LM Studio) and pull a small text model such as "
                         "llama3.2:3b; then press Explain again.",
        "should_report": False,
        "model": "",
    }

    ollama = OllamaProvider()
    lmstudio = LMStudioProvider()
    provider = None
    model = ""
    try:
        if await ollama.health():
            models = await ollama.list_models()
            text_models = [m for m in models
                           if not any(k in m.lower() for k in ("embed", "vl", "vision", "llava"))]
            if text_models:
                provider, model = ollama, text_models[0]
        if provider is None and await lmstudio.health():
            models = await lmstudio.list_models()
            if models:
                provider, model = lmstudio, models[0]
    except ModelProviderError:
        return unavailable
    except Exception as e:  # provider probing must never 500
        log.warning("troubleshoot_probe_failed", extra={"error": str(e)})
        return unavailable

    if provider is None:
        return unavailable

    prompt_lines = [
        f"Error message: {body.error_message}",
        f"HTTP/status code: {body.error_code if body.error_code is not None else 'N/A'}",
        f"Endpoint: {body.endpoint or 'N/A'}",
        f"User context: {body.context or 'N/A'}",
    ]
    if body.stack_trace:
        prompt_lines.append("Stack trace (truncated):")
        prompt_lines.append(body.stack_trace[:2000])

    try:
        response = await provider.chat(
            [Message(role="system", content=SYSTEM_INSTRUCTION),
             Message(role="user", content="\n".join(prompt_lines))],
            model=model,
            temperature=0.1,
        )
    except Exception as e:
        log.warning("troubleshoot_chat_failed", extra={"error": str(e)})
        return unavailable

    verdict = _parse_verdict(response.content)
    if verdict is None:
        return {**unavailable,
                "plain_language": "The local model answered but could not be "
                                  "parsed into a structured verdict.",
                "model": model}
    return {"available": True, **verdict, "model": model}
