#!/usr/bin/env bash
# ==============================================================================
# ElevenLabs PipeWire Bluetooth Handsfree Permanent Call Launcher
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Ensure .venv exists
if [ ! -f "$DIR/.venv/bin/python" ]; then
    echo "[*] Initializing virtual environment..."
    uv venv "$DIR/.venv"
    "$DIR/.venv/bin/python" -m pip install websockets requests webrtcvad-wheels numpy
fi

# Run the permanent call
exec "$DIR/.venv/bin/python" "$DIR/pipewire_agent_call.py" "$@"
