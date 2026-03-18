# pocpod0 Hackathon — Event Plan

## Event Overview

**Project:** pocpod0 — Decentralized learning data architecture where learners own their data
**Duration:** 6 hours
**Goal:** Accelerate Epic 3 (Cross-Context Learning Insights) by parallelizing agent development and adversarial testing across participants

## Why This Hackathon Matters

pocpod0 proves that learners — not institutions — can own their learning data. The architecture (Solid Pods + semantic graph + vector search) is built and loaded with data. Now we need **AI agents that exercise it** — asking questions across institutional silos, comparing structured vs. semantic results, and stress-testing the security boundaries.

This is where fresh eyes add the most value:
- Each agent persona is **independent work** — perfect for parallel development
- Agent configuration is **self-contained** — an `agent.yaml` + SPARQL templates + acceptance criteria
- Stress-testing the troll attack surface benefits from **adversarial creativity** you can't get solo

## What's Already Done (Epics 1-2 + Stories 3.1-3.2)

Participants clone a repo where everything is running:

| Layer | Status | What It Does |
|-------|--------|-------------|
| Infrastructure | Running | CSS, Oxigraph, Qdrant, Nginx via docker-compose |
| Pods | Provisioned | 5 learner pods + 1 school pod with ACLs configured |
| Data Pipeline | Complete | 10K xAPI statements ingested as OSLO-mapped RDF |
| Graph Layer | Loaded | Oxigraph with provenance-linked triples |
| Vector Layer | Loaded | Qdrant with bidirectional traceability metadata |
| Agent Runtime | Ready | OpenClaw configured with OpenRouter API |
| Shared Skills | Built | SPARQL skill (ACL-enforced, parameterized) + Qdrant skill |
| Troll Foundation | Validated | ACL enforcement + SPARQL injection + vector privacy tests pass |

**You don't touch infra or pipeline. You build agents and attack scripts.**

## Schedule

| Time | Activity | Details |
|------|----------|---------|
| **0:00 - 0:30** | Setup | Clone repo, `docker-compose up`, verify services healthy |
| **0:30 - 1:00** | Architecture Briefing | Walk through cheatsheet, demo the shared SPARQL/Qdrant skills, show a sample query |
| **1:00 - 1:15** | Task Assignment | Each participant picks a task card |
| **1:15 - 3:15** | Sprint 1 | Build agent configs, write SPARQL templates, test against acceptance criteria |
| **3:15 - 3:30** | Mid-point Check-in | Quick round — blockers, discoveries, pivots |
| **3:30 - 5:00** | Sprint 2 | Finish tasks, integration testing, cross-agent queries |
| **5:00 - 5:30** | Demo & Integration | Run all agents together, show results, run troll attacks |
| **5:30 - 6:00** | Retro & Findings | What worked, what broke, what surprised us |

## Participant Prerequisites

- Docker + docker-compose installed
- Git
- Basic understanding of: RDF/SPARQL (will brief), YAML configuration, Python (for troll scripts)
- OpenRouter API key (provided at event or use shared key)

## What Participants Take Away

- Hands-on experience with Solid Pods, semantic web, and AI agent orchestration
- Understanding of decentralized data architecture for education
- Their contributions merged into a real PoC targeting EU funding
