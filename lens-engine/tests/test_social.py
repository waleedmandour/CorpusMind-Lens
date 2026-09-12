"""Social tab tests (v0.2): parsers, ethics, analytics, storage, API, exports.

No test touches the network: connector tests only exercise validation and
error paths, and every import goes through in-memory fixtures.
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from lens_engine.social import ethics, parsers, social_stats, textutils
from lens_engine.social.connectors import ConnectorError, fetch_reddit, fetch_youtube
from lens_engine.storage.models import Post
from lens_engine.storage.store import Store


# --------------------------------------------------------------------------- #
# textutils
# --------------------------------------------------------------------------- #


def test_emoji_runs_and_flags():
    text = "Great day 🇴🇲 family 👨‍👩‍👧‍👦 done ✅🔥"
    found = textutils.extract_emoji(text)
    assert "🇴🇲" in found
    assert "👨‍👩‍👧‍👦" in found
    assert "🔥" in found
    assert "✅" in found
    # ZWJ family counts once, not seven times
    assert found.count("👨‍👩‍👧‍👦") == 1


def test_hashtags_mentions_urls():
    text = "Loving #CorpusMind and #corpuslinguistics with @dr_waleed at https://example.org/x?a=1"
    assert textutils.extract_hashtags(text) == ["CorpusMind", "corpuslinguistics"]
    assert textutils.extract_mentions(text) == ["dr_waleed"]
    assert textutils.extract_urls(text) == ["https://example.org/x?a=1"]


def test_tokens_english_and_arabic():
    toks = textutils.tokens("Hello world! #Tag @user https://x.y أهلا بالعالم")
    assert "hello" in toks and "world" in toks and "tag" in toks
    assert "أهلا" in toks and "بالعالم" in toks
    assert all("@" not in t and "http" not in t for t in toks)


def test_platform_time_x_format():
    iso = textutils.parse_platform_time("Tue Mar 03 15:34:12 +0000 2020")
    assert iso.startswith("2020-03-03T15:34:12")
    assert textutils.parse_platform_time("1700000000").startswith("2023-")
    assert textutils.parse_platform_time("") == ""


# --------------------------------------------------------------------------- #
# ethics
# --------------------------------------------------------------------------- #


def test_pseudonymize_is_deterministic_and_salting():
    a = ethics.pseudonymize_handle("Waleed", salt="s1")
    b = ethics.pseudonymize_handle("waleed ", salt="s1")
    c = ethics.pseudonymize_handle("Waleed", salt="s2")
    assert a == b and a != c and a.startswith("user_")


def test_redaction():
    out = ethics.redact_text(
        "contact me at a@b.com or +968 9123 4567 ok 5 times",
        emails=True, phones=True, urls=False, mentions=True,
    )
    assert "a@b.com" not in out and "[email]" in out
    assert "9123 4567" not in out and "[phone]" in out
    assert "5 times" in out  # small numbers survive
    assert ethics.redact_text("go https://secret.tld/x", emails=False, phones=False, urls=True) == "go [url]"


# --------------------------------------------------------------------------- #
# parsers
# --------------------------------------------------------------------------- #


def _x_zip_bytes() -> bytes:
    tweet = {
        "tweet": {
            "id_str": "1234567890",
            "created_at": "Tue Mar 03 15:34:12 +0000 2020",
            "full_text": "Great day at the conference #NLP @speaker https://t.co/abc 😀",
            "favorite_count": 12,
            "reply_count": 2,
            "retweet_count": 3,
            "quote_count": 1,
            "lang": "en",
            "user_id_str": "9999",
        }
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/tweet.js", "window.YTD.tweet.part0 = " + json.dumps([tweet]))
        zf.writestr("data/tweets_media/1234567890-0.jpg", b"\xff\xd8\xff\xe0FAKEJPG")
    return buf.getvalue()


def test_x_archive_zip_parsing_with_media():
    bundle = parsers.ArchiveBundle(data=_x_zip_bytes())
    try:
        drafts = parsers.parse_x_archive(bundle)
        assert len(drafts) == 1
        d = drafts[0]
        assert d["external_id"] == "1234567890"
        assert "#NLP" in d["text"]
        assert d["likes"] == 12 and d["shares"] == 4
        assert d["media"] and "1234567890" in d["media"][0]
    finally:
        bundle.close()


def test_generic_csv_mapping():
    csv_data = (
        "tweet_id,user_name,created_at,text,favorite_count,reply_count\n"
        "1,alice,2024-01-15 10:00:00,Hello world #hi,5,1\n"
        "2,bob,2024-01-16T11:00:00Z,Second post,0,0\n"
    ).encode()
    drafts = parsers.parse_csv(csv_data)
    assert len(drafts) == 2
    assert drafts[0]["external_id"] == "1"
    assert drafts[0]["author"] == "alice"
    assert drafts[0]["likes"] == 5
    assert drafts[1]["created_at"].startswith("2024-01-16T11:00")


def test_jsonl_mapping():
    lines = "\n".join(
        json.dumps(o)
        for o in [
            {"id": "a", "author": "x", "created_at": "2024-02-01T00:00:00Z", "text": "One two"},
            {"id": "b", "user": "y", "text": "Three"},
        ]
    ).encode()
    drafts = parsers.parse_jsonl(lines)
    assert len(drafts) == 2 and drafts[1]["author"] == "y"


def test_finalize_harvests_and_applies_ethics():
    drafts = [
        parsers.draft(
            external_id="1", author="waleed", text="Email me a@b.com #tag 😀",
            created_at="Tue Mar 03 15:34:12 +0000 2020",
        )
    ]
    apply = lambda t, a: ethics.apply_ethics(t, a, salt="s", pseudonymize=True)
    rows = parsers.finalize_drafts(drafts, platform="x", source_ref="test", apply=apply)
    assert rows[0]["meta"]["hashtags"] == ["tag"]
    assert rows[0]["meta"]["emoji"] == ["😀"]
    assert rows[0]["author"].startswith("user_")
    assert "[email]" in rows[0]["text"]
    assert rows[0]["created_at"].startswith("2020-03-03")


# --------------------------------------------------------------------------- #
# social_stats
# --------------------------------------------------------------------------- #


def _posts() -> list[Post]:
    def mk(pid: str, text: str, likes: int = 0, platform: str = "x", tags: list[str] | None = None):
        return Post(
            id=pid, project_id="p1", platform=platform, text=text, likes=likes,
            created_at=f"2024-01-{10 + int(pid)}T00:00:00+00:00",
            meta={"hashtags": tags or textutils.extract_hashtags(text),
                  "emoji": textutils.extract_emoji(text)},
        )

    return [
        mk("1", "Love this #nlp #corpus 😀", likes=10),
        mk("2", "Love this field #nlp", likes=0),
        mk("3", "أهلاً بالعالم #عربي", likes=5, platform="mastodon"),
    ]


def test_text_frequency_and_diversity():
    posts = _posts()
    f = social_stats.text_frequency(posts)
    assert f["tokens"] > 6 and f["profile"][0]["word"] == "love"
    d = social_stats.text_diversity(posts)
    assert 0 < d["ttr"] <= 1 and d["tokens"] == f["tokens"]


def test_emoji_and_hashtag_stats():
    posts = _posts()
    e = social_stats.emoji_stats(posts)
    assert e["total_emoji"] == 1 and e["profile"][0]["emoji"] == "😀"
    h = social_stats.hashtag_stats(posts)
    assert h["profile"][0]["hashtag"] == "#nlp" and h["profile"][0]["count"] == 2
    net = social_stats.hashtag_cooccurrence(posts, min_joint=1)
    pairs = {(e["a"], e["b"]) for e in net["edges"]}
    assert ("#corpus", "#nlp") in pairs


def test_engagement_and_keyness():
    posts = _posts()
    eng = social_stats.engagement_stats(posts)
    assert eng["likes"]["total"] == 15
    assert eng["top_posts"][0]["engagement"] == 10
    kw = social_stats.engagement_weighted_frequency(posts)
    assert kw["profile"][0]["word"] == "love"
    key = social_stats.keyness_tokens(posts[:1], posts[1:], min_freq=1)
    assert key["rows"] and "log_likelihood" in key["rows"][0]


def test_time_series():
    ts = social_stats.time_series(_posts(), bucket="day")
    assert len(ts["points"]) == 3


# --------------------------------------------------------------------------- #
# storage + API
# --------------------------------------------------------------------------- #


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "t.sqlite3")


def test_store_posts_roundtrip(store):
    proj = store.create_project("Proj")
    posts = _posts()
    for p in posts:
        p.project_id = proj.id
    store.add_posts(posts)
    assert store.count_posts(proj.id) == 3
    assert store.count_posts(proj.id, "mastodon") == 1
    got = store.list_posts(proj.id)
    assert [g.id for g in got] == ["1", "2", "3"]  # chronological reading order
    assert store.delete_posts(proj.id, "x") == 2
    assert store.count_posts(proj.id) == 1


def test_store_social_sources(store):
    from lens_engine.storage.models import SocialSource

    proj = store.create_project("Proj")
    store.add_social_source(SocialSource(id="s1", project_id=proj.id, platform="x", kind="import",
                                         label="archive.zip", attested=True, post_count=5))
    srcs = store.list_social_sources(proj.id)
    assert len(srcs) == 1 and srcs[0].attested and srcs[0].post_count == 5


def test_api_social_flow(app_client):  # app_client fixture from conftest
    client = app_client
    # project
    pid = client.post("/api/v1/projects", json={"name": "SocialProj"}).json()["id"]
    # attestation is required
    r = client.post(
        f"/api/v1/projects/{pid}/social/import",
        files={"file": ("posts.csv", b"text,created_at\nhi,2024-01-01 00:00:00\n", "text/csv")},
        data={"source": "csv", "options": json.dumps({"attested": False})},
    )
    assert r.status_code == 422
    # CSV import with attestation
    csv_bytes = (
        "id,author,created_at,text,likes\n"
        "1,alice,2024-01-01T00:00:00Z,Hello #corpus world 😀,7\n"
        "2,bob,2024-02-01T00:00:00Z,Second post about #corpus,3\n"
    ).encode()
    r = client.post(
        f"/api/v1/projects/{pid}/social/import",
        files={"file": ("posts.csv", csv_bytes, "text/csv")},
        data={"source": "csv", "options": json.dumps({"attested": True, "pseudonymize": True})},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["platform"] == "generic" and body["imported"] == 2

    # listing
    r = client.get(f"/api/v1/projects/{pid}/posts")
    assert r.json()["total"] == 2
    first = r.json()["posts"][0]
    assert first["meta"]["hashtags"] == ["corpus"]
    assert first["author"].startswith("user_")  # pseudonymised before storage

    # analyses
    for path, check in {
        "text-frequency": lambda d: d["profile"][0]["word"] == "corpus",
        "emoji": lambda d: d["total_emoji"] == 1,
        "hashtags": lambda d: d["profile"][0]["count"] == 2,
        "engagement": lambda d: d["likes"]["total"] == 10,
        "text-diversity": lambda d: d["tokens"] == 7,
        "text-ngrams?min_count=1": lambda d: d["profile"][0]["ngram"] == "hello corpus",
        "time-series": lambda d: len(d["points"]) == 2,
    }.items():
        r = client.get(f"/api/v1/projects/{pid}/social/{path}")
        assert r.status_code == 200, (path, r.text)
        assert check(r.json()), analysis

    # summary + sources
    summary = client.get(f"/api/v1/projects/{pid}/social/summary").json()
    assert summary["total_posts"] == 2 and summary["sources"][0]["attested"]

    # exports: CSV and XML both valid
    r = client.get(f"/api/v1/projects/{pid}/social-export/posts?format=csv")
    assert "text/csv" in r.headers["content-type"]
    assert "hashtags" in r.text and "alice" not in r.text  # pseudonymised
    r = client.get(f"/api/v1/projects/{pid}/social-export/hashtags?format=xml")
    assert "<result" in r.text and "#corpus" in r.text
    import xml.etree.ElementTree as ET

    ET.fromstring(r.text)  # well-formed
    r = client.get(f"/api/v1/projects/{pid}/social-export/engagement?format=tsv")
    assert "\t" in r.text


def test_api_requires_tos_for_connectors(app_client):
    client = app_client
    pid = client.post("/api/v1/projects", json={"name": "C"}).json()["id"]
    r = client.post(f"/api/v1/projects/{pid}/social/fetch",
                    json={"connector": "reddit", "acknowledge_tos": False, "params": {}})
    assert r.status_code == 422
    r = client.post(f"/api/v1/projects/{pid}/social/fetch",
                    json={"connector": "nope", "acknowledge_tos": True, "params": {}})
    assert r.status_code == 422
    r = client.post(f"/api/v1/projects/{pid}/social/fetch",
                    json={"connector": "reddit", "acknowledge_tos": True,
                          "params": {"client_id": "", "client_secret": "", "subreddit": "linguistics"}})
    assert r.status_code == 502  # connector validation error, no network attempted for fetch


def test_connector_validation_errors_without_network():
    with pytest.raises(ConnectorError):
        fetch_reddit(client_id="", client_secret="", subreddit="x")
    with pytest.raises(ConnectorError):
        fetch_reddit(client_id="id", client_secret="sec", subreddit="")
    with pytest.raises(ConnectorError):
        fetch_youtube(api_key="", query="x")
    with pytest.raises(ConnectorError):
        fetch_youtube(api_key="k", query="", video_id="")


# --------------------------------------------------------------------------- #
# tabular export
# --------------------------------------------------------------------------- #


def test_tabulate_and_xml():
    from lens_engine.export.tabular import render_rows, tabulate

    result = {"dimension": "x", "tokens": 5, "profile": [{"category": "a", "count": 3}, {"category": "b", "count": 2}]}
    meta, rows = tabulate(result)
    assert meta["dimension"] == "x" and len(rows) == 2
    content, mtype, fname = render_rows(meta, rows, "xml", "test")
    assert fname.endswith(".xml")
    import xml.etree.ElementTree as ET

    ET.fromstring(content)
    content, mtype, fname = render_rows(meta, rows, "csv", "test")
    assert content.startswith("﻿") and "category,count" in content
    meta2, rows2 = tabulate([{"a": 1}, {"a": 2}])
    assert len(rows2) == 2
