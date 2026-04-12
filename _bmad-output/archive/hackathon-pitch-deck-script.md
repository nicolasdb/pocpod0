# pocpod0 Hackathon — Pitch Deck Script

_5-minute pitch for hackathon opening. Adapt to audience._

---

## Slide 1: The Problem (1 min)

**"Every school in Belgium is a data island."**

Claire teaches 120 students. Three are failing math. One attends publicly-funded tutoring where they're actually thriving — but Claire can't see that. She's on Smartschool. The tutor is on a different system. The after-school robotics workshop? Yet another silo.

When a student transfers from a Flemish to a French-speaking school — and in Brussels, this happens constantly — their learning history starts from zero. Parents juggle two platforms for two children in two school systems. Regional policy advisors justify million-euro program budgets with self-reported PDFs.

All of this involves children's personal data, under the strictest privacy regulations in the world.

## Slide 2: The Architecture (1 min)

**"What if the learner owned the data?"**

Three layers:
- **The Passport** — a Solid Pod. Yours. Portable. You control who sees it.
- **The Encyclopedia** — a knowledge graph that connects learning events across institutions.
- **The Memory** — a semantic layer that understands *meaning*, not just structure.

AI agents stand in for each user role — teacher, parent, admin, policy advisor. They query across the silos. An adversarial "troll" agent attacks the system and honestly reports where defenses hold and where they don't.

_[Show the architecture diagram from the cheatsheet]_

## Slide 3: What's Built (30 sec)

**"The infrastructure is done. The data is loaded. We need agents."**

- Docker-compose stack running: CSS + Oxigraph + Qdrant
- 6 pods provisioned with role-based access controls
- 10K synthetic xAPI statements ingested as OSLO-mapped RDF
- Full provenance traceability: embedding → triple → pod resource
- Shared SPARQL + Qdrant skills ready for agents to call
- Troll has already validated: ACL enforcement passes, injection blocked, vector privacy assessed

## Slide 4: What We Build Today (1 min)

**"Each of you becomes an agent."**

| Task | You Build | The Scenario |
|------|-----------|-------------|
| **Claire** | Teacher agent + cross-context queries | "Show me which students struggle across ALL contexts" — the aha moment |
| **Fatima** | Parent agent + unified view | One view, two children, two schools, two languages |
| **Isabelle** | Policy agent + anonymized aggregates | "What's the STEM program impact?" — currently unanswerable in Belgium |
| **Troll** | Cross-inference attack scripts | Try to trick agents into leaking unauthorized data |

Each task is self-contained: an `agent.yaml` to configure, SPARQL templates to write, acceptance criteria to test against. The infrastructure is your playground — you build the intelligence on top.

## Slide 5: Why This Matters (30 sec)

**"This PoC targets EU funding and a pilot partnership."**

- Aligned with Athumi (Flemish government data infrastructure)
- Built for RGPD compliance with minors — the hardest case in Europe
- Your code ships in a real PoC shown to funders
- If the architecture holds, it changes how learning data works in Belgium — and beyond

**Let's build.**
