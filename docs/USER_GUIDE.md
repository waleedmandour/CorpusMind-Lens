# CorpusMind Lens — User Guide

*Audience: researchers with no programming background. Everything below happens offline against your own machine; a local Ollama or LM Studio model is optional but recommended for the Assistant and image descriptions.*

## 1. Install and start

**Desktop app (recommended).** Install CorpusMind Lens from a release bundle and open it. The app starts its own analysis engine automatically (a small local server on your machine). If the CorpusMind (Text) app is already running, Lens detects it and either works alongside it (Companion Mode) or starts on a different port — you never see a conflict.

**Web app (PWA).** Start the engine, then the web app:

```bash
cd lens-engine && uvicorn lens_engine.main:app --port 8765
cd lens-web && npm install && npm run dev   # open http://localhost:5173
```

Your browser can "install" the page as an app (address-bar install icon). The interface is available in English and Arabic (toggle in the ribbon) with full right-to-left mirroring.

### 1a. Set up local AI (Ollama or LM Studio) — recommended

The AI features (Assistant, LLM-annotated framework modes, semantic search, vision-model OCR) run entirely on your machine through a local AI backend.

- **Settings → AI backend & models** shows whether **Ollama** or **LM Studio** is present. If neither is installed, the **Install Ollama (one click, silent)** button does it for you — no admin password is needed on any platform.
- The screen also shows **your machine's specs** (RAM, CPU, GPU) and gives every model a fit badge: *GPU-fast* (fits in your graphics card), *CPU OK*, *Tight*, or **Too big** (it would run painfully slowly — pick a smaller one instead). "Recommended for this machine" picks sensible defaults for you.
- Browse more models with the task filters (Vision / Text / Embeddings) or search thousands of **HuggingFace** models directly; press **Pull** and watch real progress. The first pull to make: a vision model (e.g. Qwen2.5-VL 3B) and the embedding model **bge-m3** (used by semantic search; it understands both English and Arabic).
- If you prefer LM Studio, just start it — Lens detects it automatically; models are managed inside LM Studio itself.
- **No AI backend? Everything deterministic still works** — statistics, framework batteries, exports. The Overview banner simply reminds you what you are missing; dismiss it freely.

## 2. Create a project and an image set

1. **Overview → New project** — a project groups your work (e.g. "Election posters 2025").
2. **New image set** — the set is your corpus unit: a folder-worth of images you want to analyse together. Give it a name and, ideally, provenance/sampling notes (where the images come from, how you sampled) — future-you writing the Methods section will be grateful.

## 3. Upload images

Drag or pick files (JPG, PNG, TIFF, WebP, BMP). Ingestion is hardened: a file mislabeled with the wrong extension is rejected with a clear message instead of crashing; per-file and per-batch size caps apply. Analysis then runs **in the background** — thumbnails fill in as each image reaches *Ready*. You can keep working while it processes; a progress bar tracks the set.

Automatic, deterministic analysis per image includes:
- **Metadata** (camera, dates from EXIF; headline/creator/rights/keywords from XMP/IPTC). GPS is **never** extracted — by design, with no setting to change it.
- **OCR** (Arabic + English + mixed) with a per-image confidence score that is always shown. A set tagged Arabic is OCR'd with `ara+eng`. Missing a language pack? Re-run analysis after installing it — nothing is lost.
- **Colour & composition** — dominant colours, warm/cold balance, brightness/contrast/saturation; information value (left/right, top/bottom, centre/margin), salience, rule of thirds, visual balance — computed geometrically.
- **Object/scene detection** (if the detection models are installed): open-vocabulary bounding boxes + scene classification, all local.

## 4. Annotate (the five-dimension framework)

Open the **Vision Workbench**, pick an image, and use the *Image Set* tab. The five dimensions — Visual Morphology, Attentional Framing, Filmic Shot Scale, Path Structure & Transitions, Multimodal Integration — each offer multi-select categories plus a free-text note. Hover a category for its scholarly definition. Bulk-tag whole sets from the same tab. Category names are validated on the server: a typo can never silently corrupt your corpus.

## 5. Run the measurement battery

