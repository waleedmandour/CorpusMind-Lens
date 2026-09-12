# CorpusMind Lens

**CorpusMind Lens** is a local-first, AI-native, visual and multimodal corpus-analysis environment. It lets a researcher turn a set of images — with or without accompanying text — into publication-ready, statistically grounded, framework-lensed discourse analysis, using the same evidentiary rigor corpus linguistics has always demanded of text, applied for the first time to images at scale.

Lens is a sibling product of [CorpusMind](https://github.com/waleedmandour/CorpusMind) (text), not its "image tab": it has its own repository, its own engine, its own frontend, its own release cycle, its own brand identity, and its own Zenodo DOI. It interoperates with CorpusMind (Text) only through a documented, versioned HTTP API (optional, off by default — see *Companion Mode* in `docs/COMPANION_MODE.md`), never through shared source code or a shared UI shell.

---

## Why a standalone tool

Corpus linguistics as a field is actively moving to treat multimodal data and AI tooling as first-class methodology, and the tool landscape has not caught up:

- AntConc/WordSmith/Wordless-class concordancers have no image pipeline at all.
- CAQDAS tools (NVivo, ATLAS.ti, MAXQDA) are adding AI coding assistants but do not compute association/dispersion statistics or implement Visual Grammar as a structured score.
- The emerging "Automated Visual Content Analysis" research community mostly ships one-off academic scripts, not a maintained, zero-code, cross-platform application.

That gap is Lens's reason to exist.

## What Lens does

- **Image sets as first-class corpora.** Projects contain image sets (there is no "document" concept anywhere in Lens). Provenance notes, sampling metadata, set-level statistics, and a generic set-vs-set comparison workflow.
- **Automatic image analysis.** EXIF/XMP (IPTC-Core-aligned) extraction, Arabic+English OCR with per-image confidence, colour and geometric composition analysis, open-vocabulary object/scene detection, typography-in-image profiling — all deterministic and re-runnable.
- **The five-dimension visual annotation framework** (flagship): Visual Morphology (Cohn 2013), Attentional Framing (Kress & van Leeuwen 2006; Bateman 2008), Filmic Shot Scale (Bordwell & Thompson 2013), Path Structure & Transitions (McCloud 1993), and Multimodal Integration (Barthes 1977; Royce 2007) — 54 categories, multi-select, with bulk tagging and server-side validation.
- **A corpus-linguistics measurement battery over those annotations**: frequency profiles, diversity (TTR, Guiraud's R, MATTR, STTR), sequence n-grams over reading order, co-occurrence association between dimensions (MI, T-score, Dice, LogDice, ΔP, G², χ²), set-vs-set keyness (log-likelihood **always reported together with** effect sizes — Log Ratio, %DIFF, Simple Maths, Odds Ratio), dispersion (Juilland's D, Gries' DP with per-bin histograms), and a visual KWIC.
- **Twelve theoretical-framework discourse lenses** (Kress & van Leeuwen, Halliday's SFL, Fairclough/van Dijk/Wodak/Machin & Mayr CDA, Barthes, Peirce, Lakoff & Johnson, Martin & White, Toulmin, Aristotle) — each in a deterministic heuristic mode and an optional LLM mode, with provenance badges and framework-attributed, hedged phrasing ("under a [Framework] reading, X may indicate Y").
- **A grounded AI Assistant.** Every claim resolves to a real tool call — a computed statistic, an image region, an OCR span, or a cited framework template. Ungrounded claims are visibly flagged, never hidden.
- **Export & reporting**: xlsx/csv/tsv/json per image and per set, plus an auto-drafted **Methods Section** naming the exact detector/OCR/embedding/vision-LM versions and formula versions used.

## Non-negotiable design principles

1. **Local-first, cloud-optional.** Images, extracted text, and AI queries never leave the machine by default. Cloud is explicit, per-set opt-in, with a visible indicator whenever active.
2. **Numbers before narrative.** Every interpretive claim is backed by a deterministic, re-runnable computation; the vision-LM's prose is a second, clearly labeled layer, never the measurement itself.
3. **Interpretive claims are framework-lensed hypotheses, never facts.**
4. **Own data model, own vocabulary.** No document uploaders, POS tagsets, or compile gates — if a feature does not make sense for an image set, it does not exist in Lens's UI.
5. **Reproducibility is a feature.** Every result screen states which model/formula/version produced the number on screen.
6. **Consent and restraint around biometric-adjacent features.** Facial/body analysis ships opt-in, off by default, and never performs identity recognition. **GPS coordinates are never extracted from images — ever, no setting overrides this.**
7. **Explicit, versioned interoperability — never implicit coupling.**

See `docs/METHODOLOGY.md` for the full statistical reference and `docs/ARCHITECTURE.md` for the system design.

## Repository layout

```
CorpusMind-Lens/
├── lens-engine/          FastAPI (Python 3.12) — vision, detection, multimodal,
│                         discourse, stats, nlp_ar, ai, storage, companion, api
├── lens-web/             React + Vite + TS — Lens-only PWA frontend
├── lens-desktop/         Tauri 2 desktop shell (sidecar lifecycle for lens-engine)
├── shared/               OpenAPI-generated TS client
├── reference-data/       The 12 versioned framework YAMLs
├── docs/                 ARCHITECTURE, METHODOLOGY, COMPANION_MODE, USER_GUIDE (+AR)
├── infra/                Docker Compose for a self-hosted lens-engine
└── .github/workflows/    Own CI + release pipelines
```

## Quick start

### 1. Run the engine

```bash
cd lens-engine
pip install -e ".[all]"
uvicorn lens_engine.main:app --port 8765
# Health check: http://127.0.0.1:8765/api/v1/health
```

Optional local AI (recommended): install [Ollama](https://ollama.com) and pull a vision-capable model, e.g. `ollama pull llava` or `ollama pull moondream`. Lens auto-detects it. LM Studio (OpenAI-compatible `/v1`) is also supported. Cloud providers are opt-in and off by default.

### 2. Run the web app

```bash
cd lens-web
npm install
npm run dev
# http://localhost:5173
```

The web app is an installable PWA; `npm run build` produces a deployable bundle that talks to the engine at `http://127.0.0.1:8765`.

### 3. Or run the desktop app

```bash
cd lens-desktop/src-tauri
cargo tauri dev     # spawns lens-engine as a sidecar, health-checks, attaches
```

The desktop shell launches the engine as a child process, streams logs to a file, and fully detaches on exit. If a CorpusMind (Text) engine is already listening on port 8765, Lens detects it and either connects as a Companion or starts on a different port — it never crashes into a port conflict.

### 4. Self-hosted (lab instance)

```bash
cd infra && docker compose up
```

## Tested scale target

Lens targets **low thousands of images per set on consumer hardware** (8–16 GB RAM; a discrete GPU is optional, not required). Ingestion and analysis run in the background with progress feedback; the UI stays responsive during batch operations.

## License

AGPL-3.0-only — see [LICENSE](LICENSE). Third-party model/lexicon licenses are tracked in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Citing Lens

See [CITATION.cff](CITATION.cff) (DOI: `10.5281/zenodo.21673083`).

## Acknowledgements

CorpusMind Lens was extracted from the [CorpusMind](https://github.com/waleedmandour/CorpusMind) monorepo and rebuilt as a standalone product. The visual-analysis apparatus — the five-dimension annotation framework, the statistics battery, the framework templates, and the vision API design — originated in CorpusMind by **Dr. Waleed Mandour (Sultan Qaboos University)** and **Prof. Wesam Ibrahim (Princess Nourah Bint Abdulrahman University)**, and this project gratefully credits that origin. Lens is independently licensed and versioned under the same AGPL-3.0-only terms.

## Disclaimer

**AI-assisted development.** The application code in this repository was developed using multiple AI agents — including **GLM-5.1, GLM-5.2, and GLM-5.3 Flash, Claude, and Gemini** — working under the direction and review of the project author. As with any AI-assisted software, outputs and analyses should be verified by the researcher before being relied upon in published work.

**No funding.** No funding, grants, or sponsorships have been received for this project. It is developed voluntarily and offered free of charge.

**Built with love** for students and the academic community.
