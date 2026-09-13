"""v0.3 engine additions: Text Analysis (concordancer, collocations, n-grams,
dispersion, word sketch, reference keyness, stoplists), the default-model
picker and the local-model troubleshoot interpretation."""
from __future__ import annotations

import pytest

from lens_engine.main import get_store
from lens_engine.models_defaults import effective_model
from lens_engine.storage.models import Image

from .conftest import app_client  # noqa: F401  (fixture import)

DOCS = [
    "BIG SALE TODAY best prices in town",
    "big sale tomorrow early birds save more",
    "weather report rain all week long",
    "big sale today only best deals everywhere",
]


@pytest.fixture()
def text_set(app_client):
    """A project + image set seeded with OCR text, ready status, no pipeline."""
    import uuid

    tag = uuid.uuid4().hex[:6]
    pid = app_client.post("/api/v1/projects", json={"name": f"TextP-{tag}"}).json()["id"]
    sid = app_client.post("/api/v1/imagesets",
                          json={"project_id": pid, "name": "TextS"}).json()["id"]
    store = get_store()
    for i, text in enumerate(DOCS):
        store.add_image(Image(
            id=f"txt-{tag}-{i}", image_set_id=sid, filename=f"doc{i}.png",
            storage_path="unused", status="ready",
            meta={"ocr": {"text": text, "words": []}},
        ))
    return pid, sid


# --- Stoplists ---------------------------------------------------------------

def test_stoplist_crud_roundtrip(app_client, text_set):
    pid, _sid = text_set
    r = app_client.post(f"/api/v1/projects/{pid}/stoplists",
                        json={"name": "my-stops", "items": ["sale", "prices"]})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "my-stops" and sorted(body["items"]) == ["prices", "sale"]

    listing = app_client.get(f"/api/v1/projects/{pid}/stoplists").json()
    assert any(s["name"] == "builtin-en" for s in listing["built_in"])
    assert any(s["name"] == "my-stops" for s in listing["custom"])

    # update
    r = app_client.put(f"/api/v1/projects/{pid}/stoplists/my-stops",
                       json={"name": "my-stops", "items": ["sale"]})
    assert r.json()["items"] == ["sale"]

    # built-in names are reserved for customs
    r = app_client.post(f"/api/v1/projects/{pid}/stoplists",
                        json={"name": "builtin-x", "items": []})
    assert r.status_code == 422

    # delete
    assert app_client.delete(f"/api/v1/projects/{pid}/stoplists/my-stops").status_code == 200
    assert app_client.delete(f"/api/v1/projects/{pid}/stoplists/my-stops").status_code == 404


def test_wordlist_stoplist_resolution(app_client, text_set):
    _pid, sid = text_set
    # default (builtin) removes "in"/"the"-class words but keeps content
    body = app_client.get(f"/api/v1/imagesets/{sid}/text/wordlist").json()
    words = {it["word"] for it in body["items"]}
    assert "sale" in words and "big" in words
    # builtin-none keeps stopwords
    body_none = app_client.get(f"/api/v1/imagesets/{sid}/text/wordlist?stoplist=builtin-none").json()
    words_none = {it["word"] for it in body_none["items"]}
    assert "in" in words_none and "all" in words_none
    # custom list can hide "sale"
    pid, _ = text_set
    app_client.post(f"/api/v1/projects/{pid}/stoplists",
                    json={"name": "nosale", "items": ["sale"]})
    body_c = app_client.get(f"/api/v1/imagesets/{sid}/text/wordlist?stoplist=nosale").json()
    assert "sale" not in {it["word"] for it in body_c["items"]}
    # unknown list → 404
    assert app_client.get(
        f"/api/v1/imagesets/{sid}/text/wordlist?stoplist=missing").status_code == 404


# --- Concordancer 2.0 ----------------------------------------------------------

