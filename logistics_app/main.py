"""
BRUNs Logistics — single entry point for non-technical users.

Usage:
    python main.py           # launch the dashboard (browser opens automatically)
    python main.py --check   # sanity check: deps, Ollama, Tesseract, DB, input dir
    python main.py --dry-run # parse every PDF in data/input without touching the DB

No manual setup required beyond `pip install -r requirements.txt`.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("BRUNS_DATA_DIR", str(ROOT / "data"))

# Make sure project modules are importable
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Console helpers ─────────────────────────────────────────────────────────

def _c(msg: str, color: str = "") -> None:
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
              "blue": "\033[94m", "bold": "\033[1m", "": ""}
    reset = "\033[0m" if color else ""
    print(f"{colors.get(color,'')}{msg}{reset}")


def _banner() -> None:
    print("=" * 60)
    _c("  BRUNs Logistics — Local PDF → SQLite Pipeline", "bold")
    print("=" * 60)


# ─── Sanity checks ───────────────────────────────────────────────────────────

def _check_python() -> bool:
    ok = sys.version_info >= (3, 10)
    _c(f"  [{'OK' if ok else 'FAIL'}] Python {sys.version.split()[0]} (need 3.10+)",
       "green" if ok else "red")
    return ok


def _check_deps() -> bool:
    missing = []
    for mod in ("fitz", "streamlit", "pandas", "pydantic", "requests", "openpyxl"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        _c(f"  [FAIL] Missing packages: {', '.join(missing)}", "red")
        _c(f"         Run: pip install -r requirements.txt", "yellow")
        return False
    _c("  [OK] All Python dependencies available", "green")
    return True


def _check_ollama() -> bool:
    try:
        import requests
        import config
        base = config.OLLAMA_URL.replace("/api/generate", "").rstrip("/")
        r = requests.get(f"{base}/api/tags", timeout=3)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            want = config.OLLAMA_MODEL
            has_model = any(want in m for m in models)
            _c(f"  [OK] Ollama running at {base}", "green")
            if not has_model:
                _c(f"       Model '{want}' not found. Run: ollama pull {want}", "yellow")
            return True
    except Exception:
        pass
    _c("  [WARN] Ollama is not reachable — PDF parsing will fail until it's started.", "yellow")
    _c("         Install: https://ollama.com  |  Run: ollama serve", "yellow")
    return False


def _check_tesseract() -> None:
    try:
        import pytesseract
        from parsers.pdf_extractor import _LOCAL_TESS, _SYSTEM_TESS
        if os.path.exists(_LOCAL_TESS):
            pytesseract.pytesseract.tesseract_cmd = _LOCAL_TESS
        elif os.path.exists(_SYSTEM_TESS):
            pytesseract.pytesseract.tesseract_cmd = _SYSTEM_TESS
        v = pytesseract.get_tesseract_version()
        _c(f"  [OK] Tesseract OCR {v} (scanned PDFs supported)", "green")
    except Exception:
        _c("  [INFO] Tesseract not detected — scanned PDFs will fall back to Ollama vision.", "blue")


def _check_data_dirs() -> None:
    import config
    for d in (config.INPUT_DIR, config.LOGS_DIR, os.path.dirname(config.DB_PATH)):
        os.makedirs(d, exist_ok=True)
    _c(f"  [OK] Data dirs ready:  input={config.INPUT_DIR}", "green")
    _c(f"                         logs={config.LOGS_DIR}", "green")
    _c(f"                         db={config.DB_PATH}", "green")


def run_checks() -> int:
    _banner()
    _c("\nRunning environment check...\n", "bold")
    ok = True
    ok &= _check_python()
    ok &= _check_deps()
    if ok:
        _check_ollama()
        _check_tesseract()
        _check_data_dirs()
        _c("\n  Check complete.\n", "bold")
        return 0
    _c("\n  Check FAILED — fix the issues above before launching.\n", "red")
    return 1


# ─── Dry run (no DB writes) ──────────────────────────────────────────────────

def run_dry() -> int:
    _banner()
    try:
        import config
        from parsers.pdf_extractor import extract_text
        from agents.parser_agent import parse_document
        from utils.validator import parse_and_validate
    except Exception as e:
        _c(f"  [FAIL] Could not import pipeline: {e}", "red")
        return 1

    input_dir = Path(config.INPUT_DIR)
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        _c(f"\n  No PDFs found in {input_dir}. Drop some and try again.", "yellow")
        return 0

    _c(f"\n  Dry-running {len(pdfs)} PDF(s) from {input_dir}\n", "bold")
    ok_count = 0
    for i, p in enumerate(pdfs, 1):
        print(f"  [{i}/{len(pdfs)}] {p.name}")
        try:
            text = extract_text(str(p))
            if not text.strip():
                _c("         -> empty (no text extracted)", "red")
                continue
            raw, err = parse_document(text)
            if err:
                _c(f"         -> LLM error: {err}", "red")
                continue
            model, _, verr = parse_and_validate(raw)
            if verr or model is None:
                _c(f"         -> validation error: {verr}", "red")
                continue
            _c(f"         -> OK: {model.document_type} | "
               f"{len(model.containers)} container(s) | TAN={model.tan_number or '-'}",
               "green")
            ok_count += 1
        except Exception as e:
            _c(f"         -> crash: {type(e).__name__}: {e}", "red")

    _c(f"\n  Dry run: {ok_count}/{len(pdfs)} succeeded (no data written).\n", "bold")
    return 0 if ok_count == len(pdfs) else 1


# ─── Launcher (dashboard) ────────────────────────────────────────────────────

def _free_port(start: int = 8501) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def run_app() -> int:
    _banner()
    _c("\n  [1/3] Verifying environment...", "bold")
    if not _check_python() or not _check_deps():
        _c("\n  Environment not ready. Run `python main.py --check` for details.\n", "red")
        return 1

    _c("\n  [2/3] Checking Ollama (optional but required for PDF parsing)...", "bold")
    _check_ollama()

    _c("\n  [3/3] Starting dashboard...", "bold")
    _check_data_dirs()

    port = _free_port(8501)
    url = f"http://localhost:{port}"
    _c(f"\n  Dashboard URL: {url}", "green")
    _c("  Press Ctrl+C in this window to stop.\n", "yellow")

    # Open browser shortly after Streamlit boots
    try:
        import threading
        def _opener():
            time.sleep(3.0)
            webbrowser.open(url)
        threading.Thread(target=_opener, daemon=True).start()
    except Exception:
        pass

    args = [
        sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--theme.base", "dark",
        "--theme.primaryColor", "#6366F1",
        "--theme.backgroundColor", "#0B1020",
        "--theme.secondaryBackgroundColor", "#141A2E",
        "--theme.textColor", "#E6E9F2",
    ]
    try:
        return subprocess.call(args)
    except KeyboardInterrupt:
        _c("\n  Stopped by user.", "yellow")
        return 0
    except Exception as e:
        _c(f"\n  Failed to launch Streamlit: {e}", "red")
        return 1


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(prog="bruns", description="BRUNs Logistics launcher")
    parser.add_argument("--check", action="store_true", help="Run environment sanity checks and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Parse PDFs in data/input without writing to DB.")
    args = parser.parse_args()

    if args.check:
        return run_checks()
    if args.dry_run:
        return run_dry()
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
