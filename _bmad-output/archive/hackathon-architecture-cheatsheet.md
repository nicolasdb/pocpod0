# pocpod0 — Architecture Cheatsheet

_One-pager for hackathon participants. Full docs: `_bmad-output/planning-artifacts/architecture.md`_

---

## What is pocpod0?

Learning data is trapped in institutional silos. pocpod0 proves a new model: **learners own their data in personal Solid Pods**, and every authorized person (teacher, parent, admin, policy advisor) sees a coherent, complete picture through AI agents.

Built for the hardest case first: K-12 minors under EU privacy law (RGPD), Belgian multilingual education (NL/FR).

## Three-Layer Data Architecture

```
┌─────────────────────────────────────────────────┐
│  Pod Layer (CSS)          — Source of truth      │
│  Learner-owned Solid Pods with WebACL            │
│  Raw xAPI-as-RDF stored as Turtle resources      │
├─────────────────────────────────────────────────┤
│  Graph Layer (Oxigraph)   — Queryable index      │
│  OSLO-mapped RDF triples + provenance links      │
│  SPARQL endpoint on :7878                        │
├─────────────────────────────────────────────────┤
│  Vector Layer (Qdrant)    — Semantic index        │
│  Embeddings with triple/pod URI traceability     │
│  REST API on :6333                               │
└─────────────────────────────────────────────────┘
```

**Key principle:** Pod is source of truth. Oxigraph and Qdrant are rebuildable indexes. Deletion cascades: Pod → Oxigraph → Qdrant.

## Service Stack

| Service | Image | Port |
|---------|-------|------|
| CSS (Community Solid Server) | `communitysolidserver/community-solid-server:7` | 3000 |
| Oxigraph | `oxigraph/oxigraph:0.5.6` | 7878 |
| Qdrant | `qdrant/qdrant:v1.17.0` | 6333 |
| Nginx | `nginx:1.28.2-alpine` | 80 |

**LLM:** minimax/minimax-m2.5 via OpenRouter API (agents)
**Embeddings:** qwen/qwen3-embedding-8b via OpenRouter API
**Single secret:** `OPENROUTER_API_KEY` in `.env`

## Agent Architecture

```
Agent Layer (OpenClaw)
├── Shared SPARQL Skill   ← ACL check → parameterized .rq query → Oxigraph
├── Shared Qdrant Skill   ← Semantic similarity → Qdrant
├── Claire (teacher)      ← Cross-context queries, hybrid comparison
├── Marc (admin)          ← Transfer scenarios
├── Isabelle (policy)     ← Aggregate anonymized queries
├── Fatima (parent)       ← Unified parental view
├── Ayoub (student)       ← Sovereignty & lifecycle
└── Troll (adversary)     ← Dual access: through skills + direct to infra
```

**Hybrid query:** Agent calls SPARQL skill + Qdrant skill, merges results itself.

## Project Structure (What You Need to Know)

```
pocpod0/
├── agents/                    ← YOU WORK HERE
│   ├── openclaw.config.yaml   # OpenClaw config (already set up)
│   ├── skills/
│   │   ├── sparql-query/      # Shared SPARQL skill (already built)
│   │   │   └── templates/     # Parameterized .rq files
│   │   └── qdrant-search/     # Shared Qdrant skill (already built)
│   ├── claire-teacher/        # Agent configs to build/tune
│   ├── marc-admin/
│   ├── isabelle-policy/
│   ├── fatima-parent/
│   ├── ayoub-student/
│   └── troll-adversary/
│       └── attacks/           # Attack scripts to write/harden
├── data/
│   ├── schemas/               # OSLO vocabulary (reference)
│   ├── synthetic/             # 10K xAPI dataset (loaded)
│   └── queries/               # Reference SPARQL queries
├── infra/                     # DO NOT TOUCH — already configured
├── pipeline/                  # DO NOT TOUCH — already running
└── docker-compose.yml         # Already up
```

## Pod Setup (Pre-loaded)

| Pod | Owner | Roles with Access |
|-----|-------|-------------------|
| ayoub | Ayoub (student) | Claire (tutor), Fatima (parent), Marc (admin), Isabelle (regional) |
| claire-student-1 | Student | Claire (tutor) |
| claire-student-2 | Student | Claire (tutor) |
| fatima-child-1 | Student | Fatima (parent) |
| fatima-child-2 | Student | Fatima (parent) |
| school-community | School | Marc (admin, read/write) |

## Key Conventions

- **SPARQL templates:** `.rq` files with `$parameter` placeholders — never string concatenation
- **Agent IDs:** lowercase hyphen (`claire-teacher`, `troll-adversary`)
- **SPARQL variables:** `?camelCase` (`?studentName`, ?learningContext`)
- **Logging:** Structured JSON to stdout (captured by docker-compose)
- **Namespace prefixes:** `oslo-educ:`, `oslo-person:`, `xapi:`, `pocpod0:`
