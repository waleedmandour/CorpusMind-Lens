"""Local AI backend management (v0.2) — one intuitive AI story.

The desktop shell owns the Ollama *lifecycle* natively (find → `ollama serve`
→ TCP health) exactly like the parent CorpusMind. These routes give the
PWA/browser shell — and the UI in general — the same power through the
engine, plus the parts the shell should not own:

* ``GET  /ai/local/status``     — which backends are reachable, what models
  are installed (with sizes), machine specs, and recommended defaults.
* ``GET  /ai/catalog``          — curated model list + live HuggingFace GGUF
  search, every entry carrying a fit badge for THIS machine.
* ``POST /ai/local/pull``       — NDJSON progress stream proxying Ollama's
  /api/pull (status/completed/total), so the UI shows real progress bars.
* ``DELETE /ai/local/models``   — remove an installed model.
* ``POST /ai/local/serve``      — find the ollama executable and start
  `ollama serve` (PWA mode; the Tauri shell does this itself at startup).

Nothing here ever sends corpus data anywhere: only the local Ollama HTTP
API is contacted (``trust_env=False``, loopback).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..ai import catalog as C
from ..ai import machine
from ..ai.providers import LMStudioProvider, OllamaProvider, _no_proxy_client
from ..config import get_settings
from ..logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["ai-local"])

OLLAMA_EXE_CANDIDATES = {
    "Windows": [
        r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe",
        r"%LOCALAPPDATA%\Ollama\ollama.exe",
        r"%ProgramFiles%\Ollama\ollama.exe",
    ],
    "Darwin": [
        "/usr/local/bin/ollama",
        "/opt/homebrew/bin/ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
    ],
    "Linux": ["/usr/local/bin/ollama", "/usr/bin/ollama"],
}


def find_ollama_exe() -> str | None:
    exe_name = "ollama.exe" if os.name == "nt" else "ollama"
    found = shutil.which(exe_name)
    if found:
        return found
    for raw in OLLAMA_EXE_CANDIDATES.get(os.name, OLLAMA_EXE_CANDIDATES["Linux"]):
        path = os.path.expandvars(raw)
        if os.path.isfile(path):
            return path
    return None


class _OllamaServe:
    """Detached `ollama serve` (PWA mode). The shell owns its own instance."""

    child: subprocess.Popen | None = None
    lock = asyncio.Lock()


_serve = _OllamaServe()


async def ensure_ollama_serving(timeout: float = 20.0) -> dict:
    """Make sure something answers on 11434; spawn `ollama serve` if needed."""
    ollama = OllamaProvider()
    if await ollama.health():
        return {"action": "already-running", "reachable": True}
    exe = find_ollama_exe()
    if not exe:
        return {"action": "not-installed", "reachable": False,
                "hint": "Install Ollama (https://ollama.com) or use Settings → AI Backend → Install."}
    async with _serve.lock:
        if not await ollama.health():
            log.info("starting_ollama_serve", extra={"exe": exe})
            kwargs: dict = {}
            if os.name == "nt":
                kwargs["creationflags"] = 0x0800_0000  # CREATE_NO_WINDOW
            _serve.child = subprocess.Popen(
                [exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs
            )
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                if await ollama.health():
                    return {"action": "started", "reachable": True}
                await asyncio.sleep(0.5)
            return {"action": "timeout", "reachable": False}
    return {"action": "already-running", "reachable": True}


def _specs() -> dict:
    """Shell-supplied specs (authoritative) with engine probe as fallback."""
    env = os.environ.get("LENS_MACHINE_SPECS_JSON")
    if env:
        try:
            data = json.loads(env)
            if isinstance(data, dict) and data.get("ram_gb") is not None:
                data["source"] = "shell"
                return data
        except Exception:
            pass
    return machine.probe()


@router.get("/ai/local/status")
async def local_status() -> dict:
    ollama = OllamaProvider()
    lmstudio = LMStudioProvider()
    specs = _specs()
    installed: list[dict] = []
    reachable = await ollama.health()
    if reachable:
        try:
            async with _no_proxy_client(timeout=8) as client:
                r = await client.get(f"{ollama.base_url}/api/tags")
                for m in r.json().get("models", []):
                    installed.append({
                        "name": m.get("name", ""),
                        "size_gb": round((m.get("size") or 0) / 1024**3, 2),
                        "task": ("vision" if any(k in m.get("name", "").lower()
                                                 for k in ("vl", "vision", "llava", "moondream"))
                                 else "embedding" if "embed" in m.get("name", "").lower()
                                 else "text"),
                    })
        except Exception:
            pass
    # v0.3.2: surface LM Studio's loaded/catalogued models too, so the
    # Settings default-model pickers can offer EVERY locally installed
    # model, not just the Ollama ones (the picker must never offer a
    # model the user has not actually downloaded).
    lm_reachable = await lmstudio.health()
    lm_models: list[str] = []
    if lm_reachable:
        try:
            lm_models = await lmstudio.list_models()
        except Exception:
            lm_models = []
    return {
        "ollama": {"reachable": reachable, "installed": installed,
                   "exe_found": find_ollama_exe() is not None},
        "lmstudio": {"reachable": lm_reachable, "models": lm_models},
        "machine": specs,
        "recommended": C.recommended(specs),
        "pullable_via": "ollama pull hf.co/<user>/<repo>:<quant> (GGUF) — search in /ai/catalog",
    }


@router.get("/ai/catalog")
async def get_catalog(query: str = "", task: str = "any", limit: int = 12,
                      source: str = "all") -> dict:
    """Curated entries (+ fit badges); `query` adds live HuggingFace results."""
    specs = _specs()
    curated = C.curated(task, specs) if source in ("all", "curated") else []
    hf: list[dict] = []
    if source in ("all", "huggingface") and query.strip():
        hf = C.hf_search(query.strip(), task=task, limit=limit, specs=specs)
    return {
        "curated": curated,
        "huggingface": hf,
        "machine": specs,
        "estimates": "rule-of-thumb",
        "note": "Fit badges are conservative estimates from RAM/VRAM, not benchmarks. "
                "'too-big' models will offload and crawl — pick smaller.",
    }


class PullRequest(BaseModel):
    model: str
    provider: str = "ollama"   # ollama only for now; LM Studio manages models in-app


@router.post("/ai/local/pull")
async def pull_model(body: PullRequest) -> StreamingResponse:
    """Stream Ollama pull progress as NDJSON: {status, completed, total, done, error}."""
    if body.provider != "ollama":
        raise HTTPException(400, "Only Ollama pulls are supported here; LM Studio manages models in its own app.")
    if not find_ollama_exe() and not await OllamaProvider().health():
        raise HTTPException(409, "Ollama is not installed/running — install it first (Settings → AI Backend).")

    async def stream():
        payload = {"model": body.model, "stream": True}
        try:
            async with _no_proxy_client(timeout=None) as client:
                async with client.stream("POST", f"{OllamaProvider().base_url}/api/pull",
                                         json=payload) as r:
                    if r.status_code != 200:
                        detail = (await r.aread()).decode()[:300]
                        yield json.dumps({"done": True, "error": f"ollama /api/pull {r.status_code}: {detail}"}) + "\n"
                        return
                    async for line in r.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            continue
                        out = {"status": chunk.get("status", ""),
                               "completed": chunk.get("completed"),
                               "total": chunk.get("total")}
                        if chunk.get("error"):
                            out["error"] = chunk["error"]
                            out["done"] = True
                        if chunk.get("status") == "success":
                            out["done"] = True
                        yield json.dumps(out) + "\n"
            yield json.dumps({"done": True, "status": "success"}) + "\n"
        except Exception as e:
            yield json.dumps({"done": True, "error": str(e)}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


class DeleteRequest(BaseModel):
    name: str


@router.delete("/ai/local/models")
async def delete_model(body: DeleteRequest) -> dict:
    async with _no_proxy_client(timeout=30) as client:
        r = await client.request("DELETE", f"{OllamaProvider().base_url}/api/delete",
                                 json={"model": body.name})
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"ollama delete failed: {r.text[:200]}")
    return {"deleted": body.name}


@router.post("/ai/local/serve")
async def serve_ollama() -> dict:
    return await ensure_ollama_serving()
