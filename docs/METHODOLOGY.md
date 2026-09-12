# CorpusMind Lens — Methodology

Researcher-facing reference for the analytical apparatus: the five-dimension annotation schema and the exact statistical definitions. Every number Lens produces traces back to a definition in this document and a worked-example test in `lens-engine/tests/test_measures.py`.

---

## 1. The five-dimension visual annotation framework (§3.1)

The five dimensions are the visual analogues of levels of linguistic structure. Lens implements them verbatim (54 categories), multi-select with a free-text note per dimension per image; unknown category ids are rejected server-side so a typo never silently corrupts a corpus.

| Dimension | Framework anchor | Categories |
|---|---|---|
| **Visual Morphology** | Cohn 2013 (*The Visual Language of Comics*); Engelhardt 2002 | 12 — graphic_stroke, contour_shape, closure, color_fill, gradient_shading, texture_pattern, part_whole, repetition, symmetry, radial_structure, emblem, logograph |
| **Attentional Framing** | Kress & van Leeuwen 2006; Bateman 2008 | 15 — panel, inset, splash, full_bleed, gutter, border_solid, border_soft, border_absent, frame_break, grid_regular, grid_irregular, given_new, ideal_real, centre_margin, salience_contrast |
| **Filmic Shot Scale** | Kress & van Leeuwen social distance mapped to Bordwell & Thompson 2013 | 8 — extreme_close_up … extreme_long_shot |
| **Path Structure & Transitions** | McCloud 1993; Halliday & Hasan 1976 | 10 — moment_to_moment, action_to_action, subject_to_subject, scene_to_scene, aspect_to_aspect, non_sequitur, match_cut, fade, dissolve, ellipsis_marker |
| **Multimodal Integration** | Barthes 1977 (anchorage/relay); Royce 2007 | 9 — anchorage, relay, caption, speech_balloon, thought_bubble, sound_effect, label_title, emergent_text, contradiction |

**Reading order.** Set-level sequence analyses (n-grams, dispersion, KWIC, transition chains) order images by ingest time (`created_at` ASC). A `path_transition` value on frame *i* describes the shift from frame *i* to frame *i + 1* (an edge annotation).

**Gaps are data.** An image with no value for a dimension contributes `<gap>` to its sequence — gaps measure annotation coverage and are reported, never silently dropped from coverage statistics.

## 2. Deterministic image signals (§9.2–9.5, 9.7, 9.8)

These are the numeric substratum every interpretive claim may cite:

- **Metadata** — EXIF (make/model/software/dates) + XMP/IPTC-Core (title, creator, description, rights, headline, credit, usage terms, keywords). **GPS is never extracted, under any setting.**
- **OCR** — Tesseract (Arabic + English + mixed), per-image mean confidence always surfaced; per-word bounding boxes feed typography and KWIC. Re-analysis after installing a language pack is non-destructive.
- **Colour** — dominant colours (quantized), warm/cold balance, brightness, contrast, saturation. Colour-symbolism notes are phrased as culture-relative, never universal.
- **Composition (geometric)** — saliency = local variance against a Gaussian-blurred base; information value (left/right = given/new; top/bottom = ideal/real; centre/margin), rule-of-thirds intersection salience, golden-ratio offset, visual balance (right − left), framing balance, gradient-orientation vectors.
- **Open-vocabulary detection** — OWL-ViT-class zero-shot detector run locally; labelled bounding boxes (normalized [x, y, w, h]) with confidence; categories include people, vehicles, buildings, weapons, flags, logos, religious/political symbols. Scene classification via CLIP zero-shot. *Honesty note: precision/recall against a hand-annotated sample is published in §6 below — at the default threshold the detector is candidate-evidence-only (P ≈ R ≈ 0.41 on a 16-image smoke sample). Treat default-threshold output as experimental until the ≥ 100-image validation lands.*
- **Typography-in-image** — from OCR box geometry: size bands (pixel-height quartiles), dominant case, alignment, line estimate, size-hierarchy ratio, emphasis signals (e.g. shouty caps). Not font identification — reproducible geometry.

## 3. The corpus-linguistics battery over annotation sequences (§9.14)

