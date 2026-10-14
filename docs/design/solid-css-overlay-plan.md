# Snapshot (2026-10-14) and design of `solid-css-overlay`

## Snapshot
- **Live, pod.nicolasdb.eu**: the pod skin (deployed, confirmed).
- **pocpod0 `claude/gifted-volta-t97yy3` @ `6d5e39f`**: instance 1 of the
  template, **not deployed**. Order: `make vps-deploy` then straight away
  `make vps-welcome`.
- **solid-kit `claude/blissful-hamilton-9i2pkj` @ `2772945`**:
  `templates/css-instance/`, `test/` (smoke 15/15 on the template and
  pocpod0), `audit --skin`, skill, ADR 009.
- Canvas: https://claude.ai/artifact/UQVNBrrDvgvaCs6t3zPYxm
- Not tested: the method on a genuinely different skin (Maps of Making).

## The decision: a versioned image + an overlay per collective

```
solidproject/community-server:7.2.0            stock
  └─ FROM → ghcr.io/nicolasdb/solid-css-overlay:7.2.0-1    (repo nicolasdb/solid-css-overlay)
             generic overlay baked into /community-server/templates/
             + "pod" skin by default + secure config (no debug header)
               └─ instance (Maps of Making, Hyperscope, pod.nicolasdb.eu)
                  own repo/org, own VPS:
                  compose.yml (image pinned) + .env + overlay/ (optional)
```

### Scope of the repo: CSS + overlay + mcp-connector
- **The mcp-connector is part of the overlay** (Nicolas, 2026-10-14): it
  ships in the instance compose, as a second service next to CSS. Its source
  moves from `pocpod0/mcp-connector/` to the new repo, and its image is
  published alongside (`ghcr.io/nicolasdb/solid-mcp-connector:<version>`),
  so an instance pulls it rather than building it.
  - Checked: it does not use the debug WebID header (only `agents/` and
    `pipeline/` do), so it works with the image's secure config.
  - Per instance, in `.env`: `MCP_ALLOWED_HOSTS`, `ONBOARD_CORS_ORIGINS`,
    `OXIGRAPH_URL` (empty = graph_query/graph_ingest unavailable, the rest
    works); `identities.json` and `.env` mounted from the instance (secrets
    stay on the VPS, never in the image).
  - The gateway network (`gateway` at pocpod0) is declared `external` in the
    instance compose, with its name in `.env`: the instance's nginx gateway
    reaches the connector by container name, with no published port.
- **Not included**: qdrant, oxigraph, openclaw, pipeline, agents. They stay
  in pocpod0. Removing qdrant from pocpod0 is a separate cleanup (it still
  has callers: `agents/skills/qdrant-search`, troll, `pipeline/`).
- **Secure config by default**: stock `dpop-bearer` extraction. pocpod0's
  `UnsecureWebIdExtractor` (internal automation header) **never** enters
  the image; an instance that needs it adds it in its own `config.json`
  mount, knowingly.
- **Oxigraph = sister container, optional**, documented, not in compose. A
  shared Docker network (`docker network create solid`), CSS's compose
  joins it as `external`, `docker run --network solid --name oxigraph …`
  on the side. CSS never talks to it; the mcp-connector does (via
  `OXIGRAPH_URL=http://oxigraph:7878` on that network). Never exposed by
  the gateway (no access control). A later skill
  (`sister-service`) can do this wiring.

### What the repo contains
```
Dockerfile               FROM stock; COPY overlay/ → templates/; default config
overlay/                 generic: main.css, pod-ui.js, main.html.ejs, identity/**, welcome
skins/pod/               default skin (skin.css, fonts, mark)
config/instance.json     secure CSS config (file backend, intro, static entries for doc-view)
instance-template/       what a collective copies: compose.yml, .env.example, overlay/ (empty + README)
test/                    try-local.sh + smoke.mjs (adapted: against the built image)
scripts/check-overrides.sh, upstream-baseline.sha256
mcp-connector/           source + Dockerfile (moves from pocpod0), its own tests
skills/css-instance/     the skill (moves from solid-kit)
.github/workflows/       build + smoke + GHCR publish on tag; weekly stock-release watch
CHANGELOG.md             versions <stock>-<n>: 7.2.0-1, 7.2.0-2, 7.3.0-1…
```

