"""Model catalog — curated Ollama-library entries + HuggingFace GGUF search.

Two sources, one contract (v0.2 "wide variety + HF access, LM-Studio-style"):

1. **Curated** — hand-picked entries from the Ollama library covering the
   three tasks Lens actually uses, each with an honest size/RAM/VRAM
   estimate. Curated entries are always available offline (no network) and
   are the only source of *defaults*.

2. **HuggingFace search** — ``https://huggingface.co/api/models`` filtered to
   GGUF repos, which Ollama ≥0.5 pulls directly (``ollama pull
   hf.co/<user>/<repo>:<variant>``). This is the "browse current models like
   LM Studio" surface. HF results carry no hand-curated metadata, so fit
   badges are computed from the repo's quantized-file sizes.

Fit scoring answers one question: *will this model run on THIS machine
without brutal CPU-offload slowdowns?* The rule of thumb encoded here:

- ``gpu``       — full model fits in the largest VRAM (fast, recommended).
- ``cpu``       — fits in RAM with headroom (works everywhere, slower).
- ``tight``     — fits only with partial offload or <20% headroom; allowed
                  but flagged.
- ``too-big``   — does not fit; the UI should discourage the download.

Estimates are intentionally conservative (rule-of-thumb constants, not
benchmarks) and every response says ``estimates: "rule-of-thumb"`` so no
number is mistaken for a measurement — the parent's honesty discipline.
"""
from __future__ import annotations

import httpx
from dataclasses import dataclass

from ..logging import get_logger

log = get_logger(__name__)

HF_API = "https://huggingface.co/api/models"


# --------------------------------------------------------------------------- #
# Curated catalog (Ollama library names; sizes = default tag download size)
# --------------------------------------------------------------------------- #

@dataclass(slots=True, frozen=True)
class CatalogEntry:
    model: str              # pull name, e.g. "qwen2.5vl:3b"
    display: str
    task: str               # "vision" | "text" | "embedding"
    size_gb: float          # download size (default tag)
    ram_gb: float           # RAM needed to run comfortably
    vram_gb: float          # VRAM needed to run fully on GPU
    multilingual: bool      # Arabic-capable or language-neutral
    params: str
    notes: str


CURATED: list[CatalogEntry] = [
    # ── Vision (image describe / annotate / OCR assist) ──────────────────
    CatalogEntry("qwen2.5vl:3b", "Qwen2.5-VL 3B", "vision", 3.2, 8, 6, True, "3B",
                 "Best small local vision model; strong OCR + Arabic text."),
    CatalogEntry("qwen2.5vl:7b", "Qwen2.5-VL 7B", "vision", 6.0, 16, 8, True, "7B",
                 "Higher-fidelity describe/annotate; needs 8GB+ VRAM or 16GB RAM."),
    CatalogEntry("llama3.2-vision:11b", "Llama 3.2 Vision 11B", "vision", 7.9, 16, 10, False, "11B",
                 "Good English describe/annotate; weaker Arabic OCR."),
    CatalogEntry("llava:7b", "LLaVA 7B", "vision", 4.7, 12, 6, False, "7B",
                 "Classic baseline; lighter machines."),
    CatalogEntry("moondream", "Moondream 1.8B", "vision", 1.7, 4, 3, False, "1.8B",
                 "Tiny vision model for low-end machines; English only."),
    # ── Text (assistant / LLM framework modes / annotation pre-pass) ─────
    CatalogEntry("llama3.2:3b", "Llama 3.2 3B", "text", 2.0, 8, 4, False, "3B",
                 "Fast general chat + tool use; English-centric."),
    CatalogEntry("qwen3:4b", "Qwen3 4B", "text", 2.6, 8, 5, True, "4B",
                 "Strong multilingual (incl. Arabic) reasoning/chat."),
    CatalogEntry("qwen3:8b", "Qwen3 8B", "text", 5.2, 16, 8, True, "8B",
                 "Higher-quality multilingual analysis."),
    CatalogEntry("gemma3:4b", "Gemma 3 4B", "text", 3.3, 8, 5, True, "4B",
                 "Multilingual chat, good instruction following."),
    CatalogEntry("phi4-mini", "Phi-4-mini 3.8B", "text", 2.5, 8, 5, False, "3.8B",
                 "Efficient reasoning; English-centric."),
    # ── Embeddings (semantic search / vector KWIC; multilingual matters) ─
    CatalogEntry("bge-m3", "BGE-M3", "embedding", 1.2, 4, 2, True, "568M",
                 "Multilingual (100+ langs, strong Arabic); RECOMMENDED for Lens."),
    CatalogEntry("nomic-embed-text", "Nomic Embed Text", "embedding", 0.27, 2, 1, False, "137M",
                 "Fast English embedding; long context."),
    CatalogEntry("qwen3-embedding:0.6b", "Qwen3 Embedding 0.6B", "embedding", 0.6, 3, 2, True, "600M",
                 "Multilingual embeddings, top MTEB in class."),
]


# --------------------------------------------------------------------------- #
# Fit scoring
# --------------------------------------------------------------------------- #

