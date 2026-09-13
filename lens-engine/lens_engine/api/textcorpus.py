"""Text Analysis over the OCR corpus (v0.3, "the AntConc audit").

Lens v0.1-v0.2 analysed *annotations*; a corpus linguist also expects the
classic text-toolset over the extracted OCR text + captions. Everything here
runs on the same per-set token stream the OCR tools already produce, so the
visual and textual layers finally share one analysis surface:

* ``GET /imagesets/{id}/text/wordlist``      — frequency list with stoplist
  resolution (built-in EN/AR, per-project custom lists) and Arabic folding.
* ``GET /imagesets/{id}/text/concordance``   — Concordancer 2.0: substring or
  regex queries, L/R sort positions, per-hit metadata, CSV/XLSX/... export
  (AntConc parity; the visual KWIC stays for word-box geometry).
* ``GET /imagesets/{id}/text/collocations``  — span-based collocates with MI,
  t-score, LL, LogDice and ΔP (GraphColl-style network edges included).
* ``GET /imagesets/{id}/text/ngrams``        — n-grams / lexical bundles with
  text-dispersion (Juilland's D, Gries' DP) per reading order.
* ``GET /imagesets/{id}/text/dispersion``    — per-word dispersion gallery
  rows (D, DP, range) across the set's images.
* ``GET /imagesets/{id}/text/sketch``        — word sketch, visual edition:
  a token's typical visual co-patterns (colour, composition, typography,
  detected objects) instead of grammatical dependencies.
* ``GET /imagesets/{id}/text/references``    — bundled reference frequency
  tables (CC-BY / public-domain derivatives, attributed in-file).
* ``GET /imagesets/{id}/text/keyness-reference`` — keyness against a bundled
  reference table, so keyness works without a second image set (Hardie's
  significance + effect-size discipline carries over unchanged).
* ``/projects/{id}/stoplists`` CRUD          — editable per-project stoplists.

No new dependencies: statistics come from ``stats/measures.py`` (the same
tested formulas), tokenisation from ``api/ocrtools.py``.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..config import get_settings
from ..main import get_store
from ..nlp_ar.normalize import is_arabic, normalize_arabic
from ..stats import measures as M
from .ocrtools import AR_STOPWORDS, EN_STOPWORDS
from .ocrtools import _set_text as _ocr_set_text
from .ocrtools import _TOKEN_RE

router = APIRouter(tags=["text-corpus"])

BUILT_IN_STOPLISTS: dict[str, dict] = {
    "builtin-en": {
        "name": "builtin-en",
        "label": "Built-in English",
        "items": sorted(EN_STOPWORDS),
        "built_in": True,
    },
    "builtin-ar": {
        "name": "builtin-ar",
        "label": "Built-in Arabic",
        "items": sorted(AR_STOPWORDS),
        "built_in": True,
    },
    "builtin-none": {
        "name": "builtin-none",
        "label": "No stopword filtering",
        "items": [],
        "built_in": True,
    },
}
BUILTIN_DEFAULT = "builtin"  # EN ∪ AR, matching the pre-v0.3 behaviour


def _set_text(set_id: str) -> list[tuple[str, str, str]]:
    """(image_id, filename, text) triples in reading order."""
    store = get_store()
    if not store.get_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    out = []
    for img in store.list_images(set_id):
        meta = img.meta or {}
        text = (meta.get("ocr") or {}).get("text", "") or ""
        caption = (meta.get("user") or {}).get("caption", "")
        if caption:
            text = (text + " " + caption).strip()
        if text.strip():
            out.append((img.id, img.filename, text))
    return out


def resolve_stopwords(project_id: str, spec: str) -> set[str]:
    """Turn a ``stoplist`` query parameter into a word set.

    ``builtin`` (default) = EN ∪ AR built-ins (pre-v0.3 behaviour);
    ``builtin-en`` / ``builtin-ar`` / ``builtin-none``; anything else is
    resolved as a per-project custom stoplist name (404 when unknown).
    """
    if spec in ("", BUILTIN_DEFAULT):
        return EN_STOPWORDS | AR_STOPWORDS
    if spec in BUILT_IN_STOPLISTS:
        return set(BUILT_IN_STOPLISTS[spec]["items"])
    row = get_store().get_stoplist(project_id, spec)
    if row is None:
        raise HTTPException(404, f"Unknown stoplist: {spec}")
    return set(row["items"])


def _tokens(text: str, stop: set[str], min_len: int = 1) -> list[str]:
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if len(t) >= min_len and t.lower() not in stop
    ]


def _project_of_set(set_id: str) -> str:
    s = get_store().get_image_set(set_id)
    if not s:
        raise HTTPException(404, "Image set not found")
    return s.project_id


def _norm_tokens(set_id: str, stop: set[str], normalize_ar: bool = True,
                 min_len: int = 1) -> list[tuple[str, list[str]]]:
    """[(image_id, tokens)] with optional Arabic orthography folding."""
    out = []
    for iid, _fname, text in _set_text(set_id):
        if normalize_ar and is_arabic(text):
            text = normalize_arabic(text)
        out.append((iid, _tokens(text, stop, min_len)))
    return out


# --------------------------------------------------------------------------- #
# Wordlist
# --------------------------------------------------------------------------- #


@router.get("/imagesets/{set_id}/text/wordlist")
async def wordlist(set_id: str, stoplist: str = BUILTIN_DEFAULT,
                   normalize_ar: bool = True, min_len: int = 1) -> dict:
    project = _project_of_set(set_id)
    stop = resolve_stopwords(project, stoplist)
    counts: Counter = Counter()
    for _iid, toks in _norm_tokens(set_id, stop, normalize_ar, min_len):
        counts.update(toks)
    n = sum(counts.values())
    return {
        "tokens": n,
        "types": len(counts),
        "ttr": round(M.type_token_ratio([t for t, c in counts.items() for _ in range(c)]), 4) if n else 0.0,
        "stoplist": stoplist,
        "items": [{"word": w, "count": c, "freq_pm": round(c / n * 1_000_000, 2) if n else 0}
                  for w, c in counts.most_common()],
    }


# --------------------------------------------------------------------------- #
# Concordancer 2.0
# --------------------------------------------------------------------------- #


@router.get("/imagesets/{set_id}/text/concordance")
async def concordance(set_id: str, query: str, regex: bool = False,
                      context_words: int = 6, sort: str = "none",
                      max_hits: int = 500, stoplist: str = "builtin-none") -> dict:
    """KWIC over the OCR corpus with per-hit metadata and sort positions.

    Concordance lines keep stopwords (a concordancer must not hide "not in"
    or "of the"); stopword filtering applies to collocations/wordlists.
    ``sort`` re-orders hits on the first left (L1) or first right (R1)
    neighbour, like AntConc's sort buttons.
    """
    if max_hits > 5000:
        max_hits = 5000
    project = _project_of_set(set_id)
    stop = resolve_stopwords(project, stoplist)
    try:
        rx = re.compile(query if regex else re.escape(query), re.IGNORECASE)
    except re.error as e:
        raise HTTPException(422, f"Invalid regex: {e}")

    hits = []
    for iid, fname, text in _set_text(set_id):
        toks = _tokens(text, stop)
        positions = [i for i, tok in enumerate(toks) if rx.search(tok)]
        for i in positions:
            hits.append({
                "image_id": iid,
                "image": fname,
                "position": i,
                "left": toks[max(0, i - context_words): i],
                "node": toks[i],
                "right": toks[i + 1: i + 1 + context_words],
            })

    if sort == "L1":
        hits.sort(key=lambda h: h["left"][-1].lower() if h["left"] else "")
    elif sort == "R1":
        hits.sort(key=lambda h: h["right"][0].lower() if h["right"] else "")

    return {
        "query": query,
        "regex": regex,
        "sort": sort,
        "hits": hits[:max_hits],
        "total": len(hits),
        "truncated": len(hits) > max_hits,
    }


@router.get("/imagesets/{set_id}/text/concordance/export")
async def concordance_export(set_id: str, query: str, regex: bool = False,
                             context_words: int = 6, format: str = "csv") -> Response:
    result = await concordance(set_id, query, regex=regex,
                               context_words=context_words, max_hits=5000)
    rows = [{
        "left": " ".join(h["left"]),
        "node": h["node"],
        "right": " ".join(h["right"]),
        "image": h["image"],
        "position": h["position"],
    } for h in result["hits"]]
    return _render_rows(rows, format, f"lens-concordance-{set_id}")


def _render_rows(rows: list[dict], format: str, name: str) -> Response:
    """Same renderer the battery/export endpoints use (imported lazily to
    keep one implementation of the CSV/XLSX/XML machinery)."""
    from .export import _render

    return _render(rows, format, name)


# --------------------------------------------------------------------------- #
# Collocations + network
# --------------------------------------------------------------------------- #


@router.get("/imagesets/{set_id}/text/collocations")
async def collocations(set_id: str, node: str, span: int = 5, min_freq: int = 2,
                       metric: str = "mi", top: int = 50,
                       stoplist: str = BUILTIN_DEFAULT) -> dict:
    """Span-based collocates of ``node`` with the classic statistics.

    O = co-occurrence within ±span, R = node frequency, C = collocate
    frequency, N = number of tokens in the tokenised corpus. Every measure
    is computed, the table is sortable client-side; ``metric`` only picks
    the default ranking and the network edge weights.
    """
    if span < 1 or span > 10:
        raise HTTPException(422, "span must be 1-10")
    project = _project_of_set(set_id)
    stop = resolve_stopwords(project, stoplist)
    docs = _norm_tokens(set_id, stop)
    ntok = sum(len(toks) for _iid, toks in docs)

    node_l = node.lower()
    joint: Counter = Counter()
    r_freq = 0
    windows = 0
    for _iid, toks in docs:
        positions = [i for i, t in enumerate(toks) if t == node_l]
        r_freq += len(positions)
        for i in positions:
            lo, hi = max(0, i - span), min(len(toks), i + span + 1)
            window = toks[lo:i] + toks[i + 1:hi]
            windows += 1
            joint.update(window)

    if r_freq == 0:
        return {"node": node, "span": span, "N": ntok, "node_freq": 0,
                "rows": [], "edges": [],
                "note": f"'{node}' does not occur in this set's OCR text."}

    rows = []
    for word, o in joint.items():
        if o < min_freq:
            continue
        c = sum(toks.count(word) for _iid, toks in docs)
        mi = M.mutual_information(o, r_freq, c, windows)
        t = M.t_score(o, r_freq, c, windows)
        ll = M.log_likelihood_2x2(a=o, b=r_freq - o, c=c - o,
                                  d=max(0, ntok - r_freq - c + o))
        dice = M.dice_coefficient(o, r_freq, c)
        dp = M.delta_p(o, r_freq, c, ntok)
        rows.append({
            "word": word, "O": o, "R": r_freq, "C": c,
            "mi": round(mi, 4) if mi != float("-inf") else mi,
            "t_score": round(t, 4), "log_likelihood": round(ll, 4),
            "log_dice": round(M.log_dice(o, r_freq, c), 4) if dice > 0 else None,
            "delta_p": round(dp[0], 4), "delta_p_reverse": round(dp[1], 4),
        })

    sorters = {
        "mi": lambda r: r["mi"], "t": lambda r: r["t_score"],
        "ll": lambda r: r["log_likelihood"], "logdice": lambda r: r["log_dice"] or -99,
        "deltap": lambda r: r["delta_p"], "freq": lambda r: r["O"],
    }
    rows.sort(key=sorters.get(metric, sorters["mi"]), reverse=True)
    rows = rows[:top]

    edges = [{"source": node_l, "target": r["word"], "weight": abs(
        r["mi"] if isinstance(r["mi"], (int, float)) else 0)} for r in rows]
    return {
        "node": node, "span": span, "metric": metric, "N": ntok,
        "node_freq": r_freq, "rows": rows, "edges": edges,
        "note": "All measures computed together (MI, t, LL, LogDice, ΔP); "
                "sorting by " + metric + ".",
    }


# --------------------------------------------------------------------------- #
# N-grams / lexical bundles
# --------------------------------------------------------------------------- #


@router.get("/imagesets/{set_id}/text/ngrams")
async def ngrams(set_id: str, n: int = 2, min_count: int = 2, top: int = 50,
                 stoplist: str = BUILTIN_DEFAULT) -> dict:
    """N-grams over reading order; a high ``min_count`` turns the list into
    lexical bundles. Per-gram text dispersion (Juilland's D, Gries' DP) is
    computed over the set's images as bins (Larsson-style text dispersion)."""
    if n < 2 or n > 6:
        raise HTTPException(422, "n must be 2-6")
    project = _project_of_set(set_id)
    stop = resolve_stopwords(project, stoplist)
    docs = _norm_tokens(set_id, stop)

    counts: Counter = Counter()
    per_image: dict[tuple, Counter] = {}
    for iid, toks in docs:
        for i in range(len(toks) - n + 1):
            gram = tuple(toks[i: i + n])
            counts[gram] += 1
            per_image.setdefault(gram, Counter())[iid] += 1

    n_docs = max(1, len(docs))
    rows = []
    for gram, c in counts.most_common():
        if c < min_count:
            break
        obs = [per_image[gram].get(iid, 0) for iid, _t in docs]
        rows.append({
            "gram": list(gram),
            "count": c,
            "juillands_d": round(M.juillands_d(obs), 4),
            "gries_dp": round(M.gries_dp(obs), 4),
            "range": sum(1 for v in obs if v > 0),
            "images": n_docs,
        })
        if len(rows) >= top:
            break
    return {"n": n, "min_count": min_count, "rows": rows,
            "note": "Dispersion over reading order (bins = images in created_at order)."}


