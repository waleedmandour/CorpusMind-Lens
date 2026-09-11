# Framework prompt templates

Each file in this directory is one of the twelve supported theoretical lenses
for the discourse-analysis battery (§9.13). They are **versioned, editable
YAML files** — not hard-coded strings — so researchers can inspect, cite, and
propose edits to the exact prompt structure that produced an analysis.

## The twelve lenses

| File | Framework | Family |
|---|---|---|
| `aristotle-rhetoric.yaml` | Aristotle's Rhetoric (ethos/pathos/logos) | persuasion |
| `barthes-semiotics.yaml` | Barthes — denotation/connotation, anchorage/relay | semiotics |
| `fairclough-cda.yaml` | Fairclough — three-dimensional CDA | CDA |
| `halliday-sfl.yaml` | Halliday — Systemic Functional Linguistics | SFL |
| `kress-van-leeuwen.yaml` | Kress & van Leeuwen — Reading Images (Visual Grammar) | visual_grammar |
| `lakoff-johnson-cmt.yaml` | Lakoff & Johnson — Conceptual Metaphor Theory | metaphor |
| `machin-mayr-mcda.yaml` | Machin & Mayr — Multimodal Critical Discourse Analysis | CDA |
| `martin-white-appraisal.yaml` | Martin & White — Appraisal Theory | SFL |
| `peirce-semiotics.yaml` | Peirce — icon/index/symbol | semiotics |
| `toulmin-argumentation.yaml` | Toulmin — Argumentation Model | argumentation |
| `van-dijk-sca.yaml` | van Dijk — Socio-Cognitive Approach | CDA |
| `wodak-dha.yaml` | Wodak — Discourse-Historical Approach | CDA |

## Every template defines

- `categories` — the framework's analytic categories the claim schema must use.
- `output_schema` — claim / evidence-ids / confidence / framework attribution.
- `guardrails` — the non-negotiable instructions: evidence grounding,
  framework-lensed hypothesis phrasing, culture-relative colour symbolism,
  no identity recognition, never stating ideology as settled fact.

The engine loads these files at request time (`lens_engine.discourse.lenses`);
the LLM mode turns each template's guardrails into its system prompt, and the
heuristic mode maps its categories onto computed signals. Editing a guardrail
changes both modes' behaviour — please keep changes framework-faithful and
record the reason in a CHANGELOG entry (these files are cited by version in
every result payload and in the Methods Section export).
