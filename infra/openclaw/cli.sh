#!/bin/sh
# CLI wrapper for the openclaw-cli service.
# Automatically injects --url and --token so callers don't need to pass them.
#
# Usage (from distrobox):
#   distrobox-host-exec podman compose --profile cli run --rm openclaw-cli devices list
#   distrobox-host-exec podman compose --profile cli run --rm openclaw-cli devices approve <requestId>
#   distrobox-host-exec podman compose --profile cli run --rm openclaw-cli dashboard --no-open
#
# The openclaw-cli container shares the openclaw-data-default volume with the gateway,
# and connects container-to-container via ws://openclaw-gateway:18789 (lan bind, bridge network).
# --token is the OPENCLAW_GATEWAY_TOKEN from .env (injected via env_file in docker-compose.yml).

exec openclaw "$@" \
    --url "ws://127.0.0.1:${OPENCLAW_GATEWAY_PORT:-18789}" \
    --token "${OPENCLAW_GATEWAY_TOKEN}"