@router.get("/imagesets/{set_id}/text/ngrams/export")
async def ngrams_export(set_id: str, n: int = 2, min_count: int = 2,
                        format: str = "csv") -> Response:
    result = await ngrams(set_id, n=n, min_count=min_count, top=500)
    rows = [{"gram": " ".join(r["gram"]), "count": r["count"],
             "juillands_d": r["juillands_d"], "gries_dp": r["gries_dp"]}
            for r in result["rows"]]
    return _render_rows(rows, format, f"lens-ngrams-{set_id}")


# --------------------------------------------------------------------------- #
# Dispersion gallery
# --------------------------------------------------------------------------- #


@router.get("/imagesets/{set_id}/text/dispersion")
async def dispersion(set_id: str, top: int = 100,
                     stoplist: str = BUILTIN_DEFAULT) -> dict:
    """Per-word dispersion across the set's images (bins = reading order)."""
    project = _project_of_set(set_id)
    stop = resolve_stopwords(project, stoplist)
    docs = _norm_tokens(set_id, stop)
    counts: Counter = Counter()
    per_image: dict[str, Counter] = {}
    for iid, toks in docs:
        counts.update(toks)
        per_image.update({iid: Counter(toks)})
    n_docs = max(1, len(docs))
    rows = []
    for word, c in counts.most_common():
        obs = [per_image.get(iid, Counter()).get(word, 0) for iid, _t in docs]
        rows.append({
            "word": word, "count": c,
            "juillands_d": round(M.juillands_d(obs), 4),
            "gries_dp": round(M.gries_dp(obs), 4),
            "range": sum(1 for v in obs if v > 0),
            "images": n_docs,
        })
        if len(rows) >= top:
            break
    return {"rows": rows, "bins": n_docs,
            "note": "Juilland's D (evenness) and Gries' DP (0=even, 1=concentrated)."}


