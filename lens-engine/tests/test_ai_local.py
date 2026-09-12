"""v0.2 local-AI backend tests: model catalog fit scoring, HF search
contract (mocked), /ai/local/* endpoints, semantic search honesty, and
vision-model OCR fallback paths.

The local-first discipline applies here too: when no Ollama is present the
endpoints must FAIL LOUDLY (409) with a setup hint — never silently return
fake results.
"""
from __future__ import annotations

import asyncio
import base64

from lens_engine.ai import catalog as C
from lens_engine.vision.ocr import run_vision_ocr
from tests.conftest import make_png

SPECS_BIG = {"ram_gb": 32.0, "gpus": [{"name": "RTX 4090", "vram_gb": 24.0}]}
SPECS_MID = {"ram_gb": 16.0, "gpus": []}
SPECS_SMALL = {"ram_gb": 8.0, "gpus": []}
SPECS_NONE = {"ram_gb": None, "gpus": []}


# --- Fit scoring ---------------------------------------------------------------

def test_fit_gpu_when_vram_covers():
    entry = C.CURATED[0]  # qwen2.5vl:3b — needs ~6 GB VRAM
    badge = C.fit_badge(entry.size_gb, entry.ram_gb, entry.vram_gb, SPECS_BIG)
    assert badge["fit"] == "gpu"


def test_fit_cpu_when_ram_headroom():
    # llama3.2:3b (8 GB RAM est) on a 16 GB RAM machine without a GPU
    assert C.fit_badge(2.0, 8, 4, SPECS_MID)["fit"] == "cpu"


def test_fit_tight_and_too_big():
    # llava:7b (12 GB RAM est) on 16 GB RAM → over 1.05× but under 1.35× headroom
    assert C.fit_badge(4.7, 12, 6, SPECS_MID)["fit"] == "tight"
    # qwen2.5vl:7b (16 GB RAM est) on an 8 GB machine → will crawl
    assert C.fit_badge(6.0, 16, 8, SPECS_SMALL)["fit"] == "too-big"


def test_fit_unknown_without_specs():
    assert C.fit_badge(2.0, 8, 4, SPECS_NONE)["fit"] == "unknown"


def test_curated_tasks_and_recommendations():
    vision = C.curated("vision", SPECS_MID)
    assert vision and all(r["task"] == "vision" for r in vision)
    recs = C.recommended(SPECS_SMALL)          # low-RAM defaults
    assert [r["model"] for r in recs] == ["moondream", "llama3.2:3b", "nomic-embed-text"]
    recs_big = C.recommended(SPECS_BIG)
    assert recs_big[0]["model"] == "qwen2.5vl:7b"
    # every curated entry carries a fit badge + honest source label
    assert all(r["source"] == "curated" and r["fit"] in ("gpu", "cpu", "tight", "too-big")
               for r in C.curated("any", SPECS_MID))


# --- HuggingFace search (mocked HTTP) ------------------------------------------

class _FakeHFResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_hf_search_variant_pick_and_task_detection(monkeypatch):
    payload = [
        {"id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
         "downloads": 12000,
         "siblings": [
             {"rfilename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf", "size": 2_015_000_000},
             {"rfilename": "Llama-3.2-3B-Instruct-Q8_0.gguf", "size": 3_400_000_000},
         ]},
        {"id": "unsloth/Qwen2.5-VL-7B-GGUF", "downloads": 3000, "siblings": []},
    ]
    monkeypatch.setattr(C.httpx, "get", lambda *a, **k: _FakeHFResponse(payload))
    rows = C.hf_search("llama", task="text", specs=SPECS_MID)
    assert len(rows) == 1  # the VL repo is filtered out for task=text
    row = rows[0]
    assert row["source"] == "huggingface"
    assert row["ref"].startswith("hf.co/bartowski/")
    assert row["ref"].endswith(":Q4_K_M")           # preferred quant picked
    assert row["size_gb"] == round(2_015_000_000 / 1024**3, 2)
    assert row["task"] == "text"

    vision_rows = C.hf_search("qwen", task="vision", specs=SPECS_BIG)
    assert len(vision_rows) == 1 and vision_rows[0]["task"] == "vision"


def test_hf_search_network_failure_is_empty_not_fatal(monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("no network")

    monkeypatch.setattr(C.httpx, "get", _boom)
    assert C.hf_search("llama", specs=SPECS_MID) == []


# --- API endpoints --------------------------------------------------------------

def test_local_status_and_catalog_contract(app_client):
    r = app_client.get("/api/v1/ai/local/status")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"ollama", "lmstudio", "machine", "recommended"}
    assert body["ollama"]["reachable"] is False     # no Ollama in CI
    assert body["machine"]["source"] in ("engine", "shell")

    r2 = app_client.get("/api/v1/ai/catalog")
    assert r2.status_code == 200
    cat = r2.json()
    assert cat["estimates"] == "rule-of-thumb"
    assert len(cat["curated"]) >= 10
    assert all("fit" in m and "ref" in m for m in cat["curated"])

    r3 = app_client.get("/api/v1/ai/catalog", params={"query": "llama", "task": "text"})
    assert r3.status_code == 200
    # HF IS reachable in CI, so assert the contract (list of dicts), not emptiness
    assert isinstance(r3.json()["huggingface"], list)


