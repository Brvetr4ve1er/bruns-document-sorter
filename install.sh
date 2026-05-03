#!/usr/bin/env bash
# =============================================================================
#  BRUNs - first-time installer for Linux / macOS
# =============================================================================
#  Bash equivalent of INSTALL.bat. Idempotent — re-running is safe.
#
#  Usage (from a fresh clone):
#     chmod +x install.sh
#     ./install.sh
# =============================================================================
set -euo pipefail

GREEN=$'\e[32m'
YELLOW=$'\e[33m'
RED=$'\e[31m'
BLUE=$'\e[34m'
RESET=$'\e[0m'

VENV_DIR=".venv"

cd "$(dirname "$0")"

echo
echo "${BLUE}=============================================================${RESET}"
echo "${BLUE}  BRUNS DOCUMENT INTELLIGENCE PLATFORM - INSTALLER${RESET}"
echo "${BLUE}=============================================================${RESET}"
echo

ensure_traineddata() {
    local lang="$1"
    local tfile="tessdata/${lang}.traineddata"
    if [[ -f "$tfile" ]]; then
        echo "        [OK] ${lang}.traineddata already present"
        return
    fi
    echo "        Downloading ${lang}.traineddata ..."
    if ! curl -fsSL -o "$tfile" \
        "https://github.com/tesseract-ocr/tessdata/raw/main/${lang}.traineddata"; then
        echo "        ${YELLOW}[!] ${lang}.traineddata download failed.${RESET}"
        rm -f "$tfile"
    fi
}

# ── Step 1: Python ──────────────────────────────────────────────────────────
echo "[1/7] Checking Python..."
# Min Python is 3.11 — pandas 3.x dropped 3.10 wheels.
PYTHON=""
for cand in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
        PY_VER=$("$cand" --version 2>&1 | awk '{print $2}')
        PY_MAJOR=${PY_VER%%.*}
        PY_REST=${PY_VER#*.}
        PY_MINOR=${PY_REST%%.*}
        if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 11 ]]; then
            PYTHON="$cand"
            echo "      ${GREEN}[OK]${RESET} Found $cand ($PY_VER)"
            break
        fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    echo "      ${RED}[!!]${RESET} Python 3.10+ not found."
    echo "           macOS:  brew install python@3.12"
    echo "           Ubuntu: sudo apt install python3.12 python3.12-venv"
    echo "           Fedora: sudo dnf install python3.12"
    exit 1
fi
echo

# ── Step 2: venv ────────────────────────────────────────────────────────────
echo "[2/7] Setting up virtual environment..."
if [[ -d "$VENV_DIR" ]]; then
    echo "      ${GREEN}[OK]${RESET} $VENV_DIR/ already exists, reusing."
else
    "$PYTHON" -m venv "$VENV_DIR"
    echo "      ${GREEN}[OK]${RESET} virtual environment created."
fi
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
echo

# ── Step 3: pip install ─────────────────────────────────────────────────────
echo "[3/7] Installing Python dependencies..."
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
echo "      ${GREEN}[OK]${RESET} Python dependencies installed."
echo

# ── Step 4: Tesseract + tessdata ────────────────────────────────────────────
echo "[4/7] Checking Tesseract OCR..."
if command -v tesseract >/dev/null 2>&1; then
    TESS_VER=$(tesseract --version 2>&1 | head -1)
    echo "      ${GREEN}[OK]${RESET} ${TESS_VER}"
else
    echo "      ${YELLOW}[!]${RESET} Tesseract is not installed."
    echo "          macOS:  brew install tesseract"
    echo "          Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara"
    echo "          Fedora: sudo dnf install tesseract tesseract-langpack-fra tesseract-langpack-ara"
    echo "          The app will install but scanned-PDF OCR will not work without it."
    read -r -p "          Press Enter to continue (you can install later)..."
fi

echo "      Checking language packs (eng/fra/ara)..."
mkdir -p tessdata
ensure_traineddata eng
ensure_traineddata fra
ensure_traineddata ara
echo "      ${GREEN}[OK]${RESET} tessdata directory ready."
echo

# ── Step 5: Ollama ──────────────────────────────────────────────────────────
echo "[5/7] Checking Ollama..."
if curl -fsS --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "      ${GREEN}[OK]${RESET} Ollama is running."
    if curl -fsS --max-time 3 http://localhost:11434/api/tags | grep -q "llama3"; then
        echo "      ${GREEN}[OK]${RESET} llama3 model available."
    else
        read -r -p "      Pull llama3 now? (~4.7 GB) [y/N]: " yn
        if [[ "${yn:-N}" =~ ^[Yy]$ ]]; then ollama pull llama3; fi
    fi
else
    echo "      ${YELLOW}[!]${RESET} Ollama is not running."
    echo "          Install:  https://ollama.com/download"
    echo "          Then:     ollama pull llama3"
    read -r -p "          Press Enter to continue..."
fi
echo

# ── Step 6: data dirs ───────────────────────────────────────────────────────
echo "[6/7] Creating runtime directories..."
mkdir -p data/input/logistics data/input/travel data/logs data/vector data/exports
echo "      ${GREEN}[OK]${RESET} data/ tree ready."
echo

# ── Step 7: db init + migrations ────────────────────────────────────────────
echo "[7/7] Initialising databases..."
python - <<'PY'
import os
os.makedirs("data", exist_ok=True)
from core.storage.db import init_schema
from core.storage.migrations import run_migrations
init_schema("data/logistics.db")
init_schema("data/travel.db")
print("  applied logistics:", run_migrations("data/logistics.db"))
print("  applied travel:   ", run_migrations("data/travel.db"))
PY
echo "      ${GREEN}[OK]${RESET} databases ready."
echo

echo "${BLUE}=============================================================${RESET}"
echo "${GREEN}  INSTALL COMPLETE${RESET}"
echo "${BLUE}=============================================================${RESET}"
echo
echo "  Start the app with:  ./start.sh"
echo "  If anything goes wrong:  ./diagnose.sh"
echo
