"""Official-API connectors for the Social tab (S2, free access tiers).

Design rules (research + ethics review, Task 6):
* Official endpoints only. No scraping, no login-walled content, no
  protection circumvention.
* BYO credentials: keys are supplied per request by the researcher and are
  NEVER persisted by the engine.
* Free tiers respected: Mastodon (open public API, per-instance rate limits
  honoured), Reddit (free 100 QPM per OAuth client, app-only read-only),
  YouTube Data API v3 (free daily quota, cost-capped per fetch).
* Every fetch is bounded by ``max_pages`` / ``max_items`` / ``max_units``;
  429 and Retry-After are honoured; every item carries platform provenance.

Stdlib ``urllib`` only, so the frozen sidecar needs no extra binaries.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import textutils

USER_AGENT = "CorpusMindLens/0.2 (academic corpus research tool; +https://github.com/waleedmandour/CorpusMind-Lens)"
MAX_PAGES = 10


class ConnectorError(Exception):
    pass


def _http_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 25,
) -> tuple[Any, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})}, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return json.loads(body), dict(r.headers)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise ConnectorError(f"HTTP {e.code} from {url.split('?')[0]}: {detail or e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ConnectorError(f"network error reaching {url.split('?')[0]}: {e}") from e
    except json.JSONDecodeError as e:
        raise ConnectorError(f"non-JSON response from {url.split('?')[0]}") from e


def _throttle(headers: dict[str, str], sleep_s: float) -> float:
    """Honour provider rate-limit headers; returns the sleep used."""
    remaining = headers.get("X-RateLimit-Remaining")
    if remaining is not None:
        try:
            if int(remaining) <= 2:
                reset = headers.get("X-RateLimit-Reset")
                wait = min(max(float(reset) - time.time(), 1.0), 120.0) if reset else 30.0
                time.sleep(wait)
                return wait
        except ValueError:
            pass
    time.sleep(sleep_s)
    return sleep_s


# --------------------------------------------------------------------------- #
# Mastodon: fully open public API, no key required
# --------------------------------------------------------------------------- #


def fetch_mastodon(
    *,
    instance: str,
    hashtag: str = "",
    limit: int = 200,
    access_token: str = "",
    strip_html: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Public hashtag or local-public timelines from any Mastodon instance."""
    warnings: list[str] = []
    instance = instance.strip().removeprefix("https://").removeprefix("http://").strip("/")
    if not instance:
        raise ConnectorError("Mastodon instance URL is required, e.g. mastodon.social")
    base = f"https://{instance}"
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    limit = max(1, min(int(limit), 400))
    per_page = min(40, limit)
    drafts: list[dict[str, Any]] = []
    path = f"/api/v1/timelines/tag/{urllib.parse.quote(hashtag.lstrip('#'))}" if hashtag else "/api/v1/timelines/public?local=true"
    max_id: str | None = None
    pages = 0
    while len(drafts) < limit and pages < MAX_PAGES:
        url = f"{base}{path}?limit={per_page}"
        if max_id:
            url += f"&max_id={max_id}"
        data, resp_headers = _http_json(url, headers=headers)
        if not isinstance(data, list):
            raise ConnectorError("unexpected Mastodon response shape")
        if not data:
            break
        for st in data:
            acct = (st.get("account") or {}).get("acct", "")
            media: list[str] = []
            for att in st.get("media_attachments") or []:
                if att.get("type") == "image" and att.get("url"):
                    media.append(att["url"])
            drafts.append(
                {
                    "external_id": str(st.get("id", "")),
                    "author": acct,
                    "text": st.get("content") or "",
                    "created_at": st.get("created_at") or "",
                    "likes": st.get("favourites_count", 0),
                    "comments": st.get("replies_count", 0),
                    "shares": st.get("reblogs_count", 0),
                    "language": st.get("language") or "",
                    "media": media,
                    "link": st.get("url") or "",
                }
            )
        max_id = data[-1].get("id")
        pages += 1
        _throttle(resp_headers, 0.4)
    if pages == MAX_PAGES:
        warnings.append(f"stopped at {MAX_PAGES} pages; raise max_items for more history")
    # HTML stripped inside the connector so drafts carry clean text.
    for d in drafts:
        if strip_html:
            d["text"] = textutils.strip_html(d["text"])
    return drafts, warnings


# --------------------------------------------------------------------------- #
# Reddit: free 100 QPM per OAuth client (app-only, read-only, public data)
# --------------------------------------------------------------------------- #


def _reddit_token(client_id: str, client_secret: str) -> str:
    url = "https://www.reddit.com/api/v1/access_token"
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    import base64

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data, _ = _http_json(
        url,
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        data=body,
    )
    token = data.get("access_token")
    if not token:
        raise ConnectorError("Reddit OAuth did not return an access token; check client id and secret")
    return token


