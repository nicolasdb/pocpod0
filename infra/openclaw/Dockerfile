ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest
FROM ${OPENCLAW_IMAGE}

USER root
RUN apt-get update -qq && \
    apt-get install -y -q --no-install-recommends \
      python3-requests \
      python3-httpx && \
    rm -rf /var/lib/apt/lists/*

USER node
