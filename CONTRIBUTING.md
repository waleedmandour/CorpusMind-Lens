# Contributing to CorpusMind Lens

Thank you for considering a contribution. Lens is a research instrument: correctness of *numbers* and honesty of *claims* matter more here than in a typical web app. These guidelines exist to protect both.

## The five contribution rules

1. **Numbers before narrative.** Any feature that produces an interpretive claim must be backed by a deterministic, re-runnable computation, with the LLM's prose (if any) layered on top and clearly labeled. If your PR adds an interpretive output that cannot cite a computed statistic, an image region, or an OCR span, it will be asked to add grounding or a visible `ungrounded` flag.
2. **Framework-lensed, never factual.** Interpretive/ideological claims (CDA, framing, symbolism, power, persuasion) must be phrased as hypotheses attributed to a framework: "under a [Framework] reading, X may indicate Y." PRs that state ideology or bias as settled fact will not be merged.
3. **Own vocabulary.** Do not introduce text-corpus concepts (documents, tokens, tagsets, compile gates) into Lens's UI or data model. If a feature does not make sense for an image set, it does not belong here — this rule is the reason this repository exists as a separate codebase.
4. **Statistics are frozen contracts.** `lens_engine/stats/measures.py` implements published formulas (Church & Hanks 1990; Dunning 1993; Rychlý 2008; Gries 2008/2013; Hardie 2014; Gabrielatos & Marchi 2012; Kilgarriff 2009; Juilland et al. 1970). Changes require: (a) a citation, (b) an updated worked-example test, (c) a CHANGELOG entry explaining the validity impact. A wrong constant is a silent validity bug in a published result.
5. **Reproducibility.** Any model-touching feature must record model id, revision/version, and engine version in its result payload, and the Methods Section export must pick it up.

## Development setup

```bash
# Engine
cd lens-engine
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                 # full suite; the measures tests are the regression floor

# Web
cd lens-web && npm install && npm run dev

# Desktop (optional)
cd lens-desktop/src-tauri && cargo tauri dev
```

Optional heavy extras for detection/alignment: `pip install -e "lens-engine[models]"` (torch/transformers/sentence-transformers — see THIRD_PARTY_LICENSES.md).

## Testing expectations

- Every new stats formula ships with a hand-computed or published worked example.
- Every ported test in CI must stay green; they are the regression floor inherited from the parent engine.
- Assistant-grounding changes must extend the adversarial grounding tests: every Assistant claim resolves to a real evidence id or is visibly flagged `ungrounded` — this is release-blocking.
- Consent-gate changes must prove the gate stays CLOSED by default under all code paths (`Settings → Ethics → Facial Analysis` off ⇒ no person-descriptive content passes).

## Commit / PR style

- Imperative subject, prose body explaining *why*.
- One logical change per PR; the CI (`pytest` + `npm run build`) must pass.
- Changelog: add a prose paragraph (not just a bullet) for user-visible changes, following the existing style.

## Ethics review

PRs touching facial/body analysis, demographic inference, symbol detection categories, or biometric-adjacent features will be reviewed not only for code but for the §17 guardrails: opt-in + off by default, no identity recognition, descriptive-first output, aggregate use only.
