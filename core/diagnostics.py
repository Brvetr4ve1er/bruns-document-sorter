"""End-to-end environment diagnostics.

When a user reports "internal server error on a fresh machine" we don't have
their logs. This module runs every check that has ever caused a startup or
first-request failure and prints a verbose report. The exit code reflects the
state:

    0  — all checks passed (green)
    1  — at least one critical check failed
    2  — warnings only (app can run but with limitations)

Invoke with:
    python -m core.diagnostics
or from the launcher:
    DIAGNOSE.bat   /   ./diagnose.sh
"""
from __future__ import annotations

import os
import sys
import sqlite3
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ANSI colour helpers — Windows 10+ cmd supports them after a single VT enable.
_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_BLUE = "\033[36m"


def _enable_ansi_on_windows():
    """Switch cmd.exe into VT mode so ANSI escapes render as colours."""
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def _safe(s: str) -> str:
    """Replace non-ASCII chars on cmd.exe (cp1252) with ASCII fallbacks."""
    if sys.stdout.encoding and "utf" in sys.stdout.encoding.lower():
        return s
    # Drop the entire range of common Unicode that cp1252 can't render.
    repl = {
        "✅": "[OK]", "⚠️": "[WARN]", "❌": "[FAIL]", "ℹ️": "[INFO]",
        "→": "->",
        # Box-drawing
        "━": "=", "─": "-", "│": "|", "┃": "|",
        "┌": "+", "┐": "+", "└": "+", "┘": "+",
        "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+",
    }
    out = s
    for k, v in repl.items():
        out = out.replace(k, v)
    # Strip anything still non-encodable.
    return out.encode("ascii", "replace").decode("ascii")


# Backward-compat alias used by older lines below.
_emoji = _safe


# ─── Reporting helpers ──────────────────────────────────────────────────────

class Report:
    def __init__(self):
        self.results: list[tuple[str, str, str, str]] = []
        # status: "ok" | "warn" | "fail"

    def ok(self, name: str, detail: str = "") -> None:
        self.results.append(("ok", name, detail, ""))

    def warn(self, name: str, detail: str, fix: str = "") -> None:
        self.results.append(("warn", name, detail, fix))

    def fail(self, name: str, detail: str, fix: str = "") -> None:
        self.results.append(("fail", name, detail, fix))

    def section(self, title: str) -> None:
        self.results.append(("section", title, "", ""))

    def print(self) -> int:
        """Print the report. Return process exit code: 0 ok, 1 fail, 2 warn."""
        n_ok = n_warn = n_fail = 0
        for status, name, detail, fix in self.results:
            if status == "section":
                print()
                print(_emoji(f"{_BOLD}━━━ {name} ━━━{_RESET}"))
                continue
            if status == "ok":
                n_ok += 1
                print(_emoji(f"  {_GREEN}✅{_RESET}  {name}"))
                if detail:
                    print(f"      {detail}")
            elif status == "warn":
                n_warn += 1
                print(_emoji(f"  {_YELLOW}⚠️{_RESET}  {name}"))
                print(f"      {detail}")
                if fix:
                    print(_emoji(f"      {_BLUE}→{_RESET} {fix}"))
            else:
                n_fail += 1
                print(_emoji(f"  {_RED}❌{_RESET}  {name}"))
                print(f"      {detail}")
                if fix:
                    print(_emoji(f"      {_BLUE}→{_RESET} {fix}"))

        print()
        print(_emoji(f"{_BOLD}Summary:{_RESET}  "
                     f"{_GREEN}{n_ok} ok{_RESET}, "
                     f"{_YELLOW}{n_warn} warning(s){_RESET}, "
                     f"{_RED}{n_fail} failure(s){_RESET}"))
        if n_fail:
            return 1
        if n_warn:
            return 2
        return 0


# ─── Individual checks ──────────────────────────────────────────────────────

def check_python(r: Report) -> None:
    r.section("Python")
    v = sys.version_info
    label = f"{v.major}.{v.minor}.{v.micro}"
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        r.fail("Python version", f"Found {label}, need 3.10+",
               "Install Python 3.10 or newer from https://www.python.org/downloads/")
    else:
        r.ok("Python version", label)
    r.ok("Executable", sys.executable)


