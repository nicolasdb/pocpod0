# Story 1.3: Pod Provisioning & ACL Configuration

Status: ready-for-dev

## Story

As a **learner persona** (Ayoub, Claire's students, Fatima's children),
I want my own Solid Pod provisioned with role-based access controls,
so that my learning data is stored under my exclusive control with appropriate access granted to authorized roles.

## Acceptance Criteria

**AC-1: Pod provisioning**
Given CSS is running and healthy
When the provisioning script (`scripts/seed-pods.sh`) executes
Then 5 individual pods are created (Ayoub, Claire-student-1, Claire-student-2, Fatima-child-1, Fatima-child-2)
And 1 community pod is created (school-community)

**AC-2: ACL configuration per role**
Given pods are provisioned
When ACL configuration is applied
Then each pod has WebACL resources (`.acl` files) granting access per role:
- Tutor (Claire): read access to her students' pods
- Parent (Fatima): read access to her children's pods
- Admin (Marc): read/write on school-community pod, read on student pods
- Regional (Isabelle): aggregate read access
- Student (Ayoub): full control of own pod

**AC-3: Authorized access succeeds**
Given a provisioned pod with ACLs
When an authorized role accesses a pod resource
Then the response is returned successfully

**AC-4: Unauthorized access denied**
Given a provisioned pod with ACLs
When an unauthorized role accesses a pod resource
Then the request is denied (HTTP 403)

## Tasks / Subtasks

### Task 1: Create the provisioning Python module (AC-1)
- [ ] Create `pipeline/src/pocpod0_pipeline/provision_pods.py` with functions to:
  - Create a pod on CSS via its HTTP API
  - Accept pod name and owner identity as parameters
  - Return the pod's base URL after creation
  - Handle error cases (pod already exists, CSS unreachable)
- [ ] The module must use the CSS base URL from environment (`CSS_BASE_URL`) — this will be either `http://localhost` (Nginx path) or `http://localhost:3000` (direct CSS path), depending on Story 1.2 outcome
- [ ] When running inside Docker network, use `http://community-solid-server:3000` as the internal URL
- [ ] Add `requests` (or `httpx`) to `pipeline/pyproject.toml` dependencies

### Task 2: Define pod and persona configuration (AC-1, AC-2)
- [ ] Create a configuration structure (e.g., `infra/css/pods/pod-config.yaml` or within the Python module) defining:

  **Individual Pods (5):**
  | Pod Name | Owner | Description |
  |----------|-------|-------------|
  | `ayoub` | Ayoub (student) | Ayoub's personal learning pod |
  | `claire-student-1` | Student 1 | Claire's first student |
  | `claire-student-2` | Student 2 | Claire's second student |
  | `fatima-child-1` | Child 1 | Fatima's first child |
  | `fatima-child-2` | Child 2 | Fatima's second child |

  **Community Pod (1):**
  | Pod Name | Owner | Description |
  |----------|-------|-------------|
  | `school-community` | School (Marc admin) | Shared school community pod |

### Task 3: Define agent identities (AC-2, AC-3, AC-4)
- [ ] Create agent identity configuration (no real authentication per SEC-1). Each agent has a configured WebID-like URI:
  | Agent | Role | WebID URI (simulated) |
  |-------|------|----------------------|
  | Claire | Tutor | `http://localhost:3000/claire/profile/card#me` |
  | Fatima | Parent | `http://localhost:3000/fatima/profile/card#me` |
  | Marc | Admin | `http://localhost:3000/marc/profile/card#me` |
  | Isabelle | Regional | `http://localhost:3000/isabelle/profile/card#me` |
  | Ayoub | Student | `http://localhost:3000/ayoub/profile/card#me` |
  | Troll | Adversary | `http://localhost:3000/troll/profile/card#me` |

  Note: These are simulated identities. There is no real Solid-OIDC authentication in the PoC (SEC-1). The ACL enforcement is based on CSS's WebACL mechanism with configured agent tokens/identities.

### Task 4: Create WebACL `.acl` files (AC-2)
- [ ] Create `.acl` template files for each pod in `infra/css/pods/{pod-name}/`:

  **`ayoub/.acl`** — Ayoub's pod root ACL:
  ```turtle
  @prefix acl: <http://www.w3.org/ns/auth/acl#>.
  @prefix foaf: <http://xmlns.com/foaf/0.1/>.

  # Ayoub has full control of his own pod
  <#owner>
      a acl:Authorization;
      acl:agent <http://localhost:3000/ayoub/profile/card#me>;
      acl:accessTo <./>;
      acl:default <./>;
      acl:mode acl:Read, acl:Write, acl:Control.

  # Claire (tutor) has read access
  <#tutor>
      a acl:Authorization;
      acl:agent <http://localhost:3000/claire/profile/card#me>;
      acl:accessTo <./>;
      acl:default <./>;
      acl:mode acl:Read.

  # Marc (admin) has read access
  <#admin>
      a acl:Authorization;
      acl:agent <http://localhost:3000/marc/profile/card#me>;
      acl:accessTo <./>;
      acl:default <./>;
      acl:mode acl:Read.

  # Isabelle (regional) has read access (aggregate)
  <#regional>
      a acl:Authorization;
      acl:agent <http://localhost:3000/isabelle/profile/card#me>;
      acl:accessTo <./>;
      acl:default <./>;
      acl:mode acl:Read.
  ```

  **`claire-student-1/.acl`** and **`claire-student-2/.acl`**:
  - Student owner: full control
  - Claire (tutor): read access
  - Marc (admin): read access
  - Isabelle (regional): read access
  - No Fatima access (not her children)

  **`fatima-child-1/.acl`** and **`fatima-child-2/.acl`**:
  - Student owner: full control
  - Fatima (parent): read access
  - Marc (admin): read access
  - Isabelle (regional): read access
  - No Claire access (not her students)

  **`school-community/.acl`**:
  - Marc (admin): read AND write access (+ Control)
  - Claire (tutor): read access
  - Fatima (parent): read access
  - Isabelle (regional): read access
  - All students: read access

