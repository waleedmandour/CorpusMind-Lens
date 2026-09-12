"""Social tab routes (v0.2): import-first archives, free-tier connectors,
platform analytics, and CSV/XML exports of every outcome.

Ethics rules enforced server-side:
* imports require an explicit attestation before any row is stored;
* connector fetches require the ToS attestation and run ONLY against
  official endpoints with user-supplied credentials (never persisted);
* anonymisation happens before storage, never as an afterthought;
* provenance is recorded for every source and included in exports.
"""
from __future__ import annotations

import json
import shutil
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from ..config import get_settings
from ..main import enqueue_ingest, get_store
from ..social import connectors as conn
from ..social import ethics, parsers, social_stats
from ..storage.models import Image, Post, SocialSource
from ..storage.store import new_id
from ..vision import ingest as ingest_mod

router = APIRouter(tags=["social"])

MAX_IMPORT_MB = int(__import__("os").environ.get("LENS_SOCIAL_MAX_IMPORT_MB", "200"))
MAX_MEDIA_FILES = 500
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
ZIP_MAGIC = b"PK"

CONNECTORS = ("mastodon", "reddit", "youtube")


def _project_or_404(project_id: str):
    store = get_store()
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _posts_or_404(project_id: str, platform: str | None) -> list[Post]:
    posts = get_store().list_posts(project_id, platform)
    return posts


def _public_post(p: Post) -> dict:
    d = asdict(p)
    meta = dict(d.get("meta") or {})
    media = meta.pop("media", [])
    d["meta"] = {**meta, "media_count": len(media)}
    return d


# --------------------------------------------------------------------------- #
# Import (S1: no network calls)
# --------------------------------------------------------------------------- #


def _ethics_hook(options: dict[str, Any]):
    salt = str(options.get("salt") or new_id())

    def apply(text: str, author: str) -> tuple[str, str]:
        return ethics.apply_ethics(
            text,
            author,
            salt=salt,
            pseudonymize=bool(options.get("pseudonymize", False)),
            redact_emails=True,
            redact_phones=True,
            redact_urls=bool(options.get("redact_urls", False)),
            redact_mentions=bool(options.get("redact_mentions", False)),
        )

    return apply


def _register_media_paths(
    paths: list[str],
    project_id: str,
    *,
    vision_analyse: bool,
    set_name: str,
) -> tuple[int, int, str | None, dict[str, str]]:
    """Copy media files into engine storage; optionally register them with
    the vision pipeline (ImageSet + background ingest). Returns
    (accepted, rejected, image_set_id, media_map path -> image id)."""
    store = get_store()
    settings = get_settings()
    accepted = rejected = 0
    image_set_id: str | None = None
    media_map: dict[str, str] = {}
    paths = [p for p in paths if p][:MAX_MEDIA_FILES]
    if not paths:
        return 0, 0, None, {}
    if vision_analyse:
        s = store.create_image_set(
            project_id,
            set_name,
            description="Attached media from social data (Social tab)",
            provenance_notes="Created automatically from social import attachments",
            meta={"origin": "social"},
            tags=["social"],
        )
        image_set_id = s.id
    for i, mpath in enumerate(paths):
        p = Path(mpath)
        if not p.is_file():
            continue
        try:
            raw = p.read_bytes()
            fmt = ingest_mod.validate_upload(raw, p.name or f"media-{i}")
            img = Image(
                id=new_id(),
                image_set_id=image_set_id or "_orphans",
                filename=p.name or f"media-{i}.{fmt}",
                storage_path="",
                format=fmt,
                size_bytes=len(raw),
                status="pending",
            )
            storage_path, thumb_path = ingest_mod.persist_image_bytes(img, raw, settings=settings)
            img.storage_path = storage_path
            img.thumb_path = thumb_path
            store.add_image(img)
            if image_set_id:
                enqueue_ingest(img.id)
            media_map[str(p)] = img.id
            accepted += 1
        except Exception:
            rejected += 1
    return accepted, rejected, image_set_id, media_map