# --------------------------------------------------------------------------- #
# Word sketch — visual edition
# --------------------------------------------------------------------------- #


@router.get("/imagesets/{set_id}/text/sketch")
async def sketch(set_id: str, word: str, top: int = 10) -> dict:
    """One-page profile of a token, re-imagined for visual corpora.

    Text side: frequency, top collocates (MI), sample concordance lines.
    Visual side: the typical co-patterns of the images the token appears in
    (dominant colours, brightness/warmth, annotation dimension values,
    typography register, detected object labels) — Sketch Engine's word
    sketch idea mapped onto visual-grammar evidence instead of dependencies.
    """
    docs = _set_text(set_id)
    word_l = word.lower()
    tok_docs = [(iid, fname, _tokens(text, set())) for iid, fname, text in docs]
    containing: list[tuple[str, str]] = []
    freq: Counter = Counter()
    joint: Counter = Counter()
    for iid, fname, toks in tok_docs:
        idx = [i for i, t in enumerate(toks) if t == word_l]
        if not idx:
            continue
        containing.append((iid, fname))
        freq.update(toks)
        for i in idx:
            joint.update(toks[max(0, i - 5): i] + toks[i + 1: i + 6])

    store = get_store()
    ntok = sum(len(toks) for _i, _f, toks in tok_docs)
    node_r = freq[word_l]
    collocates = []
    for w, o in joint.most_common(60):
        if o < 2:
            break
        c = freq[w]
        mi = M.mutual_information(o, node_r, c, ntok)
        if mi != float("-inf"):
            collocates.append({"word": w, "O": o, "C": c, "mi": round(mi, 3)})
        if len(collocates) >= top:
            break

    # Visual co-patterns over the images that contain the token.
    colours: Counter = Counter()
    annotations: Counter = Counter()
    objects: Counter = Counter()
    typography: Counter = Counter()
    brightness: list[float] = []
    warmth: list[float] = []
    for iid, _fname in containing:
        img = store.get_image(iid)
        meta = (img.meta or {}) if img else {}
        col = meta.get("colour") or {}
        for c in (col.get("dominant_colours") or [])[:3]:
            hexv = c.get("hex") if isinstance(c, dict) else c
            if hexv:
                colours[hexv] += 1
        if isinstance(col.get("brightness"), (int, float)):
            brightness.append(float(col["brightness"]))
        if isinstance(col.get("warm_cold_balance"), (int, float)):
            warmth.append(float(col["warm_cold_balance"]))
        for dim, block in (meta.get("annotations") or {}).items():
            for v in (block or {}).get("values", []):
                annotations[f"{dim}:{v}"] += 1
        for d in meta.get("detections") or []:
            objects[d.get("label", "?")] += 1
        typo = meta.get("typography") or {}
        register = typo.get("register") or typo.get("style") or ""
        if register:
            typography[str(register)] += 1

    conc_lines = []
    for iid, fname, toks in tok_docs:
        for i, t in enumerate(toks):
            if t == word_l:
                conc_lines.append({
                    "image": fname, "image_id": iid,
                    "left": " ".join(toks[max(0, i - 6): i]),
                    "node": t, "right": " ".join(toks[i + 1: i + 7]),
                })
                break
        if len(conc_lines) >= 8:
            break

    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None
    return {
        "word": word_l,
        "freq": node_r,
        "images_with_token": len(containing),
        "collocates": collocates,
        "concordance_sample": conc_lines,
        "visual_copatterns": {
            "dominant_colours": [{"hex": h, "count": c} for h, c in colours.most_common(6)],
            "mean_brightness": mean(brightness),
            "mean_warm_cold_balance": mean(warmth),
            "annotation_values": [{"value": v, "count": c}
                                  for v, c in annotations.most_common(10)],
            "detected_objects": [{"label": o, "count": c} for o, c in objects.most_common(8)],
            "typography": [{"register": t, "count": c} for t, c in typography.most_common(6)],
        },
        "note": "Visual co-patterns summarise only the images in which the token occurs; "
                "claims remain framework-attributed hypotheses (Hardie discipline applies "
                "to collocation strength, not to colour aesthetics).",
    }


