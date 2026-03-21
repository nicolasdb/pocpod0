# Operating Instructions

## Skills Available
- `sparql-query`: ACL-validated SPARQL queries against Oxigraph. Pass `acl_role: parental` in every invocation.
- `qdrant-search`: Semantic similarity search against Qdrant vector store.

## ACL Identity
Always pass `acl_role: parental` and `webid: http://community-solid-server:3000/fatima/profile/card#me`
when invoking skills.

## Logging
Emit structured JSON to stdout for every skill invocation:
```json
{"timestamp":"<ISO-8601>","service":"openclaw-runtime","level":"INFO","event":"skill.invoked","agent":"fatima-parent","duration_ms":0,"details":{"skill":"sparql-query","acl_role":"parental"}}
```
