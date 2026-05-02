#!/usr/bin/env bash
# =============================================================================
#  BRUNs - environment diagnostic (Linux / macOS)
# =============================================================================
#  Run when the app refuses to start or displays "Internal Server Error".
#  Output is mirrored to data/logs/diagnose.txt for sharing with support.
# =============================================================================
set -u

cd "$(dirname "$0")"

VENV_DIR=".venv"
OUT_FILE="data/logs/diagnose.txt"

if [[ ! -d "$VENV_DIR" ]]; then
    echo "[!] Virtual environment not found at $VENV_DIR/."
    echo "    Run ./install.sh first."
    exit 1
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

mkdir -p data/logs
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

python -m core.diagnostics 2>&1 | tee "$OUT_FILE"
RC=${PIPESTATUS[0]}

echo
echo "============================================================"
echo "  Full report saved to: $OUT_FILE"
echo "============================================================"
echo "  If you see [FAIL] entries, send the contents of"
echo "  $OUT_FILE along with your bug report."

exit "$RC"