def fit_badge(entry_size_gb: float, entry_ram_gb: float, entry_vram_gb: float,
              specs: dict | None) -> dict:
    """One honest badge: 'gpu' | 'cpu' | 'tight' | 'too-big' | 'unknown'."""
    if not specs or specs.get("ram_gb") is None:
        return {"fit": "unknown", "reason": "Machine specs unavailable — fit cannot be estimated."}
    ram = float(specs["ram_gb"])
    vram = 0.0
    for g in specs.get("gpus") or []:
        try:
            vram = max(vram, float(g.get("vram_gb") or 0))
        except Exception:
            continue

    if vram >= entry_vram_gb * 1.05:
        return {"fit": "gpu", "reason": f"Fits in {vram:.0f} GB VRAM — runs fully on GPU."}
    if ram >= entry_ram_gb * 1.35:
        return {"fit": "cpu", "reason": f"Fits in {ram:.0f} GB RAM with headroom — CPU inference."}
    if ram >= entry_ram_gb * 1.05:
        return {"fit": "tight", "reason": f"Runs in {ram:.0f} GB RAM with little headroom; expect slower responses."}
    return {"fit": "too-big",
            "reason": f"Needs ~{entry_ram_gb:.0f} GB RAM/VRAM; this machine reports {ram:.0f} GB — offloading will be very slow."}


def entry_to_dict(e: CatalogEntry, specs: dict | None) -> dict:
    return {
        "model": e.model, "display": e.display, "task": e.task,
        "size_gb": e.size_gb, "params": e.params,
        "multilingual": e.multilingual, "notes": e.notes,
        "source": "curated", "ref": e.model,
        **fit_badge(e.size_gb, e.ram_gb, e.vram_gb, specs),
    }


# --------------------------------------------------------------------------- #
# HuggingFace GGUF search (Ollama ≥0.5 pulls hf.co/<user>/<repo>:<variant>)
# --------------------------------------------------------------------------- #

def _hf_pick_variant(siblings: list[dict]) -> tuple[str, float]:
    """Pick a sensible default quant (Q4_K_M if present, else largest .gguf)
    and return (variant_tag, size_gb)."""
    ggufs = [s for s in siblings if (s.get("rfilename") or "").endswith(".gguf")]
    if not ggufs:
        return "", 0.0
    by_name = {s["rfilename"]: s.get("size", 0) for s in ggufs}

    def total_for(tag: str) -> float:
        # split/repo-style sharding sums across shards with the same quant tag
        return sum(sz for name, sz in by_name.items() if tag in name)

    for tag in ("Q4_K_M", "Q4_K_S", "Q4_0", "Q5_K_M", "Q8_0"):
        sz = total_for(tag)
        if sz:
            return tag, round(sz / 1024**3, 2)
    name, sz = max(by_name.items(), key=lambda kv: kv[1])
    tail = name.rsplit(".", 1)[-1].upper() if "." in name else ""
    return tail or "Q4_K_M", round(sz / 1024**3, 2)


def hf_search(query: str, *, task: str = "text", limit: int = 12,
              specs: dict | None = None, timeout: float = 20.0) -> list[dict]:
    """Search HuggingFace for GGUF models pullable by Ollama.

    Task filters are heuristic (HF has no task axis for GGUF repos): vision
    repos usually carry 'vl'/'vision'/'llava' in their id, embedding repos
    'embed'. Everything else counts as text. Fit badges reuse the curated
    scoring with the *quantized* file size — RAM estimate ≈ 1.4 × file size
    (weights + KV cache + runtime overhead, conservative).
    """
    params = {"search": query, "filter": "gguf", "sort": "downloads",
              "direction": -1, "limit": max(5, min(40, limit))}
    try:
        r = httpx.get(HF_API, params=params, timeout=timeout,
                      headers={"User-Agent": "CorpusMind-Lens/0.2"})
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        log.warning("hf_search_failed", extra={"error": str(e)})
        return []

    out: list[dict] = []
    for row in rows:
        rid = row.get("id") or row.get("modelId") or ""
        if not rid:
            continue
        siblings = row.get("siblings") or []
        variant, size_gb = _hf_pick_variant(siblings)
        if not size_gb:
            # siblings without sizes: fetch the ?blobs=true variant lazily is
            # too costly per row; fall back to a neutral estimate by downloads
            size_gb = 0.0
        low = rid.lower()
        detected = ("vision" if any(k in low for k in ("vl", "vision", "llava", "moondream"))
                    else "embedding" if "embed" in low else "text")
        if task != "any" and task != detected:
            continue
        ram_est = round(max(size_gb * 1.4, 1.5), 1)
        vram_est = round(max(size_gb * 1.15, 1.2), 1)
        out.append({
            "model": rid,
            "display": rid.split("/")[-1],
            "task": detected,
            "size_gb": size_gb,
            "params": row.get("downloads", 0),
            "multilingual": any(k in low for k in ("qwen", "gemma", "bge", "arabic", "multi", "jina")),
            "notes": f"HuggingFace GGUF · default quant {variant or 'n/a'} · "
                     f"{row.get('downloads', 0)} downloads",
            "source": "huggingface",
            "ref": f"hf.co/{rid}:{variant}" if variant else f"hf.co/{rid}",
            **fit_badge(size_gb, ram_est, vram_est, specs),
        })
    return out


def recommended(specs: dict | None) -> list[dict]:
    """Defaults shown by the Setup screen, ordered for this machine."""
    picks = ["qwen2.5vl:3b", "qwen3:4b", "bge-m3"]
    if specs:
        ram = specs.get("ram_gb") or 0
        vram = max((float(g.get("vram_gb") or 0) for g in specs.get("gpus") or []), default=0.0)
        if ram >= 16 and vram >= 8:
            picks = ["qwen2.5vl:7b", "qwen3:8b", "bge-m3"]
        elif ram and ram < 12:
            picks = ["moondream", "llama3.2:3b", "nomic-embed-text"]
    by_model = {e.model: e for e in CURATED}
    out = []
    for m in picks:
        e = by_model.get(m)
        if e:
            out.append(entry_to_dict(e, specs))
    return out


def curated(task: str, specs: dict | None) -> list[dict]:
    rows = [entry_to_dict(e, specs) for e in CURATED]
    if task and task != "any":
        rows = [r for r in rows if r["task"] == task]
    return rows
