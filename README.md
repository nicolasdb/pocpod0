# pocpod0

A multi-agent, multi-pod data intelligence platform for learning data sovereignity and semantic reasoning across educational contexts.

## Quick Start

### Prerequisites

- Docker or Podman
- Git
- 2GB free disk space (for service data volumes)

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd pocpod0
   ```

2. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```

   If you're on **Fedora with SELinux**, update `.env`:
   ```bash
   VOLUME_FLAGS=:Z
   ```

   On **Ubuntu or other systems without SELinux**, leave `VOLUME_FLAGS` empty.

3. Start all services:
   ```bash
   docker-compose up
   ```

   Or if using Podman (especially in distrobox):
   ```bash
   distrobox-host-exec podman compose up
   ```

All services will start and health checks will pass within 60 seconds.

## Architecture Overview

pocpod0 implements a three-layer data architecture:

- **Pod Layer**: Community Solid Server (CSS) for decentralized pod storage with fine-grained access control
- **Semantic Layer**: Oxigraph for RDF triple storage with provenance tracking
- **Vector Layer**: Qdrant for semantic search via embeddings
- **API Gateway**: Nginx for content negotiation and request routing

## Project Structure

```
pocpod0/
├── infra/              # Infrastructure configs (Docker, CSS, Nginx, Oxigraph, Qdrant)
├── pipeline/           # Data ingestion and processing (Python)
├── agents/             # Multi-agent system (Claude-based agents)
├── dashboard/          # Web dashboard (Flask/web frontend)
├── data/               # Synthetic data, schemas, example queries
├── scripts/            # Setup and operational scripts
├── tests/              # Integration and end-to-end tests
├── docker-compose.yml  # Service orchestration
└── .env.example        # Environment configuration template
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Community Solid Server (CSS) | 3000 | Pod storage & access control |
| Oxigraph | 7878 | RDF triple store |
| Qdrant | 6333 (REST), 6334 (gRPC) | Vector embeddings & semantic search |
| Nginx | 80, 443 | API gateway & content negotiation |

## Configuration

See `.env.example` for all available configuration options:
- `OPENROUTER_API_KEY`: External LLM API key (Claude)
- `VOLUME_FLAGS`: SELinux volume mounting (`:Z` on Fedora, empty on Ubuntu)
- Service ports (customizable)

## Running the Pipeline

```bash
# Full run (appends to existing data)
python pipeline/run_pipeline.py

# Full run with live TUI dashboard (single terminal)
python pipeline/run_pipeline.py --with-dashboard

# Wipe all data first, then rebuild from scratch
python pipeline/run_pipeline.py --wipe --with-dashboard

# Dry run — test the dashboard without touching any data (~8s)
python pipeline/run_pipeline.py --dry-run --with-dashboard
```

Pipeline Python-level stdout is saved to `data/pipeline.log` when `--with-dashboard` is used. Stage subprocess output still appears in the terminal.

> ⚠️ `--wipe` permanently deletes all CSS pod data, Oxigraph triples, and Qdrant embeddings before rebuilding. Takes ~10 minutes.

## Development Workflow

1. Make changes in code directories (`pipeline/`, `agents/`, `dashboard/`)
2. Run tests: `pytest tests/ pipeline/tests/`
3. Check Docker logs: `docker-compose logs -f <service>`
4. See `CONTRIBUTING.md` for coding standards and naming conventions

## Testing

```bash
# Run integration tests
pytest tests/integration/

# Run pipeline unit tests
pytest pipeline/tests/

# View service logs
docker-compose logs -f community-solid-server
docker-compose logs -f oxigraph
docker-compose logs -f qdrant
docker-compose logs -f nginx
```

## License

See LICENSE file for licensing details.

## Code of Conduct

See CODE_OF_CONDUCT.md for community guidelines.

## Contributing

See CONTRIBUTING.md for contribution guidelines and development practices.
