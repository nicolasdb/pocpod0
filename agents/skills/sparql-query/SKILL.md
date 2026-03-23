---
name: sparql-query
description: ACL-validated SPARQL queries against Oxigraph. Validates the calling agent's role identity against CSS Pod ACLs before executing parameterized .rq templates. Returns results with named-graph provenance metadata.
---

# SPARQL Query Skill

This skill executes parameterized SPARQL queries against the Oxigraph triple store
(`http://oxigraph:7878/query`) with ACL enforcement at the Pod level.

## Invocation

Use your `exec` tool to run the handler as a subprocess:

```bash
python /app/agents/skills/sparql-query/handler.py \
  --query-type TEMPLATE_NAME \
  --webid YOUR_WEBID \
  --role YOUR_ROLE \
  --params '{"param_name": "value"}'
```

**Required arguments:**
- `--query-type`: Template name — one of `student-progress`, `cross-context-query`,
  `aggregate-anonymized`, `parental-view`, `transfer-profile`
- `--webid`: Your WebID URI, e.g. `http://localhost:3000/claire/profile/card#me`
- `--role`: Your role — one of `tutor`, `admin`, `regional`, `parental`, `student`
- `--params`: JSON object with template parameters (see Templates section below)

**Environment variables (set automatically in Docker):**
- `CSS_IDENTIFIER_URL=http://localhost:3000` — must match CSS `--baseUrl`; change to VPS domain on deployment
- `CSS_CONNECT_URL=http://community-solid-server:3000` — TCP endpoint for CSS (may differ from identifier URL)
- `CSS_IDENTIFIER_HOST=localhost:3000` — Host header sent to CSS (required when CONNECT_URL ≠ IDENTIFIER_URL)
- `OXIGRAPH_URL=http://oxigraph:7878`

## Templates and Parameters

### student-progress
Query a student's learning activities in a specific context/document.

```json
{
  "student_uri": "http://localhost:3000/ayoub/profile/card#me",
  "context_uri": "http://localhost:3000/ayoub/learning/course/UUID.ttl"
}
```

### cross-context-query
Query activities accessible to a role across a pod document.

```json
{
  "agent_role": "tutor",
  "pod_uri": "http://localhost:3000/ayoub/learning/course/UUID.ttl"
}
```

### aggregate-anonymized
Aggregate statistics for a program within a community (no individual records).

```json
{
  "program_uri": "http://localhost:3000/school-community/programs/stem",
  "community_uri": "http://localhost:3000/school-community/learning/UUID.ttl"
}
```

### parental-view
Query learning activities for two children, returning a unified parental view with per-child summaries and negative-space gap detection.

```json
{
  "child_pod_1": "http://community-solid-server:3000/fatima-child-1/",
  "child_pod_2": "http://community-solid-server:3000/fatima-child-2/"
}
```

Both pod URIs must end with `/` (trailing slash enforced by handler). The query scopes to both pod namespaces using `FILTER(strstarts(str(?g), str(?childPod)))`.

The handler returns a `summary` object (not raw `results`) with:
- `children`: per-child activity summaries keyed by pod URI
- `gaps`: list of detected negative-space signals:
  - `attendance_discrepancy`: same activity with different session counts across children
  - `attended_no_outcome`: sessions marked attended with no `scaledScore` recorded
  - `below_60_marked_success`: activities scored below 60% but marked `success=True`

### transfer-profile
Query a student's complete learning profile across all contexts.

```json
{
  "student_uri": "http://localhost:3000/ayoub/profile/card#me"
}
```

## Output

The handler emits structured JSON log lines first, then a final result JSON:

**Success (single-pod templates):**
```json
{
  "status": "success",
  "summary": {"total_activities": 42, "verbs": {...}, "activities_by_object": {...}},
  "provenance": ["http://localhost:3000/ayoub/"],
  "result_count": 42
}
```

**Success (parental-view):**
```json
{
  "status": "success",
  "summary": {
    "children": [
      {"pod_uri": "http://community-solid-server:3000/fatima-child-1/", "total_activities": 24, "...": "..."},
      {"pod_uri": "http://community-solid-server:3000/fatima-child-2/", "total_activities": 18, "...": "..."}
    ],
    "gaps": [
      {"type": "attendance_discrepancy", "activity": "robotics-workshop", "counts_by_child": {"fatima-child-1": 18, "fatima-child-2": 15}},
      {"type": "one_sided_activity", "activity": "stem-club", "counts_by_child": {"fatima-child-1": 6}},
      {"type": "below_60_marked_success", "object": "math-assessment-fractions", "score": 0.55}
    ]
  },
  "provenance": ["http://community-solid-server:3000/fatima-child-1/", "http://community-solid-server:3000/fatima-child-2/"],
  "result_count": 42
}
```

**Access denied:**
```json
{
  "status": "denied",
  "reason": "Access denied to http://localhost:3000/ayoub/ (HTTP 403)",
  "agent": "troll-adversary",
  "requested_resources": ["http://localhost:3000/ayoub/"]
}
```

**Error:**
```json
{"status": "error", "error": "Template not found: unknown-template"}
```

## Enforcement

1. The skill validates the agent's WebID against the target Pod's ACL (CSS WebACL) **before** executing any SPARQL query.
2. Template parameterization uses `parameterize.py` — never string concatenation (SEC-3).
3. Every execution emits a structured JSON log entry to stdout.

## Dependencies

- Oxigraph at `OXIGRAPH_URL/query` (HTTP POST)
- CSS at `CSS_CONNECT_URL` with `Host: CSS_IDENTIFIER_HOST`
- `parameterize.py` (same directory)
- Templates in `templates/` directory