All measures below are applied to category sequences (reading order) per dimension. Formula set version: **v1** (forked definitions, unit-tested against hand-computed worked examples).

### 3.1 Frequency and coverage
Per-category counts and percentages per dimension; `<gap>` rate reported as annotation coverage.

### 3.2 Diversity (categorical variation)
| Measure | Definition |
|---|---|
| TTR | types / tokens |
| Guiraud's R | types / √tokens |
| MATTR (Covington & McFall 2010) | mean TTR over every consecutive 50-token window |
| STTR (Baker 1988) | mean TTR over fixed 1000-token chunks (trailing short chunk dropped) |

### 3.3 Sequence n-grams
N-grams (n = 1–5) over the reading-order sequence; `<gap>` tokens participate unless excluded, so annotation holes stay visible in transition chains.

### 3.4 Co-occurrence association between dimensions
For pairs of category values across the same images (denominator N = images annotated on **both** dimensions):

| Measure | Definition |
|---|---|
| MI (Church & Hanks 1990) | log2(O / E), E = R·C / N |
| T-score | (O − E) / √O |
| Dice | 2·f(x,y) / (f(x)+f(y)) |
| LogDice (Rychlý 2008) | 14 + log2 Dice |
| ΔP (Gries 2013) | P(y\|x) − P(y\|¬x), both directions |
| G² (Dunning 1993) | 2·Σ O·ln(O/E) on the 2×2 table |

### 3.5 Set-vs-set keyness — significance AND effect size, always together
Following Hardie's discipline (inherited from the parent project's word-keyness implementation): a bare log-likelihood ranking is never presented as "the" salient-category list.

| Significance | Effect size |
|---|---|
| Log-likelihood G² (Dunning 1993) | Log Ratio (Hardie 2014) = log2((f1/N1)/(f2/N2)) |
| Pearson χ² + Cochran min-expected diagnostic | %DIFF (Gabrielatos & Marchi 2012) |
| Fisher exact (log-space, sparse-safe) | Simple Maths (Kilgarriff 2009), SMOOTH = 1 |
| | Odds Ratio with Haldane–Anscombe 0.5 correction |

Rows are ranked by G²; every row carries its effect sizes and the χ² validity flag.

### 3.6 Dispersion
| Measure | Definition |
|---|---|
| Juilland's D | 1 − (CV/√(n−1)) across n bins; 0–1, higher = more even |
| Gries' DP (2008) | 0.5·Σ \|obs.prop − exp.prop\|; expected = bin *size* share (unequal-bin correct) |
| DP-norm (Gries 2020) | DP · n/(n−1) |

Bins are consecutive slices of the reading order; per-bin histograms are returned for plotting.

### 3.7 Visual KWIC
Sequence concordance: every occurrence of a category with configurable left/right co-annotation context and the anchor image's id and position.

## 4. OCR corpus tools (§9.15)

The extracted OCR text + captions constitute an exportable corpus: word-frequency lists (shared EN/AR stopword handling; Arabic script normalization for matching), KWIC search, set-vs-set keyness on text, and export as a `<doc id="...">`-marked file or JSON — consumable by AntConc/WordSmith/CorpusMind (Text).

## 5. Interpretation layers — what the model contributes (§3.2, §4)

- **Heuristic lenses (deterministic).** Map computed signals onto each framework's analytic categories. Every claim cites feature paths (e.g. `composition.information_value.centre`) and carries a confidence ≤ its signal strength. Reproducible bit-for-bit.
- **LLM lenses (interpretive layer).** The framework YAML's guardrails become the system prompt; the model receives only the deterministic evidence bundle; its claims are parsed into the standard schema, flagged `ungrounded` when they cite nothing, and passed through the consent gate.
- **Phrasing discipline.** Interpretive claims are framework-attributed hypotheses: "Under a [Framework] reading, X may indicate Y." Colour symbolism is always framework/culture-relative. Metaphor candidates require the human-verification gate (MIP/MIPVU-inspired) before counting as confirmed.

## 6. Detector & embedding validation (§16)

**First validation round — published at v0.1.0.** The numbers below are a smoke-level benchmark on a deliberately small hand-annotated sample; they are an honest floor, not a claim of parity with fine-tuned, task-specific models.