def _attach_media_to_drafts(
    drafts: list[dict[str, Any]],
    project_id: str,
    *,
    vision_analyse: bool,
    set_name: str,
) -> tuple[int, int, str | None]:
    """Register local media referenced by drafts, rewrite meta to image ids,
    and drop unresolvable entries (count only)."""
    all_paths: list[str] = []
    for d in drafts:
        all_paths.extend([m for m in (d["meta"].get("media") or []) if not str(m).startswith("http")])
    accepted, rejected, image_set_id, media_map = _register_media_paths(
        all_paths, project_id, vision_analyse=vision_analyse, set_name=set_name
    )
    for d in drafts:
        media = d["meta"].get("media") or []
        ids = [media_map[m] for m in media if m in media_map]
        if ids:
            d["meta"]["media_image_ids"] = ids
        d["meta"]["media_unattached"] = len(media) - len(ids)
        d["meta"].pop("media", None)
    return accepted, rejected, image_set_id


def _store_drafts(
    drafts: list[dict[str, Any]],
    *,
    project_id: str,
    platform: str,
    source_ref: str,
    kind: str,
    label: str,
    attested: bool,
    anonymized: bool,
    details: dict[str, Any],
) -> dict:
    store = get_store()
    posts: list[Post] = []
    for d in drafts:
        posts.append(
            Post(
                id=new_id(),
                project_id=project_id,
                platform=platform,
                external_id=str(d.get("external_id") or ""),
                author=str(d.get("author") or ""),
                text=str(d.get("text") or ""),
                language=str(d.get("language") or ""),
                created_at=str(d.get("created_at") or ""),
                likes=int(d.get("likes") or 0),
                comments=int(d.get("comments") or 0),
                shares=int(d.get("shares") or 0),
                source=kind,
                source_ref=source_ref,
                meta=d.get("meta") or {},
            )
        )
    store.add_posts(posts)
    src = store.add_social_source(
        SocialSource(
            id=new_id(),
            project_id=project_id,
            platform=platform,
            kind=kind,
            label=label,
            details=details,
            attested=attested,
            anonymized=anonymized,
            post_count=len(posts),
        )
    )
    return {"post_count": len(posts), "source_id": src.id}


