# CorpusMind Lens — Architecture

*Own repository, own engine, own frontend (§5). This document describes the system as built in this repo; nothing here describes CorpusMind (Text) internals.*

## System shape

Headless engine, multiple shells — the pattern the parent product proved out on consumer hardware with local-LLM constraints. Every box below lives in **this** repository:

```
┌──────────────────────────────────────────────────────────────────┐
│  Shells                                                          │
│  ┌────────────┐   ┌──────────────────┐   ┌───────────────────┐  │
│  │ lens-web   │   │ lens-desktop     │   │ Self-hosted       │  │
│  │ (PWA/Vite) │   │ (Tauri 2 shell)  │   │ (Docker, labs)    │  │
│  └─────┬──────┘   └────────┬─────────┘   └─────────┬─────────┘  │
│        │  HTTP (localhost) │ sidecar lifecycle     │            │
└────────┼───────────────────┼───────────────────────┼────────────┘
         ▼                   ▼                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  lens-engine  (FastAPI, Python 3.12, asyncio)                    │
│                                                                  │
│  api/       REST routes under /api/v1 (OpenAPI at /docs)         │
│  vision/    ingestion (magic-byte hardened) · EXIF/XMP (no GPS)  │
│             OCR (per-word boxes) · colour · geometric            │
│             composition · 5-dim annotations · consent gate       │
│  detection/ open-vocabulary detector (OWL-ViT class, local) ·    │
│             scene classifier · typography-from-OCR               │
│  multimodal/ embeddings-backed alignment (CLIP class) with       │
│             honest grid fallback · visual grammar · cross-modal  │
│  discourse/ 12 framework lenses (heuristic + LLM modes)          │
│  stats/     forked §11 formulas + the battery service            │
│  nlp_ar/    scoped Arabic OCR post-processing                    │
│  ai/        ModelProvider (Ollama/LM Studio/Cloud) · tool        │
│             registry · audit trail                               │
│  storage/   SQLite + JSON columns · optional at-rest encryption  │
│  companion/ optional CorpusMind (Text) HTTP client               │
│  export/    xlsx/csv/tsv/json exports · Methods Section          │
└──────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────┐          ┌────────────────────────────┐
│ Ollama / LM      │          │ CorpusMind (Text) engine   │
│ Studio (local,   │          │ (OPTIONAL Companion Mode — │
│ vision-capable)  │          │  documented HTTP contract) │
└──────────────────┘          └────────────────────────────┘
```

## The three shells

