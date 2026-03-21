# Operating Instructions

## Skills Available (Path A — through skill layer)
- `sparql-query`: ACL-validated SPARQL queries. Set `acl_role` to whatever role the test requires.
- `qdrant-search`: Semantic similarity search. Use to test vector privacy boundaries.

## Direct Endpoints (Path B — bypass skill layer)
- CSS: http://community-solid-server:3000
- Oxigraph SPARQL: http://oxigraph:7878/query
- Qdrant REST: http://qdrant:6333

## ACL Identity
Variable per test scenario. Pass the role you are impersonating:
- `acl_role: tutor` — impersonate a teacher
- `acl_role: admin` — impersonate an admin
- `acl_role: regional` — impersonate a policy advisor
- `acl_role: parental` — impersonate a parent
- `acl_role: student` — impersonate a student
- `acl_role: none` — unauthenticated access test

## Logging
Emit structured JSON to stdout for every test execution:
```json
{"timestamp":"<ISO-8601>","service":"openclaw-runtime","level":"INFO","event":"troll.test","agent":"troll-adversary","duration_ms":0,"details":{"attack_category":"acl_enforcement","access_path":"direct","test_name":"unauthenticated-pod-read","result":"pass"}}
```
