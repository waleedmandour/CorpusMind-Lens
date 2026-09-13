"""Ethics layer for social data (import-first + connectors).

Every social corpus carries a provenance record (see ``SocialSource``) and
optional, transparent anonymisation applied BEFORE storage:

* ``pseudonymize_handle``: deterministic, salted handle pseudonyms so the
  same author maps to the same pseudonym within one import (network
  structure preserved, identity removed). The salt is a REQUIRED argument:
  callers must supply the per-import random id (the default "lens" salt the
  v0.2.0 build shipped was guessable, which defeats the entire purpose of
  pseudonymising against a known handle list).
* ``redact_text``: reversible-free removal of e-mails, phone numbers, URLs
  and (optionally) mentions from post text.

Design rule (brief §4): the engine ships NO scraper and never stores
connector credentials; BYO keys live client-side and are passed per request.
"""
from __future__ import annotations

import hashlib
import re

from . import textutils


def pseudonymize_handle(handle: str, salt: str) -> str:
    """Salted, deterministic pseudonym. ``salt`` is deliberately REQUIRED —
    pass the per-import random id (``SocialSource.salt``) so pseudonyms are
    never reproducible from the handle alone."""
    if not handle:
        return ""
    h = hashlib.sha1(f"{salt}:{handle.strip().lower()}".encode("utf-8")).hexdigest()[:10]
    return f"user_{h}"


# Shapes that LOOK like a phone run in the candidate regex but are almost
# always data, not phone numbers. Redacting them silently corrupted corpus
# text (v0.2.0 finding: ISO-style dates like 2024-01-15 became "[phone]").
_DATE_LIKE = re.compile(
    r"(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"       # 2024-01-15, 2024.1.15
    r"|(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"    # 15/01/2024, 1-2-24
)
# dddd-dddd (8765-8769, 2010-2015): a numeric range/ID shape, not a phone.
_FOUR_FOUR = re.compile(r"^\d{4}-\d{4}$")
# E.164 caps telephone numbers at 15 digits; longer digit runs are order
# numbers, tracking ids, hashes — never phones.
_MAX_PHONE_DIGITS = 15


def _phone_decision(match: re.Match) -> str:
    candidate = match.group(0)
    digits = sum(ch.isdigit() for ch in candidate)
    if digits < 7 or digits > _MAX_PHONE_DIGITS:
        return candidate
    if _DATE_LIKE.search(candidate) or _FOUR_FOUR.match(candidate.strip()):
        return candidate
    return "[phone]"


def redact_text(
    text: str,
    *,
    emails: bool = True,
    phones: bool = True,
    urls: bool = False,
    mentions: bool = False,
) -> str:
    out = text or ""
    if emails:
        out = re.sub(textutils._EMAIL, "[email]", out)
    if phones:
        # 7-15 digit runs count as phone numbers (privacy-first: bare digit
        # runs ARE redacted), but dates, dddd-dddd ranges and 16+-digit ids
        # are preserved intact — silently mangling corpus data is a
        # correctness failure for a statistics tool.
        out = re.sub(
            r"(?<!\d)(?:\+?\d[\d\s\-()]{6,}\d)(?!\d)",
            _phone_decision,
            out,
        )
    if urls:
        out = re.sub(textutils._URL, "[url]", out)
    if mentions:
        out = textutils._MENTION.sub("@[user]", out)
    return out


def attestation_text(platform: str, kind: str) -> str:
    """The provenance statement recorded with every import / fetch."""
    if kind == "import":
        return (
            f"Data originates from a {platform} data export owned by the importing researcher. "
            "Collected under the platform's own export mechanism without scraping. "
            "Analysis and sharing must follow the platform terms of service, the "
            "export licence, and applicable research-ethics rules; raw personal "
            "data should not be redistributed."
        )
    return (
        f"Data collected through the {platform} official API using researcher-supplied "
        "credentials on its free access tier. Only public content is requested, at "
        "rate limits the platform grants, without circumventing any technical "
        "protection. Analysis and sharing must follow the platform developer "
        "agreement and applicable research-ethics rules."
    )


def apply_ethics(
    text: str,
    author: str,
    *,
    salt: str,
    pseudonymize: bool,
    redact_emails: bool = True,
    redact_phones: bool = True,
    redact_urls: bool = False,
    redact_mentions: bool = False,
) -> tuple[str, str]:
    """Return the (text, author) pair after the selected transformations."""
    new_author = pseudonymize_handle(author, salt) if pseudonymize else author
    new_text = redact_text(
        text,
        emails=redact_emails,
        phones=redact_phones,
        urls=redact_urls,
        mentions=redact_mentions,
    )
    return new_text, new_author
