# Operating Instructions

## Skills Available
- `sparql-query`: ACL-validated SPARQL queries against Oxigraph. Pass `acl_role: tutor` in every invocation.
- `qdrant-search`: Semantic similarity search against Qdrant vector store.

## ACL Identity
Always pass `--agent claire` (not `--webid`) when invoking sparql-query. The handler
constructs your WebID from `$CSS_IDENTIFIER_URL` automatically — works on localhost dev and VPS
without any change. Your role for all SPARQL queries: `tutor`.

## Logging
Emit structured JSON to stdout for every skill invocation:
```json
{"timestamp":"<ISO-8601>","service":"openclaw-runtime","level":"INFO","event":"skill.invoked","agent":"claire-teacher","duration_ms":0,"details":{"skill":"sparql-query","acl_role":"tutor"}}
```
