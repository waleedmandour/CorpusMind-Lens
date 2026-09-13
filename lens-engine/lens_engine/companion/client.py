"""Companion Mode (§5) — the ONLY integration surface with CorpusMind (Text).

A narrow, documented, versioned HTTP client over plain HTTP, gated behind an
opt-in setting, degrading gracefully (the tool is simply absent) when no
companion engine is reachable. Contract: docs/COMPANION_MODE.md.
"""
from __future__ import annotations

from typing import Any

import httpx

from .. import __version__
from ..logging import get_logger

log = get_logger(__name__)

API_VERSION = "1"  # must match the X-CorpusMind-API-Version the parent engine advertises


class CompanionError(ConnectionError):
    pass


class CompanionClient:
    """Minimal client for the two endpoints the contract exposes."""

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        if not base_url:
            raise CompanionError("No companion engine base URL configured (Settings → Companion Mode).")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        # Version is read from the package singleton, never hardcoded: the
        # v0.2.0 build still announced "lens-engine/0.1.0" here — the exact
        # version-drift class the /health fix had just eliminated.
        return {
            "X-CorpusMind-API-Version": API_VERSION,
            "X-CorpusMind-Lens-Client": f"lens-engine/{__version__}",
        }

    async def _get(self, path: str) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                r = await client.get(f"{self.base_url}{path}", headers=self._headers())
        except httpx.HTTPError as e:
            raise CompanionError(f"companion unreachable: {e}") from e
        if r.status_code == 404:
            raise CompanionError(f"companion resource not found: {path}")
        if r.status_code != 200:
            raise CompanionError(f"companion error {r.status_code} on {path}")
        # Version negotiation: fail loudly on an incompatible contract rather
        # than silently mis-reading the other product's data (§5).
        advertised = r.headers.get("X-CorpusMind-API-Version", API_VERSION)
        if advertised.split(".")[0] != API_VERSION:
            raise CompanionError(
                f"companion API version mismatch: advertised {advertised}, client {API_VERSION}"
            )
        return r.json()

    async def get_corpus_overview(self, corpus_id: str) -> Any:
        return await self._get(f"/api/v1/corpora/{corpus_id}")

    async def get_corpus_frequency(self, corpus_id: str, *, limit: int = 50) -> Any:
        return await self._get(f"/api/v1/corpora/{corpus_id}/frequency?limit={limit}")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                r = await client.get(f"{self.base_url}/api/v1/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False
