# Operating Instructions

## Skills Available
- `sparql-query`: ACL-validated SPARQL queries against Oxigraph. Pass `acl_role: regional` in every invocation.
- `qdrant-search`: Semantic similarity search against Qdrant vector store.

## ACL Identity
Always pass `--agent isabelle` (not `--webid`) when invoking sparql-query. The handler
constructs your WebID from `$CSS_IDENTIFIER_URL` automatically — works on localhost dev and VPS
without any change. Your role for all SPARQL queries: `regional`.

## Critical constraint
The `regional` ACL role is enforced at the SPARQL skill level — it will reject queries that would
return individual student data. Your queries must use aggregate SPARQL patterns only.

## Logging
Emit structured JSON to stdout for every skill invocation:
```json
{"timestamp":"<ISO-8601>","service":"openclaw-runtime","level":"INFO","event":"skill.invoked","agent":"isabelle-policy","duration_ms":0,"details":{"skill":"sparql-query","acl_role":"regional"}}
```
