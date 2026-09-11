"""Privacy-safe image metadata extraction (IPTC-Core-aligned, §9.3).

Design decisions (inherited from the parent's hard-won v1.0.9 round):

* **EXIF via Pillow only** — no new binary dependencies.
* **XMP via packet scan** — XMP lives in an ``<x:xmpmeta>`` packet that is
  plain XML embedded in the file; we lift a small, well-known field set with
  targeted regular expressions instead of pulling in a full RDF library.
* **GPS is deliberately NOT extracted.** Location coordinates are personal
  data under GDPR and almost never needed for discourse-analytic work, so
  the extractor skips every GPS tag/namespace on purpose and records why.
  **There is no setting that overrides this** (§4 Principle 8) — the
  guarantee lives here, in code, not in configuration.
* **Never raises** — a malformed or missing metadata block must not fail an
  ingest; we return what we could read (possibly ``{}``).
* User-editable fields (source/publication/licence/genre/language-of-
  embedded-text) are merged non-destructively: the machine-extracted block
  is never user-overwritable (§9.3) — the API layer stores user fields under
  ``meta["user"]`` and machine fields under ``meta["exif"] / meta["xmp"]``.
"""
from __future__ import annotations

import re

from ..logging import get_logger

log = get_logger(__name__)

# EXIF tags we surface (tag id -> canonical name). Deliberately excludes the
# GPS IFD (0x8825) and every GPS tag.
_EXIF_TAGS: dict[int, str] = {
    271: "make",
    272: "model",
    305: "software",
    306: "date_time",
    42016: "image_unique_id",
}
_EXIF_SUB_TAGS: dict[int, str] = {
    36867: "date_time_original",
    36868: "date_time_digitized",
}

_XMP_FIELD_PATTERNS: list[tuple[str, re.Pattern[bytes]]] = [
    ("title", re.compile(rb"<dc:title[\s\S]{0,400}?<rdf:li[^>]*>([^<]{1,300})</rdf:li>", re.S)),
    ("creator", re.compile(rb"<dc:creator[\s\S]{0,400}?<rdf:li[^>]*>([^<]{1,300})</rdf:li>", re.S)),
    ("description", re.compile(rb"<dc:description[\s\S]{0,400}?<rdf:li[^>]*>([^<]{1,2000})</rdf:li>", re.S)),
    ("rights", re.compile(rb"<dc:rights[\s\S]{0,400}?<rdf:li[^>]*>([^<]{1,300})</rdf:li>", re.S)),
    ("headline", re.compile(rb"<photoshop:Headline>([^<]{1,300})</photoshop:Headline>", re.S)),
    ("credit", re.compile(rb"<photoshop:Credit>([^<]{1,300})</photoshop:Credit>", re.S)),
    ("usage_terms", re.compile(rb"<xmpRights:UsageTerms[\s\S]{0,400}?<rdf:li[^>]*>([^<]{1,300})</rdf:li>", re.S)),
    ("web_statement", re.compile(rb"<xmpRights:WebStatement>([^<]{1,300})</xmpRights:WebStatement>", re.S)),
]

_XMP_SUBJECT_PATTERN = re.compile(rb"<dc:subject[\s\S]{0,2000}?</dc:subject>", re.S)
_XMP_SUBJECT_LI = re.compile(rb"<rdf:li[^>]*>([^<]{1,120})</rdf:li>")

_XML_ENTITY = re.compile(rb"&#x([0-9a-fA-F]+);|&#(\d+);")
_XML_ESCAPES = {
    b"&lt;": b"<", b"&gt;": b">", b"&quot;": b'"', b"&apos;": b"'", b"&amp;": b"&",
}


def _clean_xml_text(raw: bytes) -> str:
    """Decode a small XML text node: entities → unicode, strip whitespace."""
    for esc, ch in _XML_ESCAPES.items():
        raw = raw.replace(esc, ch)

    def _hex_or_dec(m: re.Match[bytes]) -> bytes:
        if m.group(1):
            try:
                return bytes([int(m.group(1), 16)])
            except ValueError:
                return b""
        return bytes([int(m.group(2))])

    raw = _XML_ENTITY.sub(_hex_or_dec, raw)
    return raw.decode("utf-8", errors="replace").strip()


def extract_exif(raw: bytes) -> dict[str, str]:
    """Read the whitelisted EXIF fields. Never raises; GPS excluded by design."""
    out: dict[str, str] = {}
    try:
        from PIL import Image, ExifTags
        import io as _io

        img = Image.open(_io.BytesIO(raw))
        exif = img.getexif()
        for tag_id, name in _EXIF_TAGS.items():
            v = exif.get(tag_id)
            if v not in (None, ""):
                out[name] = str(v)[:200]
        sub = exif.get_ifd(0x8769)  # EXIF sub-IFD pointer
        for tag_id, name in _EXIF_SUB_TAGS.items():
            v = sub.get(tag_id)
            if v not in (None, ""):
                out[name] = str(v)[:200]
        # Verify GPS exclusion explicitly: ExifTags.GPSInfo (0x8825) is never read.
        _ = ExifTags.IFD.GPSInfo  # noqa: F841 — reference documents the deliberate skip
    except Exception as e:  # pragma: no cover - defensive
        log.debug("exif_extract_skipped", extra={"error": str(e)})
    return out


def extract_xmp(raw: bytes) -> dict[str, str | list[str]]:
    """Lift the IPTC-Core-aligned XMP field set from the embedded packet."""
    out: dict[str, str | list[str]] = {}
    try:
        start = raw.find(b"<x:xmpmeta")
        if start == -1:
            start = raw.find(b"<rdf:RDF")
        if start == -1:
            return out
        end = raw.find(b"</x:xmpmeta>", start)
        end = len(raw) if end == -1 else end + len(b"</x:xmpmeta>")
        packet = raw[start:end]
        for field, pat in _XMP_FIELD_PATTERNS:
            m = pat.search(packet)
            if m:
                text = _clean_xml_text(m.group(1))
                if text:
                    out[field] = text
        subj = _XMP_SUBJECT_PATTERN.search(packet)
        if subj:
            kws = [_clean_xml_text(k) for k in _XMP_SUBJECT_LI.findall(subj.group(0))]
            kws = [k for k in kws if k]
            if kws:
                out["keywords"] = kws[:50]
        # GPS namespace: intentionally NOT parsed even if present in the packet.
    except Exception as e:  # pragma: no cover - defensive
        log.debug("xmp_extract_skipped", extra={"error": str(e)})
    return out


def extract_metadata(raw: bytes) -> dict[str, dict]:
    """Full machine-extracted metadata block for ``Image.meta``."""
    return {
        "exif": extract_exif(raw),
        "xmp": extract_xmp(raw),
        "gps": {"extracted": False, "reason": "GPS is never extracted (privacy principle 8)."},
    }


USER_FIELD_IDS = ("source", "publication", "licence", "genre", "language_of_embedded_text")


def merge_user_fields(meta: dict, user_fields: dict) -> dict:
    """Non-destructively merge user-editable IPTC fields into ``meta['user']``.

    Machine blocks (``exif``/``xmp``) are never touched by user input (§9.3).
    """
    clean = {k: str(v)[:300] for k, v in (user_fields or {}).items()
             if k in USER_FIELD_IDS and str(v).strip()}
    current = dict((meta.get("user") or {}))
    current.update(clean)
    meta["user"] = current
    return meta