@router.post("/projects/{project_id}/social/import")
async def social_import(
    project_id: str,
    file: UploadFile = File(...),
    source: str = Form("auto"),
    options: str = Form("{}"),
) -> dict:
    """Import a user-owned export (S1). Everything runs locally; no network."""
    _project_or_404(project_id)
    opts = json.loads(options or "{}")
    if not opts.get("attested"):
        raise HTTPException(
            422,
            "Import requires acknowledging the ethics attestation (options.attested = true): "
            "the data comes from your own export and will be analysed under the platform terms.",
        )
    raw = await file.read()
    if len(raw) > MAX_IMPORT_MB * 1024 * 1024:
        raise HTTPException(413, f"Import cap is {MAX_IMPORT_MB} MB")
    if not raw:
        raise HTTPException(422, "Empty upload")

    filename = file.filename or "upload"
    apply = _ethics_hook(opts)
    platform = "generic"
    label = filename
    bundle: parsers.ArchiveBundle | None = None

    try:
        if raw[:2] == ZIP_MAGIC or filename.lower().endswith(".zip"):
            bundle = parsers.ArchiveBundle(data=raw)
            if bundle.find("tweet.js", "tweets.js", "Tweet.js", "Tweets.js"):
                platform, label = "x", f"X archive: {filename}"
                drafts = parsers.parse_x_archive(bundle)
            else:
                data_root: Any = None
                js_files = bundle.find("posts.json", "media.json", "your_posts*.json", "post_comments*.json")
                if js_files:
                    merged: list[Any] = []
                    for jf in js_files[:20]:
                        try:
                            merged.append(json.loads(jf.read_text(encoding="utf-8", errors="replace")))
                        except json.JSONDecodeError:
                            continue
                    data_root = merged
                    platform = "facebook" if any("your_posts" in str(jf).lower() for jf in js_files) else "instagram"
                else:
                    cj = bundle.find("user_data_tiktok.json", "Activity.json", "Videos.json")
                    if cj:
                        merged2: list[Any] = []
                        for jf in cj[:10]:
                            try:
                                merged2.append(json.loads(jf.read_text(encoding="utf-8", errors="replace")))
                            except json.JSONDecodeError:
                                continue
                        data_root = merged2
                        platform = "tiktok"
                if data_root is None:
                    raise HTTPException(422, "Unrecognised archive: no tweet.js / posts.json / TikTok activity JSON found")
                label = f"{platform} export: {filename}"
                drafts = parsers.parse_meta_export(data_root, bundle)
        elif filename.lower().endswith((".jsonl", ".ndjson")) or source == "jsonl":
            platform = str(opts.get("platform") or "generic")
            drafts = parsers.parse_jsonl(raw)
        elif source == "csv" or filename.lower().endswith(".csv"):
            platform = str(opts.get("platform") or "generic")
            drafts = parsers.parse_csv(raw)
        elif filename.lower().endswith(".js"):
            # Single tweet.js from an unpacked archive: treat as X data.
            platform = "x"
            data = json.loads(raw[raw.index(b"[") :].decode("utf-8", errors="replace"))
            rows = data if isinstance(data, list) else list(data.values())
            drafts = []
            for item in rows:
                tw = item.get("tweet", item) if isinstance(item, dict) else {}
                if isinstance(tw, dict) and (tw.get("full_text") or tw.get("text")):
                    ent = tw.get("entities") or {}
                    ee = tw.get("extended_entities") or {}
                    media = [
                        m.get("media_url_https") or m.get("media_url") or ""
                        for m in (ee.get("media") or []) + (ent.get("media") or [])
                        if isinstance(m, dict) and m.get("type") == "photo"
                    ]
                    drafts.append(
                        parsers.draft(
                            external_id=tw.get("id_str") or "",
                            author=str(tw.get("user_id_str") or ""),
                            text=tw.get("full_text") or tw.get("text") or "",
                            created_at=tw.get("created_at") or "",
                            likes=tw.get("favorite_count", 0),
                            comments=tw.get("reply_count", 0),
                            shares=(tw.get("retweet_count", 0) or 0) + (tw.get("quote_count", 0) or 0),
                            language=tw.get("lang") or "",
                            media=[m for m in media if m],
                        )
                    )
            label = f"X archive: {filename}"
        else:
            # Plain JSON: DYI walker (Instagram / Facebook / TikTok / generic dumps)
            try:
                data = json.loads(raw.decode("utf-8-sig", errors="replace"))
            except json.JSONDecodeError as e:
                raise HTTPException(422, f"Unrecognised file type for {filename}: not CSV, JSONL, JS or JSON ({e})")
            platform = str(opts.get("platform") or "generic")
            drafts = parsers.parse_meta_export(data, None)
            if not drafts:
                drafts = parsers.parse_jsonl(raw)

        finalized = parsers.finalize_drafts(
            drafts,
            platform=platform,
            source_ref=filename,
            apply=apply,
        )
        if not finalized:
            raise HTTPException(
                422,
                "No posts could be extracted from this file. Check that it is a supported "
                "export (X archive, Instagram/Facebook DYI, TikTok export, CSV, JSONL).",
            )

        # Local media (zip archives): register with the vision pipeline.
        media_accepted = media_rejected = 0
        image_set_id = None
        has_local_media = any(
            not str(m).startswith("http")
            for d in finalized
            for m in (d["meta"].get("media") or [])
        )
        if opts.get("vision_analyse", True) and has_local_media:
            media_accepted, media_rejected, image_set_id = _attach_media_to_drafts(
                finalized,
                project_id,
                vision_analyse=True,
                set_name=f"Social media: {platform} ({datetime.now(UTC).date()})",
            )

        stored = _store_drafts(
            finalized,
            project_id=project_id,
            platform=platform,
            source_ref=filename,
            kind="import",
            label=label,
            attested=True,
            anonymized=bool(opts.get("pseudonymize", False)),
            details={
                "file": filename,
                "size_bytes": len(raw),
                "options": {k: v for k, v in opts.items() if k != "salt"},
                "attestation": ethics.attestation_text(platform, "import"),
            },
        )
        return {
            "ok": True,
            "platform": platform,
            "imported": stored["post_count"],
            "media_registered": media_accepted,
            "media_rejected": media_rejected,
            "image_set_id": image_set_id,
            "source_id": stored["source_id"],
            "note": "Emails and phone numbers are always redacted; further options were applied as selected.",
        }
    finally:
        if bundle:
            bundle.close()


