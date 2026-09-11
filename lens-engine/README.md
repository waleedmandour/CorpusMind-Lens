# lens-engine

The CorpusMind Lens engine: a local-first FastAPI service implementing the visual/multimodal corpus-analysis stack — image-set ingestion, EXIF/XMP metadata (GPS permanently excluded), OCR, colour & composition analysis, open-vocabulary detection, the five-dimension annotation framework, the corpus-statistics battery over annotation sequences, twelve framework-lensed discourse analyses, a grounded AI assistant, and an optional Companion-Mode client for a running CorpusMind (Text) engine.

## Run

```bash
pip install -e ".[all]"
uvicorn lens_engine.main:app --port 8765
```

Interactive API docs: `http://127.0.0.1:8765/docs` — every route lives under `/api/v1`.

## Layout

```
lens_engine/
├── main.py          FastAPI app factory, CORS, routers, background worker
├── config.py        Settings (env: LENS_*)
├── logging.py       Structured logging
├── api/             REST + WebSocket routes (health, projects, imagesets, images,
│                    annotations, analysis, detection, alignment, visual_grammar,
│                    discourse, battery, compare, ocrtools, export, assistant,
│                    settings, companion)
├── vision/          ingestion, metadata, OCR, colour/composition, annotations,
│                    consent gate, facial analysis (opt-in)
├── detection/       open-vocabulary detector wrapper + scene classifier +
│                    typography-from-OCR profiling
├── multimodal/      embeddings-backed alignment, visual grammar, cross-modal meaning
├── discourse/       the 12 framework lenses (heuristic + LLM modes)
├── stats/           forked §11 formulas + the battery service
├── nlp_ar/          Arabic OCR/caption post-processing (scoped)
├── ai/              ModelProvider (Ollama / LM Studio / Cloud), tool registry, audit
├── storage/         Project/ImageSet/Image store (SQLite + JSON columns), encryption
├── companion/       optional CorpusMind (Text) HTTP client
└── export/          per-image/per-set exports + Methods Section draft
```

## Configuration (environment variables, all optional)

| Variable | Default | Purpose |
|---|---|---|
| `LENS_HOST` / `LENS_PORT` | `127.0.0.1` / `8765` | Bind address |
| `LENS_DATA_DIR` | `./data` | Where projects/images/SQLite live |
| `LENS_FACIAL_ANALYSIS` | `0` | Master switch for facial/body analysis (§9.6) — **off by default**; the consent gate is enforced server-side regardless of UI input |
| `LENS_CLOUD_ENABLED` | `0` | Master switch for cloud AI providers — off by default |
| `LENS_ENCRYPTION_KEY` | unset | Fernet key; when set, image bytes are encrypted at rest |
| `LENS_FRAMEWORKS_DIR` | repo `reference-data/frameworks` | Where the 12 YAML templates live |

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The statistics tests are the regression floor: every §11 formula is pinned to a hand-computed worked example.
