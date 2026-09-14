# CorpusMind Lens: User Guide

*Audience: researchers with no programming background. Everything below happens offline on your own machine; a local Ollama or LM Studio model is optional but recommended for the Assistant and image descriptions.*

## 1. Install and start

**Desktop app (recommended).** Install CorpusMind Lens from a release bundle and open it. The app starts its own analysis engine automatically (a small local server on your machine). If the CorpusMind (Text) app is already running, Lens detects it and either works alongside it (Companion Mode) or starts on a different port, so you never see a conflict.

**Web app (PWA).** Start the engine, then the web app:

```bash
cd lens-engine && uvicorn lens_engine.main:app --port 8765
cd lens-web && npm install && npm run dev   # open http://localhost:5173
```

Your browser can "install" the page as an app (address-bar install icon). The interface is available in English and Arabic (toggle in the ribbon) with full right-to-left mirroring.

### 1a. Set up local AI (Ollama or LM Studio): recommended

The AI features (Assistant, LLM-annotated framework modes, semantic search, vision-model OCR) run entirely on your machine through a local AI backend.

- **Settings → AI backend & models** shows whether **Ollama** or **LM Studio** is present. If neither is installed, the **Install Ollama (one click, silent)** button does it for you; no admin password is needed on any platform.
- The screen also shows **your machine's specs** (RAM, CPU, GPU) and gives every model a fit badge: *GPU-fast* (fits in your graphics card), *CPU OK*, *Tight*, or **Too big** (it would run painfully slowly; pick a smaller one instead). "Recommended for this machine" picks sensible defaults for you.
- Browse more models with the task filters (Vision / Text / Embeddings) or search thousands of **HuggingFace** models directly; press **Pull** and watch real progress. The first pulls to make: a vision model (e.g. Qwen2.5-VL 3B) and the embedding model **bge-m3** (used by semantic search; it understands both English and Arabic).
- **Settings → Model defaults** lets you choose which installed model each job uses (vision OCR assist, embeddings, Assistant), so the app always picks the model you intend.
- If you prefer LM Studio, just start it; Lens detects it automatically; models are managed inside LM Studio itself.
- **No AI backend? Everything deterministic still works**: statistics, framework batteries, the text analysis layer, exports. The Overview banner simply reminds you what you are missing; dismiss it freely.

## 2. The workflow menu and the task bar (v0.3)

Lens uses a full functional menu ordered by the research workflow; you choose what to do, whenever you want:

| Group | Pages |
|---|---|
| **Start** | Overview (projects, sets, next-phase hints) |
| **1 Build corpus** | Images (image sets, upload, annotation), Social Media |
| **2 Analyse** | Text Analysis, Vision Analysis, Assistant |
| **3 Share** | Export |
| **App** | Settings, Guide, About |

**The task bar at the bottom of the window** keeps you oriented, in the spirit of the parent CorpusMind app:

- An **engine chip** (online/offline) and a **processing counter** while images or models are working;
- a **Next step** suggestion computed from your live state (import, wait, annotate, analyse, export);
- an **issues badge** that opens the Smart Troubleshooting panel: every failed request is captured with a plain-language explanation, offline fix rules for common cases, and an **Interpret with local model** button that asks your local LLM to explain the error. Issues auto-resolve when the cause clears, and can be muted or reported.

Press **Ctrl/Cmd+K** for the command palette: jump to any page, toggle the theme, or switch language. There is no toolbar button; the shortcut is the way in.

## 3. Create a project and build a corpus (Images page)

1. **Overview → New project**: a project groups your work (e.g. "Election posters 2025"). The Overview page shows your three workflow phases and what to do next.
2. **Images → New image set**: the set is your corpus unit: a folder-worth of images you want to analyse together. Give it a name and, ideally, provenance/sampling notes (where the images come from, how you sampled); future-you writing the Methods section will be grateful.

**Upload** by dragging or picking files (JPG, PNG, TIFF, WebP, BMP). Ingestion is hardened: a file mislabeled with the wrong extension is rejected with a clear message instead of crashing; per-file and per-batch size caps apply. Analysis then runs **in the background**: the gallery fills in as each image reaches *Ready*, and the task bar counts what is still processing. You can keep working while it runs.

Automatic, deterministic analysis per image includes:
- **Metadata** (camera, dates from EXIF; headline/creator/rights/keywords from XMP/IPTC). GPS is **never** extracted; by design, with no setting to change it.
- **OCR** (Arabic + English + mixed) with a per-image confidence score that is always shown. A set tagged Arabic is OCR'd with `ara+eng`. Missing a language pack? Re-run analysis after installing it; nothing is lost.
- **Colour & composition**: dominant colours, warm/cold balance, brightness/contrast/saturation; information value (left/right, top/bottom, centre/margin), salience, rule of thirds, visual balance; computed geometrically.
- **Object/scene detection** (if the detection models are installed): open-vocabulary bounding boxes + scene classification, all local.

