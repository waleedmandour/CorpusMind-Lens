# Third-Party Licenses

CorpusMind Lens is licensed **AGPL-3.0-only**. This file records every third-party dependency actually used by this repository — code packages, bundled model weights, and lexicons. Per project policy, **nothing ships bundled or auto-downloaded without an entry here first.**

This file is written fresh for Lens (the parent product's dependency set differs; it was not reused verbatim).

## Python engine (`lens-engine/`)

| Package | License | Use |
|---|---|---|
| FastAPI | MIT | REST + WebSocket framework |
| Uvicorn | BSD-3-Clause | ASGI server |
| Pydantic | MIT | Schemas / validation |
| httpx | BSD-3-Clause | Provider + Companion HTTP client |
| Pillow | HPND (MIT-CMU) | Image decode/encode, EXIF |
| openpyxl | MIT | xlsx export (base dep since v0.1.0) |
| et_xmlfile | MIT | openpyxl runtime dependency |
| NumPy | BSD-3-Clause | Colour/composition/saliency computation |
| pytesseract | Apache-2.0 (GPL-3.0 for the Tesseract binary itself, see below) | OCR wrapper |
| PyYAML | MIT | Framework template loading |
| python-multipart | Apache-2.0 | Multipart upload handling |
| cryptography | Apache-2.0 / BSD-3 | At-rest encryption option |

### Optional model-serving packages (not installed by default)

These power the Phase 2 upgrades (open-vocabulary detection, embeddings-backed alignment). They are loaded lazily; the engine runs without them and reports the affected endpoints as unavailable.

| Package | License | Use |
|---|---|---|
| transformers (Hugging Face) | Apache-2.0 | OWL-ViT open-vocabulary detector; CLIP/SigLIP zero-shot scene classification |
| torch | BSD-3-Clause (with additional patent grant; NOT AGPL-compatible for *redistribution of modified* versions — tracked here for compliance) | Inference backend for the above |
| sentence-transformers | Apache-2.0 | Joint image–text embeddings (alignment) |
| timm | Apache-2.0 | Vision backbone utilities |

### Model weights (downloaded at user request, never bundled)

| Weights | License | Use |
|---|---|---|
| `google/owlvit-base-patch32` | Apache-2.0 (weights card: CC-BY-4.0 per model card terms — verify on the model page before redistribution) | Default open-vocabulary detector (§9.5) |
| `sentence-transformers/clip-ViT-B-32` | Apache-2.0 / MIT (code + weights) | Default joint image–text embedding model (§9.11) |
| `google/siglip-base-patch16-224` | Apache-2.0 | Alternative embedding / zero-shot scene backend |

> Policy: because weights licensing can change on the Hugging Face hub, Lens records the license **as observed at integration time** and surfaces the model id + revision in every result payload (reproducibility principle). The Methods Section export names the exact revision used.

## System / external binaries

| Component | License | Use |
|---|---|---|
| Tesseract OCR (system binary) | Apache-2.0 | OCR engine (Arabic + English). Users install it via their OS package manager; Lens never bundles it. |
| Ollama | MIT | Local LLM/VLM serving (user-installed, external to Lens) |
| CAMeL Tools (optional, `nlp_ar` upgrade path) | Apache-2.0 (+ data sub-licenses, see their repo) | Dialect-aware Arabic OCR post-processing. If enabled at build time, its data licenses are appended here before shipping. |

## Web frontend (`lens-web/`)

| Package | License | Use |
|---|---|---|
| React, React DOM | MIT | UI runtime |
| Vite | MIT | Build tool |
| TypeScript | Apache-2.0 | Type system |

The Lens design tokens (colour system, ribbon shell conventions) are reimplemented natively in `lens-web/src/styles/` — no CSS or component files are shared with the parent product.

## Desktop (`lens-desktop/`)

| Component | License | Use |
|---|---|---|
| Tauri 2 (Rust crates: tauri, tauri-plugin-shell, etc.) | MIT / Apache-2.0 | Desktop shell + sidecar lifecycle |
| log / env_logger | MIT / Apache-2.0 | Shell logging |

## Reference data

| Asset | License | Use |
|---|---|---|
| `reference-data/frameworks/*.yaml` (12 files) | AGPL-3.0-only (project-authored; ported verbatim from CorpusMind) | Theoretical-lens prompt templates |

> Deliberately **not** included: the parent project's USAS lexicon (`reference-data/tagsets/`, CC BY-NC-SA) — it belongs to the text product and has no reason to live in Lens.

## Compliance notes

- AGPL-3.0 copyleft: Lens derives from AGPL-3.0-licensed parent code, therefore Lens carries AGPL-3.0-only. Dependencies that are merely *used* (Apache/MIT/BSD) do not force relicensing; dependencies whose *modified redistribution* is forbidden (e.g. certain weights with NC terms) are never bundled — they are downloaded at user request and their licenses surfaced in-app.
- GPS/location metadata is never extracted from images, so no GPS-related licensing or privacy surface exists.