- [ ] Use exact Turtle syntax per WAC (Web Access Control) specification
- [ ] ACL files use `acl:default` to apply to all contained resources (inheritance)

### Task 5: Create the provisioning shell script (AC-1, AC-2)
- [ ] Create `scripts/seed-pods.sh`:
  ```bash
  #!/usr/bin/env bash
  # Provision all pods and apply ACL configuration
  # Calls pipeline/src/pocpod0_pipeline/provision_pods.py

  set -euo pipefail

  # Activate Python venv
  source pipeline/.venv/bin/activate

  # Run provisioning
  python -m pocpod0_pipeline.provision_pods

  echo "Pod provisioning complete."
  ```
- [ ] The script must:
  - Wait for CSS to be healthy before provisioning (check health endpoint)
  - Create all 6 pods
  - Apply ACL files to each pod
  - Report success/failure for each pod
  - Be idempotent (safe to re-run)

### Task 6: Implement ACL application in Python (AC-2)
- [ ] Add function in `provision_pods.py` to upload `.acl` files to each pod via CSS HTTP API:
  - Use HTTP PUT to upload `.acl` resources to pod root
  - Content-Type: `text/turtle`
  - Handle CSS-specific ACL upload requirements
- [ ] Apply ACLs from the template files in `infra/css/pods/{pod-name}/.acl`

### Task 7: Create test fixtures for ACL verification (AC-3, AC-4)
- [ ] Create `tests/integration/test_css_pods.py` with tests:
  - Test: each of the 6 pods exists and is accessible
  - Test: authorized role can read pod resource (AC-3)
  - Test: unauthorized role gets HTTP 403 (AC-4)
  - Test: Ayoub can write to his own pod
  - Test: Claire can read her students' pods but NOT Fatima's children's pods
  - Test: Fatima can read her children's pods but NOT Claire's students' pods
  - Test: Marc can read all student pods AND read/write school-community pod
  - Test: Isabelle can read all pods (aggregate access)
- [ ] Tests use `requests` or `httpx` to make HTTP requests with appropriate agent identity headers
- [ ] Add `pytest` and `requests` to `pipeline/pyproject.toml` dev dependencies

### Task 8: Run and verify provisioning (AC-1, AC-2, AC-3, AC-4)
- [ ] Run `scripts/seed-pods.sh` against running CSS instance
- [ ] Verify all 6 pods are created
- [ ] Verify ACL files are applied to each pod
- [ ] Run integration tests to confirm authorized/unauthorized access patterns
- [ ] Use `distrobox-host-exec` if running inside distrobox

## Dev Notes

### Pod Names and Structure

Exactly 6 pods must be provisioned. The names must match exactly:

| Pod | Type | CSS Path |
|-----|------|----------|
| `ayoub` | Individual | `/ayoub/` |
| `claire-student-1` | Individual | `/claire-student-1/` |
| `claire-student-2` | Individual | `/claire-student-2/` |
| `fatima-child-1` | Individual | `/fatima-child-1/` |
| `fatima-child-2` | Individual | `/fatima-child-2/` |
| `school-community` | Community | `/school-community/` |

Pod configuration files live in `infra/css/pods/{pod-name}/`.

### ACL Role Matrix

This is the complete access control matrix. Every cell must be enforced:

| Pod | Ayoub | Claire | Fatima | Marc | Isabelle |
|-----|-------|--------|--------|------|----------|
| `ayoub` | RWC (owner) | R (tutor) | - | R (admin) | R (regional) |
| `claire-student-1` | - | R (tutor) | - | R (admin) | R (regional) |
| `claire-student-2` | - | R (tutor) | - | R (admin) | R (regional) |
| `fatima-child-1` | - | - | R (parent) | R (admin) | R (regional) |
| `fatima-child-2` | - | - | R (parent) | R (admin) | R (regional) |
| `school-community` | R | R | R | RWC (admin) | R (regional) |

Legend: R=Read, W=Write, C=Control, -=No access (HTTP 403)

### No Real Authentication (SEC-1)

