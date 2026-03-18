# Story 1.1: Project Scaffold & Service Orchestration

Status: ready-for-dev

## Story

As a **developer**,
I want a single `docker-compose up` command that starts all infrastructure services with health checks and dependency ordering,
so that I have a reproducible, portable development environment from the first commit.

## Acceptance Criteria

**AC-1: Service startup with pinned versions**
Given a fresh clone of the repository with `.env` configured
When I run `docker-compose up`
Then CSS, Oxigraph, Qdrant, and Nginx containers start with pinned versions (CSS 7, Oxigraph 0.5.6, Qdrant v1.17.0, Nginx 1.28.2-alpine)
And all services report healthy within 60s
And `depends_on: condition: service_healthy` enforces startup order

**AC-2: Host portability (SELinux / Ubuntu)**
Given the repository is cloned on Fedora (SELinux) or Ubuntu
When `VOLUME_FLAGS` is set to `:Z` (Fedora) or empty (Ubuntu) in `.env`
Then bind mounts for persistent data work correctly on both hosts

**AC-3: Repository scaffold and community standards**
Given the project root
When I inspect the repository
Then README.md, LICENSE, CODE_OF_CONDUCT.md, CONTRIBUTING.md, and `.env.example` exist
And the project directory structure matches the Architecture doc scaffold (`infra/`, `pipeline/`, `agents/`, `dashboard/`, `scripts/`, `data/`, `tests/`)

## Tasks / Subtasks

### Task 1: Create project directory structure (AC-3)
- [ ] Create the full directory tree as specified in the architecture doc:
  ```
  pocpod0/
  ├── infra/
  │   ├── css/
  │   │   ├── pods/
  │   │   │   ├── ayoub/
  │   │   │   ├── claire-student-1/
  │   │   │   ├── claire-student-2/
  │   │   │   ├── fatima-child-1/
  │   │   │   ├── fatima-child-2/
  │   │   │   └── school-community/
  │   ├── nginx/
  │   │   └── ssl/
  │   ├── oxigraph/
  │   └── qdrant/
  ├── pipeline/
  │   ├── src/
  │   │   └── pocpod0_pipeline/
  │   └── tests/
  ├── agents/
  │   ├── skills/
  │   │   ├── sparql-query/
  │   │   │   └── templates/
  │   │   └── qdrant-search/
  │   ├── claire-teacher/
  │   ├── marc-admin/
  │   ├── isabelle-policy/
  │   ├── fatima-parent/
  │   ├── ayoub-student/
  │   └── troll-adversary/
  │       ├── attacks/
  │       └── report/
  ├── dashboard/
  │   ├── src/
  │   │   └── pocpod0_dashboard/
  │   │       └── templates/
  │   └── static/
  ├── data/
  │   ├── synthetic/
  │   ├── schemas/
  │   └── queries/
  │       └── examples/
  ├── scripts/
  └── tests/
      └── integration/
  ```
- [ ] Add `.gitkeep` files to empty directories so they are tracked by git