# --------------------------------------------------------------------------- #
# Reference-corpus keyness
# --------------------------------------------------------------------------- #


def _load_reference(reference_id: str) -> dict:
    """Load a bundled TSV frequency table. Header lines start with '#';
    format: word<TAB>freq [<TAB>per_million]."""
    settings = get_settings()
    table_dir = Path(settings.reference_dir)
    candidates = list(table_dir.rglob(f"{reference_id}.tsv"))
    if not candidates:
        raise HTTPException(404, f"Unknown reference table: {reference_id}")
    words: dict[str, int] = {}
    total = 0
    for raw in candidates[0].read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            f = int(float(parts[1]))
        except ValueError:
            continue
        w = parts[0].strip().lower()
        words[w] = f
        total += f
    if not words:
        raise HTTPException(500, f"Reference table {reference_id} is empty")
    return {"words": words, "total": total}


@router.get("/imagesets/{set_id}/text/references")
async def references() -> dict:
    """Bundled reference frequency tables (id, label, language, size)."""
    settings = get_settings()
    out = []
    table_dir = Path(settings.reference_dir)
    if table_dir.is_dir():
        for path in sorted(table_dir.rglob("*.tsv")):
            header = []
            for raw in path.read_text(encoding="utf-8").splitlines()[:6]:
                if raw.startswith("#"):
                    header.append(raw.lstrip("# ").strip())
                else:
                    break
            n_words = 0
            for raw in path.read_text(encoding="utf-8").splitlines():
                if raw.strip() and not raw.startswith("#"):
                    n_words += 1
            out.append({
                "id": path.stem,
                "file": str(path.relative_to(table_dir)),
                "lang": path.parent.name,
                "words": n_words,
                "description": header[0] if header else path.stem,
            })
    return {"references": out,
            "note": "Open-licensed derivative frequency lists (CC BY 4.0 / public "
                    "domain); attribution headers are preserved in each file."}


