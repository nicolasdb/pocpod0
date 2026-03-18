# Contributing to pocpod0

Thank you for your interest in contributing to pocpod0! This guide will help you get started with development.

## Development Workflow

### 1. Setup Development Environment

```bash
cp .env.example .env
# Edit .env if needed (especially VOLUME_FLAGS on Fedora)
docker-compose up
```

### 2. Make Changes

pocpod0 follows a **vertical slice** development model. Stories correspond to complete features that touch multiple layers:

- **Infrastructure Layer** (`infra/`): Docker configs, pod storage, reverse proxy
- **Pipeline Layer** (`pipeline/`): Data ingestion, transformation, schema validation
- **Agent Layer** (`agents/`): Multi-agent system and reasoning
- **Dashboard Layer** (`dashboard/`): Web UI and reporting
- **Data Layer** (`data/`): Schemas, synthetic data, example queries

**Important**: When implementing a feature, complete all layers for that story before moving to the next.

### 3. Testing

```bash
# Run all tests
pytest tests/ pipeline/tests/

# Run specific test file
pytest tests/integration/test_service_startup.py

# Run with verbose output
pytest -v tests/
```

### 4. Code Quality

- Follow naming conventions (see below)
- Keep functions small and focused
- Write clear docstrings for public APIs
- Add tests for new functionality

### 5. Commit & PR

- Create feature branches from `main`
- Write clear commit messages
- Reference story/issue numbers when applicable
- Ensure all tests pass before submitting PR

## Naming Conventions

### Docker & Infrastructure

- **Service names**: lowercase, hyphen-separated (e.g., `community-solid-server`, `oxigraph`)
- **Volume names**: `{service}-data` (e.g., `oxigraph-data`, `qdrant-data`)
- **Config files**: lowercase with hyphens (e.g., `nginx.conf`)
- **Directories**: lowercase with hyphens

### Python Code

- **Package names**: lowercase with underscores (e.g., `pocpod0_pipeline`)
- **Module files**: lowercase with underscores (e.g., `ingest_xapi.py`)
- **Class names**: PascalCase (e.g., `XAPIIngester`)
- **Function names**: snake_case (e.g., `parse_statement()`)
- **Constants**: UPPERCASE_WITH_UNDERSCORES (e.g., `MAX_BATCH_SIZE`)

### File & Directory Organization

```
infra/              # Infrastructure configs
├── css/            # Community Solid Server config
├── nginx/          # Nginx reverse proxy config
├── oxigraph/       # RDF store config
└── qdrant/         # Vector DB config

pipeline/           # Data pipeline
├── src/
│   └── pocpod0_pipeline/
│       ├── ingest.py           # Data ingestion
│       ├── transform.py        # Data transformation
│       └── schemas.py          # Schema definitions
└── tests/
    └── test_*.py              # Test files

agents/             # Multi-agent system
├── skills/                    # Shared agent skills
├── {role}-*/                  # Agent implementations
└── troll-adversary/           # Security testing agent

dashboard/          # Web UI
├── src/pocpod0_dashboard/
└── static/

tests/              # Integration & E2E tests
└── integration/

scripts/            # Operational scripts
```

## Architecture Guidelines

### Principle: Separation of Concerns

- **Infrastructure** handles deployment and networking
- **Pipeline** handles data validation and transformation
- **Agents** handle reasoning and decision-making
- **Dashboard** handles presentation and reporting

### Key Technologies

- **CSS 7**: Pod storage with WebACL for access control
- **Oxigraph 0.5.6**: RDF triple store (SPARQL endpoint)
- **Qdrant v1.17.0**: Vector database for semantic search
- **Nginx 1.28.2-alpine**: API gateway and content negotiation

## Git Workflow

### Branch Naming

- Feature branches: `feature/story-{number}` (e.g., `feature/story-1-1`)
- Bugfix branches: `fix/issue-{number}` (e.g., `fix/issue-42`)
- Main branch: `main` (protected)

### Commit Messages

Write clear, descriptive commit messages:

```
[STORY-1-1] Create project scaffold

- Add docker-compose.yml with all 4 services
- Create directory structure per architecture doc
- Add community standard files (README, LICENSE, etc)

Closes story 1.1
```

## Testing Guidelines

### Test Organization

```
tests/
├── integration/          # Service integration tests
│   ├── test_startup.py   # Service startup & health
│   └── test_acl.py       # Access control tests
└── conftest.py          # Shared fixtures
```

### Test Coverage

- **Unit Tests** (in `pipeline/tests/`): Core pipeline logic
- **Integration Tests** (in `tests/integration/`): Multi-service interactions
- **E2E Tests**: Full journey tests (added as needed)

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=pipeline --cov=tests

# Specific test
pytest tests/integration/test_startup.py::test_css_health_check
```

## Questions?

- Check the Architecture doc: `_bmad-output/planning-artifacts/architecture.md`
- Check the PRD: `_bmad-output/planning-artifacts/prd.md`
- Check existing stories and their implementation notes
- Refer to service documentation (CSS, Oxigraph, Qdrant, Nginx)

## References

- **Community Solid Server**: https://github.com/CommunitySolidServer/CommunitySolidServer
- **Oxigraph**: https://github.com/oxigraph/oxigraph
- **Qdrant**: https://github.com/qdrant/qdrant
- **OSLO Vocabulary**: https://semiceu.github.io/OSLO/