## 4. Annotate (the five-dimension framework)

Open **Images**, pick a set, then an image: the detail view is the annotation editor. The five dimensions (Visual Morphology, Attentional Framing, Filmic Shot Scale, Path Structure & Transitions, Multimodal Integration) each offer multi-select categories plus a free-text note. Hover a category for its scholarly definition. Bulk-tag whole sets from the same view. Category names are validated on the server: a typo can never silently corrupt your corpus.

The detail header carries three actions and is always available, whatever the image's state: **Re-run OCR with vision model**, **Re-run analysis** (repeats the full background pipeline for that image), and **Delete image** (asks for confirmation). Image sets can be deleted from the set chips (the ✕ beside each name, confirmation required), and whole projects from the Overview page.

## 5. Vision Analysis: measures and lenses

The **Vision Analysis** page carries the quantitative and theoretical layers for your image corpus.

**Measures** compute, per dimension:
- **Frequency** profile per category;
- **Diversity**: TTR, Guiraud's R, MATTR, STTR;
- **Sequence n-grams** over the set's reading order;
- **Dispersion**: Juilland's D and Gries' DP with per-bin histograms;
- **Keyness**: compare any two sets; results always pair *significance* (log-likelihood) with *effect sizes* (Log Ratio, %DIFF, Simple Maths, Odds Ratio). A Cochran flag warns when χ² is unreliable on sparse data.
- **Visual KWIC**: concordance lines for any category with co-annotation context.

**Lenses.** The same page offers the twelve theoretical lenses (Kress & van Leeuwen, Halliday, Fairclough/van Dijk/Wodak/Machin & Mayr, Barthes, Peirce, Lakoff & Johnson, Martin & White, Toulmin, Aristotle). Pick a **mode** first: *Heuristic (deterministic)* computes the claims locally from the measured signals, while *Local LLM* sends only the evidence bundle and the framework's guardrails to your installed Ollama or LM Studio model (the default chat model from Settings; shown as a chip). Run one on an image and you receive **claims**, each with:
- the claim, phrased as a hypothesis ("Under a Kress & van Leeuwen reading, …");
- the evidence that produced it (feature paths you can inspect);
- a confidence value and provenance badge (mode, model).

Batch-run several lenses over a whole set (with per-image error isolation and skip-if-cached). Interpretive claims are hypotheses, never facts; colour symbolism is always culture-relative.

## 6. Text Analysis: the corpus-linguistics layer (v0.3)

The **Text Analysis** page operates on the text corpus Lens already produces (OCR text + captions), so your visual and textual layers finally share one surface. Six tabs:

- **Wordlist**: frequencies with a stoplist resolver (built-in list, none, or your own per-project stoplists; create and delete them right in the tab).
- **Concordance**: a full KWIC engine with plain or regex queries, sort by left/right context positions, per-hit metadata (image, set), and export to CSV, XLSX, XML or JSON.
- **Collocations**: MI, t-score, Log-log, Log Dice and delta-P, with an interactive collocation **network** view; click a word for its **word sketch**, Lens's visual edition of the one-page grammatical summary: the token's typical visual co-patterns (colour, composition band, typography register, detected objects) plus its textual collocates.
- **N-grams**: n-grams and lexical bundles with text-dispersion measures (Juilland's D, Gries' DP) across the set's reading order.
- **Dispersion**: a per-word dispersion gallery across the set's images in reading order.
- **Keyness**: compare your corpus against **bundled reference frequency tables** (open-licensed English and Arabic references shipped inside the installer), so keyness works without needing a second image set; Log Ratio effect sizes throughout.

## 7. The AI Assistant

Ask things like "analyse this poster using Kress & van Leeuwen", "find the most salient recurring visual-morphology categories in this set", or "compare these two campaigns' compositional patterns". The Assistant answers **only** from tool calls into your actual data; every claim shows the tool that grounded it, and anything not grounded is flagged `[ungrounded]` in red. Every tool call is written to a local audit log.

## 8. The Social Media tab

The Social tab builds social media corpora two ways, and both feed the same analysis battery:

