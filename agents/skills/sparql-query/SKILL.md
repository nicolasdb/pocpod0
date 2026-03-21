---
name: sparql-query
description: ACL-validated SPARQL queries against Oxigraph. Validates the calling agent's role identity against CSS Pod ACLs before executing parameterized .rq templates. Returns results with named-graph provenance metadata.
---

# SPARQL Query Skill

This skill executes parameterized SPARQL queries against the Oxigraph triple store
(`http://oxigraph:7878/query`) with ACL enforcement at the Pod level.

## Usage

When an agent needs to query structured learning data, invoke this skill with:
- `acl_role`: the agent's role identity (tutor, admin, regional, parental, student)
- `webid`: the agent's WebID URI
- `template`: the query template name (student-progress, cross-context-query, aggregate-anonymized, parental-view, transfer-profile)
- `params`: template parameters (e.g. studentPodUri, subject)

## Enforcement

The skill validates the agent's role against the target Pod's ACL before executing.
If access is denied, it returns a structured denial response and logs the attempt.

## Implementation

Handler: `{baseDir}/handler.py`
Templates: `{baseDir}/templates/`
