1. Mission

One sentence: CorpusMind Lens is a local-first, AI-native, next-generation visual and multimodal corpus-analysis environment — it lets a researcher turn a set of images (with or without accompanying text) into publication-ready, statistically grounded, framework-lensed discourse analysis, using the same evidentiary rigor corpus linguistics has always demanded of text, applied for the first time to images at scale.

Lens is not "CorpusMind's image tab." It is a sibling product: its own repository, its own engine, its own frontend, its own release cycle, its own brand identity, and its own Zenodo DOI — built to interoperate with CorpusMind (Text) through a documented API, never through shared source code or a shared UI shell.

2. Why This Needs Its Own Repository

This is not a cosmetic reorganization. The current monorepo has a diagnosed, recurring defect, documented in the project's own CHANGELOG.md across multiple release rounds (v1.0.9, v1.2.0, v1.1.0-visual-battery): Lens keeps inheriting CorpusMind Text's concepts, components, and vocabulary because they live in the same codebase and the same UI shell, gated only by an isLensMode flag / ?shell=lens query parameter threaded through more than a dozen shared files (App.tsx, Sidebar.tsx, HomeView.tsx, CommandPalette.tsx, OnboardingModal.tsx, AboutView.tsx, CorpusSelectionView.tsx, UserGuideView.tsx, store/ui.ts, i18n.ts, api.ts, and both Vision views). Concretely, this has already caused:

Lens's "Corpora" screen once was the text corpus manager (a TXT/DOCX/PDF uploader, POS tagset picker, a tokenize→tag→parse compile gate, a tokens/types/TTR dashboard) — "none of which mean anything for an image corpus" (the project's own words, CHANGELOG v1.0.9).
A UI label collision: the discourse-framework dropdown was labeled "Lens," colliding with the product name itself.
Branding bleed: every Lens icon file was byte-for-byte identical to the main app's for multiple releases; the sidebar logo hardcoded the main app's mark even inside the Lens shell.
Release/version bleed: Lens installers went missing from tagged releases because the build pipeline treated Lens as a secondary target of the main app's workflow; version files drifted out of sync across the two products.
Navigation bleed: the "Lens boundary" was cosmetic — setActiveNav accepted any navigation target, so Home's text-tool cards opened views the Lens sidebar was supposed to hide.

The fix is architectural, not another gating flag. Two products with different mental models (a document/token/tagset model for text; an image/region/frame model for vision) need two codebases. This document specifies how to extract Lens cleanly, close the feature gaps that the shared codebase left half-built, and ship it as a genuinely independent, "next-level" product — while keeping a narrow, explicit, versioned integration path back to CorpusMind for researchers who use both.

3. Research Basis
3.1 What Lens already gets right (carry this forward faithfully)

The existing implementation's visual-analysis apparatus is genuinely research-grounded and should not be diluted in the rewrite. It already implements:

