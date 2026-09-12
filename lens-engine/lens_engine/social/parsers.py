"""Import parsers for the Social tab (S1: no network calls, ever).

Supported sources, all processed locally from user-owned exports:

* X (Twitter) archive: the zip as downloaded from the platform (data/tweet.js
  plus the tweets_media folder) or the tweet.js / tweets.js file itself.
* Instagram "Download Your Information" JSON (posts, captions).
* Facebook "Download Your Information" JSON (posts).
* TikTok data export JSON (video descriptions and activity texts).
* Generic CSV / JSONL with automatic column mapping (any platform export,
  Kaggle / Zenodo research datasets, MCL-style dumps).

Parsers emit DRAFT records; :func:`finalize_drafts` turns them into storage
``Post`` rows (timestamp normalisation, hashtag/mention/url/emoji harvesting,
ethics transformations). Media files are returned as source paths and copied
by the API layer, where attached photos can flow into the existing vision
pipeline (OCR, colour, composition, annotations).
"""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from . import textutils

MAX_MEDIA_PER_IMPORT = 2000
MAX_DRAFTS = 200_000


# --------------------------------------------------------------------------- #
# Draft record helpers
# --------------------------------------------------------------------------- #


def draft(
    *,
    external_id: str = "",
    author: str = "",
    text: str = "",
    created_at: str = "",
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    language: str = "",
    media: list[str] | None = None,
    link: str = "",
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "author": author,
        "text": text,
        "created_at": created_at,
        "likes": int(likes or 0),
        "comments": int(comments or 0),
        "shares": int(shares or 0),
        "language": language,
        "media": media or [],
        "link": link,
    }


