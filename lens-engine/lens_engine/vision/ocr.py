"""OCR (§9.4) — Arabic + English + mixed-language via Tesseract.

Per-image confidence is ALWAYS surfaced, never silently trusted (§9.4). The
per-word boxes are captured (not just the concatenated text) because two
later subsystems consume them: the §9.8 typography profiler and the visual
KWIC. A re-analysis endpoint allows a missing language pack at ingest time
to be fixed later without re-uploading (§9.4).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from ..logging import get_logger

log = get_logger(__name__)

# Corpus-level language resolution (§9.4): a set tagged arabic OCRs ara+eng.
LANGUAGE_PRESETS = {
    "arabic": "ara+eng",
    "english": "eng",
    "mixed": "eng+ara",
}


@dataclass(slots=True)
class OCRWord:
    text: str
    conf: float          # 0–1
    box: list[int]       # [x, y, w, h] in image pixels


@dataclass(slots=True)
class OCRResult:
    text: str
    confidence: float          # 0–1 average (0 if OCR unavailable)
    word_count: int
    engine: str                # "tesseract" or "none"
    language: str = "eng"
    words: list[OCRWord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "engine": self.engine,
            "language": self.language,
            "words": [
                {"text": w.text, "conf": round(w.conf, 3), "box": w.box} for w in self.words
            ],
        }


def resolve_language(per_upload: str | None, set_language: str | None) -> str:
    """Per-upload override beats set-level language, beats the default."""
    lang = per_upload or set_language or "english"
    return LANGUAGE_PRESETS.get(lang.lower(), lang)


def run_ocr(raw: bytes, *, language: str = "eng") -> OCRResult:
    """Extract text + per-word boxes from an image via Tesseract.

    Falls back to a no-OCR result if Tesseract isn't installed — the caller
    must surface engine + confidence to the user rather than silently
    treating empty text as "no text in image".
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(raw))
        data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
        words: list[OCRWord] = []
        n = len(data["text"])
        for i in range(n):
            txt = (data["text"][i] or "").strip()
            conf = int(data["conf"][i])
            if not txt or conf < 0:
                continue
            words.append(OCRWord(
                text=txt,
                conf=conf / 100.0,
                box=[int(data["left"][i]), int(data["top"][i]),
                     int(data["width"][i]), int(data["height"][i])],
            ))
        text = " ".join(w.text for w in words)
        avg_conf = sum(w.conf for w in words) / len(words) if words else 0.0
        return OCRResult(
            text=text,
            confidence=round(avg_conf, 3),
            word_count=len(words),
            engine="tesseract",
            language=language,
            words=words,
        )
    except ImportError:
        log.info("ocr_unavailable", extra={"reason": "pytesseract not installed"})
        return OCRResult(text="", confidence=0.0, word_count=0, engine="none", language=language)
    except Exception as e:
        log.warning("ocr_failed", extra={"error": str(e)})
        return OCRResult(text="", confidence=0.0, word_count=0, engine="none", language=language)
