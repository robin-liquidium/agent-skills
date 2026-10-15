#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Pinned on purpose; bump deliberately after reviewing the Telethon changelog.
TELETHON_VERSION="1.43.2"
VENV_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/telegram-cli/venv"
mkdir -p "$(dirname "$VENV_DIR")"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install "telethon==$TELETHON_VERSION"

echo "ok: telegram-cli venv ready at $VENV_DIR"