def check_repo_layout(r: Report) -> None:
    r.section("Repository layout")
    needed = [
        "core/api/server.py",
        "core/storage/db.py",
        "core/storage/migrations.py",
        "core/extraction/text_extractor.py",
        "modules/logistics/prompts.py",
        "modules/travel/prompts.py",
        "requirements.txt",
        "core/api/static/htmx.min.js",
        "core/api/static/tailwind.min.js",
        "core/api/static/daisyui.min.css",
        "core/api/static/chart.min.js",
        "core/api/templates/base.html",
    ]
    for rel in needed:
        path = ROOT / rel
        if path.exists():
            r.ok(f"  {rel}", f"{path.stat().st_size:,} bytes")
        else:
            r.fail(f"  {rel}", "missing",
                   "Re-clone the repository or check git status. UI files in core/api/static/ are committed.")


def check_templates(r: Report) -> None:
    """Verify every template referenced from server.py exists on disk.

    This was the actual root cause of the 'internal server error' on the
    friend's machine — `*.html` was previously in `.gitignore`, so all 36
    templates were silently absent from a fresh clone. Flask started fine,
    then the first request raised `jinja2.exceptions.TemplateNotFound`.
    """
    r.section("Jinja2 templates")
    templates_dir = ROOT / "core" / "api" / "templates"
    if not templates_dir.is_dir():
        r.fail("templates dir",
               f"{templates_dir} does not exist",
               "Templates directory missing — re-clone the repository.")
        return

    on_disk = sorted(p.relative_to(templates_dir).as_posix()
                     for p in templates_dir.rglob("*.html"))
    if len(on_disk) == 0:
        r.fail("template files",
               "directory exists but contains zero .html files",
               "This usually means '*.html' was in .gitignore on the clone "
               "machine. Verify .gitignore does NOT contain a bare '*.html' "
               "rule, then run: git pull")
        return
    r.ok("template files", f"{len(on_disk)} templates on disk")

    # Cross-check: every render_template() reference in server.py must exist.
    server_py = ROOT / "core" / "api" / "server.py"
    try:
        src = server_py.read_text(encoding="utf-8")
    except Exception as e:
        r.warn("server.py read", f"{e}")
        return
    import re as _re
    referenced = set(_re.findall(
        r"render_template\(\s*[\"\'](?P<n>[a-zA-Z][a-zA-Z0-9_/\.]+\.html)[\"\']", src
    ))
    missing = sorted(t for t in referenced if t not in set(on_disk))
    if missing:
        for t in missing:
            r.fail(f"  template: {t}",
                   "referenced by server.py but missing on disk",
                   "Re-clone the repository or restore the file from git.")
    else:
        r.ok("server.py template references", f"{len(referenced)} all exist on disk")


def check_dependencies(r: Report) -> None:
    r.section("Python dependencies")
    # (import_name, dist_name, label)
    # dist_name is what pip/PyPI calls the package; that's where importlib.metadata
    # looks. Avoids Flask 3.1's DeprecationWarning on `flask.__version__`.
    deps = [
        ("flask",       "flask",       "Flask"),
        ("flask_cors",  "flask-cors",  "flask-cors"),
        ("pydantic",    "pydantic",    "pydantic"),
        ("requests",    "requests",    "requests"),
        ("fitz",        "PyMuPDF",     "PyMuPDF"),
        ("pytesseract", "pytesseract", "pytesseract"),
        ("PIL",         "Pillow",      "Pillow"),
        ("passporteye", "passporteye", "passporteye"),
        ("mrz",         "mrz",         "mrz"),
        ("chromadb",    "chromadb",    "chromadb"),
        ("pandas",      "pandas",      "pandas"),
        ("openpyxl",    "openpyxl",    "openpyxl"),
        ("rapidfuzz",   "rapidfuzz",   "RapidFuzz"),
    ]
    from importlib.metadata import version as _meta_version, PackageNotFoundError
    for module, dist, label in deps:
        try:
            __import__(module)
        except ImportError as e:
            r.fail(f"  {label}", str(e),
                   "Run INSTALL.bat (or install.sh). It does pip install -r requirements.txt.")
            continue
        except Exception as e:
            r.fail(f"  {label}", f"{type(e).__name__}: {e}",
                   "Re-create the venv: delete .venv\\ then re-run INSTALL.bat")
            continue
        try:
            ver = _meta_version(dist)
        except PackageNotFoundError:
            ver = "?"
        r.ok(f"  {label}", str(ver))