### Task 2: Create community standard files (AC-3)
- [ ] Create `README.md` with project overview, setup instructions (`docker-compose up`), prerequisites, and `.env` configuration guidance
- [ ] Create `LICENSE` (choose license compatible with OSLO vocabulary's ISA Open Metadata Licence v1.1 -- note this needs legal review, use a placeholder comment)
- [ ] Create `CODE_OF_CONDUCT.md`
- [ ] Create `CONTRIBUTING.md` with development workflow, naming conventions, and architecture reference

### Task 3: Create `.env.example` and `.gitignore` (AC-2)
- [ ] Create `.env.example` with all documented variables:
  ```
  # OpenRouter API key (the only external secret)
  OPENROUTER_API_KEY=your-key-here

  # Volume mount flags: set to ":Z" on Fedora/SELinux, leave empty on Ubuntu
  VOLUME_FLAGS=

  # CSS base URL
  CSS_BASE_URL=http://localhost:3000

  # Service ports
  CSS_PORT=3000
  OXIGRAPH_PORT=7878
  QDRANT_REST_PORT=6333
  QDRANT_GRPC_PORT=6334
  NGINX_HTTP_PORT=80
  NGINX_HTTPS_PORT=443
  ```
- [ ] Create `.gitignore` that excludes `.env`, `__pycache__`, `.venv`, `*.pyc`, Docker volumes data, IDE files

### Task 4: Create `docker-compose.yml` with all 4 services (AC-1, AC-2)
- [ ] Define `community-solid-server` service:
  - Image: `communitysolidserver/community-solid-server:7`
  - Port: `${CSS_PORT:-3000}:3000`
  - Volume: `./infra/css:/config${VOLUME_FLAGS:-}` (config mount)
  - Volume: `css-pods:/data${VOLUME_FLAGS:-}` (pod data — use named volume or bind mount `./infra/css/pods`)
  - Health check: `wget --spider --quiet http://localhost:3000/.well-known/solid || exit 1` (or equivalent — CSS 7 exposes this endpoint)
  - Health check interval: 5s, timeout: 5s, retries: 12 (60s total)
- [ ] Define `oxigraph` service:
  - Image: `oxigraph/oxigraph:0.5.6`
  - Port: `${OXIGRAPH_PORT:-7878}:7878`
  - Volume: `oxigraph-data:/data${VOLUME_FLAGS:-}`
  - Command: `serve --location /data --bind 0.0.0.0:7878`
  - Health check: `wget --spider --quiet http://localhost:7878/ready || exit 1` (verify actual Oxigraph 0.5.6 health endpoint)
  - Health check interval: 5s, timeout: 5s, retries: 12
- [ ] Define `qdrant` service:
  - Image: `qdrant/qdrant:v1.17.0`
  - Ports: `${QDRANT_REST_PORT:-6333}:6333`, `${QDRANT_GRPC_PORT:-6334}:6334`
  - Volume: `qdrant-data:/qdrant/storage${VOLUME_FLAGS:-}`
  - Health check: `wget --spider --quiet http://localhost:6333/readyz || exit 1` (verify actual Qdrant health endpoint)
  - Health check interval: 5s, timeout: 5s, retries: 12
- [ ] Define `nginx` service:
  - Image: `nginx:1.28.2-alpine`
  - Ports: `${NGINX_HTTP_PORT:-80}:80`, `${NGINX_HTTPS_PORT:-443}:443`
  - Volume: `./infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro${VOLUME_FLAGS:-}`
  - Depends on: `community-solid-server` (condition: `service_healthy`)
  - Health check: `wget --spider --quiet http://localhost:80/ || exit 1`
  - Health check interval: 5s, timeout: 5s, retries: 12
- [ ] Set `depends_on` relationships:
  - Nginx depends on CSS (healthy)
  - All other services start independently (no cross-dependencies at this stage)
- [ ] Use default Docker network (do NOT define a custom network)

### Task 5: Create minimal Nginx config (AC-1)
- [ ] Create `infra/nginx/nginx.conf` — a minimal reverse proxy config that proxies to CSS on port 3000
  - Upstream: `community-solid-server:3000`
  - Server block listening on port 80
  - `proxy_pass` to upstream
  - Pass through `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` headers
  - This is a placeholder — Story 1.2 will add content negotiation logic

### Task 6: Create minimal CSS config (AC-1)
- [ ] Create `infra/css/config.json` — CSS 7 server configuration
  - Configure filesystem-based pod storage
  - Set base URL from environment or default to `http://localhost:3000`
  - Enable WebACL support
  - Note: CSS 7 configuration format — refer to CSS 7 documentation for exact config schema

### Task 7: Create placeholder configs for Oxigraph and Qdrant (AC-1)
- [ ] Create `infra/oxigraph/config.toml` if Oxigraph 0.5.6 supports external config (may not be needed — command-line args may suffice)
- [ ] Create `infra/qdrant/config.yaml` — Qdrant collection configuration placeholder

### Task 8: Create pipeline Python package stub (AC-3)
- [ ] Create `pipeline/pyproject.toml` with:
  - Project name: `pocpod0-pipeline`
  - Python >= 3.12
  - Dependencies placeholder (to be filled in later stories)
  - Dev dependencies: `pytest`
- [ ] Create `pipeline/src/pocpod0_pipeline/__init__.py` (empty)
- [ ] Create `pipeline/tests/conftest.py` (empty placeholder)

### Task 9: Verify startup and health checks (AC-1, AC-2)
- [ ] Run `docker-compose up` and confirm all 4 services start
- [ ] Verify health checks pass within 60s (NFR4)
- [ ] Verify `depends_on` ordering works (Nginx waits for CSS)
- [ ] Test on available host with appropriate `VOLUME_FLAGS` setting
- [ ] Use `distrobox-host-exec podman` or `distrobox-host-exec docker` if running inside a distrobox environment

### Task 10: Create setup script (AC-3)
- [ ] Create `scripts/setup.sh` — first-time setup script:
  - Check Docker/Podman is available
  - Check `.env` exists (copy from `.env.example` if not)
  - Create data directories if needed
  - Print environment summary

## Dev Notes

### Docker Image Versions (PINNED - NFR18)

| Service | Image | Tag | Port(s) |
|---------|-------|-----|---------|
| CSS | `communitysolidserver/community-solid-server` | `7` | 3000 |
| Oxigraph | `oxigraph/oxigraph` | `0.5.6` | 7878 |
| Qdrant | `qdrant/qdrant` | `v1.17.0` | 6333 (REST), 6334 (gRPC) |
| Nginx | `nginx` | `1.28.2-alpine` | 80, 443 |

**NEVER use `latest` tag.** All images must be pinned to these exact versions.

### Health Check Requirements (NFR4)

All services must be healthy within 60 seconds of `docker-compose up`. Use `healthcheck` directives with `depends_on: condition: service_healthy` for dependency ordering.

Recommended health check settings per service:
- `interval: 5s`
- `timeout: 5s`
- `retries: 12`
- `start_period: 10s` (gives containers time to initialize)

### SELinux Volume Handling (NFR14)

The `.env` file contains `VOLUME_FLAGS` which should be:
- `:Z` on Fedora with SELinux (relabels volume for container access)
- Empty string on Ubuntu/non-SELinux hosts

Use interpolation in docker-compose volume definitions: `./path:/container/path${VOLUME_FLAGS:-}`

### Naming Conventions

- **Docker service names:** lowercase, hyphen-separated (`community-solid-server`, `oxigraph`, `qdrant`, `nginx`)
- **Volume names:** `{service}-data` (e.g., `oxigraph-data`, `qdrant-data`, `css-pods`)
- **File naming:** all lowercase, hyphen-separated for configs, snake_case for Python
- **Python package:** `pocpod0_pipeline` (underscore, not hyphen)

### Distrobox Isolation Note

When developing inside a distrobox environment, use `distrobox-host-exec` to access podman/docker containers on the host. Example:
```bash
distrobox-host-exec podman compose up
distrobox-host-exec podman ps
```
This is because Docker/Podman runs on the host, not inside the distrobox container.

### CSS 7 Configuration

Community Solid Server version 7 uses a JSON-LD configuration system. Key points:
- Pod storage: filesystem-based (bind-mounted directory)
- WebACL: must be enabled in config for ACL enforcement
- Base URL: configurable via environment or config
- The exact config schema should be verified against CSS 7 documentation — it changed significantly from earlier versions

### Network Configuration

Use the default Docker network. Services communicate via container names:
- `community-solid-server:3000`
- `oxigraph:7878`
- `qdrant:6333` (REST) / `qdrant:6334` (gRPC)
- `nginx:80`

Do NOT define a custom network in docker-compose.yml.

### Project Structure Notes

The following directories and files need to be **created** in this story:

**Root level:**
- `docker-compose.yml`
- `.env.example`
- `.gitignore`
- `README.md`
- `LICENSE`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`

**Infrastructure configs:**
- `infra/css/config.json`
- `infra/css/pods/` (subdirectories: `ayoub/`, `claire-student-1/`, `claire-student-2/`, `fatima-child-1/`, `fatima-child-2/`, `school-community/`)
- `infra/nginx/nginx.conf`
- `infra/nginx/ssl/` (empty, for future use)
- `infra/oxigraph/config.toml` (if needed)
- `infra/qdrant/config.yaml`

**Pipeline stub:**
- `pipeline/pyproject.toml`
- `pipeline/src/pocpod0_pipeline/__init__.py`
- `pipeline/tests/conftest.py`

**Scripts:**
- `scripts/setup.sh`

**Empty directories with `.gitkeep`:**
- `agents/skills/sparql-query/templates/`
- `agents/skills/qdrant-search/`
- `agents/claire-teacher/`
- `agents/marc-admin/`
- `agents/isabelle-policy/`
- `agents/fatima-parent/`
- `agents/ayoub-student/`
- `agents/troll-adversary/attacks/`
- `agents/troll-adversary/report/`
- `dashboard/src/pocpod0_dashboard/templates/`
- `dashboard/static/`
- `data/synthetic/`
- `data/schemas/`
- `data/queries/examples/`
- `tests/integration/`

### References

- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` (sections: INFRA-1, INFRA-2, INFRA-3, Project Structure, Naming Patterns)
- PRD: `_bmad-output/planning-artifacts/prd.md` (sections: Infrastructure Model, Deployment & Portability, NFR4, NFR14, NFR15, NFR18, NFR19)
- Epics doc: `_bmad-output/planning-artifacts/epics.md` (Story 1.1 acceptance criteria)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (key: `story-1-1-project-scaffold-service-orchestration`)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
