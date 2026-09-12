"""Text utilities for the Social tab: emoji extraction, tokenisation,
hashtag/mention/url harvesting, and HTML stripping. Stdlib only, Unicode
aware (English and Arabic both tokenise correctly through ``\\w`` with
``re.UNICODE``), no network access.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Emoji detection over the standard blocks. One token = one base emoji with
# optional modifiers (skin tone, VS16); ZWJ chains (families) stay ONE
# token; regional-indicator pairs count as one flag token.
_EMOJI_BASE = (
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF\U00002300-\U000023FF\U000025A0-\U000025FF\U00002930-\U000029FF"
    "\U00003030\U0000303D\U00003297\U00003299\U00002139\U00002122"
    "\U0000231A\U0000231B\U0000203C\U00002049\U0000203D]"
)
_EMOJI_MODS = "[\U0000FE0F\U000020E3\U0001F3FB-\U0001F3FF]?"
_EMOJI_RUN = re.compile(
    "(?:[\U0001F1E6-\U0001F1FF]{2}"  # regional indicators: flags
    "|" + _EMOJI_BASE + _EMOJI_MODS + "(?:\u200d" + _EMOJI_BASE + _EMOJI_MODS + ")*"
    ")"
)

_MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9_\.]{1,80})")
_HASHTAG = re.compile(r"(?<![\w#])#([^\s#]{1,100})")
_URL = re.compile(r"https?://[^\s<>\"']+")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_TAG = re.compile(r"<[^>]+>")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s\-()]{6,}\d)(?!\d)")

# Emoji presentation variants that should not inflate counts. ZWJ is kept
# so family sequences stay one canonical token.
_STRIP_CHARS = "\ufe0f\ufe0e"


def extract_emoji(text: str) -> list[str]:
    """Emoji runs in order of appearance; ZWJ sequences collapse to one."""
    out: list[str] = []
    for m in _EMOJI_RUN.finditer(text):
        run = "".join(ch for ch in m.group(0) if ch not in _STRIP_CHARS)
        if run:
            out.append(run)
    return out


def emoji_frequency(texts: list[str]) -> Counter:
    c: Counter = Counter()
    for t in texts:
        c.update(extract_emoji(t))
    return c


def extract_hashtags(text: str) -> list[str]:
    return [m.group(1) for m in _HASHTAG.finditer(text) if m.group(1).strip()]


def extract_mentions(text: str) -> list[str]:
    return [m.group(1) for m in _MENTION.finditer(text)]


def extract_urls(text: str) -> list[str]:
    return [m.group(0) for m in _URL.finditer(text)]


def strip_html(text: str) -> str:
    """Mastodon and some DYI exports carry HTML fragments."""
    text = _TAG.sub(" ", text)
    text = (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&amp;", "&")
        .replace("<br>", "\n")
        .replace("<br/>", "\n")
    )
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def tokens(text: str) -> list[str]:
    """Lowercased word tokens for frequency/diversity/ngram statistics.

    URLs and e-mail addresses are excluded as noise; hashtag words keep
    their content (the ``#`` itself is dropped); mentions are dropped so
    pseudonymised handles never leak into lexical profiles.
    """
    text = _URL.sub(" ", text)
    text = _EMAIL.sub(" ", text)
    text = _MENTION.sub(" ", text)
    text = text.replace("#", " ")
    text = unicodedata.normalize("NFC", text)
    return [w.lower() for w in re.findall(r"[\w']+", text, re.UNICODE) if w.strip("'_")]


def parse_platform_time(raw: str) -> str:
    """Normalise a platform timestamp to ISO-8601 (best effort).

    X archives use ``Tue Mar 03 15:34:12 +0000 2020``; Reddit/YouTube/
    Mastodon arrive numeric or ISO. Returns ``""`` when unparseable.
    """
    import datetime

    raw = (raw or "").strip()
    if not raw:
        return ""
    if re.fullmatch(r"\d{9,13}", raw):  # unix seconds / millis
        n = int(raw)
        if n > 10_000_000_000:
            n //= 1000
        try:
            return datetime.datetime.fromtimestamp(n, datetime.UTC).isoformat()
        except (ValueError, OverflowError, OSError):
            return ""
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue
    try:  # already ISO-ish
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return ""