Visual Grammar (Kress & van Leeuwen 2006, Reading Images) — the three metafunctions (Representational, Interactional, Compositional).
A five-dimension visual annotation framework, purpose-built to give image corpora the same analytical apparatus text corpora have: Visual Morphology (Cohn 2013, The Visual Language of Comics; Engelhardt 2002) — 12 categories; Attentional Framing (Kress & van Leeuwen 2006; Bateman 2008, Multimodal Film Analysis) — 15 categories; Filmic Shot Scale (social-distance mapped to Bordwell & Thompson's film taxonomy) — 8 categories; Path Structure and Transitions (McCloud 1993, Understanding Comics; Halliday & Hasan 1976 cohesive conjunction) — 10 categories; Multimodal Integration (Barthes 1977 anchorage/relay; Royce 2007 intersemiotic complementarity) — 9 categories.
A corpus-linguistics measurement battery applied to that annotation scheme: frequency profiles, a diversity battery (TTR, Guiraud's R, MATTR, STTR), sequence n-grams over reading order, co-occurrence association between dimensions (MI, T-score, Dice, LogDice, ΔP, G²), set-vs-set keyness (full battery, LL-ranked), dispersion (Juilland's D, Gries' DP), and a visual KWIC. This is the single most distinctive thing about the product — no mainstream tool does this — and is the anchor of the "next-level" positioning requested for this rebuild.
Twelve theoretical-framework prompt templates for the AI layer (Kress & van Leeuwen, Halliday's SFL, Fairclough's CDA, van Dijk's SCA, Wodak's DHA, Machin & Mayr's MCDA, Barthes' Semiotics, Peircean Semiotics, Lakoff & Johnson's CMT, Martin & White's Appraisal, Toulmin's Argumentation, and Aristotle's Rhetoric).
Design guidance drawn from the CLARIN multimodal-resource family, the CASS corpus-methods-for-multimodal-data project, and IPTC photo metadata conventions for image provenance.
A deliberate research-ethics default: GPS coordinates are never extracted from image EXIF/XMP, and facial/demographic inference ships opt-in and off by default (see §17).
3.2 What "next-level" means: closing the gap against current research

Two concrete engineering gaps exist in the current implementation that keep it short of the product this document specifies, and both map directly onto active 2023–2026 research directions Lens should now absorb:

Object and scene recognition is still a stub. The Representational metafunction of Visual Grammar needs "what is depicted" (people, objects, scenes) to be anything more than a placeholder, but no open-vocabulary detector or scene classifier is wired in anywhere in the current engine — only OCR and geometric composition/colour analysis exist. Recent computational visual-semiotics work (the AICE framework, Männistö et al. 2022; and the broader "Automated Visual Content Analysis" / "Images-as-Data" / "Distant Viewing" literature — Schwemmer et al. 2023; Joo & Steinert-Threlkeld 2022; Arnold & Tilton 2023) converges on exactly this pattern: map an operationalized visual-grammar taxonomy onto computer-vision outputs so every category is numeric and reproducible, not just narrated by a language model. Build this, prioritizing a lightweight open-vocabulary detector (e.g., Grounding DINO / OWL-ViT / YOLO-World class of model, run locally) for reproducible bounding boxes, with the vision-LM's free-text description as a complementary, clearly separate narrative layer — never conflating the two.
Multimodal alignment is still a grid-based heuristic, not embeddings. The current alignment.py explicitly documents itself as a placeholder ("Phase 5 swaps in proper CLIP-style embeddings behind the same interface") that was never swapped in. Given how fast vision-language modeling has moved (VLM-related work is now the single fastest-growing topic at CVPR/ICLR/NeurIPS, per recent bibliometric surveys of the field), this is the highest-value single upgrade available: replace the heuristic with real joint image-text embeddings (a local CLIP/SigLIP-class model, or the connected vision-LM's own embedding endpoint where available) behind the same interface, so every existing caller keeps working.

Both upgrades must keep the project's own non-negotiable stance: a numeric, inspectable signal from a deterministic model, with any LLM-generated prose layered on top and clearly labeled as interpretation, never as the measurement itself (see Principle 2, §4).

3.3 The wider field context (for the agent's situational awareness)

Corpus linguistics as a field is actively moving to incorporate multimodal data and AI tooling as a first-class methodology rather than an afterthought, and the tool landscape has not caught up: AntConc/WordSmith/Wordless-class concordancers have no image pipeline at all; qualitative CAQDAS tools (NVivo, ATLAS.ti, MAXQDA) are adding AI coding assistants but do not compute association/dispersion statistics or implement Visual Grammar as a structured score; and the emerging "Automated Visual Content Analysis" research community mostly ships one-off academic scripts, not a maintained, zero-code, cross-platform application. That gap is Lens's reason to exist.

4. Non-Negotiable Design Principles
Local-first, cloud-optional. By default, images, extracted text, and AI queries never leave the machine. Cloud providers are explicit, per-set opt-in, with a visible indicator whenever active.
Grounded AI, never a bare vision chatbot. Every claim the Assistant makes must resolve to a real tool call — a computed statistic, an image region, an OCR span, or a cited framework template — never free generation presented as fact. Ungrounded claims are visibly flagged, not hidden.
Numbers before narrative. Every interpretive/geometric claim (salience, information value, shot scale, colour symbolism, object presence) is backed by a deterministic, re-runnable computation. The vision-LM's prose is a second, clearly labeled layer on top of that, never a replacement for it.
Interpretive claims are framework-lensed hypotheses, never facts. Anything in the CDA/MCDA/ideology/power/persuasion/symbolism family is labeled with the theoretical framework that produced it and phrased as "under a [Framework] reading, X may indicate Y." Colour/cultural symbolism claims are explicitly framework/culture-relative, never universal.
Own data model, own vocabulary — no borrowed concepts. Lens does not surface a document uploader, a POS tagset, a "compile" gate, a token/type/TTR dashboard, or any other text-corpus-shaped affordance in its default corpus workflow (see §7). If a feature does not make sense for an image set, it does not exist in Lens's UI, full stop — this principle exists specifically because its violation is the reason this repository split is happening.
Own product identity. Own name, own icon (the existing aperture-eye mark), own colour badge, own bundle identifier, own version line, own release pipeline, own DOI. Nothing is shared byte-for-byte with the parent app's assets or version files.
Reproducibility is a feature. Every project pins the exact vision-LM model/version, detector model/version, OCR engine/version, and formula versions used, and can emit a "Methods" paragraph for a manuscript.
Consent and restraint around biometric-adjacent features. Facial/body age-group, gender-presentation, emotion, gaze, and dominance/submission inference ship opt-in, off by default, and never perform identity recognition or re-identification. GPS/location metadata is never extracted from images, ever, no setting overrides this.
Practical scale, honestly stated. State a real, tested image-set size target (thousands of images on consumer hardware, with background processing and progress feedback) rather than an unqualified "no limit" claim.
Explicit, versioned interoperability — never implicit coupling. Any connection to CorpusMind (Text) happens over a documented HTTP API contract (§5), gated behind an opt-in "Companion Mode" setting. Lens must be fully functional, and fully self-explanatory in its own vocabulary, with zero CorpusMind (Text) instance present.
5. Relationship to CorpusMind (Text): Siblings, Not Shared Internals

Both products may still be developed by the same authors and share a design language (colour system, typography, ribbon-style shell conventions), but from this point forward they are separate codebases with a network boundary between them, not a monorepo with a mode flag.

No shared source tree. Lens does not import from, symlink to, or git submodule the CorpusMind repository. Where Lens needs logic CorpusMind Text already has (e.g., the §11 collocation/keyness/dispersion formulas), that logic is forked into Lens's own engine/stats/ module with its own tests — a small amount of intentional duplication is the correct trade-off against cross-repo coupling for a handful of pure, stable math functions.
"Companion Mode" (optional, off by default). A researcher who has both products installed can point Lens at a running CorpusMind engine's base URL in Settings. When enabled, Lens's AI Assistant gains a get_text_corpus_overview(base_url, corpus_id) tool that calls the other engine's existing /api/v1/corpora/{id} and /api/v1/corpora/{id}/frequency endpoints over plain HTTP, so one conversation can reason over an image set and a companion text corpus together. This is the only integration surface. It degrades gracefully (the tool is simply absent) if no companion engine is reachable. Document this contract in docs/COMPANION_MODE.md and version it (X-CorpusMind-API-Version header) so either product can evolve independently without silently breaking the other.
Shared design tokens, not shared components. It's fine — good, even — for Lens's UI to look like a sibling of CorpusMind (same colour system, same ribbon shell pattern, same dark/light theming approach). Reimplement those tokens natively in Lens's own web/src/styles/; do not import CorpusMind's CSS or component files.
6. What to Bring Over from the Existing Monorepo

The current monorepo (waleedmandour/CorpusMind, path prefixes below are relative to its root) is your reference source, not your new repo's git history. Treat it as read-only material to port logic and hard-won correctness from — never copy-paste a UI file wholesale, because the whole point is that those files are entangled with the text product.

Port the logic, rewriting call sites to Lens's own data model:

engine/vision/ (OCR, EXIF/XMP extraction, facial-analysis pipeline + consent gate, image metadata) — port in full, this is Lens-specific already.
engine/multimodal/ (alignment, visual grammar scoring, cross-modal discourse) — port and then complete per §3.2's two gap-closing items.
engine/vision/annotations.py — the five-dimension schema. Port verbatim; it is correct and has no text-app entanglement.
The vision-facing API routers: engine/api/vision.py, engine/api/visual_corpus.py, engine/api/phase5.py (the 12 discourse-lens routes) — port and re-home under Lens's own route prefixes.
The reused statistics: engine/stats/measures.py's formulas — fork into Lens's own engine/stats/ with the exact same tested definitions (§11).
reference-data/frameworks/*.yaml (all 12) — port verbatim; these are already a clean, versioned, editable asset with zero text-app coupling.
engine/ai/providers.py (the ModelProvider abstraction: Ollama, LM Studio, Cloud) — port verbatim, it's product-agnostic infrastructure.
The relevant test files as your regression floor: test_phase4_vision.py, test_vision_*.py (5 files), test_lens_v109.py, test_alignment_llm.py, test_discourse_llm.py, test_consent_gate.py, test_assistant_vision_tools.py, test_visual_annotations.py, test_ai_chat_endpoint_e2e.py (the cross-modal-grounding parts only).
download/icon-lens.svg and the *-lens.* favicon/PWA icon set — this is already Lens's own purpose-made mark (an eye whose iris is a camera aperture, gold barrel ring, corpus-constellation pupil, on badge 
#2563eb) and should become Lens's only mark, not an alternate skin.
desktop-lens/ — use as the starting skeleton for Lens's own Tauri 2 project (identifier: org.corpusmind.lens, product name "CorpusMind Lens"), but strip the ?shell=lens query-parameter pattern once Lens has its own dedicated web/ build with no mode-switching to do.

Rebuild from scratch, informed by (but not copied from) the existing UI:

The entire web/src/ frontend. The existing VisionCorporaView.tsx four-tab workbench (Overview / Corpus / Measures / Vision Analysis) is a good design — reuse its information architecture — but implement it as Lens's native, only corpus view, not as one branch of a shared component tree that also renders text-corpus concepts.
The desktop shell's sidecar-lifecycle Rust code — reimplement following the same proven pattern (spawn engine as sidecar, health-check poll, log-to- file, full detach on exit) but as Lens's own binary, its own process name, its own port-conflict check against a possibly-running CorpusMind Text engine (keep this specific check — with both apps installed, the second one to launch should detect the other engine on 8765 and either connect to it as a Companion or launch on a different port, never crash).
README.md, CHANGELOG.md, CONTRIBUTING.md, CITATION.cff, THIRD_PARTY_LICENSES.md, docs/ARCHITECTURE.md, docs/METHODOLOGY.md, docs/USER_GUIDE.md (+ Arabic) — all written fresh, Lens-only, in Lens's own voice. Do not inherit a single sentence that describes text-corpus features Lens doesn't have.

Leave behind entirely (do not port):

Everything under engine/ingestion/, engine/nlp/, engine/discourse/ (the Hyland metadiscourse/stance/metaphor-for-text module), engine/storage/models.py's Corpus/Document/Token/AnnotationVersion classes, engine/api/corpora.py, engine/api/analysis.py, engine/api/arabic.py, engine/api/cleaning.py, engine/api/research.py, engine/api/wordlists.py, reference-data/reference-corpora/, reference-data/wordlists/, reference-data/tagsets/ (the USAS lexicon, CC BY-NC-SA licensed — has no reason to live in Lens), and every text-oriented web view (ConcordancerView, AnalysisView, ArabicView, CorpusSelectionView, TagsetSelector).
The exception: if Arabic OCR needs dialect-aware post-processing for captions/embedded text extracted from images, that is a new, narrowly scoped Lens feature (§9.6) — implement it directly against CAMeL Tools in Lens's own engine/nlp_ar/ module; do not import the parent's general Arabic-morphology pipeline wholesale, since Lens only ever needs it applied to short OCR/caption strings, not a full tokenize→tag→parse corpus pipeline.
7. Data Model for the New Repo

Replace the inherited Project → Corpus → {Documents, ImageSets} → Images hierarchy with a model that has no text-corpus baggage:

Project
 └── ImageSet            (was: Corpus, for images only — rename the concept)
      ├── description, provenance/sampling notes, tags
      ├── companion_link: { engine_base_url, corpus_id } | null   (§5, optional)
      └── Image
           ├── raw bytes on disk; meta JSON: user / exif / xmp / tags
           ├── annotations: { visual_morphology, attentional_framing,
           │                  shot_scale, path_transition,
           │                  multimodal_integration }   (§3.1 schema, verbatim)
           ├── ocr: { text, engine, confidence, per-word boxes }
           ├── detections: [{ label, bbox, confidence, model, version }]  (NEW, §3.2)
           ├── embedding: { model, version, vector_ref }                  (NEW, §3.2)
           ├── vlm_description: { text, model, version, timestamp }
           └── discourse_lens_results: { framework_id → structured claims }

ImageSet is the top-level corpus unit — there is no intervening "Corpus" concept that also has to make sense for text. companion_link is the only place a CorpusMind (Text) identifier is ever stored, and it is nullable and inert unless Companion Mode (§5) is on.

8. System Architecture

Keep the proven headless engine, multiple shells pattern from CorpusMind (it works, and consumer hardware/local-LLM constraints don't change just because the product is now standalone) — but every box below lives in the new repo:

lens-engine/            (FastAPI, Python 3.12, asyncio)
├── vision/             ingestion, EXIF/XMP, OCR, facial consent gate
├── detection/          NEW — open-vocabulary object/scene detector wrapper
├── multimodal/         alignment (embeddings-backed), visual grammar, cross-modal meaning
├── discourse/          the 12 framework-lensed discourse-analysis routes
├── stats/              forked §11 formulas, applied over annotation sequences
├── nlp_ar/             narrow Arabic OCR/caption post-processing (CAMeL Tools)
├── ai/                 ModelProvider (Ollama/LM Studio/Cloud), tool registry, audit trail
├── storage/            Project/ImageSet/Image models, SQLite, at-rest encryption
├── companion/          NEW — the optional CorpusMind (Text) HTTP client (§5)
└── api/                REST + WebSocket routes, OpenAPI schema

lens-web/               (React + Vite + TS — a fresh, Lens-only codebase)
├── views/               Overview · Corpora · Vision Workbench · Assistant ·
│                        Settings (incl. Ethics/consent, Companion Mode)
└── public/manifest.webmanifest, service-worker.ts   (installable PWA)

lens-desktop/           (Tauri 2 — adapted from desktop-lens/, own identity)
├── src-tauri/           sidecar lifecycle for lens-engine (+ optional Ollama)
└── binaries/

shared/                 Lens's own OpenAPI-generated TS client
reference-data/
└── frameworks/          the 12 theoretical-lens YAMLs (ported verbatim)
docs/
infra/                  Docker Compose for a self-hosted lens-engine

Ship lens-web the same three ways the parent product proved out: an installable PWA, embedded in lens-desktop via Tauri sidecar, and self-hostable for a lab's shared instance. The ModelProvider abstraction (Ollama native + OpenAI-compatible /v1, LM Studio /v1, opt-in Cloud) is reused verbatim — it was already product-agnostic infrastructure.

9. Full Feature Specification

Build in this order; §16 groups these into phases. Status tags — [HAVE] logic exists and should be ported per §6; [GAP] spec'd previously but never actually implemented, close it now; [NEW] not previously spec'd, added for the "next-level" mandate.

9.1 Project & Image-Set Management [HAVE]

Unlimited projects and image sets, bounded by disk. Provenance/sampling notes per set. Genre/source/date-range metadata (user-definable, not a fixed schema). Set-level statistics: format mix, orientation mix, resolution/date ranges, OCR/caption/VLM/annotation coverage.

9.2 Input Formats [HAVE]

JPG, PNG, TIFF, WebP, BMP. (Not SVG — it's not a raster photograph and the existing docstring claiming SVG support was already flagged as wrong; drop the claim, don't fix the claim.) Upload hardening: per-file size cap, batch cap, magic-byte sniffing so a mislabeled file fails clearly instead of crashing the image library.

9.3 Image Metadata (IPTC-Core-aligned) [HAVE]

EXIF (camera, capture date) + XMP/IPTC-Core (headline, creator, rights, usage terms, keywords) extracted at ingest. User-editable source/publication/ licence/genre/language-of-embedded-text fields, non-destructively merged with the machine-extracted block (which is never user-overwritable). GPS is never extracted (§4 Principle 8) — no exceptions, no setting.

9.4 OCR [HAVE]

Arabic + English + mixed-language, via Tesseract (or an equivalent engine with strong Arabic support), with a per-image confidence score always shown, never silently trusted. Per-upload language override; corpus-level language resolution (an Arabic-tagged set OCRs with ara+eng). A re-analysis endpoint so a missing language pack at ingest time isn't permanent.

9.5 Object & Scene Detection [GAP → build now]

An open-vocabulary detector (people, animals, objects, vehicles, buildings, food, products, logos, weapons, religious/national/political symbols, flags) producing labeled bounding boxes with confidence — geometric and reproducible, feeding the Representational metafunction (§9.10) with real data instead of a stub. Scene classification (office, home, street, classroom, hospital, battlefield, mosque, church, supermarket, airport, …) alongside it. Run locally; no cloud vision API calls without the same explicit opt-in as the LLM Cloud provider.

9.6 Facial & Body Analysis [HAVE, keep opt-in]

Age group, gender presentation, expression/emotion, gaze, head direction, posture/gesture, dominance/submission cues — always output as a described visual cue first ("figure occupies more vertical frame space, direct frontal gaze") with an optional, clearly labeled interpretive gloss. Ships behind the existing Settings → Ethics → Facial Analysis toggle, off by default, backend consent gate enforced regardless of what the UI sends. Never identity recognition or re-identification.

9.7 Colour & Composition Analysis [HAVE]

Dominant colours, harmony, warm/cold balance, brightness, contrast, saturation; information value (left/right, top/bottom, centre/margin), salience, framing, vectors, visual/reading paths, golden ratio, rule of thirds, visual balance — computed geometrically (saliency + bounding-box centroids), not impressionistically. Colour-symbolism output is always framework/culture-relative, labeled as such, never universal.

9.8 Typography-in-Image, Logo, and Symbol Detection [GAP → build now]

For text embedded in images (posters, ads, memes): font weight/size/ capitalization/spacing/alignment/hierarchy, derived from OCR bounding-box geometry. Logo/institution/political-party/NGO/university detection and religious/national/cultural/political/corporate symbol detection, both as ordinary object-detection classes on top of §9.5's detector — this is legitimate media/propaganda-studies analysis of existing published content, not generation of new material.

9.9 The Five-Dimension Visual Annotation Framework [HAVE — flagship]

Port §3.1's schema verbatim. Multi-select values + free-text note per dimension per image; unknown category ids are rejected server-side (a typo never silently corrupts a corpus). Bulk-tagging across a whole set. This is Lens's most distinctive existing asset — do not water it down.

9.10 Visual Grammar Module (Kress & van Leeuwen) [HAVE, now completed by 9.5]

Structured score/breakdown across Representational / Interactional / Compositional metafunctions, each claim citing exactly which sub-analysis (colour, composition, detection, OCR) produced it, plus an AI-generated natural-language explanation. Phrased per Principle 4 (§4): "under a Kress & van Leeuwen reading, X may indicate Y."

9.11 Multimodal Alignment [GAP → upgrade now]

Replace the grid-based heuristic with real joint image-text embeddings behind the same interface (§3.2, §8). Every alignment ships with a confidence score and the exact region/span pair it links; nothing is a black box.

9.12 Cross-Modal Meaning [HAVE]

Reinforcement, complementarity, contradiction, irony, mismatch, amplification, silence, redundancy between image and (embedded or companion-linked) text — each output labeled with which alignment (§9.11) it is based on.

9.13 Discourse-Lens Battery [HAVE — 12 frameworks]

Social Semiotics, CDA (with sub-framework variant: Fairclough / van Dijk / Wodak / Machin & Mayr), Persuasion (Aristotle/Toulmin-grounded), Framing (Entman-grounded), Narrative (Labov-grounded), Visual/cross-modal Metaphor (MIP/MIPVU-inspired, human-verification gate before any candidate counts as confirmed), Emotion, Cultural analysis — each with LLM and heuristic modes, provenance badges (mode/model/confidence), and redaction notices where applicable.

9.14 The Corpus-Linguistics Battery over Visual Annotations [HAVE — flagship]

Reusing the forked §11 formulas exactly: frequency profile per dimension, diversity battery (TTR, Guiraud's R, MATTR, STTR), sequence n-grams over reading order (with <gap> surfacing), co-occurrence association between dimensions (MI, T-score, Dice, LogDice, ΔP, G²), set-vs-set keyness (full battery, LL-ranked), dispersion (Juilland's D, Gries' DP + per-bin histograms), and a visual KWIC (sequence concordance with left/right context). This is what makes Lens a corpus tool and not just an image annotator.

9.15 OCR Corpus Tools [HAVE]

KWIC-style search over OCR text + captions, word-frequency lists (shared EN/AR stopword handling), and set-vs-set keyness on the extracted text — exportable as a <doc>-marked corpus file or structured JSON, so the extracted text can flow into any standard text-analysis tool (including a Companion-linked CorpusMind Text instance, §5).

9.16 Arabic Support [GAP, narrowly scoped → build now]

Dialect-aware OCR guidance and post-processing for Arabic embedded text and captions (normalization, diacritics handling, dialect identification on short spans) via CAMeL Tools — scoped to OCR/caption strings, not a full morphology pipeline (§6). Full RTL UI mirroring throughout Lens, not just RTL text within an LTR layout.

9.17 Bilingual / Comparative Sets [NEW]

Set-vs-set comparison across any two image sets on every applicable metric (§9.14) — the generic "compare A vs B" workflow (before/after, campaign A/B, country A/B, publication A/B), not per-category bespoke code, per the original spec's own guidance for this feature family.

9.18 Batch Runner [HAVE]

Describe and/or run any subset of the 12 discourse lenses over a whole image set with per-image error isolation, skip-if-cached, and consent-gate enforcement; status/cancel endpoints; a batch-results view.

9.19 Export & Reporting [HAVE + extend]

Per-image and per-set export (xlsx/csv/tsv/txt/json): metadata, OCR, colour/composition stats, detections, latest VLM description, discourse summaries. [NEW]: a "Methods Section" auto-draft (mirroring CorpusMind Text's feature) naming the exact detector/OCR-engine/embedding-model/vision- LM versions and formulas used, for a manuscript's methodology section — directly serving Principle 7 (§4).

9.20 AI Assistant (Lens) [HAVE + extend]

Natural-language Q&A: "analyse this poster using Kress & van Leeuwen," "compare these two campaigns' compositional patterns," "find the most salient recurring visual-morphology categories in this set." Grounded tool-calling only (§4 Principle 2); tool surface in §10; with Companion Mode on, can reason over a linked text corpus in the same conversation.

9.21 Ease of Use [HAVE + rebuild natively, §6]

Ribbon-style shell, dark/light themes, command palette, keyboard shortcuts, interactive onboarding written entirely in Lens's own vocabulary (image sets, not corpora-with-documents), WCAG 2.1 AA target, full RTL mirroring.

10. The AI Assistant Layer

Tool surface (extend the ported ModelProvider/tool-registry infrastructure with these tools; log every call + result to the audit trail per Principle 7):

list_image_sets, get_image_set_summary, get_image_analysis(image_id), describe_image_region(image_id, bbox), get_detections(image_id) (new, §9.5), get_alignment(image_id), get_visual_profile(set_id, dimension), get_visual_ngrams(set_id, dimension), get_visual_collocations(set_id, dim_a, dim_b), get_visual_keyness(set_a, set_b), get_visual_dispersion( set_id, dimension), visual_kwic(set_id, category), get_framework_template( name), and — only when Companion Mode is on — get_text_corpus_overview(base_url, corpus_id) (§5).

Each of the 12 framework templates keeps its structured system prompt: analytic categories, required output schema (claim / evidence-ids / confidence / framework attribution), and an explicit instruction never to state ideology, bias, or power relations as settled fact. Store them as the ported, versioned reference-data/frameworks/*.yaml files.

11. Statistical & Computational Reference

Fork these exact, precisely-named definitions from the parent engine's stats/measures.py into Lens's own engine/stats/, unit-tested against the same worked examples — a wrong constant here is a silent validity bug in both products:

Measure	Use	Definition
MI (Church & Hanks 1990)	Dimension co-occurrence	log2(O / E), E = R·C / N
T-score	Dimension co-occurrence	(O − E) / sqrt(O)
Log-likelihood / G² (Dunning 1993)	Co-occurrence, keyness	2·Σ Oᵢⱼ·ln(Oᵢⱼ/Eᵢⱼ)
Dice coefficient	Co-occurrence	2·f(x,y) / (f(x)+f(y))
LogDice (Rychlý 2008)	Co-occurrence	14 + log2(2·f(x,y)/(f(x)+f(y)))
Chi-square	Co-occurrence, keyness	Pearson χ² on the 2×2 table
Delta P (Gries 2013)	Directional association	`P(y
Log Ratio (Hardie 2014)	Keyness effect size	log2((f1/N1)/(f2/N2))
%DIFF (Gabrielatos & Marchi 2012)	Keyness effect size	((norm_f1−norm_f2)/norm_f2)×100
Simple Maths (Kilgarriff 2009)	Keyness score	(norm_f1+SMOOTH)/(norm_f2+SMOOTH)
Odds Ratio	Keyness effect size	(f1·(N2−f2))/(f2·(N1−f1))
Juilland's D	Dispersion	1 − (CV/sqrt(n−1)) across n parts
Gries' DP (2008)	Dispersion	0.5·Σ|obs. prop.ᵢ − exp. prop.ᵢ|
STTR / MATTR	Lexical (here: categorical) variation	TTR over fixed-size windows, averaged
Guiraud's R	Diversity	types / sqrt(tokens)

Applied here over sequences of annotation-category values per dimension (reading order = created_at ascending within a set), exactly as the current implementation already does — carry the exact same "significance and effect size, always together" discipline into visual keyness that CorpusMind Text applies to word keyness: never present a bare log-likelihood ranking as "the" salient-category list without an accompanying effect-size measure.

12. Product Identity & Branding
Name: CorpusMind Lens (always both words; never abbreviate to "Lens" alone in UI copy, to avoid exactly the label-collision bug already fixed once in the parent repo).
Mark: the existing aperture-eye icon (download/icon-lens.svg) — ported as the only mark, not an alternate skin. Badge colour 
#2563eb.
Desktop bundle identifier: org.corpusmind.lens (unchanged — already correctly namespaced separately from org.corpusmind if that's the parent's identifier; confirm the parent's exact identifier and keep this one distinct from it).
Version line: starts its own semantic-versioning line in the new repo. [Confirm with the project owner, §19] whether to restart at 0.1.0 (a clean new-repo signal) or continue from the existing 1.1.0 (preserving the version history researchers may already cite) — either is defensible, but it must be a deliberate choice recorded in the new CHANGELOG.md's first entry, not an accident of copy-pasted package.json files.
DOI: the project already reserved 10.5281/zenodo.21673083 for Lens in a prior changelog entry — write a Lens-only CITATION.cff (modeled on the parent's, §6) pointing at it, and mint/confirm the Zenodo record against the new repository, not the monorepo.
License: AGPL-3.0-only. This is not an open decision — the ported code (§6) is AGPL-3.0-licensed, and AGPL's copyleft requires the derivative to carry the same license. Write a fresh THIRD_PARTY_LICENSES.md covering every dependency actually used in this repo (Tesseract, OpenCV, Pillow, the chosen open-vocabulary detector's weights/license, the chosen embedding model's weights/license, CAMeL Tools if §9.16 is built) — do not reuse the parent's file verbatim, since Lens's dependency set differs.
13. Non-Functional Requirements
Privacy: local-first by default; no telemetry without explicit, separate opt-in; at-rest encryption option for image bytes and metadata; the cloud-AI indicator is unmissable whenever active; GPS never extracted (§4 Principle 8, no exceptions).
Performance: design and message around a stated, tested target (e.g., low-thousands of images per set on consumer hardware with a discrete GPU optional, degrading gracefully with background processing + progress feedback) rather than an unqualified "no limit" claim — background/async processing for uploads is mandatory (the parent app shipped a real regression here once: synchronous Pillow/Tesseract/numpy analysis on the request thread froze the whole engine during batch ingest; do not repeat that mistake).
Accessibility & i18n: WCAG 2.1 AA; full RTL mirroring (menus, ribbon, alignment, not just text direction); string externalization from day one.
Licensing compliance: every bundled/downloaded model or lexicon's license recorded in THIRD_PARTY_LICENSES.md before it ships; refuse to bundle anything unrecorded.
Reproducibility: pin OCR-engine, detector-model, embedding-model, and vision-LM versions per analysis; every result screen states which model/formula/version produced the number on screen.
14. Repository Structure
CorpusMind-Lens/
├── .github/workflows/         ci.yml, release.yml (own pipeline, own targets)
├── lens-engine/                (see §8)
├── lens-web/
├── lens-desktop/
├── shared/
├── reference-data/frameworks/
├── docs/
│   ├── AI_AGENT_BUILD_PROMPT.md    (this file, kept in sync)
│   ├── ARCHITECTURE.md
│   ├── METHODOLOGY.md              (§11's formulas + §3.1's schema, researcher-facing)
│   ├── COMPANION_MODE.md           (§5's API contract)
│   └── USER_GUIDE.md (+ _AR.md)
├── infra/                      Docker Compose for self-hosted lens-engine
├── THIRD_PARTY_LICENSES.md
├── CITATION.cff
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE                     (AGPL-3.0-only)
└── README.md
15. Phased Delivery Roadmap
Phase 0 — Repo & engine skeleton. New repo scaffold; lens-engine skeleton with health-check API; lens-web skeleton as an installable PWA in Lens's own vocabulary from the first commit; lens-desktop Tauri 2 shell spawning lens-engine as a sidecar; ModelProvider ported and wired; own CI.
Phase 1 — Port the working core (§6/§9.1–9.4, 9.6, 9.7, 9.9, 9.10, 9.12, 9.13, 9.14, 9.15, 9.18, 9.19, 9.20, 9.21), rebuilt natively. This alone, done cleanly and self-consistently, is already a shippable, differentiated product — and is where the "confusion" bugs get permanently fixed by construction (there is no shared code left to leak from).
Phase 2 — Close the gaps (§9.5, §9.8, §9.11, §9.16). Object/scene detection, typography/logo/symbol detection, embeddings-backed alignment, scoped Arabic OCR support. This is the phase that actually earns the "next-level" claim — validate the detector and embedding swap thoroughly (adversarial spot-checks against hand-labeled images) before treating them as production defaults.
Phase 3 — Companion Mode (§5). The optional, versioned integration back to CorpusMind (Text); build and test it against a real running instance of the parent engine, including the port-conflict / already- running-engine detection logic.
Phase 4 — Polish, packaging, release. Accessibility/i18n hardening, cross-platform desktop verification (sidecar lifecycle on Windows/Linux/ macOS, the documented pitfalls: target-triple binary naming, macOS quarantine stripping, log-to-file not piped, full child-process detachment), first tagged release, Zenodo DOI mint, docs/USER_GUIDE.md (+ Arabic).
16. Testing & Validation Plan
Treat the ported test files (§6) as a regression floor, not a ceiling — every one must pass against the new engine before Phase 1 is considered done, and every new/upgraded module (detector, embeddings, Arabic OCR scoping) gets its own new tests.
Statistics correctness: unit-test every §11 formula against hand- computed or published worked examples, independently of the parent's test suite (don't assume the fork stayed byte-identical).
Grounding: adversarial-test that every Assistant claim is either tied to a real evidence id or visibly flagged as ungrounded — release-blocking.
Detector/embedding validation: benchmark the chosen open-vocabulary detector and embedding model against a small hand-annotated sample before trusting default thresholds; report precision/recall honestly in docs/METHODOLOGY.md rather than assuming parity with fine-tuned, task-specific models (the same honesty standard the parent project already applies to its LLM-assisted metaphor detection).
Cross-platform desktop: verify the sidecar lifecycle on all three OSes explicitly, including the port-conflict-with-a-running-CorpusMind-engine case from §5/§15.
17. Ethical & Legal Guardrails
Facial/body/demographic inference ships opt-in, off by default, with an in-app notice explaining what it does and does not do (no identity recognition, aggregate/descriptive use only).
Interpretive/ideological claims (CDA/MCDA, framing, cultural analysis) are always framework-attributed hypotheses with cited evidence, never bare assertions of fact about real people, institutions, or groups.
Object/symbol categories like "weapons," "religious symbols," and "political symbols" are legitimate, standard categories in media/ propaganda/discourse studies (analysis of existing published media) — implement them as ordinary detection classes, like any other.
No real, identifiable individual is ever named or re-identified from an uploaded image. GPS/location metadata is never extracted, under any setting.
18. Definition of Done for Lens v1.0 (Standalone)

A researcher with no programming background can, without help and without CorpusMind (Text) installed: install the Lens desktop app or open the Lens PWA, create a project, upload an image set, watch EXIF/XMP/OCR run automatically, annotate images against the five-dimension framework (or trust the auto-detected categories where available), run the visual frequency/ n-gram/collocation/keyness/dispersion battery, run at least one framework- lensed discourse analysis (e.g., Kress & van Leeuwen) on an image and get a grounded, citation-backed answer from the AI Assistant, and export results plus an auto-drafted Methods paragraph — entirely offline against a local Ollama or LM Studio vision-capable model. Enabling Companion Mode against a running CorpusMind (Text) instance is optional and never required to reach any of the above.

19. Open Decisions — Confirm With the Project Owner Before Locking In
New repository name/URL under the owner's GitHub account (this document assumes CorpusMind-Lens).
Version-line continuity: restart at 0.1.0 vs. continue from 1.1.0 (§12).
Which open-vocabulary detector and which embedding model to standardize on for §9.5/§9.11 (weigh license, size, and CPU-only feasibility — the same "consumer hardware ceiling" reasoning the parent spec already applies to LLM sizing applies here).
Whether Companion Mode (§5) ships in v1.0 or is deferred to a fast-follow release — it is not required for the Definition of Done (§18).
Whether the Zenodo DOI already reserved for Lens (10.5281/zenodo.21673083) gets minted against the new repository at the first tagged release, or a fresh DOI is requested instead.
Self-hosting/collaboration model for a shared lab lens-engine instance — mirror the parent's Docker Compose, single-tenant-per-instance approach (§7.4/§10.2 of the parent's own build prompt) unless real-time co-editing is now a requirement.
20. Handoff Notes for the Agent
Source material for porting is the main branch of https://github.com/waleedmandour/CorpusMind as of this writing (latest tagged release referenced throughout this document: v1.1.0, 2026-09-07). Clone it read-only into a scratch directory; do not fork it on GitHub and do not carry its git history into the new repository — the new repo starts its own history with an honest "extracted from CorpusMind, rebuilt as a standalone product" first commit that credits the origin in README.md's acknowledgements, matching how the parent project already credits its own upstream dependencies.
Create the new repository, then work Phase 0 → Phase 4 (§15) in order, committing at each phase boundary with a CHANGELOG.md entry in the parent project's own style (a short prose explanation of why, not just a bullet diff) — that changelog style is a real project asset and worth keeping.
At every step, re-read Principle 5 (§4): if you are about to build a screen, an endpoint, or a piece of copy by generalizing a text-corpus concept "just to reuse the pattern," stop — that instinct is exactly how the previous coupling happened.