def test_concordance_substring_metadata_and_sort(app_client, text_set):
    _pid, sid = text_set
    r = app_client.get(f"/api/v1/imagesets/{sid}/text/concordance",
                       params={"query": "sale"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    hit = body["hits"][0]
    assert hit["image_id"].startswith("txt-")
    assert hit["image"].startswith("doc")
    assert isinstance(hit["position"], int)
    assert hit["node"] == "sale"
    assert isinstance(hit["left"], list) and isinstance(hit["right"], list)

    # L1 sort orders on the first left neighbour (bird/best/big here)
    r2 = app_client.get(f"/api/v1/imagesets/{sid}/text/concordance",
                        params={"query": "sale", "sort": "L1"})
    lefts = [h["left"][-1] for h in r2.json()["hits"] if h["left"]]
    assert lefts == sorted(lefts, key=str.lower)


def test_concordance_regex_and_export(app_client, text_set):
    _pid, sid = text_set
    r = app_client.get(f"/api/v1/imagesets/{sid}/text/concordance",
                       params={"query": r"\bsav(e|es|ing)", "regex": True})
    body = r.json()
    assert body["total"] >= 1 and body["regex"] is True

    bad = app_client.get(f"/api/v1/imagesets/{sid}/text/concordance",
                         params={"query": "([", "regex": True})
    assert bad.status_code == 422

    exp = app_client.get(f"/api/v1/imagesets/{sid}/text/concordance/export",
                         params={"query": "sale", "format": "csv"})
    assert exp.status_code == 200
    assert b"node" in exp.content and b"sale" in exp.content


# --- Collocations --------------------------------------------------------------

def test_collocations_statistics(app_client, text_set):
    _pid, sid = text_set
    r = app_client.get(f"/api/v1/imagesets/{sid}/text/collocations",
                       params={"node": "sale", "span": 4, "min_freq": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["node_freq"] == 3
    rows = {row["word"]: row for row in body["rows"]}
    assert "big" in rows and rows["big"]["O"] == 3
    # every measure present and finite
    for w, row in rows.items():
        assert {"mi", "t_score", "log_likelihood", "log_dice", "delta_p"} <= set(row)
    # edges carry the network payload
    assert body["edges"] and body["edges"][0]["source"] == "sale"

    # freq ranking sorts descending on O
    r2 = app_client.get(f"/api/v1/imagesets/{sid}/text/collocations",
                        params={"node": "sale", "metric": "freq", "min_freq": 1})
    os_ = [row["O"] for row in r2.json()["rows"]]
    assert os_ == sorted(os_, reverse=True)


# --- N-grams / bundles ---------------------------------------------------------

def test_ngrams_counts_and_dispersion(app_client, text_set):
    _pid, sid = text_set
    r = app_client.get(f"/api/v1/imagesets/{sid}/text/ngrams",
                       params={"n": 2, "min_count": 2})
    body = r.json()
    grams = {tuple(g["gram"]): g for g in body["rows"]}
    assert ("big", "sale") in grams and grams[("big", "sale")]["count"] == 3
    row = grams[("big", "sale")]
    assert 0.0 <= row["juillands_d"] <= 1.0
    assert 0.0 <= row["gries_dp"] <= 1.0
    assert row["range"] == 3  # appears in docs 0, 1, 3

    assert app_client.get(f"/api/v1/imagesets/{sid}/text/ngrams",
                          params={"n": 9}).status_code == 422


# --- Dispersion gallery ---------------------------------------------------------

def test_dispersion_gallery(app_client, text_set):
    _pid, sid = text_set
    body = app_client.get(f"/api/v1/imagesets/{sid}/text/dispersion").json()
    assert body["bins"] == 4
    rows = {r["word"]: r for r in body["rows"]}
    assert rows["sale"]["range"] == 3
    assert rows["weather"]["range"] == 1
    assert rows["weather"]["gries_dp"] > rows["sale"]["gries_dp"]


# --- Word sketch (visual edition) ----------------------------------------------

def test_word_sketch_shape(app_client, text_set):
    _pid, sid = text_set
    body = app_client.get(f"/api/v1/imagesets/{sid}/text/sketch",
                          params={"word": "sale"}).json()
    assert body["freq"] == 3 and body["images_with_token"] == 3
    assert any(c["word"] == "big" for c in body["collocates"])
    assert body["concordance_sample"]
    vc = body["visual_copatterns"]
    assert {"dominant_colours", "annotation_values", "detected_objects"} <= set(vc)

    # absent word → zeros, not an error
    body0 = app_client.get(f"/api/v1/imagesets/{sid}/text/sketch",
                           params={"word": "zebra"}).json()
    assert body0["freq"] == 0 and body0["images_with_token"] == 0


# --- Reference keyness ----------------------------------------------------------

def test_references_listing_and_keyness(app_client, text_set):
    _pid, sid = text_set
    refs = app_client.get(f"/api/v1/imagesets/{sid}/text/references").json()["references"]
    ids = {r["id"] for r in refs}
    assert "be06-freq-top1000" in ids and "camel-arabic-top1000" in ids

    body = app_client.get(f"/api/v1/imagesets/{sid}/text/keyness-reference",
                          params={"reference": "leipzig-english-news-top100"}).json()
    assert body["N1"] > 0 and body["N2"] > 0
    terms = {r["term"]: r for r in body["rows"]}
    # "sale" is highly distinctive against a news reference: strong LL, and a
    # Log Ratio of +infinity (absent from the reference) renders as null on
    # the JSON wire — non-finite floats are null (same as set-vs-set keyness).
    assert terms["sale"]["f2"] == 0
    assert terms["sale"]["log_likelihood"] > 0
    lr = terms["sale"]["log_ratio"]
    assert lr is None or lr > 0
    assert "chi2_min_expected" in terms["sale"]

    missing = app_client.get(f"/api/v1/imagesets/{sid}/text/keyness-reference",
                             params={"reference": "nope"})
    assert missing.status_code == 404


# --- Default model picker ---------------------------------------------------------

def test_model_defaults_get_put_and_effective(app_client):
    snap = app_client.get("/api/v1/settings/models").json()
    assert snap["vision_ocr_model"] and snap["embed_model"] and snap["chat_model"]
    assert "overrides" in snap and "env_defaults" in snap

    r = app_client.put("/api/v1/settings/models",
                       json={"chat_model": "qwen2.5:7b", "embed_model": "bge-m3"})
    assert r.json()["saved"] is True

    snap2 = app_client.get("/api/v1/settings/models").json()
    assert snap2["chat_model"] == "qwen2.5:7b"
    assert snap2["overrides"]["chat"] == "qwen2.5:7b"
    # embed requested the same value as the env default → recorded as override
    assert effective_model("chat") == "qwen2.5:7b"

    # clear override → back to env/built-in default
    app_client.put("/api/v1/settings/models", json={"clear": ["chat"]})
    assert effective_model("chat") == "llama3.1"


# --- Smart Troubleshooting (local interpretation) ---------------------------------

def test_troubleshoot_status_and_honest_unavailable(app_client, monkeypatch):
    status = app_client.get("/api/v1/troubleshoot/status").json()
    assert {"available", "backend", "models"} <= set(status)

    # No Ollama in CI: probe fails → honest unavailable verdict, never a 500
    from lens_engine.ai.providers import OllamaProvider, LMStudioProvider

    async def _down(self):
        return False

    monkeypatch.setattr(OllamaProvider, "health", _down)
    monkeypatch.setattr(LMStudioProvider, "health", _down)

    r = app_client.post("/api/v1/troubleshoot/interpret", json={
        "error_message": "HTTP 500: internal error on /api/v1/imagesets/x/battery",
        "error_code": 500, "endpoint": "/api/v1/imagesets/x/battery",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["suggested_fix"]  # points the user at Settings, AI backend


def test_troubleshoot_parses_local_verdict(app_client, monkeypatch):
    from lens_engine.ai.providers import ChatResponse, OllamaProvider

    async def _up(self):
        return True

    async def _models(self):
        return ["llama3.1:8b", "bge-m3"]

    async def _chat(self, messages, *, model, temperature=0.2, tools=None):
        return ChatResponse(content=(
            '{"severity": "warning", "plain_language": "The image set is empty.", '
            '"likely_cause": "No images were uploaded yet.", '
            '"suggested_fix": "Upload images on the Images page.", '
            '"should_report": false}'),
            model=model, provider="ollama")

    monkeypatch.setattr(OllamaProvider, "health", _up)
    monkeypatch.setattr(OllamaProvider, "list_models", _models)
    monkeypatch.setattr(OllamaProvider, "chat", _chat)

    body = app_client.post("/api/v1/troubleshoot/interpret", json={
        "error_message": "Nothing to export",
    }).json()
    assert body["available"] is True
    assert body["model"] == "llama3.1:8b"  # embedding models skipped
    assert body["severity"] == "warning"
    assert body["should_report"] is False
