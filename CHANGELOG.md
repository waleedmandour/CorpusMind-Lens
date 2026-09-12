# Changelog

All notable changes to **CorpusMind Lens** are documented here, in the parent project's prose style: each entry explains *why*, not just *what*.

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
