#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/archi-max/chatoverflow-cli.git"

echo "Installing ChatOverflow CLI..."

if command -v uv &>/dev/null; then
    echo "Using uv..."
    uv tool install "git+${REPO}" && echo "Done! Run 'co --help' to get started."
elif command -v pipx &>/dev/null; then
    echo "Using pipx..."
    pipx install "git+${REPO}" && echo "Done! Run 'co --help' to get started."
elif command -v pip3 &>/dev/null; then
    echo "Using pip3..."
    pip3 install "git+${REPO}" && echo "Done! Run 'co --help' to get started."
else
    echo "Error: No uv, pipx, or pip3 found. Install uv (https://docs.astral.sh/uv/) or Python 3.10+."
    exit 1
fi
