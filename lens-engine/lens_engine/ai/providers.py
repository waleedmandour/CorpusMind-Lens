"""ModelProvider abstraction — ported, product-agnostic infrastructure.

Three concrete implementations share one interface:

  - OllamaProvider    → http://127.0.0.1:11434  (native /api/chat + /api/tags)
  - LMStudioProvider  → http://127.0.0.1:1234/v1 (OpenAI-compatible)
  - CloudProvider     → user-supplied API key, opt-in, OFF by default

The port keeps the parent's proven wire-level decisions:

* Ollama uses the NATIVE ``/api/chat`` endpoint (cleaner message structure,
  reliable system prompts with small models, vision ``images`` field).
* LM Studio and Cloud use the OpenAI-compatible ``/v1`` schema.
* All providers bypass proxies for loopback traffic (``trust_env=False``)
  so corporate VPNs cannot silently intercept localhost requests.
* Vision messages carry raw image bytes; each provider translates them to
  its wire format (Ollama ``images`` field / OpenAI ``image_url`` parts).
* ``embed()`` exposes joint text/image embeddings for the §9.11 alignment
  upgrade. Local text embedding via Ollama ``/api/embed``; image embedding
  is served by the dedicated multimodal embedding backend (see
  ``multimodal/embeddings.py``) because neither chat API returns image
  vectors — the provider surface still exposes it for uniformity.
"""
from __future__ import annotations

import abc
import base64
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from ..config import get_settings
from ..logging import get_logger

log = get_logger(__name__)

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str
    name: str | None = None
    # Vision extension: raw PNG/JPEG bytes attached to this message.
    images: tuple[bytes, ...] = ()


@dataclass(frozen=True, slots=True)
class ChatResponse:
    content: str
    model: str
    provider: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    vector: list[float]
    model: str
    provider: str


class ModelProviderError(RuntimeError):
    """Base error for any provider failure (network, auth, model-missing, ...)."""


class CloudDisabledError(ModelProviderError):
    """Raised when cloud is hard-disabled in settings (§13.2 belt-and-suspenders)."""


class ModelProvider(abc.ABC):
    """All providers implement chat(), stream(), and embed()."""

    name: str

    @abc.abstractmethod
    async def chat(self, messages: list[Message], *, model: str, temperature: float = 0.2,
                   tools: list[dict] | None = None) -> ChatResponse: ...

    @abc.abstractmethod
    async def stream(self, messages: list[Message], *, model: str,
                     temperature: float = 0.2) -> AsyncIterator[str]: ...

    @abc.abstractmethod
    async def embed(self, text: str, *, model: str) -> EmbeddingResponse: ...

    @abc.abstractmethod
    async def list_models(self) -> list[str]: ...

    @abc.abstractmethod
    async def health(self) -> bool: ...


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _no_proxy_client(timeout: float = 120.0) -> httpx.AsyncClient:
    """Loopback traffic must never traverse a proxy (corporate VPN safety)."""
    return httpx.AsyncClient(timeout=timeout, trust_env=False)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


# --------------------------------------------------------------------------- #
# Ollama (native /api/chat)
# --------------------------------------------------------------------------- #


