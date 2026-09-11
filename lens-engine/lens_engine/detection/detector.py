"""Open-vocabulary object/scene detection (§9.5 — the first Phase-2 gap).

Design (§3.2): map an operationalized visual-grammar taxonomy onto
computer-vision outputs so every category is numeric and reproducible —
prioritising a lightweight open-vocabulary detector run **locally**, with the
vision-LM's free-text description as a clearly separate narrative layer,
never conflated with the measurement.

Default backend: OWL-ViT (``google/owlvit-base-patch32``, Apache-2.0) via
``transformers`` — permissive license, CPU-feasible, genuinely open-vocabulary
(text-queryable categories: people, animals, objects, vehicles, buildings,
food, products, logos, weapons, religious/national/political symbols, flags).

The backend is **pluggable** (:class:`Detector` protocol) and **lazily
loaded**: when torch/transformers are not installed the engine reports
``model: "unavailable"`` rather than pretending to run (honest degradation),
and callers fall back to OCR/composition signals only.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ..logging import get_logger

log = get_logger(__name__)

DEFAULT_DETECTOR_MODEL = "google/owlvit-base-patch32"
DEFAULT_DETECTOR_REVISION = "main"

DEFAULT_QUERY_CATEGORIES = [
    "person", "crowd", "child", "animal", "vehicle", "building", "weapon",
    "flag", "logo", "religious symbol", "political symbol", "food", "product",
]

_SCENE_CLASSES = [
    "office", "home interior", "street", "classroom", "hospital", "battlefield",
    "mosque", "church", "supermarket", "airport", "stadium", "protest", "beach",
    "mountains", "factory", "studio portrait",
]


@dataclass(slots=True)
class Detection:
    label: str
    bbox: list[float]        # [x, y, w, h] normalized 0–1 (reproducible across resizes)
    confidence: float
    model: str
    revision: str

    def to_dict(self) -> dict:
        return {"label": self.label, "bbox": [round(v, 4) for v in self.bbox],
                "confidence": round(self.confidence, 3), "model": self.model,
                "revision": self.revision}


@dataclass(slots=True)
class DetectorStatus:
    available: bool
    model: str
    revision: str
    reason: str = ""


class Detector:
    """Protocol: open-vocabulary detection over raw image bytes."""

    name: str = "abstract"

    async def detect(self, raw: bytes, *, categories: list[str] | None = None,
                     threshold: float = 0.15) -> list[Detection]: ...

    async def status(self) -> DetectorStatus: ...


_owl_pipeline = None
_owl_model_id: str | None = None
_owl_lock = asyncio.Lock()


async def _get_owl(model_id: str):
    global _owl_pipeline, _owl_model_id
    async with _owl_lock:
        if _owl_pipeline is not None and _owl_model_id == model_id:
            return _owl_pipeline
        from transformers import pipeline as hf_pipeline  # heavy import, lazy

        _owl_pipeline = hf_pipeline(
            "zero-shot-object-detection", model=model_id, device=-1  # CPU by default
        )
        _owl_model_id = model_id
        return _owl_pipeline


class OWLViTDetector(Detector):
    name = "owlvit"

    def __init__(self, model_id: str = DEFAULT_DETECTOR_MODEL,
                 revision: str = DEFAULT_DETECTOR_REVISION) -> None:
        self.model_id = model_id
        self.revision = revision

    async def status(self) -> DetectorStatus:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError as e:
            return DetectorStatus(False, self.model_id, self.revision,
                                  reason=f"model deps not installed (lens-engine[models]): {e}")
        return DetectorStatus(True, self.model_id, self.revision)

    async def detect(self, raw: bytes, *, categories: list[str] | None = None,
                     threshold: float = 0.15) -> list[Detection]:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGB")
        labels = categories or DEFAULT_QUERY_CATEGORIES
        candidates = [f"a photo of {c}" for c in labels]
        try:
            pipe = await _get_owl(self.model_id)
        except Exception as e:
            log.warning("detector_unavailable", extra={"error": str(e)})
            return []
        import asyncio as aio

        results = await aio.to_thread(pipe, img, candidate_labels=candidates, threshold=threshold)
        out: list[Detection] = []
        for r in results[:50]:
            label = r.get("label", "")
            # strip the "a photo of " prompt prefix back to the bare category
            for c in labels:
                if label.endswith(c):
                    label = c
                    break
            box = r.get("box", {})
            x, y = box.get("xmin", 0), box.get("ymin", 0)
            w = max(0, box.get("xmax", 0) - x)
            h = max(0, box.get("ymax", 0) - y)
            out.append(Detection(
                label=label,
                bbox=[x / img.width, y / img.height, w / img.width, h / img.height],
                confidence=float(r.get("score", 0.0)),
                model=self.model_id,
                revision=self.revision,
            ))
        return out


class UnavailableDetector(Detector):
    """Honest fallback: reports unavailable; detect() returns []."""

    name = "unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def status(self) -> DetectorStatus:
        return DetectorStatus(False, "unavailable", "", reason=self.reason)

    async def detect(self, raw: bytes, *, categories: list[str] | None = None,
                     threshold: float = 0.15) -> list[Detection]:
        return []


def get_detector() -> Detector:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401

        return OWLViTDetector()
    except ImportError as e:
        return UnavailableDetector(f"torch/transformers not installed: {e}")


# --------------------------------------------------------------------------- #
# Scene classification (zero-shot, CLIP-class; same honest degradation)
# --------------------------------------------------------------------------- #


class SceneClassifier:
    name = "clip-zero-shot"

    def __init__(self, model_id: str = "openai/clip-vit-base-patch32") -> None:
        self.model_id = model_id
        self._pipe = None

    def available(self) -> bool:
        try:
            import transformers  # noqa: F401

            return True
        except ImportError:
            return False

    async def classify(self, raw: bytes, *, top_k: int = 3) -> list[dict]:
        if not self.available():
            return []
        import io

        from PIL import Image

        if self._pipe is None:
            from transformers import pipeline as hf_pipeline

            self._pipe = hf_pipeline("zero-shot-image-classification", model=self.model_id)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        import asyncio as aio

        res = await aio.to_thread(self._pipe, img, candidate_labels=_SCENE_CLASSES)
        return [{"scene": r["label"], "score": round(float(r["score"]), 4)}
                for r in res[:top_k]]


def validate_detections(detections: list[dict]) -> list[Detection]:
    """Rehydrate persisted detection dicts, dropping malformed entries."""
    out = []
    for d in detections or []:
        try:
            out.append(Detection(
                label=d["label"], bbox=[float(v) for v in d.get("bbox", [0, 0, 0, 0])],
                confidence=float(d.get("confidence", 0.0)),
                model=d.get("model", "unknown"), revision=d.get("revision", ""),
            ))
        except Exception:
            continue
    return out