def check_tesseract(r: Report) -> None:
    r.section("Tesseract OCR")
    local = ROOT / "tesseract_bin" / "tesseract.exe"
    sysw = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    syslin = Path("/usr/bin/tesseract")
    sysmac = Path("/opt/homebrew/bin/tesseract")

    where = None
    if local.exists():
        where = local
        r.ok("Tesseract binary", f"bundled at {local}")
    elif sysw.exists():
        where = sysw
        r.ok("Tesseract binary", f"system install at {sysw}")
    elif syslin.exists():
        where = syslin
        r.ok("Tesseract binary", f"{syslin}")
    elif sysmac.exists():
        where = sysmac
        r.ok("Tesseract binary", f"{sysmac}")
    else:
        # Maybe it's on PATH
        try:
            import shutil
            tess = shutil.which("tesseract")
            if tess:
                where = Path(tess)
                r.ok("Tesseract binary", f"on PATH at {tess}")
        except Exception:
            pass

    if where is None:
        r.warn("Tesseract binary",
               "not found anywhere — scanned-PDF OCR will fail",
               "Windows: run install_tesseract.bat. macOS: brew install tesseract. Linux: apt install tesseract-ocr")
        return

    # Try invoking it
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = str(where)
        v = pytesseract.get_tesseract_version()
        r.ok("Tesseract callable", f"version {v}")
    except Exception as e:
        r.fail("Tesseract callable",
               f"{type(e).__name__}: {e}",
               "Tesseract.exe found but won't run. Re-install Tesseract.")

    # Language packs
    tessdata = ROOT / "tessdata"
    for lang in ("eng", "fra", "ara"):
        f = tessdata / f"{lang}.traineddata"
        if f.exists():
            r.ok(f"  tessdata/{lang}.traineddata", f"{f.stat().st_size:,} bytes")
        else:
            r.warn(f"  tessdata/{lang}.traineddata",
                   "missing",
                   f"Download from https://github.com/tesseract-ocr/tessdata/raw/main/{lang}.traineddata into tessdata/")


def check_ollama(r: Report) -> None:
    r.section("Ollama (local LLM)")
    try:
        import requests
        url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/tags")
        if "/api/" not in url:
            url = url.rstrip("/") + "/api/tags"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            names = [m.get("name", "?") for m in models]
            r.ok("Ollama daemon", f"reachable at {url}")
            if any("llama3" in n for n in names):
                r.ok("llama3 model", f"present ({len(names)} models total)")
            else:
                r.warn("llama3 model",
                       f"not found in Ollama. Available: {', '.join(names) or '(none)'}",
                       "Run: ollama pull llama3")
        else:
            r.warn("Ollama daemon",
                   f"HTTP {resp.status_code} from {url}",
                   "Restart the Ollama desktop app or run 'ollama serve'.")
    except Exception as e:
        r.warn("Ollama daemon",
               f"unreachable ({type(e).__name__})",
               "Install Ollama from https://ollama.com/download then run: ollama pull llama3")


def check_data_dirs(r: Report) -> None:
    r.section("Runtime directories")
    for d in ("data", "data/input", "data/input/logistics", "data/input/travel",
              "data/logs", "data/vector", "data/exports"):
        p = ROOT / d
        if p.is_dir():
            r.ok(f"  {d}/")
        else:
            r.warn(f"  {d}/", "missing",
                   f"Will be auto-created on first launch, but you can pre-create with `mkdir -p {d}`")
    # Test writability
    try:
        test = ROOT / "data" / ".write_probe"
        test.parent.mkdir(parents=True, exist_ok=True)
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        r.ok("data/ is writable")
    except Exception as e:
        r.fail("data/ is writable",
               f"cannot write to data/ ({e})",
               "Check directory permissions on data/. The user running the app needs write access.")


def check_databases(r: Report) -> None:
    r.section("SQLite databases")
    from core.storage.db import init_schema, get_connection
    from core.storage.migrations import run_migrations

    for name in ("logistics.db", "travel.db"):
        path = ROOT / "data" / name
        if not path.exists():
            r.warn(f"data/{name}", "does not exist",
                   f"Run: python -c \"from core.storage.db import init_schema; init_schema('data/{name}')\"")
            continue

        # Open + verify key tables
        try:
            conn = sqlite3.connect(str(path))
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
        except Exception as e:
            r.fail(f"data/{name}",
                   f"cannot open: {e}",
                   f"Delete data/{name} and re-run INSTALL.bat")
            continue

        required = (
            {"documents", "shipments", "containers", "extraction_cache",
             "audit_log", "schema_version"}
            if name == "logistics.db"
            else {"documents", "persons", "families", "documents_travel",
                  "extraction_cache", "audit_log", "schema_version"}
        )
        missing = required - tables
        if missing:
            r.fail(f"data/{name}",
                   f"tables missing: {', '.join(sorted(missing))}",
                   f"Run: python -c \"from core.storage.db import init_schema; init_schema('data/{name}')\"")
        else:
            r.ok(f"data/{name}", f"{len(tables)} tables present")


