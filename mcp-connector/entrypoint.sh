#!/bin/sh
# Story 8.4 Task 6: the `mcp-audit` named Docker volume is created root-owned
# on first use, but the app runs as the non-root `node` user (image default,
# Dockerfile), so every audit write EACCES'd until this ran. Fix it here
# rather than as a one-off manual chown, so it self-heals on the next
# `docker compose up -d --force-recreate` too (same class of trap already
# hit once for identities.json — see README).
set -e
mkdir -p /app/audit
chown -R node:node /app/audit
exec gosu node "$@"
