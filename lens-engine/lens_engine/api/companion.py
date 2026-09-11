"""Companion Mode routes (§5) — opt-in, off by default, degrades gracefully."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..companion.client import CompanionClient, CompanionError
from ..config import get_settings
from ..main import get_store

router = APIRouter(tags=["companion"])


def _client() -> CompanionClient:
    s = get_settings()
    if not s.companion_enabled:
        raise HTTPException(409, "Companion Mode is off (Settings → Companion Mode). "
                                 "Lens is fully functional without it.")
    if not s.companion_base_url:
        raise HTTPException(409, "No companion engine base URL configured.")
    return CompanionClient(s.companion_base_url)


@router.get("/companion/status")
async def companion_status() -> dict:
    s = get_settings()
    if not s.companion_enabled or not s.companion_base_url:
        return {"enabled": False, "reachable": False,
                "note": "Companion Mode is optional and never required for any Lens feature."}
    try:
        client = CompanionClient(s.companion_base_url)
        return {"enabled": True, "reachable": await client.health(),
                "base_url": s.companion_base_url}
    except CompanionError:
        return {"enabled": True, "reachable": False, "base_url": s.companion_base_url}


@router.get("/companion/corpora/{corpus_id}")
async def companion_corpus(corpus_id: str) -> dict:
    try:
        return {"overview": await _client().get_corpus_overview(corpus_id)}
    except CompanionError as e:
        raise HTTPException(502, str(e))


@router.get("/companion/corpora/{corpus_id}/frequency")
async def companion_frequency(corpus_id: str, limit: int = 50) -> dict:
    try:
        return {"frequency": await _client().get_corpus_frequency(corpus_id, limit=limit)}
    except CompanionError as e:
        raise HTTPException(502, str(e))


@router.post("/imagesets/{set_id}/companion-link")
async def link_companion(set_id: str, link: dict) -> dict:
    """Set the nullable companion_link ({engine_base_url, corpus_id}) — the
    ONLY place a CorpusMind (Text) identifier is ever stored (§7)."""
    store = get_store()
    s = store.get_image_set(set_id)
    if not s:
        raise HTTPException(404, "Image set not found")
    base = str(link.get("engine_base_url", "")).strip()
    cid = str(link.get("corpus_id", "")).strip()
    companion_link = None if not (base and cid) else {"engine_base_url": base, "corpus_id": cid}
    s = store.update_image_set(set_id, companion_link=companion_link)
    return {"companion_link": s.companion_link}