@router.get("/imagesets/{set_id}/text/keyness-reference")
async def keyness_reference(set_id: str, reference: str,
                            stoplist: str = BUILTIN_DEFAULT) -> dict:
    """Keyness of the set's OCR corpus against a bundled reference table.

    f2/N2 come from the reference frequencies, so keyness works without a
    second image set. Significance (LL, χ², Fisher) and effect size
    (Log Ratio, %DIFF, ...) are always computed together, exactly as in the
    set-vs-set keyness endpoint.
    """
    ref = _load_reference(reference)
    project = _project_of_set(set_id)
    stop = resolve_stopwords(project, stoplist)
    ct: Counter = Counter()
    for _iid, toks in _norm_tokens(set_id, stop):
        ct.update(toks)
    N1 = sum(ct.values())
    N2 = ref["total"]
    rows = []
    for term in set(ct) | (set(ref["words"]) & {t for t, c in ct.items() if c > 0}):
        row = M.compute_keyness_row(term, ct[term], ref["words"].get(term, 0), N1, N2)
        rows.append({
            "term": row.term, "f1": row.f1, "f2": row.f2,
            **{k: (round(v, 4) if abs(v) != float("inf") else v)
               for k, v in row.measures.items()},
        })
    rows.sort(key=lambda r: r["log_likelihood"], reverse=True)
    return {"reference": reference, "N1": N1, "N2": N2, "rows": rows[:500],
            "note": "Significance + effect size always together (Hardie's discipline)."}


