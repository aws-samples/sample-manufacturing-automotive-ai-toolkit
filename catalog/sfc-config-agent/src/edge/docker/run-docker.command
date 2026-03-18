#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(dirname "$SCRIPT_DIR")"
PKG_ID="$(python3 -c "import json; print(json.load(open('$PKG_ROOT/iot/iot-config.json'))['packageId'])")"
IMAGE_NAME="sfc-launch-package-${PKG_ID}"
cd "$PKG_ROOT"
docker build -f docker/Dockerfile -t "$IMAGE_NAME" .
docker run --rm "$IMAGE_NAME"
