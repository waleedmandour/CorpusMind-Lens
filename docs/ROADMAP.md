# Roadmap — CorpusMind Lens

Where Lens goes next, and *why* — every item below is anchored in what the
field is actually doing (2025–2026 literature and tool landscape), not in
speculation. Statuses: ✅ shipped · 🔨 building · 📋 planned · 💭 exploring.

## What the field demands (evidence base)

Three converging currents define the 2025–2026 corpus-linguistics tool
landscape:

1. **LLM-assisted analysis is mainstream — but only survives peer review
   when it is verifiable.** LLM-assisted annotation is now an established
   method (Yu et al. 2024, cited 119×; Bianco 2026; LATA 2025), and the
   field's consensus is that LLMs work best as **first-pass filters with a
   human in the loop** (Míguez-Rego 2026; Schroeder et al. 2025).
   Lens's grounding-badge + audit-trail architecture is built for exactly
   this discipline.
2. **Embeddings are entering the concordancer.** Laurence Anthony
   (AntConc's author) dedicates his 2025 work to word/sentence embeddings
   for semantic concordancing; Sketch Engine and english-corpora.org are
   shipping AI features. Corpus tools that stay purely literal (regex +
   lemma) are becoming the "manual transmission" of the field.
3. **Multimodal corpora are growing faster than the tooling.** Researchers
   assemble image+text corpora with ATLAS.ti, ELAN, or one-off scripts
   (Sha 2026; Hiippala 2024 — including Peircean semiotic annotation, which
   Lens already implements). Framework-guided *visual* corpus analysis
   remains an open niche — Lens's reason to exist.

## Where Lens stands after v0.3

- ✅ One installer per platform, engine bundled (v0.1.1)
- ✅ Ollama/LM Studio auto-detection, auto-start, one-click silent install (v0.2)
- ✅ Machine-spec-aware model catalog with fit badges + HuggingFace GGUF search (v0.2)
- ✅ Semantic search over an image set's OCR+captions (bge-m3 via local Ollama) (v0.2)
- ✅ Vision-model OCR assist for packaged builds without Tesseract (v0.2)
- ✅ Core visual pipeline: ingest → OCR → colour/composition → annotations →
  12 framework batteries → visual KWIC → keyness/dispersion/n-grams → exports
  (incl. Methods-section auto-draft) (v0.1.x)
- ✅ Companion Mode to CorpusMind (Text), consent gate, local-first AI, no GPS (v0.1.0)
- ✅ Workflow interface: full functional menu (Build corpus → Analyse → Share),
  permanent task bar with Smart-Troubleshooting issue store, offline fix rules,
  LOCAL-model error interpretation, in-app guide + About, default-model picker,
  engine restart + log diagnostics (v0.3)
- ✅ Text layer over the OCR corpus: Concordancer 2.0, collocation engine with
  network view, n-grams/lexical bundles with dispersion, dispersion gallery,
  word sketches (visual edition), reference-corpus keyness (bundled EN/AR
  frequency tables), per-project stoplists (v0.3)

## Shipped — corpus-linguistics backbone (v0.3, "the AntConc audit")

A gap analysis against the classic toolset (AntConc's ten tools, Sketch
Engine's word sketches/thesaurus, LancsBox X's GraphColl, CQPweb) over
Lens's extracted text corpus — the features a corpus linguist expects and
Lens does not yet have. Everything below operates on the OCR corpus +
captions Lens already produces, so the visual and textual layers finally
share one analysis surface. v0.3 ships items 1, 3-7 and 9; the remainder
stay planned:

1. ✅ **Concordancer 2.0** — text KWIC with left/right sort positions,
   regex queries, per-hit metadata, export to CSV/XLSX (AntConc parity;
   today's visual KWIC stays for word-box geometry). (v0.3)
2. 📋 **CQL-lite query language** — the common subset of Corpus Query
   Language (token, lemma, pos, distance operators) over a light
   tokenizer+tagger for OCR text; Sketch Engine users should feel at home.
3. ✅ **Collocation engine + GraphColl-style networks** — MI, t-score,
   Log-log, LL and **Log Ratio** (Hardie's effect-size discipline, already
   enforced in Lens's keyness), interactive collocation network view. (v0.3)
4. ✅ **Reference-corpus keyness** — curated reference frequency
   tables (the parent project's BE06/Leipzig/CAMEL lists, open-licensed)
   shipped inside the installers so keyness works *without* needing a
   second image set; dispersion-incorporated variants listed under
   n-grams/bundles. (v0.3)
5. ✅ **Lexical bundles & n-gram dispersion** — bundle extraction with
   text-dispersion measures (Larsson 2025-style Juilland's D / Gries' DP
   over reading order), useful for EAP-facing analyses of OCR'd
   student/poster text. (v0.3)
6. ✅ **Dispersion gallery** — Juilland's D, DP (already computed) as
   per-word dispersion rows across the set's images in reading order. (v0.3)
7. ✅ **Word sketches (visual grammar edition)** — Sketch Engine's
   one-page grammatical summary, re-imagined for visual data: for a chosen
   token, its typical visual co-patterns (colour, composition band,
   typography register, detected objects) instead of grammatical
   dependencies. This is Lens's differentiated answer to the word sketch. (v0.3)
8. 📋 **Semantic/USAS tagging of OCR text** — port the parent's USAS
   top-lexicon bridge; enables semantically-grouped keyword lists and
   metaphor/metonymy triage (Krennmayr-style MIP support pairs with the
   existing CMT framework lens).
9. ✅ **Stoplist & wordlist manager** — editable EN/AR stoplists per
   project (beyond today's built-in list), resolved in every wordlist,
   collocation and n-gram run. (v0.3)

## Planned — LLM-assisted analysis, verifiably (v0.4)

1. 📋 **Human-in-the-loop annotation pipeline** — the LLM pre-annotates a
   sample under a chosen framework; the researcher confirms/edits with
   per-item accept/reject; agreement statistics (Cohen's κ, raw agreement)
   between model pass and human pass are computed and exportable. Anchored
   in Schroeder 2025 + Míguez-Rego 2026; the ethics gate and JSONL audit
   trail already exist.
2. 📋 **Chat-with-your-corpus (RAG)** — retrieval over OCR text +
   annotations + framework outputs via the local embedding store, served
   through the Assistant's existing grounded/ungrounded contract.
3. 📋 **Vector KWIC** — semantic neighbour ordering of concordance lines
   (Anthony 2025) using the same embedding backend.
4. 📋 **Cross-set semantic comparison** — "what do these two campaign
   sets talk about differently?" via embedding-space topic clusters
   (BERTopic-style, local-only).

## Planned — Arabic & regional scholarship (v0.4–v0.5)

Arabic NLP is active but tool-poor (Alayba 2025; the 2026 "Is Arabic
really well-resourced?" survey) — and both Lens's authors are Gulf-based.

1. 📋 Dialect-aware normalization presets extended to Gulf/MSA mixing in
   OCR post-processing (current `nlp_ar` is deliberately scoped).
2. 📋 Arabic-first UI terminology review with a proper glossary (the
   parent's arabic-glossary pattern).
3. 📋 CAMeL-tools-class morphological annotations as an optional local
   dependency for the CQL layer.
4. 📋 Arabic reference corpora for keyness (port CAMEL/Quranic tables).

## Exploring

- 💳 **Reproducibility manifest** — one-click FAIR "analysis manifest"
  (framework YAML versions, model IDs+quantisation, seeds, corpus
  checksums, engine version) exported alongside every battery, citable
  with the Zenodo DOI.
- 💳 **Plugin detectors** — documented interface for lab-specific
  open-vocabulary detectors beyond the OWL-ViT-class default.
- 💳 **Rust engine core** — long-term: fold the hot statistics path into
  the shell to shrink the sidecar; the FastAPI surface stays.

## Non-goals (recorded deliberately)

- No cloud dependency by default — every AI feature must keep working
  against a local Ollama/LM Studio, full stop.
- No identity recognition, no GPS — the ethics architecture is not for sale.
- No "auto-analysis" without the framework attribution + hedging discipline;
  interpretive claims remain labeled hypotheses with cited evidence.
