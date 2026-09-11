"""API smoke tests: the full app boots with every router registered; core
flows (project → set → upload → analysis → annotate → battery → export)."""
from __future__ import annotations

import time

from tests.conftest import make_png


def test_health(app_client):
    r = app_client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["product"] == "CorpusMind Lens"
    assert body["status"] == "ok"
    assert body["facial_analysis"] is False  # off by default


def test_full_flow(app_client):
    c = app_client
    # project + set
    p = c.post("/api/v1/projects", json={"name": "P1", "description": "d"}).json()
    s = c.post("/api/v1/imagesets", json={"project_id": p["id"], "name": "Posters"}).json()
    assert s["name"] == "Posters"

    # upload (2 valid + 1 mislabeled + 1 SVG)
    png = make_png()
    files = [
        ("files", ("a.png", png, "image/png")),
        ("files", ("b.png", png, "image/png")),
        ("files", ("fake.png", b"this is text", "image/png")),
        ("files", ("v.svg", b"<svg/>", "image/svg+xml")),
    ]
    r = c.post(f"/api/v1/imagesets/{s['id']}/images", files=files)
    assert r.status_code == 202
    body = r.json()
    assert len(body["accepted"]) == 2
    assert len(body["rejected"]) == 2
    assert "magic-byte" in body["rejected"][0]["error"]

    # wait for background workers
    for _ in range(80):
        imgs = c.get(f"/api/v1/imagesets/{s['id']}/images").json()
        if all(i["status"] in ("ready", "error") for i in imgs):
            break
        time.sleep(0.1)
    assert all(i["status"] == "ready" for i in imgs)
    first = imgs[0]
    assert first["width"] == 64 and first["height"] == 48

    # analysis block exists (OCR engine may be "none" without tesseract lang packs)
    a = c.get(f"/api/v1/images/{first['id']}/analysis").json()
    assert a["ocr"]["engine"] in ("tesseract", "none")
    assert a["colour"]["dominant_colours"]
    assert "information_value" in a["composition"]

    # annotations: valid + invalid
    r = c.put(f"/api/v1/images/{first['id']}/annotations", json={
        "dimensions": {"shot_scale": {"values": ["medium_shot"], "note": "n"}},
        "tags": ["test"]})
    assert r.status_code == 200
    r = c.put(f"/api/v1/images/{first['id']}/annotations", json={
        "dimensions": {"shot_scale": {"values": ["bogus_category"], "note": ""}}})
    assert r.status_code == 422  # typo never silently corrupts a corpus

    # battery endpoints
    r = c.get(f"/api/v1/imagesets/{s['id']}/battery/frequency/shot_scale").json()
    assert r["total_observations"] >= 1
    r = c.get(f"/api/v1/imagesets/{s['id']}/battery/ngrams/shot_scale?n=2&min_count=1").json()
    assert "grams" in r

    # set stats
    r = c.get(f"/api/v1/imagesets/{s['id']}/stats").json()
    assert r["image_count"] == 2
    assert "coverage" in r

    # export json
    r = c.get(f"/api/v1/imagesets/{s['id']}/export?format=json")
    assert r.status_code == 200

    # methods section
    r = c.get(f"/api/v1/imagesets/{s['id']}/methods-section").json()
    assert "CorpusMind Lens engine" in r["methods"]
    assert "GPS" in r["methods"]


def test_discourse_heuristic_flow(app_client):
    c = app_client
    frameworks = c.get("/api/v1/discourse/frameworks").json()
    ids = [f["id"] for f in frameworks]
    assert len(ids) == 12
    assert "kress-van-leeuwen" in ids and "fairclough-cda" in ids

    p = c.post("/api/v1/projects", json={"name": "P2"}).json()
    s = c.post("/api/v1/imagesets", json={"project_id": p["id"], "name": "S2"}).json()
    png = make_png()
    r = c.post(f"/api/v1/imagesets/{s['id']}/images",
               files=[("files", ("a.png", png, "image/png"))]).json()
    image_id = r["accepted"][0]
    for _ in range(80):
        img = c.get(f"/api/v1/images/{image_id}").json()
        if img["status"] in ("ready", "error"):
            break
        time.sleep(0.1)

    res = c.post(f"/api/v1/images/{image_id}/discourse/kress-van-leeuwen?mode=heuristic").json()
    assert res["framework"] == "kress-van-leeuwen"
    assert isinstance(res["claims"], list)
    for claim in res["claims"]:
        assert claim["evidence"], "heuristic claims always cite evidence"
        assert "may" in claim["claim"] or "reads as" in claim["claim"] or "metrics" in claim["claim"]

    # visual grammar routes
    vg = c.post(f"/api/v1/images/{image_id}/visual-grammar").json()
    assert set(vg["metafunctions"]) == {"representational", "interactional", "compositional"}
    assert "interpretive" in vg["explanation_layer"]


