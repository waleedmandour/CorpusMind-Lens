"""Audit trail (§4 Principle 2, §10) — every Assistant tool call + result is
logged, append-only, JSONL. Local-first: the file lives in the data dir."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from ..config import get_settings
from ..logging import get_logger

log = get_logger(__name__)
_lock = Lock()


def audit_event(event: str, **fields) -> None:
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    try:
        settings = get_settings()
        path: Path = settings.data_dir / "logs" / "assistant_audit.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # audit must never break the request path
        log.warning("audit_write_failed", extra={"error": str(e)})


def read_audit(limit: int = 200) -> list[dict]:
    try:
        settings = get_settings()
        path = settings.data_dir / "logs" / "assistant_audit.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []
