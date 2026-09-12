"""Lens data model (build brief §7).

    Project
     └── ImageSet           (the top-level corpus unit — there is no
          │                  intervening "Corpus" concept that also has to
          │                  make sense for text)
          ├── description, provenance/sampling notes, tags, genre/source/date
          ├── companion_link: { engine_base_url, corpus_id } | null   (§5)
          └── Image
               ├── stored bytes (+ optional at-rest encryption)
               ├── meta JSON: { user, exif, xmp, tags, annotations, ocr,
               │               detections, embedding_ref, vlm_description,
               │               colour, composition, typography }
               └── created_at  (the set's reading order anchor)

``companion_link`` is the only place a CorpusMind (Text) identifier is ever
stored, and it is nullable and inert unless Companion Mode is on (§5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Project:
    id: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> "Project":
        return cls(**r)


@dataclass(slots=True)
class ImageSet:
    id: str
    project_id: str
    name: str
    description: str = ""
    provenance_notes: str = ""
    # User-definable genre/source/date-range metadata — not a fixed schema (§9.1).
    meta: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    companion_link: dict[str, str] | None = None  # {engine_base_url, corpus_id}
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        import json

        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "provenance_notes": self.provenance_notes,
            "meta_json": json.dumps(self.meta, ensure_ascii=False),
            "tags_json": json.dumps(self.tags, ensure_ascii=False),
            "companion_link_json": (
                json.dumps(self.companion_link, ensure_ascii=False) if self.companion_link else None
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> "ImageSet":
        import json

        return cls(
            id=r["id"],
            project_id=r["project_id"],
            name=r["name"],
            description=r["description"],
            provenance_notes=r["provenance_notes"],
            meta=json.loads(r["meta_json"] or "{}"),
            tags=json.loads(r["tags_json"] or "[]"),
            companion_link=json.loads(r["companion_link_json"]) if r["companion_link_json"] else None,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )


@dataclass(slots=True)
class Image:
    id: str
    image_set_id: str
    filename: str
    storage_path: str
    thumb_path: str | None = None
    width: int = 0
    height: int = 0
    format: str = ""
    size_bytes: int = 0
    status: str = "pending"  # pending → processing → ready | error
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        import json

        return {
            "id": self.id,
            "image_set_id": self.image_set_id,
            "filename": self.filename,
            "storage_path": self.storage_path,
            "thumb_path": self.thumb_path,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "error": self.error,
            "meta_json": json.dumps(self.meta, ensure_ascii=False),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> "Image":
        import json

        return cls(
            id=r["id"],
            image_set_id=r["image_set_id"],
            filename=r["filename"],
            storage_path=r["storage_path"],
            thumb_path=r["thumb_path"],
            width=r["width"],
            height=r["height"],
            format=r["format"],
            size_bytes=r["size_bytes"],
            status=r["status"],
            error=r["error"],
            meta=json.loads(r["meta_json"] or "{}"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )


@dataclass(slots=True)
class Post:
    """A social media unit of analysis (v0.2 Social tab).

    One row per post/comment/video description. Flexible platform detail
    (hashtags, mentions, urls, emoji, attachment media) lives in ``meta``
    JSON, the same zero-migration pattern as ``Image.meta``. ``source`` is
    ``import`` (user-owned archive/export, no network) or ``connector``
    (official free-tier API, BYO credentials). ``created_at`` is the
    platform timestamp when available and drives the chronological reading
    order for sequence statistics.
    """

    id: str
    project_id: str
    platform: str  # x | instagram | facebook | tiktok | reddit | youtube | mastodon | generic
    external_id: str = ""
    author: str = ""
    text: str = ""
    language: str = ""
    created_at: str = ""
    likes: int = 0
    comments: int = 0
    shares: int = 0
    source: str = "import"  # import | connector
    source_ref: str = ""    # archive filename or API endpoint
    meta: dict[str, Any] = field(default_factory=dict)
    ingested_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        import json

        return {
            "id": self.id,
            "project_id": self.project_id,
            "platform": self.platform,
            "external_id": self.external_id,
            "author": self.author,
            "text": self.text,
            "language": self.language,
            "created_at": self.created_at,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "source": self.source,
            "source_ref": self.source_ref,
            "meta_json": json.dumps(self.meta, ensure_ascii=False),
            "ingested_at": self.ingested_at,
        }

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> "Post":
        import json

        return cls(
            id=r["id"],
            project_id=r["project_id"],
            platform=r["platform"],
            external_id=r["external_id"],
            author=r["author"],
            text=r["text"],
            language=r["language"],
            created_at=r["created_at"],
            likes=int(r["likes"] or 0),
            comments=int(r["comments"] or 0),
            shares=int(r["shares"] or 0),
            source=r["source"],
            source_ref=r["source_ref"],
            meta=json.loads(r["meta_json"] or "{}"),
            ingested_at=r["ingested_at"],
        )


@dataclass(slots=True)
class SocialSource:
    """Provenance record for one social import or connector fetch (ethics layer).

    Stores what was collected, from where, under which attestation, and with
    which anonymisation options applied. This is what makes an exported
    social corpus defensible in a methods section.
    """

    id: str
    project_id: str
    platform: str
    kind: str  # import | connector
    label: str
    details: dict[str, Any] = field(default_factory=dict)
    attested: bool = False
    anonymized: bool = False
    post_count: int = 0
    created_at: str = field(default_factory=_now)

    def to_row(self) -> dict[str, Any]:
        import json

        return {
            "id": self.id,
            "project_id": self.project_id,
            "platform": self.platform,
            "kind": self.kind,
            "label": self.label,
            "details_json": json.dumps(self.details, ensure_ascii=False),
            "attested": 1 if self.attested else 0,
            "anonymized": 1 if self.anonymized else 0,
            "post_count": self.post_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> "SocialSource":
        import json

        return cls(
            id=r["id"],
            project_id=r["project_id"],
            platform=r["platform"],
            kind=r["kind"],
            label=r["label"],
            details=json.loads(r["details_json"] or "{}"),
            attested=bool(r["attested"]),
            anonymized=bool(r["anonymized"]),
            post_count=int(r["post_count"] or 0),
            created_at=r["created_at"],
        )