def test_catalog_hf_failure_is_empty_not_error(app_client, monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("no network")

    monkeypatch.setattr(C.httpx, "get", _boom)
    r = app_client.get("/api/v1/ai/catalog", params={"query": "llama"})
    assert r.status_code == 200
    assert r.json()["huggingface"] == []


def test_pull_rejected_without_ollama(app_client):
    r = app_client.post("/api/v1/ai/local/pull", json={"model": "bge-m3"})
    assert r.status_code == 409
    assert "install" in r.json()["detail"].lower()


# --- Semantic search honesty -----------------------------------------------------

def _mk_png_b64() -> str:
    from conftest import make_png

    return base64.b64encode(make_png()).decode()


def test_semantic_search_409_without_backend(app_client):
    from lens_engine.main import get_store

    pid = app_client.post("/api/v1/projects", json={"name": "P"}).json()["id"]
    sid = app_client.post("/api/v1/imagesets",
                          json={"project_id": pid, "name": "S"}).json()["id"]
    r = app_client.post(f"/api/v1/imagesets/{sid}/semantic-search",
                        json={"query": "protest"})
    assert r.status_code == 409
    assert "ollama" in r.json()["detail"].lower()
    _ = get_store  # keep import referenced


def test_semantic_search_ranks_with_mocked_ollama(app_client, monkeypatch):
    from lens_engine.ai.providers import EmbeddingResponse, OllamaProvider
    from lens_engine.main import get_store
    from lens_engine.storage.models import Image

    async def fake_health(self):
        return True

    async def fake_list_models(self):
        return ["bge-m3:latest"]

    async def fake_embed(self, text, *, model):
        # toy space: anything mentioning 'sale' → (1,0); everything else (0,1)
        vec = [1.0, 0.0] if "sale" in text.lower() else [0.0, 1.0]
        return EmbeddingResponse(vector=vec, model=model or "bge-m3", provider="ollama")

    monkeypatch.setattr(OllamaProvider, "health", fake_health)
    monkeypatch.setattr(OllamaProvider, "list_models", fake_list_models)
    monkeypatch.setattr(OllamaProvider, "embed", fake_embed)

    pid = app_client.post("/api/v1/projects", json={"name": "P2"}).json()["id"]
    sid = app_client.post("/api/v1/imagesets",
                          json={"project_id": pid, "name": "S2"}).json()["id"]

    # Seed images directly through the store (status=ready, no ingest worker
    # involvement) so the test stays hermetic.
    store = get_store()
    for i, text in enumerate(["BIG SALE TODAY", "weather report"]):
        store.add_image(Image(
            id=f"img-{i}", image_set_id=sid, filename=f"img{i}.png",
            storage_path="unused", status="ready",
            meta={"ocr": {"text": text, "words": []}},
        ))

    r = app_client.post(f"/api/v1/imagesets/{sid}/semantic-search",
                        json={"query": "sale discount"})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "bge-m3" and body["provider"] == "ollama"
    assert body["hits"][0]["snippet"].lower().startswith("big sale")
    assert body["coverage"]["embedded"] == 2
    assert "not CLIP joint-space" in body["note"]


# --- Vision-model OCR ------------------------------------------------------------

class _FakeProvider:
    def __init__(self, content: str = "BIG SALE"):
        self.content = content
        self.calls: list[dict] = []

    async def chat(self, messages, *, model, temperature=0.2, tools=None):
        self.calls.append({"model": model, "n_images": len(messages[0].images)})
        from lens_engine.ai.providers import ChatResponse

        return ChatResponse(content=self.content, model=model, provider="ollama")


def test_vision_ocr_success_path():
    provider = _FakeProvider("HELLO WORLD 123")
    result = asyncio.run(run_vision_ocr(make_png(), provider=provider, model="qwen2.5vl:3b"))
    d = result.to_dict()
    assert d["text"] == "HELLO WORLD 123"
    assert d["engine"] == "vision-model:qwen2.5vl:3b"
    assert d["words"] == []                     # honest: no boxes from a VLM
    assert d["word_count"] == 3
    assert d["confidence"] == 0.6               # flat marker, not a measurement
    assert provider.calls[0]["n_images"] == 1


def test_vision_ocr_unreachable_is_explicit(monkeypatch):
    from lens_engine.ai.providers import OllamaProvider

    async def down(self):
        return False

    monkeypatch.setattr(OllamaProvider, "health", down)
    result = asyncio.run(run_vision_ocr(make_png(), model=None))
    assert result.engine == "vision-model-unreachable"
    assert result.text == ""


# --- machine probe ----------------------------------------------------------------

def test_machine_probe_shape():
    from lens_engine.ai.machine import probe

    specs = probe()
    assert set(specs) >= {"os", "arch", "cpu_cores", "ram_gb", "gpus", "source"}
    assert specs["source"] == "engine"