**Sample.** 16 freely licensed images (10 object images with 32 hand-annotated boxes + 6 scene-labelled images), sourced via Openverse with per-image attribution and license recorded in `scripts/validation-sample.json`. This is below the ≥ 100-image target set earlier in this section; growing the sample is ongoing work, and the current numbers should be read with that in mind. Annotation policy: single annotator (coarse normalized boxes by visual inspection), depictions of people counted as `person` ground truth (consistent with the consent gate treating depictions as people-representations).

**Method.** The engine's own `OWLViTDetector` (`google/owlvit-base-patch32`) over the default 13-category prompt set; images square-padded (≤ 800 px) for the benchmark run; greedy matching by confidence, same category, IoU ≥ 0.5; CPU-only (2 threads). Reproduce with `python scripts/validate_detector.py` (see script for subcommands and environment notes).

**Micro-averaged detection (32 ground-truth boxes):**

| threshold | precision | recall | TP / FP / FN |
|---|---|---|---|
| 0.40 | **1.000** | 0.125 | 4 / 0 / 28 |
| 0.25 | 0.727 | 0.250 | 8 / 3 / 24 |
| 0.15 (engine default) | 0.406 | 0.406 | 13 / 19 / 19 |

**Per category at the default threshold 0.15:**

| category | precision | recall | notes |
|---|---|---|---|
| building | 0.417 | 0.625 | over-triggers on incidental architecture |
| crowd | 1.0 | 1.0 | n = 1 — not meaningful yet |
| flag | 0.5 | 1.0 | the one large flag was found |
| person | 0.25 | 0.6 | noisy: mural/painted figures detected as persons (by our own depiction policy these are *also* valid positives, so real-world precision is between the strict table value and ~0.5) |
| vehicle | 0.667 | 0.333 | missed a large, saturated red car at default threshold |
| weapon | 1.0 | 0.5 | found the tracked gun, missed the second vehicle-weapon |
| food | 0.0 | 0.0 | missed painted fruit entirely |
| product | 0.0 | 0.0 | missed a shelf of wine bottles entirely |
| religious symbol | 0.0 | 0.0 | missed a carved cross slab |

**Honest reading (§16 requires this be blunt):**

1. At the default threshold the detector is roughly a coin flip (P = R ≈ 0.41 on this sample). Treat every detection as *candidate evidence requiring human verification* — the UI and API already label it as such — not as a measurement.
2. The failure cases concentrate exactly where media-studies researchers need sensitivity: products, food, religious symbols (all recall 0 on this sample), and the second weapon. These categories must not be used for absence claims ("no weapons appear in this set") at v0.1.0.
3. Raising the threshold trades noise for silence: 0.25 is a precision-leaning profile (P = 0.73), 0.40 is near-silence. The default remains 0.15 until the larger sample says otherwise.
4. **Scene classification (CLIP zero-shot over the 16 configured scene classes, 6 images): top-1 5/6, top-3 6/6** — the one miss (coastal street read as beach) is a defensible confusion, and the expected label appeared in top-3 every time.
5. **Embedding backend (`sentence-transformers/clip-ViT-B-32`, zero-shot over the 13 object categories, 10 images): top-1 8/10, top-3 9/10** — image-level zero-shot categorisation is markedly stronger than box-level detection on this sample, which supports using embeddings for alignment/retrieval while treating boxes as candidate evidence.
6. Latency: ~10 s/image at 0.15 (CPU, 2 threads) after a ~21 s warm-up pass — batch ingestion on CPU-only machines should budget accordingly.

Still open before Phase-2 defaults can be called production-quality:

1. Grow the hand-annotated sample to ≥ 100 stratified images (the current tables are a floor, and small-n cells like `crowd` are placeholders).
2. Spot-check embedding alignment confidence calibration (the [0.2, 0.4] cosine → [0, 1] mapping) against human-verified region/span pairs; adjust and re-document.
3. Re-evaluate the detector default threshold and consider a stronger open-vocabulary backend behind the same pluggable interface (the `Detector` protocol was built for exactly this swap).

Detection endpoints remain labelled experimental; where model dependencies are absent the engine reports `model: "unavailable"` rather than pretending to run.
