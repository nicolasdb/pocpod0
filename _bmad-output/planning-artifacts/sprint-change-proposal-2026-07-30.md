# Sprint Change Proposal — 2026-07-30

**Trigger:** Handoff from a Claude-chat planning session — `MISSION_BRIEF_solid-mcp-connector.md` — for a self-hosted MCP connector letting Claude.ai (and any MCP client) read/write pods and inspect WAC permissions on `pod.nicolasdb.eu`.

## 1. Issue Summary

HyperScope is migrating its own internal knowledge infra (Git + Obsidian) to Solid pods on the same CSS instance the pilot already runs on. The brief's "walking the talk" principle: HyperScope uses its own tools internally before offering them to Singelijn or wider partners. A Node.js toolkit (`solid-pod-agent.zip`, unzipped into `mcp-connector/`) is provided: `auth.js`, `podClient.js`, `wacManager.js`, `onboarding.js`, `whoami.js`, `mcp-server.js` (stdio transport). Validated offline only — never run against a real pod.

Verified in the planning session: claude.ai's code-execution sandbox cannot reach `pod.nicolasdb.eu` (network allowlist blocks it), so a Skill is not viable — a remote MCP connector calling from Anthropic's infrastructure to a public VPS URL is the only path for a live link from claude.ai.

## 2. Impact Analysis

- **Epic impact:** No existing epic covers this. Not Epic 7 (pod-owner backoffice UI product for pilot users) and not Epic 4 (parked, Marc/Discord transfer capstone) — this is HyperScope's own ops tooling, a different codebase (Node MCP server, not the `backoffice/` static app). New **Epic 8: Solid MCP Connector** created.
- **Story impact:** Six new stories (8.1-8.6), sharded from the brief's T1-T7 tasks (T2 — per-request header auth — confirmed unavailable on Claude Pro, folded into 8.1 context as a documented non-goal rather than its own story).
- **Artifact conflicts:** None. `mcp-connector/` is a new top-level dir, no changes to `backoffice/`, `pipeline/`, or `infra/` beyond a new systemd unit + reverse-proxy vhost (Story 8.4).
- **Technical impact / reuse:** on inspection, `wacManager.js` already uses Inrupt's WAC-*specific* low-level calls (`createAcl`, `setAgentResourceAccess`, `saveAclFor`) — not the auto-detecting `universalAccess` API the brief's annex warns about, and not what `backoffice/pod-api.js` had before Story 7.3 fixed it. Its comments already document several of the exact pitfalls Story 7.3 hit independently (orphaned ACL, `getAgentAccessAll` argument shape, `createAclFromFallbackAcl` return type). So this is not a known-broken dependency to blindly replace. It is, however, **never been run against a real pod**, and Story 7.3 found that even careful-looking Inrupt ACL code silently produced ineffective `.acl` writes (missing `acl:default` on containers, wrong `accessTo` target) that only surfaced under live out-of-app verification — the failure mode wasn't obvious from reading the code. Story 8.1 is therefore a live-verification-first story: exercise Inrupt's WAC-specific writer against the same bug patterns Story 7.3 found, using the same out-of-app method (independent anonymous/second-WebID `fetch`, re-`GET` the raw `.acl`). If it reproduces those bugs, fall back to porting Story 7.3's hand-rolled Turtle read/write from `backoffice/pod-api.js`; if it doesn't, keep the simpler Inrupt calls and lock the verified behavior in with a regression check.
- **Security constraints carried in from the brief (non-negotiable, not to be simplified away):** two-token model — OWNER (`hyperscope_ndb`) only for one-time onboarding, never deployed/committed; AGENT (`nicolas_claude`) is the runtime identity and can never self-grant since it never holds `acl:Control` on a data pod. One CSS account per person (no shared account across pods). `solid_grant_access` / `solid_revoke_access` / `setPublicAccess` MCP tools must be annotated destructive so the client requires explicit approval.

## 3. Recommended Approach

**Direct Adjustment** — additive epic, no rollback, no MVP change to the pilot PRD.

- Effort: 8.1 small (refactor against known-good reference code). 8.2-8.3 small (transport + routing). 8.4-8.5 medium (deploy + live verification, first real network calls this toolkit has ever made). 8.6 small (doc).
- Risk: low to the pilot — entirely new surface, no shared runtime with `backoffice/`/`pipeline/`. Main risk is scoped to Epic 8 itself: a live WAC/CSS bug during 8.5 verification (mitigated by 8.1 landing first).
- Timeline: independent of Epic 4/7 sequencing — different codebase, can run in parallel with Epic 7's remaining stories (7.5, 7.6).

## 4. Detailed Change Proposals

### 4a. epics.md — Epic List section, append after Epic 7 entry

```
### Epic 8: Solid MCP Connector _(ADDED 2026-07-30 — Quest B handoff, MISSION_BRIEF_solid-mcp-connector.md)_
A self-hosted MCP server lets Claude.ai (or any MCP client) read/write pod resources and inspect WAC permissions on `pod.nicolasdb.eu`, scoped per-person to each team member's own AGENT WebID — HyperScope using its own pod tooling internally before offering it to Singelijn/partners.
**Origin:** Claude-chat planning handoff, `solid-pod-agent.zip` toolkit (validated offline, never run against a real pod).
**Relationship:** Independent of Epic 7 (pod-owner backoffice UI) and Epic 4 (parked pilot capstone) — different codebase (Node MCP server), same CSS instance and WAC model. Story 8.1 ports Story 7.3's hand-rolled ACL Turtle logic rather than trusting the toolkit's untested Inrupt-based `wacManager.js`.
**Non-negotiables:** two-token model (OWNER never deployed, AGENT is runtime identity, agent never self-grants), one CSS account per person, grants always container-scoped with `scope: 'both'`, permission-writing tools require explicit human approval.
**Dashboard backlog:** none (server-side connector, no UI of its own)
```

### 4b. sprint-status.yaml — development_status, append after epic-7 block

```yaml
  # Epic 8: Solid MCP Connector (ADDED 2026-07-30 — Quest B handoff, MISSION_BRIEF_solid-mcp-connector.md)
  # Independent of Epic 7/4 — new mcp-connector/ Node service, not a backoffice/pipeline change.
  # Story 8.1 must land before 8.5 (live verification) — ports Story 7.3's ACL Turtle fix into
  # wacManager.js instead of trusting the toolkit's untested Inrupt universal-access calls.
  epic-8: backlog
  story-8-1-wac-turtle-port: ready-for-dev
  story-8-2-http-transport: backlog
  story-8-3-per-person-endpoints: backlog
  story-8-4-vps-deploy-hardening: backlog
  story-8-5-live-verification: backlog
  story-8-6-team-onboarding-doc: backlog
  epic-8-retrospective: optional
```

### 4c. Repo — import toolkit

Unzip `solid-pod-agent.zip` into `mcp-connector/` (tracked), keep `README.md`/`SKILL.md`/`references/architecture-and-checklist.md` beside it. Zip stays in `_bmad-output/planning-artifacts/` as the original handoff artifact.

## 5. Implementation Handoff

- **Scope:** Minor-to-Moderate (backlog addition, no replan of the pilot PRD).
- **Route:** SM (`bmad-create-story` for 8.1 when ready) → dev team.
- **Success criteria:** matches the brief's own Definition of Done — a team member on Claude Pro adds the connector, authenticates with their own AGENT token, lists/reads/writes only within their WAC grants, views WAC permissions, and any out-of-scope attempt fails cleanly.
