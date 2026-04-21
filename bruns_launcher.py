"""
BRUNs Logistics — Standalone EXE entry point.

When run as a PyInstaller bundle:
  1. Sets up sys.path to point at the bundled app files
  2. Starts a Streamlit server on a free port
  3. Opens the browser automatically

This file is referenced by bruns.spec as the Analysis entry point.
"""
import os
import sys
import socket
import subprocess
import time
import webbrowser
import threading
from pathlib import Path


def _get_base_dir() -> Path:
    """Return the directory containing the bundled app files."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running normally (dev mode)
        return Path(__file__).parent


def _find_free_port(start: int = 8501) -> int:
    """Find an available TCP port starting from `start`."""
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start  # fallback


def _open_browser(url: str, delay: float = 2.5):
    """Open browser after a short delay to let Streamlit start."""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    base = _get_base_dir()

    # ── PATH setup ────────────────────────────────────────────────────────────
    # Add base dir to sys.path so all our modules are importable
    sys.path.insert(0, str(base))

    # ── Data directories ──────────────────────────────────────────────────────
    # When frozen, write mutable data next to the .exe, not inside the bundle
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        data_dir = exe_dir / "data"
    else:
        data_dir = base / "data"

    (data_dir / "input").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)

    # Patch config to use absolute data paths
    os.environ["BRUNS_DATA_DIR"] = str(data_dir)

    # ── Port selection ────────────────────────────────────────────────────────
    port = _find_free_port(8501)
    url  = f"http://localhost:{port}"

    # ── Console banner ────────────────────────────────────────────────────────
    print("\n" + "═" * 52)
    print("  BRUNs Logistics Dashboard — Phase 3")
    print("═" * 52)
    print(f"  Dashboard: {url}")
    print(f"  Data dir:  {data_dir}")
    print("  Press Ctrl+C to stop")
    print("═" * 52 + "\n")

    # ── Open browser ──────────────────────────────────────────────────────────
    _open_browser(url, delay=3.0)

    # ── Launch Streamlit ──────────────────────────────────────────────────────
    # When frozen, streamlit CLI is bundled; we import it directly instead
    app_script = str(base / "app.py")

    streamlit_args = [
        "streamlit", "run", app_script,
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--theme.base", "dark",
        "--theme.primaryColor", "#6366F1",
        "--theme.backgroundColor", "#0B1020",
        "--theme.secondaryBackgroundColor", "#141A2E",
        "--theme.textColor", "#E6E9F2",
    ]

    if getattr(sys, "frozen", False):
        # Inside bundle: use the bundled streamlit module directly
        from streamlit.web import cli as stcli
        sys.argv = streamlit_args
        stcli.main()
    else:
        # Dev mode: spawn as subprocess
        subprocess.run(streamlit_args)


if __name__ == "__main__":
    main()
