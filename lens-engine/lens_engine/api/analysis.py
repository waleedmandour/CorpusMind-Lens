"""Per-image analysis result routes (§9.2–9.4, 9.7): OCR, colour,
composition, metadata, vision-LM description (consent-gated)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..ai.providers import Message, get_provider
from ..config import get_settings
from ..main import get_store
from ..vision.consent_gate import filter_describe_response
from ..vision.facial import enforce_consent_or_raise, extract_visual_cues

router = APIRouter(tags=["analysis"])


def _require_image(image_id: str):
    img = get_store().get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    return img


@router.get("/images/{image_id}/analysis")
async def image_analysis(image_id: str) -> dict:
    """The full deterministic analysis block from Image.meta."""
    img = _require_image(image_id)
    meta = img.meta or {}
    return {
        "image_id": image_id,
        "status": img.status,
        "error": img.error,
        "metadata": meta.get("exif_xmp", {}),
        "user_fields": meta.get("user", {}),
        "ocr": meta.get("ocr", {}),
        "colour": meta.get("colour", {}),
        "composition": meta.get("composition", {}),
        "detections": meta.get("detections", []),
        "typography": meta.get("typography", {}),
        "vlm_description": meta.get("vlm_description", {}),
    }


@router.post("/images/{image_id}/describe")
async def describe_image(image_id: str, provider_id: str = "ollama", model: str = "") -> dict:
    """Vision-LM description — a NARRATIVE layer on top of the deterministic
    analysis, never a replacement (§4 Principle 3). Person-descriptive
    content passes through the consent gate (off by default)."""
    img = _require_image(image_id)
    settings = get_settings()
    raw = await _image_bytes(img)
    prompt = (
        "Describe this image factually for a discourse-analysis research corpus: "
        "depicted scene, objects, any visible text, layout, and salient visual "
        "elements. Stick to what is visible. Do not guess identities, ages, or "
        "personal characteristics of any people shown."
    )
    provider = get_provider(provider_id, api_key="")
    try:
        resp = await provider.chat(
            [Message(role="user", content=prompt, images=(raw,))],
            model=model or _default_vision_model(provider_id),
        )
    except Exception as e:
        raise HTTPException(502, f"Vision model unavailable ({provider_id}): {e}")

    gated = filter_describe_response(resp.content)
    description = {
        "text": gated["description"],
        "model": resp.model,
        "provider": resp.provider,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        "person_descriptive_redacted": gated["person_descriptive_redacted"],
        "note": "Narrative layer — interpretive, model-generated. Deterministic signals "
                "(colour, composition, detections, OCR) are stored separately.",
    }
    meta = dict(img.meta or {})
    meta["vlm_description"] = description
    get_store().update_image(image_id, meta=meta)
    return description


@router.post("/images/{image_id}/facial-cues")
async def facial_cues(image_id: str) -> dict:
    """Opt-in (§9.6): described visual cues + labelled interpretive glosses.
    Backend consent gate enforced regardless of what the UI sends."""
    enforce_consent_or_raise()
    img = _require_image(image_id)
    desc = (img.meta or {}).get("vlm_description", {}).get("text", "")
    return extract_visual_cues(desc)


async def _image_bytes(img) -> bytes:
    import asyncio

    from ..storage.encryption import decrypt_bytes
    from ..vision.ingest import read_image_bytes

    return await asyncio.to_thread(read_image_bytes, img.storage_path,
                                   get_settings().encryption_key)


def _default_vision_model(provider_id: str) -> str:
    return {"ollama": "moondream", "lmstudio": "local-model", "cloud": "gpt-4o-mini"}.get(
        provider_id, "local-model"
    )
