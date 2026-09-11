"""SQLite-backed store for Projects, ImageSets, and Images.

Stdlib ``sqlite3`` with JSON columns for the flexible per-image metadata —
the same zero-migration access pattern the parent engine proved out with
``Image.meta``. A single writer connection guarded by a lock; the engine is
a local, single-user/Single-tenant-per-instance service (§13), so the
concurrency profile is intentionally modest: background ingestion workers
enqueue via ``asyncio.to_thread`` and the lock serialises writes.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..logging import get_logger
from .models import Image, ImageSet, Project

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS image_sets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    provenance_notes TEXT DEFAULT '',
    meta_json TEXT DEFAULT '{}',
    tags_json TEXT DEFAULT '[]',
    companion_link_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    image_set_id TEXT NOT NULL REFERENCES image_sets(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    thumb_path TEXT,
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    format TEXT DEFAULT '',
    size_bytes INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error TEXT,
    meta_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sets_project ON image_sets(project_id);
CREATE INDEX IF NOT EXISTS idx_images_set ON images(image_set_id);
CREATE INDEX IF NOT EXISTS idx_images_created ON images(image_set_id, created_at);
"""


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    """Persistence facade. All timestamps are ISO-8601 UTC strings; the
    per-set reading order for sequence statistics is ``created_at`` ASC (§7)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.commit()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # -- generic helpers ----------------------------------------------------
    @staticmethod
    def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
        return {k: r[k] for k in r.keys()}

    # -- Projects -----------------------------------------------------------
    def create_project(self, name: str, description: str = "") -> Project:
        p = Project(id=new_id(), name=name.strip() or "Untitled project", description=description)
        with self._tx() as c:
            c.execute(
                "INSERT INTO projects VALUES (:id,:name,:description,:created_at,:updated_at)",
                p.to_row(),
            )
        return p

    def list_projects(self) -> list[Project]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return [Project.from_row(self._row_to_dict(r)) for r in rows]

    def get_project(self, pid: str) -> Project | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return Project.from_row(self._row_to_dict(r)) if r else None

    def delete_project(self, pid: str) -> bool:
        with self._tx() as c:
            cur = c.execute("DELETE FROM projects WHERE id=?", (pid,))
        return cur.rowcount > 0

    # -- ImageSets ----------------------------------------------------------
    def create_image_set(
        self,
        project_id: str,
        name: str,
        description: str = "",
        provenance_notes: str = "",
        meta: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> ImageSet:
        s = ImageSet(
            id=new_id(),
            project_id=project_id,
            name=name.strip() or "Untitled image set",
            description=description,
            provenance_notes=provenance_notes,
            meta=meta or {},
            tags=tags or [],
        )
        with self._tx() as c:
            c.execute(
                "INSERT INTO image_sets VALUES (:id,:project_id,:name,:description,"
                ":provenance_notes,:meta_json,:tags_json,:companion_link_json,:created_at,:updated_at)",
                s.to_row(),
            )
        return s

    def list_image_sets(self, project_id: str | None = None) -> list[ImageSet]:
        q = "SELECT * FROM image_sets"
        args: tuple = ()
        if project_id:
            q += " WHERE project_id=?"
            args = (project_id,)
        q += " ORDER BY created_at"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [ImageSet.from_row(self._row_to_dict(r)) for r in rows]

    def get_image_set(self, sid: str) -> ImageSet | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM image_sets WHERE id=?", (sid,)).fetchone()
        return ImageSet.from_row(self._row_to_dict(r)) if r else None

    def update_image_set(self, sid: str, **fields: Any) -> ImageSet | None:
        allowed = {"name", "description", "provenance_notes", "meta", "tags", "companion_link"}
        sets: list[ImageSet] = []
        s = self.get_image_set(sid)
        if not s:
            return None
        for k, v in fields.items():
            if k in allowed:
                setattr(s, k, v)
        s.updated_at = _now_iso()
        with self._tx() as c:
            c.execute(
                "UPDATE image_sets SET name=:name, description=:description,"
                " provenance_notes=:provenance_notes, meta_json=:meta_json,"
                " tags_json=:tags_json, companion_link_json=:companion_link_json,"
                " updated_at=:updated_at WHERE id=:id",
                s.to_row(),
            )
        return self.get_image_set(sid)

    def delete_image_set(self, sid: str) -> bool:
        with self._tx() as c:
            cur = c.execute("DELETE FROM image_sets WHERE id=?", (sid,))
        return cur.rowcount > 0

    # -- Images ---------------------------------------------------------------
    def add_image(self, img: Image) -> Image:
        with self._tx() as c:
            c.execute(
                "INSERT INTO images VALUES (:id,:image_set_id,:filename,:storage_path,:thumb_path,"
                ":width,:height,:format,:size_bytes,:status,:error,:meta_json,:created_at,:updated_at)",
                img.to_row(),
            )
        return img

    def update_image(self, image_id: str, **fields: Any) -> Image | None:
        img = self.get_image(image_id)
        if not img:
            return None
        for k, v in fields.items():
            setattr(img, k, v)
        img.updated_at = _now_iso()
        with self._tx() as c:
            c.execute(
                "UPDATE images SET storage_path=:storage_path, thumb_path=:thumb_path,"
                " width=:width, height=:height, format=:format, size_bytes=:size_bytes,"
                " status=:status, error=:error, meta_json=:meta_json, updated_at=:updated_at"
                " WHERE id=:id",
                img.to_row(),
            )
        return img

    def get_image(self, image_id: str) -> Image | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
        return Image.from_row(self._row_to_dict(r)) if r else None

    def list_images(self, image_set_id: str) -> list[Image]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM images WHERE image_set_id=? ORDER BY created_at ASC",
                (image_set_id,),
            ).fetchall()
        return [Image.from_row(self._row_to_dict(r)) for r in rows]

    def delete_image(self, image_id: str) -> Image | None:
        img = self.get_image(image_id)
        if not img:
            return None
        with self._tx() as c:
            c.execute("DELETE FROM images WHERE id=?", (image_id,))
        return img

    # -- aggregate helper used by set-level statistics ------------------------
    def count_images(self, image_set_id: str) -> int:
        with self._lock:
            r = self._conn.execute(
                "SELECT COUNT(*) AS n FROM images WHERE image_set_id=?", (image_set_id,)
            ).fetchone()
        return int(r["n"])


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