def finalize_drafts(
    drafts: list[dict[str, Any]],
    *,
    platform: str,
    source_ref: str,
    apply: Any = None,
) -> list[dict[str, Any]]:
    """Harvest social markers, normalise time, apply ethics, drop empties.

    ``apply(text, author) -> (text, author)`` is the ethics hook (see
    ``ethics.apply_ethics`` partially applied with the user's options).
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in drafts[:MAX_DRAFTS]:
        text = textutils.strip_html(d.get("text") or "").strip()
        author = (d.get("author") or "").strip()
        if apply:
            text, author = apply(text, author)
        if not text and not d.get("media"):
            continue
        key = f"{d.get('external_id')}|{text[:200]}"
        if key in seen:
            continue
        seen.add(key)
        meta: dict[str, Any] = {
            "hashtags": textutils.extract_hashtags(text),
            "mentions": textutils.extract_mentions(text),
            "urls": textutils.extract_urls(text),
            "emoji": textutils.extract_emoji(text),
        }
        if d.get("link"):
            meta["link"] = d["link"]
        if d.get("media"):
            meta["media"] = d["media"][:MAX_MEDIA_PER_IMPORT]
        out.append(
            {
                "external_id": d.get("external_id") or "",
                "author": author,
                "text": text,
                "language": d.get("language") or "",
                "created_at": textutils.parse_platform_time(d.get("created_at") or ""),
                "likes": d.get("likes", 0),
                "comments": d.get("comments", 0),
                "shares": d.get("shares", 0),
                "meta": meta,
                "platform": platform,
                "source_ref": source_ref,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Zip / file bundle handling
# --------------------------------------------------------------------------- #


class ArchiveBundle:
    """A uploaded zip (or plain folder) safely unpacked to a temp dir."""

    def __init__(self, data: bytes | None = None, root: Path | None = None):
        import shutil
        import tempfile

        self._tmp: Any = None
        if root is not None:
            self.root = root
            return
        self._tmp = tempfile.mkdtemp(prefix="lens-social-")
        target = Path(self._tmp) / "archive"
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            base = target.resolve()
            for info in zf.infolist():
                if info.is_dir():
                    continue
                dest = (base / info.filename).resolve()
                if not str(dest).startswith(str(base)):  # zip-slip guard
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))
        self.root = target

    def close(self) -> None:
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

    def find(self, *patterns: str) -> list[Path]:
        out: list[Path] = []
        for pat in patterns:
            out.extend(self.root.rglob(pat))
        return out


# --------------------------------------------------------------------------- #
# X (Twitter) archive
# --------------------------------------------------------------------------- #


def _load_js_json(path: Path) -> list[Any]:
    """tweet.js style: one JS assignment line, then a JSON array."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = raw[raw.index("[") :] if "[" in raw else raw
    data = json.loads(raw)
    if isinstance(data, dict):
        data = list(data.values())
    return data if isinstance(data, list) else []


def _tweet_media_paths(bundle: ArchiveBundle, tweet_id: str) -> list[str]:
    if not tweet_id:
        return []
    hits: list[str] = []
    for folder in ("tweets_media", "data/tweets_media", "data"):
        for d in bundle.root.rglob(folder):
            if not d.is_dir():
                continue
            for f in sorted(d.iterdir()):
                if f.is_file() and tweet_id in f.name and _is_media(f.name):
                    hits.append(str(f))
    return hits[:12]


def _is_media(name: str) -> bool:
    return bool(re.search(r"\.(jpe?g|png|gif|webp|mp4|mov|avi)$", name, re.I))


def parse_x_archive(bundle: ArchiveBundle) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    files = bundle.find("tweet.js", "tweets.js", "Tweet.js", "Tweets.js")
    for path in files:
        for item in _load_js_json(path):
            tw = item.get("tweet", item) if isinstance(item, dict) else {}
            if not isinstance(tw, dict):
                continue
            text = tw.get("full_text") or tw.get("text") or ""
            if not text and "entities" not in tw:
                continue
            ent = tw.get("entities") or {}
            media_refs: list[str] = []
            ee = tw.get("extended_entities") or {}
            for m in (ee.get("media") or []) + (ent.get("media") or []):
                if isinstance(m, dict) and m.get("type") == "photo":
                    media_refs.append(m.get("media_url_https") or m.get("media_url") or "")
            media_refs = [m for m in media_refs if m]
            tid = tw.get("id_str") or str(tw.get("id") or "")
            local = _tweet_media_paths(bundle, tid)
            drafts.append(
                draft(
                    external_id=tid,
                    author=str(tw.get("user_id_str") or tw.get("screen_name") or ""),
                    text=text,
                    created_at=tw.get("created_at") or "",
                    likes=tw.get("favorite_count", 0),
                    comments=tw.get("reply_count", 0),
                    shares=(tw.get("retweet_count", 0) or 0) + (tw.get("quote_count", 0) or 0),
                    language=tw.get("lang") or "",
                    media=local or media_refs,
                    link=f"https://x.com/i/status/{tid}" if tid else "",
                )
            )
    return drafts


# --------------------------------------------------------------------------- #
# Instagram / Facebook / TikTok: tolerant DYI walkers
# --------------------------------------------------------------------------- #

_TEXT_KEYS = ("text", "caption", "title", "description", "desc", "post", "body", "content", "label")
_TIME_KEYS = ("creation_timestamp", "timestamp", "created_at", "created_time", "Date", "date", "Time", "time")
_AUTHOR_KEYS = ("author", "username", "user", "sender_name", "channel", "account")
_MEDIA_KEYS = ("uri", "media_url", "media_url_https", "link", "url", "play_addr", "download_link")
_LIKE_KEYS = ("likes", "favorite_count", "like_count", "digg_count", "score", "play_count")
_COMMENT_KEYS = ("comments", "reply_count", "comment_count", "comments_count")
_SHARE_KEYS = ("shares", "retweet_count", "reblog_count", "reblogs_count", "share_count", "repost_count")


def _walk(node: Any, depth: int = 0) -> Iterator[dict]:
    if depth > 12:
        return
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v, depth + 1)


def _first(d: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return None


def _media_in(d: dict, seen_paths: set[str]) -> list[str]:
    out: list[str] = []
    for k in _MEDIA_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v and v not in seen_paths and _is_media(v):
            resolved = bundle_media_path(v)
            if resolved:
                seen_paths.add(v)
                out.append(resolved)
    return out


# Set by the API layer before walking, so relative DYI "uri" entries can be
# resolved against the unpacked archive root.
_BUNDLE_ROOT: Path | None = None


def bundle_media_path(ref: str) -> str | None:
    ref = ref.split("?")[0]
    if not _is_media(ref):
        return None
    if _BUNDLE_ROOT is None:
        return None
    direct = (_BUNDLE_ROOT / ref).resolve()
    if direct.is_file():
        return str(direct)
    hits = sorted(_BUNDLE_ROOT.rglob(Path(ref).name))
    return str(hits[0]) if hits else None


def parse_meta_export(data: Any, bundle: ArchiveBundle | None = None) -> list[dict[str, Any]]:
    """Tolerant walker for Instagram / Facebook / TikTok DYI JSON."""
    global _BUNDLE_ROOT
    _BUNDLE_ROOT = bundle.root if bundle else None
    try:
        drafts: list[dict[str, Any]] = []
        media_seen: set[str] = set()
        for node in _walk(data):
            text = _first(node, _TEXT_KEYS)
            if not isinstance(text, str) or not text.strip():
                continue
            time_v = _first(node, _TIME_KEYS)
            media = _media_in(node, media_seen)
            if not media and not text.strip():
                continue
            # Nested containers (attachments, media_metadata) often hold media.
            if not media:
                for child in _walk(node.get("attachments") or node.get("media_metadata") or node.get("media") or {}):
                    media = _media_in(child, media_seen)
                    if media:
                        break
            drafts.append(
                draft(
                    author=str(_first(node, _AUTHOR_KEYS) or ""),
                    text=text,
                    created_at=str(time_v or ""),
                    likes=_int_or(_first(node, _LIKE_KEYS)),
                    comments=_int_or(_first(node, _COMMENT_KEYS)),
                    shares=_int_or(_first(node, _SHARE_KEYS)),
                    media=media,
                )
            )
        return drafts
    finally:
        _BUNDLE_ROOT = None


def _int_or(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------- #
# Generic CSV / JSONL
# --------------------------------------------------------------------------- #

_TEXT_COLS = ("text", "full_text", "tweet", "content", "body", "post", "selftext", "title", "caption", "description", "comment", "message")
_ID_COLS = ("id", "id_str", "tweet_id", "post_id", "external_id", "status_id", "video_id", "link_id")
_AUTHOR_COLS = ("author", "username", "user", "screen_name", "handle", "user_name", "channel", "channel_title", "acct", "sender")
_TIME_COLS = ("created_at", "timestamp", "date", "datetime", "created_time", "created_utc", "published_at", "posted_at", "time", "Date")
_LANG_COLS = ("lang", "language", "lang_code")
_LIKE_COLS = ("likes", "favorite_count", "favourites_count", "like_count", "score", "digg_count", "likes_count")
_COMMENT_COLS = ("comments", "reply_count", "replies", "comment_count", "num_comments", "comments_count")
_SHARE_COLS = ("shares", "retweet_count", "retweets", "reblog_count", "share_count", "reposts", "shares_count")


def _map_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {c.lower().strip(): c for c in columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    for cand in candidates:  # substring fallback
        for low, orig in lowered.items():
            if cand in low:
                return orig
    return None


def parse_csv(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = list(reader)
    if not rows:
        return []
    cols = [c for c in rows[0].keys() if c]
    c_text = _map_column(cols, _TEXT_COLS)
    if not c_text:
        raise ValueError("CSV import: no text-like column found (expected one of: " + ", ".join(_TEXT_COLS) + ")")
    c_id = _map_column(cols, _ID_COLS)
    c_author = _map_column(cols, _AUTHOR_COLS)
    c_time = _map_column(cols, _TIME_COLS)
    c_lang = _map_column(cols, _LANG_COLS)
    c_likes = _map_column(cols, _LIKE_COLS)
    c_comments = _map_column(cols, _COMMENT_COLS)
    c_shares = _map_column(cols, _SHARE_COLS)
    drafts: list[dict[str, Any]] = []
    for r in rows[:MAX_DRAFTS]:
        val = (r.get(c_text) or "").strip()
        if not val:
            continue
        drafts.append(
            draft(
                external_id=(r.get(c_id) or "").strip() if c_id else "",
                author=(r.get(c_author) or "").strip() if c_author else "",
                text=val,
                created_at=(r.get(c_time) or "").strip() if c_time else "",
                likes=_int_or(r.get(c_likes)) if c_likes else 0,
                comments=_int_or(r.get(c_comments)) if c_comments else 0,
                shares=_int_or(r.get(c_shares)) if c_shares else 0,
                language=(r.get(c_lang) or "").strip() if c_lang else "",
            )
        )
    return drafts


def parse_jsonl(data: bytes) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    for line in data.decode("utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows = obj if isinstance(obj, list) else [obj]
        for item in rows:
            if not isinstance(item, dict):
                continue
            val = _first(item, _TEXT_COLS)
            if not isinstance(val, str) or not val.strip():
                continue
            drafts.append(
                draft(
                    external_id=str(_first(item, _ID_COLS) or ""),
                    author=str(_first(item, _AUTHOR_COLS) or ""),
                    text=val,
                    created_at=str(_first(item, _TIME_COLS) or ""),
                    likes=_int_or(_first(item, _LIKE_COLS)),
                    comments=_int_or(_first(item, _COMMENT_COLS)),
                    shares=_int_or(_first(item, _SHARE_COLS)),
                    language=str(_first(item, _LANG_COLS) or ""),
                )
            )
        if len(drafts) > MAX_DRAFTS:
            break
    return drafts