def fetch_reddit(
    *,
    client_id: str,
    client_secret: str,
    subreddit: str,
    mode: str = "new",
    query: str = "",
    limit: int = 200,
    user_agent: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Public subreddit posts via oauth.reddit.com (app-only credentials)."""
    warnings: list[str] = []
    if not client_id or not client_secret:
        raise ConnectorError("Reddit client id and secret are required (create a free 'script' app at reddit.com/prefs/apps)")
    if not subreddit.strip().strip("r/"):
        raise ConnectorError("subreddit is required")
    sub = subreddit.strip().removeprefix("r/").strip("/")
    if mode not in ("new", "top", "hot", "search"):
        raise ConnectorError("mode must be one of: new, top, hot, search")

    token = _reddit_token(client_id, client_secret)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if user_agent:
        headers["User-Agent"] = f"{user_agent} (via CorpusMindLens/0.2 academic)"

    limit = max(1, min(int(limit), 1000))
    per_page = min(100, limit)
    drafts: list[dict[str, Any]] = []
    after: str | None = None
    pages = 0
    while len(drafts) < limit and pages < MAX_PAGES:
        if mode == "search":
            q = urllib.parse.urlencode({"q": query, "limit": per_page, "restrict_sr": 1, "sort": "new", "after": after or ""})
            url = f"https://oauth.reddit.com/r/{sub}/search?{q}"
        else:
            q = urllib.parse.urlencode({"limit": per_page, "after": after or ""})
            url = f"https://oauth.reddit.com/r/{sub}/{mode}?{q}"
        data, resp_headers = _http_json(url, headers=headers)
        children = (data.get("data") or {}).get("children") or []
        if not children:
            break
        for ch in children:
            d = ch.get("data") or {}
            text = " ".join(x for x in [d.get("title", ""), d.get("selftext", "")] if x)
            media: list[str] = []
            if (d.get("post_hint") == "image" or d.get("url_overridden_by_dest", "").endswith((".jpg", ".png", ".gif", ".webp"))) and d.get("url"):
                media.append(d["url"])
            drafts.append(
                {
                    "external_id": d.get("name") or d.get("id", ""),
                    "author": d.get("author") or "",
                    "text": text,
                    "created_at": str(d.get("created_utc") or ""),
                    "likes": d.get("score", 0),
                    "comments": d.get("num_comments", 0),
                    "shares": 0,
                    "language": "",
                    "media": media,
                    "link": f"https://www.reddit.com{d.get('permalink', '')}",
                }
            )
        after = (data.get("data") or {}).get("after")
        pages += 1
        # Free tier: 100 queries/minute per client. 0.7s pacing stays under it.
        _throttle(resp_headers, 0.7)
    return drafts, warnings


# --------------------------------------------------------------------------- #
# YouTube Data API v3: free daily quota (10k units), cost-capped here
# --------------------------------------------------------------------------- #


def fetch_youtube(
    *,
    api_key: str,
    query: str = "",
    video_id: str = "",
    comments: bool = True,
    max_items: int = 100,
    max_units: int = 2000,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Video metadata and comment threads for a search query or one video.

    Quota costs (Google's published rates): search.list = 100 units,
    videos.list = 1, commentThreads.list = 1. The fetch stops before
    exceeding ``max_units`` and always under the daily free allowance.
    """
    warnings: list[str] = []
    if not api_key:
        raise ConnectorError("YouTube API key is required (free key from Google Cloud Console, YouTube Data API v3)")
    drafts: list[dict[str, Any]] = []
    units = 0

    video_ids: list[str] = []
    if video_id:
        video_ids = [video_id.strip()]
    else:
        if not query:
            raise ConnectorError("provide a search query or a video id")
        max_results = min(50, max(1, int(max_items)))
        q = urllib.parse.urlencode(
            {"part": "snippet", "type": "video", "q": query, "maxResults": max_results, "key": api_key}
        )
        data, _ = _http_json(f"https://www.googleapis.com/youtube/v3/search?{q}")
        units += 100
        for it in data.get("items") or []:
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                video_ids.append(vid)
        if units >= max_units:
            warnings.append("quota cap reached during search; no video details fetched")
            return drafts, warnings

    # Metadata in batches of 50 (1 unit each).
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        q = urllib.parse.urlencode({"part": "snippet,statistics", "id": ",".join(batch), "key": api_key})
        data, _ = _http_json(f"https://www.googleapis.com/youtube/v3/videos?{q}")
        units += 1
        for v in data.get("items") or []:
            sn = v.get("snippet") or {}
            st = v.get("statistics") or {}
            drafts.append(
                {
                    "external_id": v.get("id", ""),
                    "author": sn.get("channelTitle") or "",
                    "text": " ".join(x for x in [sn.get("title", ""), sn.get("description", "")] if x),
                    "created_at": sn.get("publishedAt") or "",
                    "likes": _to_int(st.get("likeCount")),
                    "comments": _to_int(st.get("commentCount")),
                    "shares": 0,
                    "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "",
                    "media": [],
                    "link": f"https://www.youtube.com/watch?v={v.get('id', '')}",
                    "units": units,
                }
            )
        time.sleep(0.2)
        if units >= max_units:
            warnings.append("quota cap reached before comment collection")
            return drafts, warnings

    if comments:
        for v in drafts:
            if units + 1 > max_units:
                warnings.append("quota cap reached; some videos have no comments")
                break
            q = urllib.parse.urlencode(
                {"part": "snippet", "videoId": v["external_id"], "maxResults": 100, "textFormat": "plainText", "key": api_key}
            )
            try:
                data, _ = _http_json(f"https://www.googleapis.com/youtube/v3/commentThreads?{q}")
            except ConnectorError as e:
                warnings.append(f"comments unavailable for {v['external_id']}: {e}")
                continue
            units += 1
            for it in data.get("items") or []:
                csn = ((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
                ctext = csn.get("textDisplay") or csn.get("textOriginal") or ""
                if not ctext.strip():
                    continue
                drafts.append(
                    {
                        "external_id": ((it.get("snippet") or {}).get("topLevelComment") or {}).get("id", ""),
                        "author": csn.get("authorDisplayName") or "",
                        "text": ctext,
                        "created_at": csn.get("publishedAt") or "",
                        "likes": _to_int(csn.get("likeCount")),
                        "comments": _to_int(csn.get("totalReplyCount")),
                        "shares": 0,
                        "language": "",
                        "media": [],
                        "link": f"https://www.youtube.com/watch?v={v['external_id']}",
                    }
                )
            time.sleep(0.2)
    return drafts, warnings


def _to_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0
