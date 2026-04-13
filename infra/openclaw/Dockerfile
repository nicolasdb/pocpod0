ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest
FROM ${OPENCLAW_IMAGE}

USER root
RUN apt-get update -qq && \
    apt-get install -y -q --no-install-recommends \
      python3-requests \
      python3-httpx && \
    rm -rf /var/lib/apt/lists/*

# Bake agent workspace seed files into the image.
# The entrypoint copies these to the named volume on first boot (seed-on-boot).
# On subsequent restarts the named volume is used as-is (idempotent).
# Factory reset: docker-compose down -v && docker-compose up
COPY agents/ /app/agents-seed/

# Install and wire entrypoint
COPY infra/openclaw/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER node
