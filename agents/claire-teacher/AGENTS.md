# Operating Instructions

## Skills Available
- `sparql-query`: ACL-validated SPARQL queries against Oxigraph. Pass `acl_role: tutor` in every invocation.
- `qdrant-search`: Semantic similarity search against Qdrant vector store.

## ACL Identity
Always pass `acl_role: tutor` and `webid: http://community-solid-server:3000/claire/profile/card#me`
when invoking skills. The skill layer enforces access control based on this identity.

## Logging
Emit structured JSON to stdout for every skill invocation:
```json
{"timestamp":"<ISO-8601>","service":"openclaw-runtime","level":"INFO","event":"skill.invoked","agent":"claire-teacher","duration_ms":0,"details":{"skill":"sparql-query","acl_role":"tutor"}}
```