class OllamaProvider(ModelProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def _wire_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            entry: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.images:
                entry["images"] = [_b64(i) for i in m.images]
            out.append(entry)
        return out

    async def chat(self, messages: list[Message], *, model: str, temperature: float = 0.2,
                   tools: list[dict] | None = None) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._wire_messages(messages),
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools
        async with _no_proxy_client() as client:
            r = await client.post(f"{self.base_url}/api/chat", json=payload)
            if r.status_code != 200:
                raise ModelProviderError(f"ollama /api/chat {r.status_code}")
            data = r.json()
        msg = data.get("message", {})
        return ChatResponse(
            content=msg.get("content", ""),
            model=data.get("model", model),
            provider=self.name,
            raw={"tool_calls": msg.get("tool_calls") or []},
        )

    async def stream(self, messages: list[Message], *, model: str,
                     temperature: float = 0.2) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": self._wire_messages(messages),
            "stream": True,
            "options": {"temperature": temperature},
        }
        async with _no_proxy_client() as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    raise ModelProviderError(f"ollama stream {r.status_code}")
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = httpx.Response(200, content=line).json()
                    except Exception:
                        continue
                    piece = (chunk.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break

    async def embed(self, text: str, *, model: str) -> EmbeddingResponse:
        async with _no_proxy_client() as client:
            r = await client.post(f"{self.base_url}/api/embed", json={"model": model, "input": text})
            if r.status_code != 200:
                raise ModelProviderError(f"ollama /api/embed {r.status_code}")
            data = r.json()
        return EmbeddingResponse(
            vector=data["embeddings"][0], model=model, provider=self.name
        )

    async def list_models(self) -> list[str]:
        try:
            async with _no_proxy_client(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                if r.status_code != 200:
                    return []
                return [m.get("name", "") for m in r.json().get("models", [])]
        except Exception:
            return []

    async def health(self) -> bool:
        try:
            async with _no_proxy_client(timeout=3) as client:
                return (await client.get(f"{self.base_url}/api/tags")).status_code == 200
        except Exception:
            return False


# --------------------------------------------------------------------------- #
# OpenAI-compatible (LM Studio / any /v1 server, including cloud)
# --------------------------------------------------------------------------- #


class _OpenAICompatibleProvider(ModelProvider):
    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str | None = None, provider_name: str | None = None,
                 timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = provider_name or self.name
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _wire_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.images:
                parts: list[dict[str, Any]] = [{"type": "text", "text": m.content}]
                for img in m.images:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_b64(img)}"},
                    })
                out.append({"role": m.role, "content": parts})
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    async def chat(self, messages: list[Message], *, model: str, temperature: float = 0.2,
                   tools: list[dict] | None = None) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._wire_messages(messages),
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        async with _no_proxy_client(self.timeout) as client:
            r = await client.post(f"{self.base_url}/chat/completions", json=payload,
                                  headers=self._headers())
            if r.status_code != 200:
                raise ModelProviderError(f"{self.name} /chat/completions {r.status_code}")
            data = r.json()
        choice = (data.get("choices") or [{}])[0]
        return ChatResponse(
            content=(choice.get("message") or {}).get("content", ""),
            model=data.get("model", model),
            provider=self.name,
            raw={"tool_calls": (choice.get("message") or {}).get("tool_calls") or []},
        )

    async def stream(self, messages: list[Message], *, model: str,
                     temperature: float = 0.2) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": self._wire_messages(messages),
            "temperature": temperature,
            "stream": True,
        }
        async with _no_proxy_client(self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload,
                                     headers=self._headers()) as r:
                if r.status_code != 200:
                    raise ModelProviderError(f"{self.name} stream {r.status_code}")
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    body = line[5:].strip()
                    if body == "[DONE]":
                        break
                    try:
                        chunk = httpx.Response(200, content=body).json()
                    except Exception:
                        continue
                    delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta

    async def embed(self, text: str, *, model: str) -> EmbeddingResponse:
        async with _no_proxy_client(self.timeout) as client:
            r = await client.post(f"{self.base_url}/embeddings", json={"model": model, "input": text},
                                  headers=self._headers())
            if r.status_code != 200:
                raise ModelProviderError(f"{self.name} /embeddings {r.status_code}")
            data = r.json()
        return EmbeddingResponse(
            vector=data["data"][0]["embedding"], model=model, provider=self.name
        )

    async def list_models(self) -> list[str]:
        try:
            async with _no_proxy_client(timeout=5) as client:
                r = await client.get(f"{self.base_url}/models", headers=self._headers())
                if r.status_code != 200:
                    return []
                return [m.get("id", "") for m in r.json().get("data", [])]
        except Exception:
            return []

    async def health(self) -> bool:
        return bool(await self.list_models())


class LMStudioProvider(_OpenAICompatibleProvider):
    name = "lmstudio"

    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1") -> None:
        super().__init__(base_url, provider_name="lmstudio")


class CloudProvider(_OpenAICompatibleProvider):
    """Opt-in cloud AI (§4 Principle 1). Construction is refused unless the
    user explicitly enabled cloud in settings — belt-and-suspenders on top of
    the UI gate, matching the parent's §13.2 defence."""

    name = "cloud"

    def __init__(self, base_url: str, api_key: str) -> None:
        settings = get_settings()
        if not settings.cloud_enabled:
            raise CloudDisabledError(
                "Cloud AI is disabled. Enable it explicitly in Settings → AI Providers "
                "(LENS_CLOUD_ENABLED=1) — Lens is local-first by default."
            )
        super().__init__(base_url, api_key=api_key, provider_name="cloud")


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def get_provider(provider_id: str = "ollama", **kwargs: Any) -> ModelProvider:
    """Factory used by the AI layer. ``provider_id`` ∈ {ollama, lmstudio, cloud}."""
    if provider_id == "ollama":
        return OllamaProvider(base_url=kwargs.get("base_url", "http://127.0.0.1:11434"))
    if provider_id == "lmstudio":
        return LMStudioProvider(base_url=kwargs.get("base_url", "http://127.0.0.1:1234/v1"))
    if provider_id == "cloud":
        return CloudProvider(
            base_url=kwargs.get("base_url", "https://api.openai.com/v1"),
            api_key=kwargs.get("api_key", ""),
        )
    raise ModelProviderError(f"Unknown provider: {provider_id}")
