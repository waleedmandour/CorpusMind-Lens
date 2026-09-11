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
- **Open-vocabulary detection** — OWL-ViT-class zero-shot detector run locally; labelled bounding boxes (normalized [x, y, w, h]) with confidence; categories include people, vehicles, buildings, weapons, flags, logos, religious/political symbols. Scene classification via CLIP zero-shot. *Honesty note: published precision/recall against a hand-annotated sample is pending (§16); treat default thresholds as experimental until the table appears in this document.*
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

Before the Phase-2 defaults can be treated as production-quality:

1. Hand-annotate a small stratified sample (≥ 100 images) for the detector's priority categories.
2. Report precision/recall per category here — honestly, including failures on the categories researchers care about (weapons, religious/political symbols, flags).
3. Spot-check embedding alignment confidence calibration (the [0.2, 0.4] cosine → [0, 1] mapping) against human-verified region/span pairs; adjust and re-document.

Until that table lands, detection endpoints are labelled experimental and alignment falls back to the clearly-labelled grid heuristic where model dependencies are absent.
