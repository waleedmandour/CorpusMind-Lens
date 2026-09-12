"""Engine settings — explicit, local-first by default (build brief §4, §13).

Every cloud/privacy-sensitive capability has a master switch that is OFF by
default and enforced server-side, not merely in the UI:

* ``facial_analysis`` — §9.6 facial/body analysis. Off by default; the
  consent gate additionally filters person-descriptive content from *all*
  vision-LM outputs while it is off.
* ``cloud_enabled`` — cloud AI providers. Off by default; the provider layer
  refuses to construct a CloudProvider unless this is explicitly set.
* GPS/location extraction — there is **no setting** for this. It is never
  extracted (§4 Principle 8). The extractor module owns that guarantee.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    # lens_engine/config.py → lens-engine/ → repo root
    return Path(__file__).resolve().parent.parent.parent


def _frozen_base() -> Path:
    """Resource base when running as a PyInstaller sidecar.

    Onefile builds unpack data files under ``sys._MEIPASS``; the release
    pipeline ships the 12 discourse frameworks there via
    ``--add-data …:reference-data/frameworks``. Onedir builds keep them next
    to the executable.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(sys.executable).resolve().parent


def _default_frameworks_dir() -> Path:
    env = os.environ.get("LENS_FRAMEWORKS_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):  # PyInstaller sidecar (release builds)
        cand = _frozen_base() / "reference-data" / "frameworks"
        if cand.is_dir():
            return cand
    root = _repo_root()
    cand = root / "reference-data" / "frameworks"
    if cand.is_dir():
        return cand
    # packaged fallback (PyInstaller sidecar)
    return root / "lens-engine" / "reference-data" / "frameworks"


@dataclass(slots=True)
class Settings:
    host: str = field(default_factory=lambda: os.environ.get("LENS_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("LENS_PORT", "8765")))
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("LENS_DATA_DIR", "./data")).resolve()
    )
    facial_analysis: bool = field(
        default_factory=lambda: os.environ.get("LENS_FACIAL_ANALYSIS", "0") == "1"
    )
    cloud_enabled: bool = field(
        default_factory=lambda: os.environ.get("LENS_CLOUD_ENABLED", "0") == "1"
    )
    encryption_key: str | None = field(
        default_factory=lambda: os.environ.get("LENS_ENCRYPTION_KEY") or None
    )
    frameworks_dir: Path = field(default_factory=_default_frameworks_dir)
    default_ocr_language: str = field(
        default_factory=lambda: os.environ.get("LENS_OCR_LANGUAGE", "eng")
    )
    # Upload hardening (§9.2): per-file and per-batch caps.
    max_file_mb: int = field(default_factory=lambda: int(os.environ.get("LENS_MAX_FILE_MB", "40")))
    max_batch_images: int = field(
        default_factory=lambda: int(os.environ.get("LENS_MAX_BATCH_IMAGES", "2000"))
    )
    # Companion Mode (§5): off by default; the base URL is set by the user in Settings.
    companion_enabled: bool = field(
        default_factory=lambda: os.environ.get("LENS_COMPANION_ENABLED", "0") == "1"
    )
    companion_base_url: str = field(
        default_factory=lambda: os.environ.get("LENS_COMPANION_BASE_URL", "")
    )
    # v0.2 local-AI defaults. bge-m3 is the multilingual (EN+AR) embedding
    # default — it replaces the absent torch CLIP stack in packaged builds
    # for text-side semantics. The vision-OCR model is the Ollama vision
    # model used by the OCR-assist re-analysis endpoint.
    default_embedding_model: str = field(
        default_factory=lambda: os.environ.get("LENS_EMBED_MODEL", "bge-m3")
    )
    vision_ocr_model: str = field(
        default_factory=lambda: os.environ.get("LENS_VISION_OCR_MODEL", "qwen2.5vl:3b")
    )

    def ensure_dirs(self) -> None:
        (self.data_dir / "images").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "thumbs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def reset_settings() -> None:
    """Test hook."""
    global _settings
    _settings = None