def test_batch_runner(app_client):
    c = app_client
    p = c.post("/api/v1/projects", json={"name": "P3"}).json()
    s = c.post("/api/v1/imagesets", json={"project_id": p["id"], "name": "S3"}).json()
    png = make_png()
    r = c.post(f"/api/v1/imagesets/{s['id']}/images",
               files=[("files", ("a.png", png, "image/png")),
                      ("files", ("b.png", png, "image/png"))]).json()
    for _ in range(80):
        imgs = c.get(f"/api/v1/imagesets/{s['id']}/images").json()
        if all(i["status"] in ("ready", "error") for i in imgs):
            break
        time.sleep(0.1)
    r = c.post(f"/api/v1/imagesets/{s['id']}/discourse/batch",
               json={"frameworks": ["kress-van-leeuwen", "barthes-semiotics"]})
    job = r.json()
    assert job["status"] == "running"
    for _ in range(100):
        st = c.get(f"/api/v1/discourse/batch/{job['job_id']}").json()
        if st["status"] in ("complete", "cancelled"):
            break
        time.sleep(0.05)
    assert st["done"] == st["total"] == 4
    res = c.get(f"/api/v1/discourse/batch/{job['job_id']}/results").json()
    assert len(res["results"]) == 4
    assert res["errors"] == []


def test_assistant_tools_surface_and_grounding(app_client):
    c = app_client
    tools = c.get("/api/v1/assistant/tools").json()
    names = [t["name"] for t in tools]
    assert "list_image_sets" in names
    assert "get_visual_keyness" in names
    assert "get_text_corpus_overview" not in names  # Companion Mode off → tool absent

    p = c.post("/api/v1/projects", json={"name": "P4"}).json()
    s = c.post("/api/v1/imagesets", json={"project_id": p["id"], "name": "S4"}).json()
    r = c.post(f"/api/v1/imagesets/{s['id']}/images",
               files=[("files", ("a.png", make_png(), "image/png"))]).json()
    image_id = r["accepted"][0]
    for _ in range(80):
        img = c.get(f"/api/v1/images/{image_id}").json()
        if img["status"] in ("ready", "error"):
            break
        time.sleep(0.1)

    # direct tool execution via the registry (grounded, audited)
    from lens_engine.ai.tools import run_tool

    out = run_tool("get_image_analysis", {"image_id": image_id})
    assert out["grounded"] is True
    assert out["evidence"]["image_id"] == image_id
    bad = run_tool("get_image_analysis", {"image_id": "nope"})
    assert bad["grounded"] is False
    audit = c.get("/api/v1/assistant/audit").json()
    assert any(e["event"] == "tool_call" for e in audit)


def test_settings_and_ethics(app_client):
    c = app_client
    st = c.get("/api/v1/settings").json()
    assert st["facial_analysis"] is False
    assert st["cloud_enabled"] is False
    eth = c.get("/api/v1/settings/ethics").json()
    assert eth["gps_extraction"]["supported"] is False
    assert "never extracted" in eth["gps_extraction"]["reason"]


def test_companion_disabled_by_default(app_client):
    c = app_client
    st = c.get("/api/v1/companion/status").json()
    assert st["enabled"] is False
    r = c.get("/api/v1/companion/corpora/abc")
    assert r.status_code == 409


def test_describe_is_consent_gated_narrative_layer(app_client):
    c = app_client
    p = c.post("/api/v1/projects", json={"name": "P5"}).json()
    s = c.post("/api/v1/imagesets", json={"project_id": p["id"], "name": "S5"}).json()
    r = c.post(f"/api/v1/imagesets/{s['id']}/images",
               files=[("files", ("a.png", make_png(), "image/png"))]).json()
    image_id = r["accepted"][0]
    # No provider reachable in CI → the route should 502, NOT leak into pretending
    r2 = c.post(f"/api/v1/images/{image_id}/describe?provider_id=ollama&model=none")
    assert r2.status_code == 502
    # facial cues endpoint gated server-side (not just UI-hidden)
    r3 = c.post(f"/api/v1/images/{image_id}/facial-cues")
    assert r3.status_code in (403, 500)  # ConsentRequiredError → not silently allowed
