#!/usr/bin/env bash
# launch_dev.sh — Development launcher: mock insurance site + UI.
#
# Starts the mock site on port 8080 then the Streamlit UI on port 8501.
# Use this when developing against the local mock insurance site.
#
# For production/general use (your own site), use launch_ui.sh instead.
#
# Usage: bash launch_dev.sh

set -e

echo ""
echo "🎭  AI Playwright Test Generator — Dev Launcher"
echo "================================================"
echo ""

# Check Python
if ! command -v python &>/dev/null; then
  echo "❌  Python not found."
  exit 1
fi
echo "✅  Python: $(python --version)"

# Check uv
if ! command -v uv &>/dev/null; then
  echo "❌  uv not found. Install it with: pip install uv"
  exit 1
fi
echo "✅  uv: $(uv --version)"

# Sync dependencies
echo "📦  Syncing dependencies…"
uv sync

# Activate venv if not already active
if [[ "$VIRTUAL_ENV" == "" ]]; then
  source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
fi

# Check mock site HTML exists
MOCK_HTML="generated_tests/mock_insurance_site.html"
if [[ ! -f "$MOCK_HTML" ]]; then
  echo "❌  Mock site not found at $MOCK_HTML"
  echo "    Ensure you are running from the project root."
  exit 1
fi

# Start mock site in background if not already running
if ! curl -s http://localhost:8080 &>/dev/null; then
  echo "🌐  Starting mock site at http://localhost:8080…"
  python -m http.server 8080 --directory generated_tests &
  MOCK_PID=$!
  sleep 1
  echo "✅  Mock site running (PID $MOCK_PID)"
else
  echo "✅  Mock site already running on port 8080"
  MOCK_PID=""
fi

echo ""
echo "🚀  Starting UI at http://localhost:8501"
echo "    Mock site: http://localhost:8080"
echo "    Press Ctrl+C to stop both"
echo ""

# Trap Ctrl+C — kill mock server if we started it
cleanup() {
  echo ""
  echo "🛑  Shutting down…"
  if [[ -n "${MOCK_PID:-}" ]]; then
    kill "$MOCK_PID" 2>/dev/null && echo "✅  Mock site stopped (PID $MOCK_PID)"
  fi
}
trap cleanup EXIT

uv run streamlit run streamlit_app.py \
  --server.port 8501 \
  --server.headless false \
  --browser.gatherUsageStats false \
  --theme.base dark \
  --theme.backgroundColor "#0d0f14" \
  --theme.secondaryBackgroundColor "#111318" \
  --theme.textColor "#e2e8f0" \
  --theme.primaryColor "#4ade80"
