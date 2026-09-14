# Changelog

All notable changes to **CorpusMind Lens** are documented here, in the parent project's prose style: each entry explains *why*, not just *what*.

## [0.3.2] - 2026-09-14 - The refinement release: first-testing fixes, export choice, and honest naming

**Why:** v0.3.1 was the first version tested end to end by the project owner, and the round surfaced six concrete frictions plus a handful of smaller inconsistencies. Several were trust issues rather than crashes: a Vision Analysis page that never touched the local LLM even though the engine supported it, default-model pickers that advertised models the user had never downloaded, and exports that silently landed in Downloads with no confirmation of where. v0.3.2 closes all six reports, ships the smaller polish items alongside them, and aligns the Social Media vocabulary with what the analyses actually are.

### Fixed

- **The Delete action is always available for images.** The image detail header now renders for every selected image, including ones still processing or failed, with Delete (confirm-guarded), Re-run OCR, and a new Re-run analysis action. Previously the buttons appeared only after an analysis existed, leaving fresh and broken images action-less.
- **Vision Analysis really uses the local LLM when asked.** The Discourse lenses tab gains an explicit mode selector: Heuristic (deterministic) or Local LLM, with the effective chat model shown as a chip and an explanatory note. The view previously hard-coded heuristic mode, so the engine's `mode=llm` path was silently unreachable from the interface. Failed runs now produce an inline, actionable message (start Ollama or LM Studio, pull a model, run again) instead of an unhandled rejection.
- **The engine no longer falls back to a hard-coded model name.** LLM lens runs (single image and batch) resolve their model from Settings → Default models via the existing authority chain, so the user's downloaded default is what actually runs; the previous `moondream` constant ignored the defaults entirely.
- **Default models read from downloaded models only.** The pickers on Settings → Default models now list exactly what is installed, merged across Ollama and LM Studio (LM Studio's loaded models were previously invisible), each labelled with its backend. If the currently effective default is not installed, the card says so and offers a one-click reset to the built-in default instead of silently leaving a blank select.
- **The LM Studio status line no longer hides its models.** `/ai/local/status` reports the LM Studio model list alongside Ollama's, which is what makes the merged picker honest.

### Added

- **A Save As dialog for every export (desktop).** All engine exports, from battery tables to the social corpus, now open the native Save dialog defaulting to the Downloads folder; the user can pick any location, and the toast confirms the exact saved path. In the browser the download is unchanged, and the toast points at the Downloads folder so the destination is never a mystery. Cancelled dialogs are silent by design.
- **A model-selection reminder on Home.** When models are installed but no defaults have been chosen, a dismissible card explains that Lens is still on built-in defaults and deep-links to Settings → Default models.
- **Textual Analyses and Engagement and Network Analyses.** The Social Media tabs formerly labelled by their lead analysis are renamed to what they contain: the textual battery (frequency, diversity, n-grams, KWIC) and the engagement and network battery (emoji, hashtags, hashtag network, engagement, engagement-weighted keyness, timeline). The export row is now always visible in both tabs (dimmed until a run produces a table), and the Posts tab keeps its full-corpus export.
- **A signpost to CorpusMind under Textual Analyses.** A short note tells researchers where to go for heavier analysis (flexible concordancing, semantic tagging, wider statistical modelling) and links the free CorpusMind download page; both languages carry it.
- **Delete for projects and image sets.** The Home page projects and the Images page set chips gain confirm-guarded delete actions, wired to the engine DELETE endpoints that already existed.
- **A visible command-palette hint in the task bar** (Ctrl/Cmd+K chip that opens the palette), a social media corpus export section on the Export & Methods page, and inline run errors for the battery and visual grammar tabs.

### Changed

- Versions bumped to 0.3.2 across the engine, desktop shell, web client, and citation metadata; user guide (EN/AR) refreshed for the new vocabulary and export flow.

## [0.3.1] - 2026-09-13 - Identity release: the right icon on every surface

**Why:** Within a day of v0.3.0, two packaging leftovers from the parent-app scaffold surfaced and made a correct build look like an old one. First, the Windows .ico and macOS .icns inside the installers still carried the parent CorpusMind artwork: the icon set had been regenerated only partially when Lens got its own repository, so Windows taskbars and macOS Docks showed the parent product's icon next to a v0.3.0 About page. Second, the README download table still named v0.2.1 files (some in a filename pattern that has not existed since v0.1.x), so following the README's own links reinstalled the previous release. Nothing about the application code changed; this release exists so that what a researcher installs finally looks, and links, like the current Lens.

### Fixed

- **The complete icon set is now the official CorpusMind Lens artwork, everywhere.** The Windows .ico, the macOS .icns, every Linux PNG size, the in-app ribbon brand mark and the About page, the web favicon, the PWA manifest icons, and the README header are all generated from the single 1024 px official tile (kept in the repository as `lens-desktop/src-tauri/app-icon.png` so future regenerations stay one command away). The mixed set that carried parent artwork in `icon.ico`, `icon.icns`, and the 128 px files is gone.
- **The README download table names and links the current files.** Every row now points at a permanent v0.3.1 asset permalink, and a note tells readers to prefer the Releases page for the newest build. The previous rows pointed at v0.2.1 names, two of them in a lowercase pattern removed after v0.1.x, which is how a fresh download could silently produce the old app.

### Changed

- The two-page user guide is refreshed for 0.3.1 and now carries the official application icon on page 1.
- Versions bumped to 0.3.1 across the engine, desktop shell, web client, and citation metadata. No engine, API, or interface behaviour changes in this release.

## [0.3.0] - 2026-09-13 - The workflow release: full menu, task bar, and the text layer

**Why:** v0.2 analysed *annotations* well but made researchers work to find the tools: "Image Sets" and "Vision Workbench" overlapped confusingly, a decorative Ctrl-K button did nothing visible, and errors surfaced as one-line toasts that vanished before they could be read. v0.3 rebuilds the interface around the research workflow the way the parent CorpusMind does it: a full functional menu the user picks tools from, a permanent task bar that shows what is running and what to do next, and a proper text-analysis layer over the OCR corpus so the classic corpus-linguistics toolset finally has a home.

### Added - interface (the three user directives)

- **Full functional menu in streamlined order.** The sidebar is now the complete toolset, grouped in workflow order: Start (Home), Build corpus (Images, Social Media), Analyse (Text Analysis, Vision Analysis, Assistant), Share (Export & Methods), App (Settings, User Guide, About). Every function has its own page; the user chooses what to do.
- **Image Sets and Vision Workbench are gone as confusing twins.** Their overlapping halves are merged and re-homed: corpus building (sets, upload, background processing, image details, annotation) lives on **Images**; the statistical battery, visual grammar and discourse lenses live on **Vision Analysis**. A set picker sits at the top of every analysis page, so nothing depends on a hidden "active set" state.
- **The task bar (below), like the parent app.** A permanent bottom bar shows the engine state, background image-processing progress (N/M images), and a suggested next step computed from the workflow state (import, wait, annotate, analyse, export). Failed API calls and health-check failures land in a deduplicated issue store; a red badge opens an expandable panel with per-issue cards: plain-language message, code and endpoint, an instant offline one-line fix (a rules table adapted from the parent's Smart Troubleshooting), an optional deeper interpretation generated by the **local** AI model (never a cloud call, per Lens's ethics line), resolve and report-to-developer actions. The bar respects a persisted mute toggle and degrades honestly when the engine is down.
- **The dead "K" button is removed.** The toolbar button that only re-rendered the current view is gone; the Ctrl/Cmd+K shortcut stays and the command palette behind it is extended to every page plus theme and language toggles (the parent's registry pattern).
- **In-app User Guide and About pages.** Ten bilingual accordion chapters replace "open the PDF" as first-line help; the About page carries the privacy position, open-data credits and a citation block. The three-page welcome tour is updated to the new menu and replayable as before.

### Added - engine (the AntConc audit, phase one)

- **Text Analysis over the OCR corpus** (`/imagesets/{id}/text/*`), all on the same token stream as the visual layer, with the tested statistics of `stats/measures.py` and no new dependencies: word list with stoplist resolution; **Concordancer 2.0** (substring or regex queries, L1/R1 sort positions, per-hit image metadata, CSV/TSV/XLSX/XML/JSON export); **collocations** with MI, t-score, log-likelihood, LogDice and ΔP plus GraphColl-style network edges; **n-grams and lexical bundles** with text dispersion (Juilland's D, Gries' DP) over reading order; a **dispersion gallery** per word; and a **word sketch, visual edition**, which summarises a token's typical visual co-patterns (dominant colours, brightness/warmth, annotation values, detected objects, typography register) alongside its textual collocates.
- **Reference-corpus keyness without a second set.** Four open-licensed frequency tables ship inside the sidecar and the installers (BE06-derived and Leipzig English news for English; CAMEL/Leipzig Arabic and a Quranic list for Arabic, attribution headers preserved and recorded in THIRD_PARTY_LICENSES.md), so keyness works out of the box with significance and effect size always together.
- **Per-project stoplist manager.** CRUD endpoints plus built-in EN/AR lists; custom lists resolve by name in every wordlist, collocation and n-gram run.
- **Default-model picker.** `GET/PUT /settings/models` persists UI overrides (vision OCR, embeddings, assistant chat) in the new `app_settings` store; env vars keep working for headless setups and explicit per-request arguments still win. The Settings card writes through immediately.
- **Engine restart and log tail from the shell.** New Tauri commands (`restart_engine`, `engine_logs`) power the Settings diagnostics card, closing the operational gap the borrow review flagged: until now a stuck engine could only be fixed by restarting the whole app.

### Changed

- The old routes (`/ocrtools/*`, battery, social) are unchanged for compatibility; the text layer is additive.
- The release smoke test now demands the new text-analysis, stoplist, troubleshoot and model-defaults routes in the frozen sidecar, and the PyInstaller build bundles the reference frequency tables.

### Why these changes are safe

- 12 new engine tests (concordance sorting and regex, collocation statistics, n-gram dispersion, sketch shape, reference keyness against the bundled tables, stoplist CRUD and reserved names, model-default round-trip, honest local-interpretation unavailability, verdict parsing) bring the suite to 145.
- The task bar's error capture lives at the single API choke point, is deduplicated (5 s window, 20 issues), and can never break a request path.

## [0.2.1] - 2026-09-13 - External audit: all nine findings closed

**Why:** An independent code audit of the v0.2.0 tag confirmed nine findings across three severities. The worst reproduced the exact failure class v0.2.0 had just been rebuilt to fix: the app opened, its engine started and answered health checks, yet the webview could not legally talk to it. This release closes all nine findings, adds regression tests for each, and ships the heavyweight model stacks inside every installer so detection and CLIP alignment stop degrading silently.

### Fixed (critical)

- **Port picker inversion (release blocker).** `engine_alive_on()` returned the *inverse* of "something is listening", so on any clean machine `pick_port()` walked 8765-8769 while they were FREE and landed on 8770: outside the webview CSP allow-list. The sidecar booted healthy, the frontend discovered 8770, and every API fetch was then blocked by CSP; the app looked alive while nothing worked. The predicate is corrected and pinned by three new Rust unit tests (run in CI from now on), and the CSP window carries 8770 as a belt-and-braces margin for the all-ports-busy edge case.
- **CSV/TSV formula injection (CWE-1236).** Exports wrote cell values verbatim, so a post whose text starts with `=HYPERLINK(...)` or `=cmd|'/c calc'!A1` would execute in Excel or Google Sheets the moment a researcher opened the export. Every CSV/TSV cell that could parse as a formula is now neutralised with the OWASP marker-quote, while signed numbers (log ratios, effect sizes) stay numeric so researchers can keep computing on exported statistics.
- **Packaging: the [models] stack now ships inside the installers.** v0.2.0's own release notes blamed the missing torch stack, yet release builds still installed without it, so object detection and CLIP scene/alignment analysis degraded to heuristics in every downloadable installer. Sidecars now bundle CPU-only torch + transformers + sentence-transformers from the pytorch cpu index (no CUDA payloads), with transformers capped to the battle-tested 4.x API the engine is written against. Installers get larger and first launch self-extracts more slowly; `/api/v1/health` now reports every optional stack with an honest note on what it enables and how to get it, mirrored by a new Settings card (EN and AR).

### Fixed (medium and low)

- **XML attribute escaping.** Project or column names containing a double quote broke out of the attribute and produced invalid XML; attribute values now go through `quoteattr()` and round-trip exactly.
- **Phone redaction no longer corrupts corpus data.** ISO dates (`2024-01-15`), slash dates, `dddd-dddd` ranges (8765-8769, 2010-2015) and 16-plus digit ids survive redaction untouched; genuine phone numbers (7-15 digits, E.164 bound) are still redacted, privacy-first.
- **Tauri capabilities match reality.** Four plugins (shell, dialog, fs, http) were declared and permissioned but never registered, and the http scope ignored the fallback ports; the dead plugins are removed and capabilities now document exactly what the running app uses (core invoke and events; the CSP governs webview fetch).
- **Companion Mode version drift.** The client header hardcoded `lens-engine/0.1.0` on a 0.2.0 install; it now reads the package version, enforced by test.
- **Framework YAMLs deduplicated.** The twelve templates existed in two byte-identical copies, a drift risk the moment one copy gets edited; `reference-data/frameworks/` is now the single canonical location the engine, the Docker image and the PyInstaller build all read.
- **Pseudonym salt is required.** `pseudonymize_handle()` no longer accepts a guessable default salt; callers must pass the per-import random salt.

### Changed

- CI runs the new Rust sidecar unit tests (`cargo test`) alongside `cargo check`, and the engine install no longer references a non-existent `encryption` extra.
- Test suite grown 120 to 133 (formula injection, XML quoting, redaction precision, salt contract, version header, capability reporting).

## [0.2.0] — 2026-09-12 · One intuitive AI, social corpora, rebuilt shell

**Why:** v0.1.0 answered "can Lens run locally?" but left the AI story to the user's imagination — the parent CorpusMind finds and starts Ollama for you; Lens did nothing at all, and its packaged builds shipped without torch, so detection/CLIP/embeddings degraded to "unavailable" with no visible way back. The researcher experience the parent shipped — *install, and the AI is just there* — is the experience Lens now ships too, with the model-selection problem solved honestly: a 7B pull onto an 8GB laptop is a support ticket in waiting, so fit badges computed from the machine's actual RAM/VRAM appear **before** any multi-gigabyte download.

> **Rebuild note.** The first v0.2.0 build opened to a blank white window on upgraded installs and its bundled engine never started at all, so v0.2.0 was pulled, root-caused, and rebuilt in place. The full story is in the "Fixed" section below. Alongside the fixes, this rebuild adds the Social Media tab (offline imports plus free-tier official-API connectors), CSV/XML/TSV/JSON export for every analysis outcome, a three-page welcome window, and a more organised shell.

### Added

- **AI backend lifecycle in the shell** (the parent's `OllamaManager` pattern, upgraded): Ollama is found across all known install locations, started automatically (`ollama serve`, log-to-file, only Lens's own daemon is ever killed on exit), health-checked over TCP, and restartable from the UI. LM Studio presence is reported in the same place (the engine already speaks its OpenAI-compatible `/v1`).
- **One-click silent install** when Ollama is missing: `winget` (fallback: per-user `OllamaSetup.exe /VERYSILENT`) on Windows, `Ollama.dmg` → `~/Applications` on macOS, and the official tarball into `~/.lens-engine-data/ollama-runtime` on Linux — per-user on every platform, no admin prompts, no sudo.
- **Model catalog with fit badges**: curated Ollama-library entries (vision / text / embeddings — Qwen2.5-VL, Llama 3.2, Qwen3, Gemma3, LLaVA, Moondream, BGE-M3, Nomic, Qwen3-Embedding) plus live **HuggingFace GGUF search** (Ollama ≥0.5 pulls `hf.co/<user>/<repo>:<quant>` directly) with a preferred-quant picker. Every entry carries a conservative `gpu / cpu / tight / too-big / unknown` badge from the machine probe (sysinfo in the shell, stdlib fallback in the engine; NVIDIA VRAM via `nvidia-smi`; Apple unified memory treated honestly). Estimates are labelled `rule-of-thumb`, never benchmarks. Pulls stream real progress (NDJSON from `/api/pull`); installed models can be deleted.
- **Semantic search over an image set** (`POST /imagesets/{id}/semantic-search`): OCR text + captions embedded via local Ollama (`bge-m3` — multilingual EN+AR — by default, `LENS_EMBED_MODEL` to override), vectors cached in image meta, cosine-ranked hits with coverage stats and an explicit "not CLIP joint-space" disclaimer. This is the first step of the Anthony-2025 embeddings-in-concordancing roadmap.
- **Vision-model OCR assist** (`POST /images/{id}/ocr/vision`): re-extracts text with a local VLM (default `qwen2.5vl:3b`) for packaged builds without Tesseract — text only, no per-word boxes, flat confidence marker, engine label always explicit; Tesseract remains the engine of record for typography/word geometry.
- **Setup UI**: a new "AI backend & models" card in Settings (status, machine specs line, recommended models, task-filtered catalog, HF search, progress bars), an Overview banner when no backend is reachable (dismissible; deterministic features keep working), and EN/AR strings throughout.

### Changed

- The shell hands its machine probe to the engine (`LENS_MACHINE_SPECS_JSON`) so UI and API score fits against identical numbers.
- CI/release: engine sidecars stay CI-artifacts-only (v0.1.1 decision unchanged); versions bumped to 0.2.0 across the five manifests; test suite grown 85 → 100 → 120 (social parsers incl. X archive zip with media, ethics redaction and pseudonymisation, social analytics, posts storage and API flow, CSV/XML export shapes, connector validation without network, tabular renderer).
- `docs/ROADMAP.md` added — the corpus-linguistics gap analysis (AntConc/Sketch Engine/LancsBox audit), the LLM-annotation-with-verification plan, the Arabic-first track, and the recorded non-goals.

### Added (rebuild: Social Media tab, exports, welcome)

- **Social Media tab, import-first (S1, zero network).** A dedicated view for social media corpora built entirely from the researcher's own exports: X (Twitter) archive zip or tweet.js (media folder matched by tweet id), Instagram and Facebook "Download Your Information" JSON, TikTok export JSON, and any CSV or JSONL with a text column (automatic column mapping, delimiter sniffing). Parsers extract text, timestamps, engagement counts, media attachments, and derive hashtags, @mentions, URLs and emoji at import time. Attached images flow into the existing vision pipeline (an ImageSet is created per import; OCR, colour, composition and annotations apply as with any image).
- **Ethics layer, enforced server-side.** Every import requires an explicit attestation before a single row is stored; emails and phone numbers are always redacted, with optional URL redaction, @mention redaction, and deterministic salted pseudonymisation of handles (same author, same pseudonym within an import). A provenance record (source, file, options, attestation text, post count) is stored with the corpus and shown in the UI.
- **Official-API connectors on free tiers (S2, BYO credentials, first choice for open access).** Mastodon (no key needed: public hashtag and local timelines, per-instance rate-limit headers honoured), Reddit (free script app, app-only read-only OAuth for public subreddit content, paced well under the 100 queries per minute free tier, Retry-After honoured), and YouTube Data API v3 (free API key, search + video metadata + comment threads with a per-fetch quota cap well under the daily allowance). Credentials are supplied per request and never stored; every fetch requires the terms-of-service attestation; no scraper ships anywhere in the product and login-walled content is never requested.
- **Social analytics for corpus and media researchers.** The same statistical battery as the visual side, applied to post text (frequency, diversity battery TTR/Guiraud/MATTR/STTR, chronological n-grams, KWIC concordance), plus social-native measures: emoji frequency with ZWJ-sequence and flag handling, hashtag frequency, hashtag co-occurrence networks, engagement statistics (means, medians, platform breakdown, top posts), engagement-weighted frequency (weight = 1 + ln(1 + likes)), cross-project keyness over the full §11 battery (log likelihood, log ratio, %DIFF, odds ratio), and a posting time series. English and Arabic tokenise correctly; pseudonymised handles never leak into lexical profiles.
- **CSV/XML/TSV/JSON export of every analysis outcome.** A generic tabular renderer flattens any battery or social result into records with metadata; Workbench Measures rows (frequency, diversity, n-grams, dispersion) and every Social analysis carry export buttons; post-level corpora export with all harvested markers and provenance. CSV is RFC-4180 with a UTF-8 BOM for Excel; XML is well-formed with per-column tags; downloads work in the browser PWA and the desktop shell via object URLs.
- **Three-page welcome window.** Shown on first launch of the new interface (and replayable from Settings and the sidebar): what Lens is and what local-first means; how the workspace fits together (projects, image sets, social corpora, workbench); optional local AI with a one-click Ollama install or an honest skip. Preference is remembered per major-version key.
- **Professional shell organisation.** Icon sidebar with all six destinations and a version footer, toast notifications for long actions and errors, empty states with guidance, sticky-header result tables, and a resilient engine status chip that keeps polling through slow sidecar boots. EN and AR (RTL-mirrored) throughout.

### Fixed (rebuild: the blank white window and friends)

- **Blank white window (release blocker).** Root cause: the PWA service worker, registered inside the Tauri WebView where `http://tauri.localhost` is a secure context, served its cache-first shell from the PREVIOUS build's cache; the stale index.html referenced hashed assets that no longer existed, so no module ran and the window stayed blank. Reproduced in a clean browser by simulating an upgrade, then fixed on both sides: the desktop shell never registers a service worker and actively unregisters any SW left by earlier builds and clears their caches (self-healing for machines already in the broken state), and `sw.js` is now network-first for navigations with cache-first reserved for content-hashed assets only, so a stale app shell can never be served again in browser installs either.
- **The engine never started (release blocker).** The bundled sidecar was spawned by a command that no code called: no setup hook in the shell and no caller in the frontend, so the packaged app ran permanently offline. The shell now auto-starts the engine at launch on a detached thread (the window never waits on PyInstaller first-run scans), and the frontend adopts the port the shell actually picked.
- **Health check robustness.** The 60-second health poll previously shelled out to `curl`, which silently never succeeded without curl on PATH; it now probes over a raw TCP HTTP request. The frontend status chip retries through slow first boots instead of declaring offline after one attempt.
- **CSP port window.** The webview could not call the engine if it started on a fallback port; the CSP now covers the whole 8765 to 8769 candidate range (and the localhost variants), and the port picker is constrained to exactly that window.
- **Engine version drift.** `/health` reported 0.1.0 while every manifest said 0.2.0; the engine package version is aligned.
- **No visible failure mode.** A root ErrorBoundary now renders readable diagnostics and a reload action for any render crash, so a silent blank window cannot recur.
- **The packaged engine shipped without its AI-models and semantic-search routes (second release blocker, found by a frozen-binary audit).** PyInstaller cannot see dynamically imported modules; routers were registered through `importlib` behind a hand-maintained hidden-import list that had drifted, so the frozen sidecar silently booted with 69 of 75 routes: the entire AI backend card, model catalog, HuggingFace search, and semantic search were dead in every installed build while working in development. Router registration is now fully static (correct by construction, no list to maintain), and the release pipeline smoke tests the actual frozen binary: it must boot, expose the complete API surface, and log zero router warnings before installers can be built.
- **Images served by the engine were blocked inside the desktop app.** The WebView CSP allowed fetches to the engine but not engine-served `<img>` sources, so image thumbnails and attached media previews appeared broken in installed builds while rendering fine in the browser PWA. The CSP now covers the engine port window for images as well.
- **An unreachable engine used to look like a broken app.** Views stayed empty and actions failed without a word. Overview now shows an explicit offline banner with a retry action, a start-the-engine action on desktop, and the log file location; failed actions surface an error toast.
- **Version drift in the UI.** The web bundle hard-coded version 0.1.0, so the sidebar reported the wrong version; it is now injected from package.json at build time.

## [0.1.1] — 2026-09-12 · Single-package release page

**Why:** the v0.1.0 release page listed nine assets — five installers *plus* four standalone `lens-engine-*` binaries. The binaries were a relic of the staging logic (they exist for CI/headless use) and, worse, they *implied* a second mandatory download. A researcher who just wants to analyse an image set should make exactly one decision: which installer matches my platform. Nothing else.

### Changed

- **One installer per platform, nothing else on the release page.** The engine sidecar already ships *inside* every installer (`bundle.resources`), so the four standalone `lens-engine-*` release assets are gone. Engine binaries remain available as CI artifacts for headless/CLI use, and the Docker image (`infra/docker-compose.yml`) covers server deployments. The release staging step now asserts *exactly* 5 assets (deb, AppImage, setup.exe, msi, dmg) instead of ≥9, so any packaging regression fails loudly.
- **Windows installer hooks.** Ported the parent's NSIS pre-install/pre-uninstall hooks for the sidecar: the stock Tauri NSIS template only stops the main executable, so a surviving `lens-engine.exe` (crash, Task-Manager kill) locked the install tree and broke upgrades ("Error opening file for writing" — the same failure class as Tauri issue #15134). The Lens hooks stop `lens-engine.exe` and `CorpusMind Lens.exe` before any file operation, and deliberately leave the parent CorpusMind (Text) product's processes untouched.
- README gained a "Download & install (end users)" matrix: one file per platform, with the AI-backend expectation (Ollama/LM Studio detected automatically) stated up front.

## [0.1.0] — 2026-09-12 · Standalone extraction ("own repo, own identity")

This is the first release of **CorpusMind Lens as its own repository**. It is simultaneously a new beginning and a continuation: the codebase starts its own semantic-versioning line at **0.1.0** rather than continuing the parent monorepo's 1.1.0, because the researchers who cited CorpusMind v1.1.0 cited the *combined* product; the standalone Lens deserves an honest version line of its own whose history begins with this entry, not an accident of a copy-pasted `package.json`. (Decision recorded here per the build brief §19 — version-line continuity was an open decision, and "clean new-repo signal" was chosen.)

### Why the split

Lens kept inheriting CorpusMind (Text)'s concepts, components, and vocabulary because both products lived in one codebase and one UI shell, gated only by an `isLensMode` flag threaded through a dozen shared files. The parent project's own CHANGELOG diagnosed the recurring damage across three release rounds (v1.0.9, v1.1.0-visual-battery, v1.2.0): Lens's "Corpora" screen was once the text corpus manager — a TXT/DOCX/PDF uploader, a POS tagset picker, a tokenize→tag→parse compile gate, a tokens/types/TTR dashboard — none of which mean anything for an image corpus. A framework dropdown was once labeled "Lens," colliding with the product name itself. Lens icons were byte-for-byte identical to the main app's. Lens installers went missing from tagged releases because the pipeline treated Lens as a secondary build target. The "Lens boundary" was cosmetic — navigation state accepted any target, so hidden views stayed reachable.

The fix is architectural, not another gating flag: two products with different mental models (document/token/tagset vs. image/region/frame) get two codebases. This repository is the second one.

### What this release contains (Phases 0–3 of the build brief)

- **Own identity.** Own name (always "CorpusMind Lens" — never abbreviated to "Lens" alone in UI copy, to avoid the label-collision bug fixed once in the parent), own aperture-eye mark (`icon-lens.svg`, badge colour `#2563eb`), own bundle identifier `org.corpusmind.lens`, own version line, own CI/release pipelines, own CITATION.cff pointing at the reserved DOI `10.5281/zenodo.21673083`.
- **Own data model.** `Project → ImageSet → Image`, with no intervening "Corpus" concept that also has to make sense for text. The UI vocabulary is *image sets* everywhere — the word "corpus" survives only where it is analytically precise (e.g. "visual corpus", "OCR corpus" as export artifacts).
- **Ported, working core.** The five-dimension visual annotation schema (verbatim), the corpus-statistics formulas (forked into `lens_engine/stats/` with the same tested definitions and worked-example tests), the vision pipeline (ingestion with magic-byte sniffing, EXIF/XMP with GPS permanently excluded, OCR with confidence, colour + geometric composition analysis), the consent gate for person-descriptive content, the twelve framework templates (ported verbatim as versioned YAML), the visual-grammar module, cross-modal meaning, the discourse-lens battery, the assistant tool surface, batch runner, and exports including the auto-drafted Methods Section.
- **Gap closures (the "next-level" items).** An open-vocabulary object/scene detection module (OWLViT-class, run locally, pluggable, feeding the Representational metafunction with real data), real embedding-backed multimodal alignment behind the same interface the grid heuristic used, typography-in-image profiling from OCR bounding-box geometry, and narrowly scoped Arabic OCR post-processing (`nlp_ar`).
- **Companion Mode.** The only integration surface back to CorpusMind (Text): an opt-in, documented, versioned HTTP client (`docs/COMPANION_MODE.md`, `X-CorpusMind-API-Version` header). Off by default; Lens is fully functional and self-explanatory with zero CorpusMind (Text) present.
- **Desktop shell.** A Tauri 2 app with its own sidecar lifecycle for `lens-engine` (spawn → health poll → log-to-file → full detach), including the port-conflict check against a possibly-running CorpusMind (Text) engine on 8765: the second engine to start detects the first and either treats it as a Companion or moves to another port — it never crashes.

### Honest limitations at 0.1.0

- The open-vocabulary detector and embedding backend degrade gracefully when their (heavy, optional) model dependencies are absent: detection/alignment endpoints report `model: "unavailable"` rather than pretending to run. The heuristic alignment fallback is deterministic and clearly labeled as such.
- Precision/recall for the default detector **are published** in `docs/METHODOLOGY.md §6` — from the first §16 validation round on a 16-image hand-annotated sample (micro P = R ≈ 0.41 at the default threshold; scene top-1 5/6; embedding zero-shot top-1 8/10). Detection output is candidate evidence requiring human verification, and the documented failures (products, food, religious symbols at recall 0) are stated as bluntly as the successes (the parent project's honesty standard for LLM-assisted metaphor detection applies here too).
- Companion Mode is shipped but *not* required for the Definition of Done; it can be deferred at packaging time without touching any other subsystem.

### Credits

Extracted from [CorpusMind](https://github.com/waleedmandour/CorpusMind) (AGPL-3.0-only) by Dr. Waleed Mandour (Sultan Qaboos University) and Prof. Wesam Ibrahim (Princess Nourah Bint Abdulrahman University). This repository starts its own history; the visual-analysis apparatus it carries originated there.
