# shared/

Lens's OpenAPI-generated TypeScript client lives here (§8).

The engine is the source of truth: its OpenAPI schema is served at
`http://127.0.0.1:8765/openapi.json`. Regenerate the client after any API
change so the frontend and the contract never drift apart:

```bash
# from the repository root
scripts/generate-client.sh
# → writes shared/lens-api.d.ts + shared/lens-api.ts via openapi-typescript
```

## Why generated, not hand-written

The parent product proved the pattern: a generated client keeps the web app
honest about the API contract (route names, payload shapes, error codes).
`lens-web/src/lib/api.ts` wraps the generated client with Lens-specific
error handling and provider selection; it never invents endpoints.