**Import from your own export (offline, no network at all).** Download your data from the platform yourself, then drop the file into Social → Import. Supported: the X (Twitter) archive zip (posts plus attached photos are picked up automatically), Instagram and Facebook "Download Your Information" JSON, TikTok export JSON, and any CSV or JSONL file that contains a text column. Before importing you confirm an ethics attestation, and you can choose to pseudonymise author handles, redact URLs or @mentions; email addresses and phone numbers are always redacted. A provenance record of the import is stored with the corpus. Attached photos are analysed by the vision pipeline like any other image set.

**Fetch through an official free-tier API.** For public content on Mastodon (no key needed, just an instance such as mastodon.social), Reddit (create a free "script" app at reddit.com/prefs/apps and enter the client id and secret; fetch new, top, hot or search results from a subreddit), or YouTube (a free API key from Google Cloud Console; search videos or fetch one video with its comment threads). Credentials are used for that one request and never stored; requests stay within the platform's free rate limits and only public content is requested. A terms-of-service confirmation is required before the first fetch.

**Analyses.** The **Textual Analyses** tab carries word frequency, lexical diversity (TTR, Guiraud's R, MATTR, STTR), n-grams and the KWIC concordance; the **Engagement and Network Analyses** tab carries emoji frequency, hashtag frequency, a hashtag co-occurrence network, engagement statistics, engagement-weighted frequency, a posting time series, and keyness against another project. The export row is always visible in both tabs: run an analysis and the CSV, XML, TSV and JSON buttons light up, and the post corpus itself exports from the Posts tab.

**Going deeper.** Under Textual Analyses a short note points to **CorpusMind**, the desktop suite Lens grew out of: for flexible concordancing, semantic tagging and wider statistical modelling, export your corpus and open it there (free download from github.com/waleedmandour/CorpusMind/releases).

## 9. Export

The **Export** page gathers everything a project can emit: batteries, concordances, wordlists, collocations, the social media corpus (per project, all platforms) and the post corpus, in xlsx/csv/tsv/json (xml for concordances and social exports), including the auto-drafted **Methods paragraph** naming every model and formula version used.

**Where files go.** In the desktop app every export opens a **Save As** dialog that starts in your Downloads folder; pick any location and the confirmation toast shows the exact saved path. In the browser the download lands in the browser's Downloads folder, and the toast tells you so.

## 10. Settings reference

- **AI backend & models**: detect/install Ollama or LM Studio, machine specs, fit badges, catalogue and HuggingFace search.
- **Model defaults**: which installed model each job uses (vision OCR assist, embeddings, Assistant). Only models **actually downloaded on this machine** are listed, merged from Ollama and LM Studio with the backend named; if the effective default is not installed, the card says so and can reset the slot to the built-in default.
- **Capabilities**: what the engine may do (person/face analysis stays opt-in and off by default).
- **AI providers**: cloud settings, off by default; when enabled an indicator stays visible.
- **Ethics**: the guarantees below (§11).
- **Companion Mode**: optional link to CorpusMind (Text).
- **Appearance**: theme and language.
- **Engine diagnostics**: engine health, the recent log tail, and a **Restart engine** button, so a stuck engine no longer requires quitting the app.

## 11. Ethics settings (important)

**Settings → Ethics** explains what is and is not possible:
- Facial/body analysis is **opt-in, off by default**; when off, person-descriptive content generated by any model is redacted before it reaches you.
- Lens never performs identity recognition or re-identification of real people.
- GPS/location metadata is never extracted, under any setting.
- Cloud AI is off by default; when enabled, an indicator stays visible.

## 12. Companion Mode (optional)

If you also run CorpusMind (Text), Settings → Companion Mode can point Lens at it. This lets the Assistant reason over a *text* corpus in the same conversation as your image sets. It is never required for any Lens feature, and nothing from your images ever leaves Lens through it.

## 13. Troubleshooting

- **Something failed?** The task bar's issues badge lists every failed request with a plain-language explanation and offline fix rules; try its suggestions first.
- **Engine unreachable?** Use **Settings → Engine diagnostics → Restart engine**. If that does not bring it back, quit and reopen the app; the engine starts automatically.
- **Model errors?** Check the model fit badges and **Model defaults**; a model too large for your machine is the most common cause.
- Nothing leaves your machine in any of these paths; the **Report** action in the issues panel opens a prepared email with the technical details for you to review before sending.

## 14. Definition of Done: try this walkthrough

Create a project → upload an image set and watch metadata/OCR run automatically → annotate a few images on the five dimensions (Images) → run the frequency/n-gram/keyness battery and a lens (Vision Analysis) → try a concordance and collocation network on the OCR text (Text Analysis) → ask the Assistant which categories dominate and why → export results + the Methods paragraph (Export). All of it offline, with no CorpusMind (Text) installed.
