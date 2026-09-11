"""Test fixtures — isolated data dir per session, synthetic images."""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lens-data")
    old = dict(os.environ)
    os.environ["LENS_DATA_DIR"] = str(tmp)
    os.environ["LENS_FACIAL_ANALYSIS"] = "0"
    os.environ["LENS_CLOUD_ENABLED"] = "0"
    os.environ["LENS_FRAMEWORKS_DIR"] = str(
        Path(__file__).resolve().parent.parent.parent / "reference-data" / "frameworks")
    from lens_engine.config import reset_settings

    reset_settings()
    yield
    os.environ.clear()
    os.environ.update(old)
    from lens_engine.config import reset_settings

    reset_settings()


@pytest.fixture()
def app_client():
    from fastapi.testclient import TestClient

    from lens_engine.main import app

    with TestClient(app) as client:  # lifespan starts background workers
        yield client


def make_png(width: int = 64, height: int = 48, colour=(180, 40, 40)) -> bytes:
    """A real raster PNG generated in-memory (no committed binaries)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), colour)
    d = ImageDraw.Draw(img)
    d.rectangle([width // 4, height // 4, 3 * width // 4, 3 * height // 4], fill=(30, 30, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