### Installing from scratch (user side): CLI first, the skill drives it
```sh
mkdir my-instance && cd my-instance
curl -LO …/instance-template/{compose.yml,.env.example}   # or: copy the folder
cp .env.example .env        # CSS_BASE_URL, port, image version
docker compose pull && docker compose up -d
```
→ a working server with the generic overlay and the "pod" skin. **No
design system needed** to start.
- **Own look later**: put `skin.css` + `fonts/` (+ copy) in `overlay/`;
  compose mounts it on top. `docker compose up -d`, no build.
- **The skill** (Claude Code) does the same steps and adds: a draft from a
  design system (canvas), `audit --skin`, smoke run, deploy over SSH,
  update. It is never required.
- **Update**: change `CSS_OVERLAY_VERSION` in `.env` (or a CI in the
  collective's repo that proposes it), `pull && up -d`, check. Two sources
  stay separable: a new stock → new `7.x.y-1`; a new overlay → `-n+1`.
- **Allowed drift**: an instance can mount its own version of any generic
  file; `check-overrides` + smoke tell it what diverges from the version it
  pins.

## Roles (Nicolas, 2026-10-14)
- **solid-kit**: jump-starts a new Solid *app*. Not a server.
- **pocpod0**: exploration of CSS and the custom features. Frozen once
  migrated; until then, only fixes for what is live.
- **solid-css-overlay**: the product: stock CSS + the overlay (pages,
  mcp-connector, config). Every instance remains a compliant Solid
  server: a WebID from another provider works there, just without the
  overlay's features.

## Work in progress: where it goes
Rule: **a feature that every instance will get is built in
solid-css-overlay**; pocpod0 only gets urgent fixes for what is live. Otherwise
everything is built twice and the migration drags a backlog with it.

- **Access log (epic 9)**: the receipts live in the mcp-connector
  (`src/receipt.js`, `infra/css/pods/access-receipt.ttl.j2`), which moves to
  the new repo → build it **there**. If a slice is half-finished in pocpod0
  and used live, finish *that slice* in pocpod0, then bring it over as the
  starting point.
- **Pods as subdomains** (`alice.pod.example` rather than
  `pod.example/alice/`): a CSS config choice
  (`css:config/util/identifiers/subdomain.json`) + wildcard DNS + wildcard
  certificate on the gateway (DNS-01 challenge). Decide it **before the first
  release**: it is the image's default for every new instance and becomes
  hard to change once pods exist. **Never on pocpod0's existing pods**:
  their URIs are their identity (ADR 002) — switching would break every
  WebID, every ACL, every link. pocpod0 stays on suffix, or at most offers
  subdomains for new accounts if CSS can handle both (to check).
- **A custom domain per account**: solid-kit's ADR 002 already settles it:
  - tier 1 (**to build**): *bring your own WebID*: the person points their
    domain at the gateway, which serves the certificate and the profile
    document; the account links that WebID. The identity lives on their
    domain, the storage stays with us. Belongs to the overlay
    (gateway + connector/backoffice "connect your domain" step).
  - tier 2 (not now): storage on the custom domain = one CSS instance per
    domain; **URI rewriting at the proxy forbidden**.
  → To be confirmed: "attach a custom domain" = tier 1.

## Next session: first steps
1. Create `nicolasdb/solid-css-overlay` (empty, by you), then I move the
   template + tests + skill there, with a Dockerfile and secure config.
2. Build the image locally, smoke run **against the image** (not node);
   the connector's tests pass in the new repo.
3. CI: build + smoke + GHCR on tag (two images: CSS+overlay, connector);
   first release `7.2.0-1`.
4. `instance-template/` + README "install from scratch" tested on a clean
   Docker.
5. solid-kit: remove `templates/css-instance/` and point to the repo
   (atlas, ADR 009 amended: image + overlay, not copy).
6. Then pocpod0 migrates (pinned image + its overlay), then Maps of Making.

Decided (Nicolas, 2026-10-14):
- **GHCR images public** (`solid-css-overlay` and `solid-mcp-connector`).
- **The welcome page is served by the image**: `static-root.json` (CSS's
  stock "root is not a pod" mode, the one `file.json` uses), so `/` serves
  `templates/root/static/index.html` = our welcome. An instance replaces it
  by mounting its own `overlay/welcome/index.html` over it. No more copying
  into the data volume, no more `vps-welcome`.
  - Watch-out for pocpod0's migration: it runs with `initialize-intro.json`
    (the root is a container that stores `index.html`). Before switching,
    check what the root holds besides `index.html` (the stock intro also
    creates `.acl`/`README`) and whether anything reads `/` as LDP. If so,
    keep `initialize-intro` for pocpod0 only, in its own config.
