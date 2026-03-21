# Operating Instructions

## Skills Available
- `sparql-query`: ACL-validated SPARQL queries against Oxigraph. Pass `acl_role: regional` in every invocation.
- `qdrant-search`: Semantic similarity search against Qdrant vector store.

## ACL Identity
Always pass `acl_role: regional` and `webid: http://community-solid-server:3000/isabelle/profile/card#me`
when invoking skills.

## Critical constraint
The `regional` ACL role is enforced at the SPARQL skill level — it will reject queries that would
return individual student data. Your queries must use aggregate SPARQL patterns only.

## Logging
Emit structured JSON to stdout for every skill invocation:
```json
{"timestamp":"<ISO-8601>","service":"openclaw-runtime","level":"INFO","event":"skill.invoked","agent":"isabelle-policy","duration_ms":0,"details":{"skill":"sparql-query","acl_role":"regional"}}
```
