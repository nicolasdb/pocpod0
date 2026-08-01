# Story 8.4: mcp-connector as a compose service, no host node/npm on the VPS.
# Follows infra/openclaw/Dockerfile for house style (non-root user, pinned base).
FROM node:22.14.0-slim

WORKDIR /app

# Install from the committed lockfile, not the local node_modules/ tree —
# rsync excludes node_modules/ (Task 1.4), and a host-platform tree would be
# wrong inside the container anyway.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY src/ ./src/
COPY scripts/ ./scripts/

# identities.json and .env are bind-mounted read-only at runtime (Task 1.5) —
# never baked into the image layer.

# node:*-slim already ships a non-root "node" user (uid/gid 1000) — reuse it
# rather than creating a second one that would collide on the gid.
RUN chown -R node:node /app

# gosu: entrypoint.sh needs to start as root (to chown the mcp-audit named
# volume, which Docker creates root-owned on first use — story 8.4 Task 6)
# and then drop to the non-root "node" user before exec'ing the app.
RUN apt-get update \
  && apt-get install -y --no-install-recommends gosu \
  && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3939

ENTRYPOINT ["/entrypoint.sh"]
CMD ["node", "src/mcp-server.js"]