# --------------------------------------------------------------------------- #
# Connector fetches (S2: official free tiers, BYO credentials)
# --------------------------------------------------------------------------- #


def _download_media(urls: list[str], project_id: str) -> tuple[int, int]:
    """Download public media URLs through the connector's user agent and
    register them with the vision pipeline (opt-in, capped)."""
    import tempfile

    accepted = rejected = 0
    tmpdir = Path(tempfile.mkdtemp(prefix="lens-social-media-"))
    try:
        paths: list[str] = []
        for i, url in enumerate(urls[:MAX_MEDIA_FILES]):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": conn.USER_AGENT})
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read(MAX_DOWNLOAD_BYTES + 1)
                if not raw or len(raw) > MAX_DOWNLOAD_BYTES:
                    raise ValueError("media too large or empty")
                fmt = ingest_mod.validate_upload(raw, Path(url.split("?")[0]).name or f"media-{i}")
                p = tmpdir / f"media-{i}.{fmt}"
                p.write_bytes(raw)
                paths.append(str(p))
                accepted += 1
            except Exception:
                rejected += 1
        if paths:
            a, rej, _sid, _map = _register_media_paths(
                paths,
                project_id,
                vision_analyse=True,
                set_name=f"Social media: connector ({datetime.now(UTC).date()})",
            )
            accepted, rejected = a, rejected + rej
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return accepted, rejected


@router.post("/projects/{project_id}/social/fetch")
async def social_fetch(project_id: str, body: dict) -> dict:
    """Fetch public data through an official API on its free tier (S2).

    Credentials are supplied per request and are NEVER stored. Requires the
    ToS attestation (``acknowledge_tos: true``)."""
    _project_or_404(project_id)
    connector = (body.get("connector") or "").lower()
    if connector not in CONNECTORS:
        raise HTTPException(422, f"connector must be one of: {', '.join(CONNECTORS)}")
    if not body.get("acknowledge_tos"):
        raise HTTPException(422, "Fetching requires acknowledge_tos = true: official API, public content, rate limits honoured.")
    params: dict[str, Any] = body.get("params") or {}
    max_items = min(int(body.get("max_items", 200)), 1000)

    try:
        if connector == "mastodon":
            drafts, warnings = conn.fetch_mastodon(
                instance=str(params.get("instance", "")),
                hashtag=str(params.get("hashtag", "")),
                limit=max_items,
                access_token=str(params.get("access_token", "") or ""),
            )
        elif connector == "reddit":
            drafts, warnings = conn.fetch_reddit(
                client_id=str(params.get("client_id", "")),
                client_secret=str(params.get("client_secret", "")),
                subreddit=str(params.get("subreddit", "")),
                mode=str(params.get("mode", "new")),
                query=str(params.get("query", "")),
                limit=max_items,
                user_agent=str(params.get("user_agent", "")),
            )
        else:
            drafts, warnings = conn.fetch_youtube(
                api_key=str(params.get("api_key", "")),
                query=str(params.get("query", "")),
                video_id=str(params.get("video_id", "")),
                comments=bool(body.get("comments", True)),
                max_items=max_items,
                max_units=min(int(body.get("max_units", 2000)), 9000),
            )
    except conn.ConnectorError as e:
        raise HTTPException(502, str(e))

    apply = _ethics_hook({"pseudonymize": body.get("pseudonymize", False), **body.get("options", {})})
    finalized = parsers.finalize_drafts(
        drafts, platform=connector, source_ref=f"{connector} API", apply=apply
    )
    media_accepted = media_rejected = 0
    if body.get("download_media", True) and connector == "mastodon":
        urls = [m for d in finalized for m in (d["meta"].get("media") or [])]
        media_accepted, media_rejected = _download_media(urls, project_id)

    stored = _store_drafts(
        finalized,
        project_id=project_id,
        platform=connector,
        source_ref=f"{connector} official API",
        kind="connector",
        label=f"{connector} fetch ({datetime.now(UTC).isoformat(timespec='seconds')})",
        attested=True,
        anonymized=bool(body.get("pseudonymize", False)),
        details={
            "params": {k: v for k, v in params.items() if "secret" not in k.lower() and "key" not in k.lower() and "token" not in k.lower()},
            "warnings": warnings,
            "attestation": ethics.attestation_text(connector, "connector"),
            "credentials_stored": False,
        },
    )
    return {
        "ok": True,
        "connector": connector,
        "imported": stored["post_count"],
        "warnings": warnings,
        "media_registered": media_accepted,
        "media_rejected": media_rejected,
        "source_id": stored["source_id"],
    }


