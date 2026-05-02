#!/usr/bin/env bash
# =============================================================================
#  BRUNs - quick launcher for Linux / macOS
# =============================================================================
#  Bash equivalent of START_APP.bat. Auto-runs install.sh on first launch.
#
#  Usage:
#     chmod +x start.sh
#     ./start.sh
# =============================================================================
set -euo pipefail

GREEN=$'\e[32m'
YELLOW=$'\e[33m'
RED=$'\e[31m'
BLUE=$'\e[34m'
RESET=$'\e[0m'

VENV_DIR=".venv"
PORT="${BRUNS_API_PORT:-7845}"

cd "$(dirname "$0")"

echo
echo "${BLUE}=============================================================${RESET}"
echo "${BLUE}  BRUNS DOCUMENT INTELLIGENCE PLATFORM${RESET}"
echo "${BLUE}=============================================================${RESET}"
echo

# ── Sanity: in the right place ──────────────────────────────────────────────
if [[ ! -f "core/api/server.py" ]]; then
    echo "${RED}[!!]${RESET} core/api/server.py not found."
    echo "     Run this script from the BRUNs project root."
    echo "     Current dir: $(pwd)"
    exit 1
fi

# ── Check 1: venv exists ────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    echo "${YELLOW}[!]${RESET} Virtual environment not found at $VENV_DIR/."
    echo
    echo "    First-time setup is required."
    read -r -p "    Run install.sh now? [Y/n]: " yn
    yn=${yn:-Y}
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        echo
        bash ./install.sh
        echo
        echo "--- Installer complete, continuing to launch ---"
        echo
    else
        echo "    Run ./install.sh manually when ready."
        exit 1
    fi
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# ── Check 2: dependencies installed ─────────────────────────────────────────
if ! python -c "import flask, pydantic, chromadb" >/dev/null 2>&1; then
    echo "${YELLOW}[!]${RESET} Some Python dependencies are missing."
    echo "    Re-running install.sh to repair..."
    bash ./install.sh
    source "$VENV_DIR/bin/activate"
fi

# ── Check 3: Ollama warning ─────────────────────────────────────────────────
echo "Checking Ollama connectivity..."
if curl -fsS --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "${GREEN}[OK]${RESET} Ollama is ready."
else
    echo
    echo "${YELLOW}[!]${RESET} Ollama is not running."
    echo "    Document processing requires Ollama. You can still browse existing data."
    echo
    echo "    Install:  https://ollama.com/download"
    echo "    Then:     ollama pull llama3"
    echo
    read -r -p "    Continue anyway? [y/N]: " cont
    if [[ ! "${cont:-N}" =~ ^[Yy]$ ]]; then
        echo "Exiting..."
        exit 0
    fi
fi

# ── Check 4: port is free ───────────────────────────────────────────────────
if (command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1) ||
   (command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$PORT "); then
    echo
    echo "${RED}[!]${RESET} Port $PORT is already in use."
    echo "    Another instance may be running. Free the port first:"
    echo "      lsof -iTCP:$PORT -sTCP:LISTEN"
    echo "      kill <pid>"
    exit 1
fi

# ── Launch ──────────────────────────────────────────────────────────────────
echo
echo "Starting Flask server on http://localhost:${PORT} ..."
echo "Open your browser at: http://localhost:${PORT}/"
echo "Stop with Ctrl+C."
echo

# Best-effort browser open after a short delay (non-blocking).
(
    sleep 2
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:${PORT}/" >/dev/null 2>&1
    elif command -v open >/dev/null 2>&1; then open "http://localhost:${PORT}/" >/dev/null 2>&1
    fi
) &

exec python -m core.api.server
