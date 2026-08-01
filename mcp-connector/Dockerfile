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
# Pinned to a fixed release + arch binary (not `apt-get install gosu`, which
# floats to whatever version is in the base image's apt snapshot at build
# time) so a rebuild months from now can't silently pick up a different
# gosu build for this privilege-drop step.
ARG GOSU_VERSION=1.17
RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends ca-certificates wget; \
  rm -rf /var/lib/apt/lists/*; \
  dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')"; \
  wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${dpkgArch}"; \
  chmod +x /usr/local/bin/gosu; \
  gosu --version; \
  gosu nobody true

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3939

ENTRYPOINT ["/entrypoint.sh"]
CMD ["node", "src/mcp-server.js"]