@router.get("/imagesets/{set_id}/text/keyness-reference/export")
async def keyness_reference_export(set_id: str, reference: str,
                                   format: str = "csv") -> Response:
    result = await keyness_reference(set_id, reference)
    return _render_rows(result["rows"], format, f"lens-keyness-{reference}-{set_id}")


# --------------------------------------------------------------------------- #
# Stoplist CRUD (per project)
# --------------------------------------------------------------------------- #


class StoplistPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    items: list[str] = Field(default_factory=list)


@router.get("/projects/{project_id}/stoplists")
async def list_stoplists(project_id: str) -> dict:
    store = get_store()
    if not store.get_project(project_id):
        raise HTTPException(404, "Project not found")
    custom = store.list_stoplists(project_id)
    for row in custom:
        row["label"] = row["name"]
    return {"built_in": list(BUILT_IN_STOPLISTS.values()), "custom": custom}


@router.post("/projects/{project_id}/stoplists")
async def create_stoplist(project_id: str, payload: StoplistPayload) -> dict:
    store = get_store()
    if not store.get_project(project_id):
        raise HTTPException(404, "Project not found")
    name = payload.name.strip()
    if name.startswith("builtin-"):
        raise HTTPException(422, "Names starting with 'builtin-' are reserved")
    row = store.upsert_stoplist(project_id, name, payload.items)
    return row


@router.put("/projects/{project_id}/stoplists/{name}")
async def update_stoplist(project_id: str, name: str, payload: StoplistPayload) -> dict:
    store = get_store()
    if not store.get_stoplist(project_id, name):
        raise HTTPException(404, "Stoplist not found")
    if name.startswith("builtin-"):
        raise HTTPException(422, "Built-in stoplists cannot be modified")
    return store.upsert_stoplist(project_id, name, payload.items)


@router.delete("/projects/{project_id}/stoplists/{name}")
async def delete_stoplist(project_id: str, name: str) -> dict:
    if not get_store().delete_stoplist(project_id, name):
        raise HTTPException(404, "Custom stoplist not found (built-ins cannot be deleted)")
    return {"deleted": name}
