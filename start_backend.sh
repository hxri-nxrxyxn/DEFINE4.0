#!/usr/bin/env bash
# ==============================================================================
# Start the call backend for the DEFINE app:
#   - core platform API (Exotel dispatch / analytics / retry) on :8000
#   - a cloudflared tunnel so Exotel can reach the ExoML + audio endpoints
#
# The tunnel URL is exported as EXOTEL_CALLBACK_URL so the core server hands it
# to Exotel for each call. Keep this running alongside `npm run dev` in app-ui.
# ==============================================================================
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PORT="${CORE_PORT:-8000}"
LOG="${TMPDIR:-/tmp}/cloudflared-${PORT}.log"

if ! command -v cloudflared >/dev/null 2>&1; then
	echo "[!] cloudflared not found. Install it or set EXOTEL_CALLBACK_URL manually." >&2
fi

echo "[*] Starting cloudflared tunnel -> http://localhost:${PORT}"
: > "$LOG"
cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate >"$LOG" 2>&1 &
TUNNEL_PID=$!

# Wait for the public URL to appear.
TUNNEL_URL=""
for _ in $(seq 1 30); do
	TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
	[ -n "$TUNNEL_URL" ] && break
	sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
	echo "[!] Could not detect tunnel URL (see $LOG). Falling back to cred file value." >&2
else
	echo "[*] Public callback URL: ${TUNNEL_URL}"
fi

cleanup() {
	echo "[*] Shutting down backend..."
	kill "$TUNNEL_PID" 2>/dev/null || true
	[ -n "${CORE_PID:-}" ] && kill "$CORE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[*] Starting core API on 0.0.0.0:${PORT}"
EXOTEL_CALLBACK_URL="${TUNNEL_URL:-${EXOTEL_CALLBACK_URL:-}}" \
	python3 core/api_server.py --port "${PORT}" --host 0.0.0.0 &
CORE_PID=$!

wait "$CORE_PID"
