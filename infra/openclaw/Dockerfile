ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest
FROM ${OPENCLAW_IMAGE}

USER root
RUN apt-get update -qq && \
    apt-get install -y -q --no-install-recommends \
      python3-requests \
      python3-httpx \
      python3-yaml && \
    rm -rf /var/lib/apt/lists/*

# Bake agent workspace seed files into the image.
# The entrypoint copies these to the named volume on first boot (seed-on-boot).
# On subsequent restarts the named volume is used as-is (idempotent).
# Factory reset: docker-compose down -v && docker-compose up
COPY agents/ /app/agents-seed/

# Bake pipeline package so acl-manage/handler.py can import pocpod0_pipeline.provision_pods.
# handler.py uses POCPOD0_ROOT=/app (set in docker-compose) to locate pipeline/src/.
COPY pipeline/src/ /app/pipeline/src/
# pod-config.yaml is needed by PodProvisioner constructor.
COPY infra/css/pods/ /app/infra/css/pods/

# Install and wire entrypoint + CLI wrapper
COPY infra/openclaw/entrypoint.sh /app/entrypoint.sh
COPY infra/openclaw/cli.sh /app/cli.sh
RUN chmod +x /app/entrypoint.sh /app/cli.sh

USER node