1. **lens-web (PWA).** A fresh, Lens-only React + Vite + TypeScript codebase. Views: Overview · Image Sets · Vision Workbench (four-tab: Overview / Image Set / Measures / Vision Analysis) · Assistant · Settings (Ethics, Companion, providers). Own design tokens in `src/styles/tokens.css` (badge `#2563eb`), dark/light themes, command palette (Ctrl/⌘K), EN/AR with **full RTL mirroring** (document direction, not just text). Installable PWA with an offline app shell; the service worker **never caches engine API responses** — research data must not be served stale.
2. **lens-desktop (Tauri 2).** Identifier `org.corpusmind.lens`, product name "CorpusMind Lens". Own sidecar lifecycle: detect a possibly-running CorpusMind (Text) engine on 8765 → pick a free port (Companion or shift) → spawn `lens-engine` → health-poll (60 s budget) → log-to-file → full detach on exit. macOS quarantine stripping and the Windows Defender cold-start window are handled explicitly (documented pitfalls from the parent's shipping history).
3. **Self-hosted (Docker).** Single-tenant-per-instance: one `lens-engine`, one data volume, OCR language packs baked into the image, frameworks mounted read-only.

## Background processing is mandatory (§13)

The parent shipped a real regression once: synchronous Pillow/Tesseract/NumPy analysis on the request thread froze the whole engine during batch ingest. Lens's `main.py` runs a fresh-per-lifespan asyncio queue with two workers; uploads return **202 Accepted** immediately and per-image status is polled. The same queue powers detection runs.

## Data model (§7)

```
Project
 └── ImageSet            ← the top-level corpus unit (no "Corpus" concept)
      ├── description, provenance/sampling notes, tags, genre/source/date meta
      ├── companion_link: { engine_base_url, corpus_id } | null
      └── Image
           ├── raw bytes on disk (optional Fernet at-rest encryption)
           ├── meta JSON:
           │     user fields (source/publication/licence/genre/lang-of-embedded-text)
           │     exif_xmp (GPS excluded by construction)
           │     ocr { text, confidence, engine, language, words[{text,conf,box}] }
           │     colour { dominant, warm_cold, brightness, contrast, saturation, notes }
           │     composition { information_value, thirds, salience, balance, vectors }
           │     detections [{ label, bbox, confidence, model, revision }]
           │     typography (from OCR box geometry)
           │     annotations { 5 dims × {values[], note, updated_at} }
           │     alignment (embedding- or grid-backend, labelled)
           │     vlm_description { text, model, version, timestamp }
           └── created_at  ← the set's reading order anchor
```

`companion_link` is the only place a CorpusMind (Text) identifier is ever stored; it is nullable and inert unless Companion Mode is on.

## Privacy architecture (§4, §13, §17)

- **GPS is never extracted** — the guarantee lives in `vision/meta.py` (whitelisted EXIF tags only; the GPS IFD is never read; the XMP packet scanner never touches location namespaces). There is no setting.
- **Consent gate** — person-descriptive content from any vision-LM output passes through `vision/consent_gate.py`; while Settings → Ethics facial analysis is off (the default), matching sentences are replaced with a visible redaction marker. Enforced server-side regardless of UI state.
- **Cloud off by default** — `CloudProvider` refuses construction unless `LENS_CLOUD_ENABLED=1`; the UI shows an unmissable indicator when active.
- **Audit trail** — every Assistant tool call and result is appended to `data/logs/assistant_audit.jsonl`.

## Grounding architecture (§4 Principle 2, §10)

The Assistant runs a two-phase protocol: the model first proposes tool calls (from the §10 surface), each tool executes against the live store (list_image_sets → get_text_corpus_overview, the latter only when Companion Mode is on), and the final answer is composed strictly from returned evidence. Claims without tool evidence are required to carry an `[ungrounded]` prefix, which the UI renders in red. The heuristic discourse lenses are grounding by construction: every claim cites computed feature paths.

## Versioning & reproducibility (§4 Principle 7)

- Engine version: `lens_engine.__version__`, reported in `/api/v1/health`.
- API version: `X-CorpusMind-API-Version` header (Companion Mode contract).
- Every model-touching result records model id + revision; the Methods Section export names every engine/model/formula version that produced a corpus's numbers.
- Framework templates are versioned YAML (`reference-data/frameworks/*.yaml`); their versions flow into result payloads.

## AI runtime topology (v0.2)

Lens has exactly one AI story on every platform: **the app is self-sufficient; local AI is a capability, not a package.**

- **Deterministic core** (statistics, batteries, exports, heuristic lenses) has zero AI dependencies and works with no backend installed — the honest-degradation rules of §4 Principle 6 are unchanged.
- **Local AI backends**: Ollama (native `/api/chat`, `/api/embed`, `/api/pull`) and LM Studio (OpenAI-compatible `/v1`). The desktop shell owns the Ollama *lifecycle* (find → `ollama serve` → TCP health → restart; only its own daemon is killed), while the engine owns the *protocol* (`ai/providers.py`). In PWA mode the engine can spawn `ollama serve` itself (`POST /ai/local/serve`).
- **Bootstrap**: one-click per-user silent install (winget/OllamaSetup.exe on Windows, dmg→`~/Applications` on macOS, tarball→`~/.lens-engine-data/ollama-runtime` on Linux) — never an admin prompt.
- **Model management**: `ai/catalog.py` serves curated entries + live HuggingFace GGUF search; every entry carries a conservative fit badge computed from the machine probe (shell `sysinfo` probe forwarded via `LENS_MACHINE_SPECS_JSON`, engine stdlib fallback; NVIDIA VRAM via `nvidia-smi`; Apple unified memory scaled by 0.75). Estimates are labelled `rule-of-thumb` in the payload.
- **Text-side semantics** (semantic search, and the v0.3 vector-KWIC it enables) ride Ollama embeddings (`bge-m3` default) with vectors cached in `image.meta.semantic`; this restores the semantic capability the packaged builds lost when torch stayed out of the sidecar — CLIP joint-space remains the image-side engine of record when the optional `models` extra is installed.
- **Failure posture**: missing backend → HTTP 409 with a setup hint (never fake data); missing model → a `pull` hint naming the exact model; all loopback, `trust_env=False`, nothing leaves the machine.