The *Measures* tab computes, per dimension:
- **Frequency** profile per category;
- **Diversity** — TTR, Guiraud's R, MATTR, STTR;
- **Sequence n-grams** over the set's reading order;
- **Dispersion** — Juilland's D and Gries' DP with per-bin histograms;
- **Keyness** — compare any two sets; results always pair *significance* (log-likelihood) with *effect sizes* (Log Ratio, %DIFF, Simple Maths, Odds Ratio). A Cochran flag warns when χ² is unreliable on sparse data.
- **Visual KWIC** — concordance lines for any category with co-annotation context.

Export everything (xlsx/csv/tsv/json) from the set view, including an auto-drafted **Methods paragraph** naming every model and formula version used.

## 6. Framework-lensed discourse analysis

The *Vision Analysis* tab offers the twelve theoretical lenses (Kress & van Leeuwen, Halliday, Fairclough/van Dijk/Wodak/Machin & Mayr, Barthes, Peirce, Lakoff & Johnson, Martin & White, Toulmin, Aristotle). Run one on an image and you receive **claims**, each with:
- the claim, phrased as a hypothesis ("Under a Kress & van Leeuwen reading, …");
- the evidence that produced it (feature paths you can inspect);
- a confidence value and provenance badge (mode, model).

Batch-run several lenses over a whole set (with per-image error isolation and skip-if-cached) from the batch endpoint. Interpretive claims are hypotheses, never facts; colour symbolism is always culture-relative.

## 7. The AI Assistant

Ask things like "analyse this poster using Kress & van Leeuwen", "find the most salient recurring visual-morphology categories in this set", or "compare these two campaigns' compositional patterns". The Assistant answers **only** from tool calls into your actual data; every claim shows the tool that grounded it, and anything not grounded is flagged `[ungrounded]` in red. Every tool call is written to a local audit log.

## 7a. The Social Media tab (v0.2)

The Social tab builds social media corpora two ways, and both feed the same analysis battery:

**Import from your own export (offline, no network at all).** Download your data from the platform yourself, then drop the file into Social → Import. Supported: the X (Twitter) archive zip (posts plus attached photos are picked up automatically), Instagram and Facebook "Download Your Information" JSON, TikTok export JSON, and any CSV or JSONL file that contains a text column. Before importing you confirm an ethics attestation, and you can choose to pseudonymise author handles, redact URLs or @mentions; email addresses and phone numbers are always redacted. A provenance record of the import is stored with the corpus. Attached photos are analysed by the vision pipeline like any other image set.

**Fetch through an official free-tier API.** For public content on Mastodon (no key needed, just an instance such as mastodon.social), Reddit (create a free "script" app at reddit.com/prefs/apps and enter the client id and secret), or YouTube (a free API key from Google Cloud Console). Credentials are used for that one request and never stored; requests stay within the platform's free rate limits and only public content is requested. A terms-of-service confirmation is required before the first fetch.

**Analyses.** Word frequency, lexical diversity (TTR, Guiraud's R, MATTR, STTR), n-grams, KWIC concordance, emoji frequency, hashtag frequency, a hashtag co-occurrence network, engagement statistics, engagement-weighted frequency, a posting time series, and keyness against another project. Every result exports as CSV, XML, TSV or JSON, and the post corpus itself exports with all harvested markers.

## 8. Ethics settings (important)

**Settings → Ethics** explains what is and is not possible:
- Facial/body analysis is **opt-in, off by default**; when off, person-descriptive content generated by any model is redacted before it reaches you.
- Lens never performs identity recognition or re-identification of real people.
- GPS/location metadata is never extracted, under any setting.
- Cloud AI is off by default; when enabled, an indicator stays visible.

## 9. Companion Mode (optional)

If you also run CorpusMind (Text), Settings → Companion Mode can point Lens at it. This lets the Assistant reason over a *text* corpus in the same conversation as your image sets. It is never required for any Lens feature, and nothing from your images ever leaves Lens through it.

## 10. Definition of Done — try this walkthrough

Create a project → upload an image set → watch metadata/OCR run automatically → annotate a few images against the five dimensions → run the frequency/n-gram/keyness battery → run Kress & van Leeuwen on one image → ask the Assistant which categories dominate and why → export results + the Methods paragraph. All of it offline, with no CorpusMind (Text) installed.
