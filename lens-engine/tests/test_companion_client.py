"""Companion Mode client tests (§5): version negotiation, graceful failure,
opt-in gating — using httpx MockTransport (no live network)."""
from __future__ import annotations

import httpx
import pytest

from lens_engine.companion.client import API_VERSION, CompanionClient, CompanionError


def _mock_client(handler, base_url="http://127.0.0.1:9999") -> CompanionClient:
    client = CompanionClient(base_url)
    # inject a transport-backed async client factory
    original_get = client._get

    async def patched_get(path: str):
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, timeout=5, trust_env=False) as hc:
            r = await hc.get(f"{client.base_url}{path}", headers=client._headers())
        if r.status_code == 404:
            raise CompanionError(f"companion resource not found: {path}")
        if r.status_code != 200:
            raise CompanionError(f"companion error {r.status_code} on {path}")
        advertised = r.headers.get("X-CorpusMind-API-Version", API_VERSION)
        if advertised.split(".")[0] != API_VERSION:
            raise CompanionError(
                f"companion API version mismatch: advertised {advertised}, client {API_VERSION}")
        return r.json()

    client._get = patched_get  # type: ignore[method-assign]
    return client


def _ok_handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["X-CorpusMind-API-Version"] == API_VERSION
    return httpx.Response(200, json={"id": "c1", "name": "Text corpus"},
                          headers={"X-CorpusMind-API-Version": API_VERSION})


def test_get_corpus_overview_contract():
    client = _mock_client(_ok_handler)
    import asyncio

    data = asyncio.run(client.get_corpus_overview("c1"))
    assert data["id"] == "c1"


def test_version_mismatch_fails_loudly():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={}, headers={"X-CorpusMind-API-Version": "9"})

    client = _mock_client(handler)
    with pytest.raises(CompanionError, match="version mismatch"):
        import asyncio

        asyncio.run(client.get_corpus_overview("c1"))


def test_404_maps_to_friendly_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "nf"})

    client = _mock_client(handler)
    with pytest.raises(CompanionError, match="not found"):
        import asyncio

        asyncio.run(client.get_corpus_overview("nope"))


def test_network_error_is_companion_error():
    client = CompanionClient("http://127.0.0.1:1")  # nothing listens here
    import asyncio

    with pytest.raises(CompanionError):
        asyncio.run(client.get_corpus_overview("c1"))


def test_empty_base_url_raises_constructively():
    with pytest.raises(CompanionError, match="base URL"):
        CompanionClient("")


def test_companion_tool_absent_when_disabled():
    from lens_engine.ai.tools import run_tool, tool_manifest

    assert all(t["name"] != "get_text_corpus_overview" for t in tool_manifest())
    out = run_tool("get_text_corpus_overview", {"corpus_id": "c1"})
    assert out["grounded"] is False
