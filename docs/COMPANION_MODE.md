# Companion Mode — the CorpusMind (Text) integration contract (§5)

Companion Mode is the **only** integration surface between CorpusMind Lens and CorpusMind (Text). It is:

- **Optional.** Off by default. Lens is fully functional and fully self-explanatory with zero CorpusMind (Text) present — no feature anywhere in Lens requires it.
- **Explicit.** The user points Lens at a running CorpusMind engine's base URL in Settings → Companion Mode.
- **Versioned.** Every request carries `X-CorpusMind-API-Version: 1`; a mismatch in the major version fails loudly rather than silently mis-reading the other product's data.
- **Graceful.** If no companion engine is reachable, the `get_text_corpus_overview` Assistant tool is simply absent from the tool surface and the endpoints return a clean 502 — nothing crashes.

## Contract

Lens calls exactly two endpoints on the companion engine — both already exposed by CorpusMind (Text)'s existing API:

### 1. Corpus overview

```
GET {engine_base_url}/api/v1/corpora/{corpus_id}
X-CorpusMind-API-Version: 1
X-CorpusMind-Lens-Client: lens-engine/0.1.0
```

Response (200): the corpus's metadata + summary as served by the parent engine (id, name, description, size, language mix — whatever the parent's `/corpora/{id}` returns). Lens treats the payload as opaque except for display fields.

### 2. Corpus frequency list

```
GET {engine_base_url}/api/v1/corpora/{corpus_id}/frequency?limit={limit}
X-CorpusMind-API-Version: 1
```

Response (200): ranked frequency list entries. Used by the Lens Assistant to reason over a text corpus in the same conversation as an image set (e.g. "compare the word choices in the companion corpus with the visual morphology patterns here").

### Version negotiation

The client compares the advertised `X-CorpusMind-API-Version` major version with its own (`1`). On mismatch, `CompanionError("companion API version mismatch: …")` is raised and surfaced — either product can evolve independently without silently breaking the other.

## Storage rules (§7)

`companion_link: { engine_base_url, corpus_id } | null` is the **only** place a CorpusMind (Text) identifier is ever stored, per ImageSet, nullable, and inert while Companion Mode is off.

## Engine-side behaviour

- `lens_engine/companion/client.py` — the client; no other module may talk to a companion engine.
- `lens_engine/api/companion.py` — `/companion/status`, `/companion/corpora/{id}`, `/companion/corpora/{id}/frequency`, and the per-set `companion-link` setter. Off ⇒ 409 with an explanatory message.
- `lens_engine/ai/tools.py` — `get_text_corpus_overview` appears in the Assistant tool surface **only** when Companion Mode is on (§5: "the tool is simply absent").

## Port-conflict / coexistence (§15 Phase 3)

Both products use the same default engine port (8765). Lens's desktop shell checks whether something is already listening **before** starting its sidecar: if a CorpusMind (Text) engine holds 8765, Lens either connects to it as a Companion (if the user enables Companion Mode) or starts on the next free port (8766, 8767, …). The second engine to launch never crashes into a port conflict.

## What Companion Mode is NOT

- Not shared source code, shared UI shell, or shared components (§5).
- Not a data-synchronisation channel — no image, annotation, or analysis data leaves Lens via this contract; it is a read-only query surface into the companion's corpus metadata and frequency lists.
- Not required for the Definition of Done (§18) — deferrable at packaging time without touching any other subsystem.