This PoC does NOT implement Solid-OIDC authentication. Agent identity is **configured, not authenticated**:
- Each agent has a simulated WebID URI
- CSS enforces ACLs based on the identity presented in the request
- The mechanism for presenting identity depends on CSS 7's configuration for non-OIDC access
- Investigate CSS 7's `--config` options for setting up identity without OIDC (e.g., HTTP Basic, token-based, or header-based identity)

**Important:** You need to figure out how CSS 7 handles identity in a non-OIDC setup. Options to investigate:
1. CSS `UnsecureWebIdExtractor` or similar for development mode
2. CSS account/pod creation API that returns tokens
3. Custom CSS configuration that maps request headers to WebIDs

### CSS 7 Pod Provisioning API

CSS 7 has a pod provisioning API. Key endpoints to investigate:
- `POST /.account/` — create account
- `POST /.account/{id}/pod/` — create pod for account
- The exact API may differ — check CSS 7 documentation

Alternative: CSS 7 can be configured with a file-based pod backend where pods are directories on the filesystem. Since pods are bind-mounted from `infra/css/pods/`, you may be able to pre-create pod directories with seed data.

### WebACL Specification

ACL files follow the WAC (Web Access Control) specification:
- Namespace: `http://www.w3.org/ns/auth/acl#`
- Key predicates: `acl:agent`, `acl:accessTo`, `acl:default`, `acl:mode`
- Modes: `acl:Read`, `acl:Write`, `acl:Control`, `acl:Append`
- `acl:default` makes the ACL apply to all contained resources (inheritance)
- ACL resources are named `.acl` and stored alongside the resources they protect

### Script Execution Flow

```
scripts/seed-pods.sh
  └── Activates Python venv
  └── Calls: python -m pocpod0_pipeline.provision_pods
      ├── Reads pod config (6 pods)
      ├── For each pod:
      │   ├── Creates pod via CSS API
      │   ├── Reads .acl template from infra/css/pods/{name}/.acl
      │   └── Uploads .acl to pod via HTTP PUT
      └── Reports summary
```

### Python Environment

- Python >= 3.12
- Virtual environment at `pipeline/.venv/`
- Always activate venv before running Python: `source pipeline/.venv/bin/activate`
- Dependencies managed via `pipeline/pyproject.toml`
- Install: `cd pipeline && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`

### Dependency on Story 1.2 Outcome

This story must use the CSS base URL determined by Story 1.2:
- **If Nginx spike passed:** Use `http://localhost` (through Nginx on port 80)
- **If fallback applied:** Use `http://localhost:3000` (direct CSS access)
- Read the value from `CSS_BASE_URL` in `.env`
- For inter-container communication within Docker network, always use `http://community-solid-server:3000`

### Error Handling

Follow the architecture's error handling pattern:
- Pipeline errors: log + continue (don't halt provisioning for one pod failure)
- Log each pod creation attempt with success/failure
- Log each ACL application with success/failure
- Report summary at end: "6/6 pods created, 6/6 ACLs applied" or equivalent

### Distrobox Isolation Note

When running provisioning scripts or tests from inside a distrobox:
```bash
# The CSS container runs on the host
# From inside distrobox, access via distrobox-host-exec
distrobox-host-exec curl http://localhost:3000/.well-known/solid

# Or run the script which talks to CSS over HTTP (this works directly
# from distrobox since HTTP goes through the host network)
```
Note: HTTP requests from inside distrobox to `localhost` ports typically work because distrobox shares the host network namespace. Verify this in your environment.

### Project Structure Notes

Files **created** in this story:
- `pipeline/src/pocpod0_pipeline/provision_pods.py` — pod provisioning and ACL application logic
- `scripts/seed-pods.sh` — shell wrapper to run provisioning
- `infra/css/pods/ayoub/.acl` — Ayoub's ACL template
- `infra/css/pods/claire-student-1/.acl` — Student 1 ACL template
- `infra/css/pods/claire-student-2/.acl` — Student 2 ACL template
- `infra/css/pods/fatima-child-1/.acl` — Child 1 ACL template
- `infra/css/pods/fatima-child-2/.acl` — Child 2 ACL template
- `infra/css/pods/school-community/.acl` — Community pod ACL template
- `tests/integration/test_css_pods.py` — integration tests for pod provisioning and ACL enforcement
- `tests/integration/conftest.py` — shared test fixtures (CSS URL, agent identities)

Files **modified** in this story:
- `pipeline/pyproject.toml` — add `requests` (or `httpx`) dependency
- `pipeline/src/pocpod0_pipeline/__init__.py` — may add exports

### References

- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` (sections: SEC-1, SEC-2, DA-1, Project Structure, Naming Patterns, Process Patterns — Error Handling)
- PRD: `_bmad-output/planning-artifacts/prd.md` (sections: FR1, FR2, FR3, Technical Success — "5 individual + 1 community pod, ACLs per role")
- Epics doc: `_bmad-output/planning-artifacts/epics.md` (Story 1.3 acceptance criteria)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (key: `story-1-3-pod-provisioning-acl-configuration`)
- Story 1.2 decision: `infra/nginx/SPIKE-DECISION.md` (determines CSS base URL)
- WAC specification: https://solidproject.org/TR/wac
- CSS 7 documentation: https://communitysolidserver.github.io/CommunitySolidServer/

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