def check_migrations(r: Report) -> None:
    r.section("Schema migrations")
    try:
        from core.storage.migrations import run_migrations
    except Exception as e:
        r.fail("import migrations module", f"{type(e).__name__}: {e}")
        return

    for name in ("logistics.db", "travel.db"):
        path = ROOT / "data" / name
        if not path.exists():
            r.warn(f"  {name}", "DB missing — skipping migrations")
            continue
        try:
            applied = run_migrations(str(path))
            if applied:
                r.ok(f"  {name}", f"applied: {applied}")
            else:
                r.ok(f"  {name}", "all migrations already applied")
        except Exception as e:
            r.fail(f"  {name}",
                   f"{type(e).__name__}: {e}",
                   "Inspect the traceback. Common cause: schema_version column type mismatch.")


def check_server_startup(r: Report) -> None:
    """Import the Flask app the same way the server does. Catches startup-time
    crashes that the user would otherwise see only as 'internal server error'.
    """
    r.section("Flask app startup")
    try:
        from core.api.server import app
        n = len(list(app.url_map.iter_rules()))
        r.ok("server.py imports", f"{n} routes registered")
    except Exception as e:
        r.fail("server.py imports",
               f"{type(e).__name__}: {e}",
               "Inspect the traceback below. This is the actual reason for the 'internal server error'.")
        traceback.print_exc()
        return

    # Test the splash route — this is what the browser hits first.
    try:
        with app.test_client() as c:
            resp = c.get("/")
            if resp.status_code == 200:
                r.ok("GET /", f"200 OK ({len(resp.data)} bytes)")
            else:
                r.fail("GET /",
                       f"HTTP {resp.status_code}",
                       "Splash page failed. See server logs at data/logs/bruns.log.")
    except Exception as e:
        r.fail("GET /",
               f"{type(e).__name__}: {e}",
               "The mode-picker route crashed. Inspect data/logs/bruns.log.")
        traceback.print_exc()
        return

    # Hit a route that touches the DB
    try:
        with app.test_client() as c:
            resp = c.get("/logistics")
            if resp.status_code == 200:
                r.ok("GET /logistics", f"200 OK ({len(resp.data)} bytes)")
            else:
                r.fail("GET /logistics",
                       f"HTTP {resp.status_code}",
                       "Logistics dashboard failed — likely DB schema mismatch. See data/logs/bruns.log.")
    except Exception as e:
        r.fail("GET /logistics",
               f"{type(e).__name__}: {e}",
               "This is the most common 'internal server error' source. Check the traceback.")
        traceback.print_exc()


def check_env_summary(r: Report) -> None:
    r.section("Environment")
    r.ok("ROOT", str(ROOT))
    r.ok("PWD", os.getcwd())
    if "BRUNS_DATA_DIR" in os.environ:
        r.ok("BRUNS_DATA_DIR", os.environ["BRUNS_DATA_DIR"])
    if "BRUNS_API_PORT" in os.environ:
        r.ok("BRUNS_API_PORT", os.environ["BRUNS_API_PORT"])
    if "BRUNS_LOGISTICS_DB" in os.environ:
        r.ok("BRUNS_LOGISTICS_DB", os.environ["BRUNS_LOGISTICS_DB"])
    if "OLLAMA_URL" in os.environ:
        r.ok("OLLAMA_URL", os.environ["OLLAMA_URL"])
    if "BRUNS_CORS_ORIGINS" in os.environ:
        r.ok("BRUNS_CORS_ORIGINS", os.environ["BRUNS_CORS_ORIGINS"])


# ─── Entry point ────────────────────────────────────────────────────────────

def run() -> int:
    _enable_ansi_on_windows()
    print(_emoji(f"\n{_BOLD}BRUNs Diagnostic{_RESET}"))
    print(_emoji(f"{_BOLD}━━━━━━━━━━━━━━━━{_RESET}\n"))
    print("If the app shows 'internal server error', the failures below tell you")
    print("exactly what is wrong. Re-run after fixing each one.")

    r = Report()
    check_python(r)
    check_env_summary(r)
    check_repo_layout(r)
    check_templates(r)              # <-- NEW: catches the .gitignore *.html bug
    check_dependencies(r)
    check_tesseract(r)
    check_ollama(r)
    check_data_dirs(r)
    check_databases(r)
    check_migrations(r)
    check_server_startup(r)

    return r.print()


if __name__ == "__main__":
    sys.exit(run())