# --------------------------------------------------------------------------- #
# Posts, provenance, summary
# --------------------------------------------------------------------------- #


@router.get("/projects/{project_id}/posts")
async def list_posts(
    project_id: str,
    platform: str = "all",
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    _project_or_404(project_id)
    store = get_store()
    posts = store.list_posts(project_id, platform, limit=limit, offset=offset)
    return {
        "total": store.count_posts(project_id, platform),
        "platform_counts": store.post_platform_counts(project_id),
        "posts": [_public_post(p) for p in posts],
    }


@router.delete("/projects/{project_id}/posts")
async def delete_posts(project_id: str, platform: str = "all") -> dict:
    _project_or_404(project_id)
    n = get_store().delete_posts(project_id, platform)
    return {"deleted": n}


@router.get("/projects/{project_id}/social/summary")
async def social_summary(project_id: str, platform: str = "all") -> dict:
    _project_or_404(project_id)
    store = get_store()
    posts = store.list_posts(project_id, platform)
    platforms = store.post_platform_counts(project_id)
    dated = [p.created_at for p in posts if p.created_at]
    return {
        "total_posts": len(posts),
        "platform_counts": platforms,
        "date_range": [min(dated), max(dated)] if dated else None,
        "sources": [asdict(s) for s in store.list_social_sources(project_id)],
    }


@router.get("/projects/{project_id}/social/sources")
async def social_sources(project_id: str) -> list[dict]:
    _project_or_404(project_id)
    return [asdict(s) for s in get_store().list_social_sources(project_id)]


@router.delete("/projects/{project_id}/social/sources/{source_id}")
async def delete_social_source(project_id: str, source_id: str) -> dict:
    _project_or_404(project_id)
    ok = get_store().delete_social_source(source_id)
    if not ok:
        raise HTTPException(404, "Source record not found")
    return {"deleted": source_id}


# --------------------------------------------------------------------------- #
# Analyses (shared by JSON routes and export routes)
# --------------------------------------------------------------------------- #


def run_analysis(project_id: str, analysis: str, params: dict[str, Any]) -> dict:
    store = get_store()
    platform = str(params.get("platform") or "all")
    posts = store.list_posts(project_id, platform)
    if analysis != "keyness" and not posts:
        raise HTTPException(404, "No posts found for this project/platform filter; import or fetch data first.")
    if analysis == "text-frequency":
        return social_stats.text_frequency(posts, min_count=int(params.get("min_count", 1)))
    if analysis == "text-diversity":
        return social_stats.text_diversity(posts)
    if analysis == "text-ngrams":
        return social_stats.text_ngrams(posts, n=int(params.get("n", 2)), min_count=int(params.get("min_count", 2)))
    if analysis == "text-kwic":
        return social_stats.text_kwic(posts, str(params.get("query", "")), context=int(params.get("context", 6)))
    if analysis == "emoji":
        return social_stats.emoji_stats(posts)
    if analysis == "hashtags":
        return social_stats.hashtag_stats(posts)
    if analysis == "hashtag-network":
        return social_stats.hashtag_cooccurrence(posts, min_joint=int(params.get("min_joint", 2)))
    if analysis == "engagement":
        return social_stats.engagement_stats(posts)
    if analysis == "engagement-keyness":
        return social_stats.engagement_weighted_frequency(posts, min_count=int(params.get("min_count", 1)))
    if analysis == "time-series":
        return social_stats.time_series(posts, bucket=str(params.get("bucket", "month")))
    if analysis == "keyness":
        other = str(params.get("other_project_id") or "")
        if not other or not store.get_project(other):
            raise HTTPException(422, "keyness needs other_project_id (a second project as reference corpus)")
        ref_posts = store.list_posts(other, platform)
        return social_stats.keyness_tokens(posts, ref_posts, min_freq=int(params.get("min_freq", 2)))
    raise HTTPException(404, f"Unknown social analysis: {analysis}")


ANALYSES = (
    "text-frequency", "text-diversity", "text-ngrams", "text-kwic",
    "emoji", "hashtags", "hashtag-network", "engagement",
    "engagement-keyness", "time-series", "keyness",
)


@router.get("/projects/{project_id}/social/{analysis}")
async def social_analysis(project_id: str, analysis: str, request: Request) -> dict:
    _project_or_404(project_id)
    return run_analysis(project_id, analysis, dict(request.query_params))


# --------------------------------------------------------------------------- #
# Exports (CSV / XML / JSON / TSV)
# --------------------------------------------------------------------------- #


def _post_rows(posts: list[Post]) -> list[dict]:
    rows = []
    for p in posts:
        meta = p.meta or {}
        rows.append(
            {
                "id": p.id,
                "platform": p.platform,
                "external_id": p.external_id,
                "author": p.author,
                "text": p.text,
                "language": p.language,
                "created_at": p.created_at,
                "likes": p.likes,
                "comments": p.comments,
                "shares": p.shares,
                "source": p.source,
                "source_ref": p.source_ref,
                "hashtags": ";".join(meta.get("hashtags") or []),
                "mentions": ";".join(meta.get("mentions") or []),
                "urls": ";".join(meta.get("urls") or []),
                "emoji": "".join(meta.get("emoji") or []),
                "media_images": ";".join(meta.get("media_image_ids") or []),
                "ingested_at": p.ingested_at,
            }
        )
    return rows


@router.get("/projects/{project_id}/social-export/posts")
async def export_posts(project_id: str, format: str = "csv", platform: str = "all") -> Response:
    _project_or_404(project_id)
    posts = get_store().list_posts(project_id, platform)
    return _render(_post_rows(posts), format, f"lens-posts-{project_id}")


@router.get("/projects/{project_id}/social-export/{analysis}")
async def export_analysis(project_id: str, analysis: str, request: Request, format: str = "csv") -> Response:
    _project_or_404(project_id)
    params = {k: v for k, v in request.query_params.items() if k != "format"}
    result = run_analysis(project_id, analysis, params)
    return _render_from_result(result, format, f"lens-{analysis}-{project_id}")


def _render(rows: list[dict], format: str, name: str) -> Response:
    from ..export.tabular import render_rows, tabulate

    try:
        meta, rows2 = tabulate(rows)
        content, media_type, filename = render_rows(meta, rows2, format, name)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _render_from_result(result: dict, format: str, name: str) -> Response:
    from ..export.tabular import render_rows, tabulate

    try:
        meta, rows = tabulate(result)
        content, media_type, filename = render_rows(meta, rows, format, name)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
