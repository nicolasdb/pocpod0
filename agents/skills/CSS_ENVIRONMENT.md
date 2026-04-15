---
name: css-environment
description: Canonical reference for CSS (Community Solid Server) environment variables and the two-space model. Read this before invoking any skill that touches pod URIs, WebIDs, or ACL operations.
---

# CSS Environment — Two-Space Model

All skills that interact with CSS (sparql-query, acl-manage) use three environment variables
that split "pod identity" from "network routing". **You never need to change these** — they are
set correctly for the current environment (local dev or VPS) by the platform.

## The Three Variables

| Variable | Dev value | VPS value | Purpose |
|---|---|---|---|
| `CSS_IDENTIFIER_URL` | `http://localhost:3000` | `https://mypods.example.com` | **Pod namespace** — WebIDs and pod URIs live here |
| `CSS_CONNECT_URL` | `http://community-solid-server:3000` | same as IDENTIFIER_URL | TCP routing — where the handler dials CSS |
| `CSS_IDENTIFIER_HOST` | `localhost:3000` | derived from IDENTIFIER_URL | Host header sent to CSS |

## Rule: two distinct spaces

```
community-solid-server:3000   ← Docker TCP hostname  — for direct curl inside container ONLY
$CSS_IDENTIFIER_URL/...       ← Pod identity space   — for ALL skill params and WebIDs
```

**NEVER** use `community-solid-server:3000` in skill parameters or WebID arguments.
It is a Docker-internal TCP hostname, not a pod identity. On VPS it does not exist at all.

## Your WebID

Your WebID is always: `$CSS_IDENTIFIER_URL/<your-agent-name>/profile/card#me`

You don't need to know the value — use `--agent <your-name>` with sparql-query and the
handler constructs it from the environment automatically. This works on both dev and VPS.

## Pod URIs in skill parameters

Always read `$CSS_IDENTIFIER_URL` from the environment and construct pod URIs as:

```bash
CSS_ID=$(echo $CSS_IDENTIFIER_URL)
# e.g. http://localhost:3000 on dev, https://mypods.example.com on VPS

--params "{\"student_uri\": \"${CSS_ID}/ayoub/profile/card#me\", ...}"
```

Or pass the literal `http://localhost:3000/...` — the platform sets the correct value
and you will always be running in a consistent environment.

## Direct CSS access (curl)

If you ever make direct HTTP requests to CSS (e.g. for ACL probing), dial via `CSS_CONNECT_URL`
and always include the Host header:

```bash
curl -H "Host: $(echo $CSS_IDENTIFIER_HOST)" \
     -H "Authorization: WebID $CSS_IDENTIFIER_URL/<you>/profile/card#me" \
     http://community-solid-server:3000/ayoub/
```

## Summary for new agents

1. Use `--agent <your-name>` with sparql-query — never `--webid` unless your pod is external.
2. Use `$CSS_IDENTIFIER_URL/<name>/profile/card#me` for all `--identity` args in acl-manage.
3. Use `$CSS_IDENTIFIER_URL/...` for all pod URI params.
4. `community-solid-server:3000` is TCP only — never in URIs passed to skills.
