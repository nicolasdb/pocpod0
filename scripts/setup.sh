#!/bin/bash

# pocpod0 Setup Script
# First-time setup script for pocpod0 development environment

set -e

echo "🚀 pocpod0 Setup"
echo "================="
echo ""

# Check for Docker or Podman
if command -v docker &> /dev/null; then
    CONTAINER_CMD=("docker")
    echo "✓ Docker found"
elif command -v podman &> /dev/null; then
    CONTAINER_CMD=("podman")
    echo "✓ Podman found"
else
    echo "✗ Neither Docker nor Podman found. Please install one of them."
    exit 1
fi

# Check if running in distrobox
if [[ -f /.dockerenv ]] || [[ -f /run/.containerenv ]]; then
    if command -v distrobox-host-exec &> /dev/null; then
        CONTAINER_CMD=("distrobox-host-exec" "${CONTAINER_CMD[@]}")
        echo "✓ Running in distrobox container environment"
        echo "  Using: ${CONTAINER_CMD[*]}"
    fi
fi

# Check for .env file
echo ""
if [[ ! -f .env ]]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env created. Please review and update if needed."
    echo ""
    echo "⚠️  IMPORTANT: If you're on Fedora with SELinux:"
    echo "   Edit .env and set: VOLUME_FLAGS=,Z"
    echo ""
else
    echo "✓ .env already exists"
fi

# Create data directories
echo ""
echo "📁 Creating data directories..."
mkdir -p infra/css/pods/{ayoub,claire-student-1,claire-student-2,fatima-child-1,fatima-child-2,school-community}
mkdir -p infra/oxigraph
mkdir -p infra/qdrant
echo "✓ Data directories created"

# Print environment summary
echo ""
echo "📋 Environment Summary:"
echo "   Container engine: ${CONTAINER_CMD[*]}"
echo "   Environment file: .env"

# Load environment variables
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

echo ""
echo "Service Configuration:"
echo "   CSS:      http://localhost:${CSS_PORT:-3000}"
echo "   Oxigraph: http://localhost:${OXIGRAPH_PORT:-7878}"
echo "   Qdrant:   http://localhost:${QDRANT_REST_PORT:-6333}"
echo "   Nginx:    http://localhost:${NGINX_HTTP_PORT:-80}"
echo ""

# Final instructions
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "   1. Review .env configuration (especially VOLUME_FLAGS on Fedora)"
echo "   2. Start services: ${CONTAINER_CMD[*]} compose up"
echo "   3. Services will be healthy within 60 seconds"
echo ""
echo "For more information, see README.md and CONTRIBUTING.md"
