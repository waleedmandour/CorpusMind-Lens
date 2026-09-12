"""Ethics layer for social data (import-first + connectors).

Every social corpus carries a provenance record (see ``SocialSource``) and
optional, transparent anonymisation applied BEFORE storage:

* ``pseudonymize_handle``: deterministic, salted handle pseudonyms so the
  same author maps to the same pseudonym within one import (network
  structure preserved, identity removed).
* ``redact_text``: reversible-free removal of e-mails, phone numbers, URLs
  and (optionally) mentions from post text.

Design rule (brief §4): the engine ships NO scraper and never stores
connector credentials; BYO keys live client-side and are passed per request.
"""
from __future__ import annotations

import hashlib
import re

from . import textutils


def pseudonymize_handle(handle: str, salt: str = "lens") -> str:
    if not handle:
        return ""
    h = hashlib.sha1(f"{salt}:{handle.strip().lower()}".encode("utf-8")).hexdigest()[:10]
    return f"user_{h}"


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
        # Only sequences of 7+ digits qualify, to avoid shredding ordinary numbers.
        out = re.sub(
            r"(?<!\d)(?:\+?\d[\d\s\-()]{6,}\d)(?!\d)",
            lambda m: "[phone]" if sum(ch.isdigit() for ch in m.group(0)) >= 7 else m.group(0),
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
