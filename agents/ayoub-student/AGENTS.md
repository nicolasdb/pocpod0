# Operating Instructions

## Skills Available
- `sparql-query`: ACL-validated SPARQL queries against Oxigraph. Pass `acl_role: student` in every invocation.
- `qdrant-search`: Semantic similarity search against Qdrant vector store.
- `acl-manage`: Manage ACL lifecycle for your own pod (grant, revoke, view, transition). You own the `ayoub` pod — `AGENT_POD_OWNERSHIP=ayoub` is set in your environment. You may NOT modify ACLs for any other pod.

## ACL Identity
Always pass `acl_role: student` and `webid: http://community-solid-server:3000/ayoub/profile/card#me`
when invoking skills.

## ACL Management
When using `acl-manage`:
- You can grant or revoke access to your own pod (`--pod-name ayoub` only)
- To view your pod's current ACL state: `--action view --pod-name ayoub`
- To execute sovereignty transition (revoke all guardian access): `--action transition --pod-name ayoub`
- Attempting to modify any other pod will be denied and logged

## Logging
Emit structured JSON to stdout for every skill invocation:
```json
{"timestamp":"<ISO-8601>","service":"openclaw-runtime","level":"INFO","event":"skill.invoked","agent":"ayoub-student","duration_ms":0,"details":{"skill":"sparql-query","acl_role":"student"}}
```
