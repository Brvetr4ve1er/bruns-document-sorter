# Healthcheck — All the Ways This App Could Break on Another Computer

A systematic audit of every failure mode I could find when running the app on
a fresh machine. Findings are ranked by severity, with the **actual root
cause of your friend's "internal server error"** at the top.

---

## TL;DR — What was breaking your friend's machine

**`*.html` was in `.gitignore`.** This single line silently excluded **all 36
templates** from every fresh clone. Flask started fine, the browser hit `/`,
Jinja2 raised `TemplateNotFound: mode_picker.html`, Flask caught that and
returned the generic **"Internal Server Error"** page. There was no specific
error visible to the user because Flask only shows tracebacks in debug mode.

This has been fixed. All 36 templates are now in git, and the diagnostic
check explicitly verifies them on every run.

---

## Why would the templates folder break?

Flask resolves templates via `app = Flask(__name__)` → looks in
`<package_dir>/templates/`. The folder lookup itself is robust. What broke
on the friend's machine was simpler: **the folder existed but was empty**
because git never tracked the `.html` files. From Flask's perspective
everything imports correctly; only on the first `render_template()` does
Jinja2 fail.

Other ways the templates folder *could* break (none of which were the cause
this time but are worth knowing):

1. **Encoding mismatch** — if a template contains non-UTF-8 bytes
   (e.g. cp1252 from a Windows editor), `template.render()` raises a
   `UnicodeDecodeError` that becomes a 500. We checked: all 36 templates
   are valid UTF-8, no BOM.
2. **Case-sensitive filename mismatch on Linux** — Windows treats
   `Mode_Picker.html` and `mode_picker.html` as the same file; Linux does
   not. We use lowercase consistently in `render_template()` calls and on
   disk, so this isn't an issue today.
3. **Jinja2 inheritance broken** — every operational template extends
   `base.html`. If `base.html` itself is missing, every page fails. The
   diagnostic checks for it explicitly.
4. **Wrong working directory** — if Flask's template loader were
   misconfigured to use `cwd`, running from a different directory would
   break it. We use the package-relative loader, so this is safe.

---

## What can cause "Internal Server Error" on first launch?

Internal Server Error = HTTP 500 = unhandled Python exception in a route
handler. Sources, in order of how likely each one is on a fresh install:

| Source | What you see | Diagnosed by |
|--------|--------------|--------------|
| Templates missing (the bug above) | `TemplateNotFound: mode_picker.html` | `check_templates()` |
| Database tables missing | `sqlite3.OperationalError: no such table: shipments` | `check_databases()` |
| Migration partially applied | `OperationalError: no such column: reviewed_at` | `check_migrations()` |
| Tesseract called but missing | `pytesseract.TesseractNotFoundError` (only if upload) | `check_tesseract()` |
| ChromaDB version mismatch | `chromadb.errors.IncompatibleSchemaError` | manual: `rm -rf data/vector` |
| Ollama unreachable on upload | timeout in `_generate_sql_from_question()` (NL2SQL) | `check_ollama()` |
| Cwd-relative log dir not writable | `PermissionError: [Errno 13] data/logs/bruns.log` | `check_data_dirs()` |
| Encoding crash on French chars | `UnicodeEncodeError: 'charmap'` (cp1252 console) | the launcher now sets `PYTHONUTF8=1` |
| `init_prompts()` failed at startup | extraction returns `"No prompt registered"` | check `data/logs/bruns.log` |
| Stale `.venv` after Python upgrade | `ImportError: DLL load failed` | re-create venv |
| Port already in use | `OSError: [Errno 10048] Only one usage of each socket` | `check_server_startup()` (sort of) |
| Werkzeug + non-ASCII filename | `UnicodeDecodeError` on upload | `secure_filename` strips non-ASCII |

Run `DIAGNOSE.bat` (or `./diagnose.sh`) to test all of the above in one shot.

---

## Things we hadn't accounted for

### 1. `.gitignore` had `*.html` — the showstopper

**Why it happened**: probably copy-pasted from a Tesseract-bundle ignore
list (the man-page documentation files that Tesseract installs are all
`*.1.html` / `*.5.html`). The author meant to ignore those specific files
but used the broad glob.

**Fix applied**: `.gitignore` rewritten with per-file rules for the Tesseract
docs, and explicit comments warning against broad globs. All 36 templates
now in git.

**Diagnostic added**: `check_templates()` in `core/diagnostics.py` cross-checks
every `render_template()` call in `server.py` against actual files on disk
and reports any mismatch as a `[FAIL]` entry.

---

### 2. `pandas==3.0.2` had no Python 3.10 wheel

**The pin was tighter than the install script's claimed minimum.** Verified
on PyPI: pandas 3.0.2 ships wheels only for cp311–cp314. A fresh machine with
Python 3.10 (which the installer accepted) would hit pip falling back to
source build, which needs Visual C++ Build Tools — a 6 GB IDE install most
home machines don't have.

**Fix applied**:
- `requirements.txt` switched to `pandas>=2.2,<4`
- `INSTALL.bat` and `install.sh` raised the floor to Python 3.11
- All other pins relaxed to `~=` (compatible release) so transitive
  resolution can find ABI-matching wheels for the host Python.

---

### 3. `configure_logging()` used cwd-relative `data/logs`

**Symptom**: if the launcher was started from a Windows shortcut whose
"Start in" directory was wrong, or if the user ran `python -m core.api.server`
from any folder other than the repo root, the log file would either fail to
open (PermissionError on a read-only system folder) or get scattered around
the filesystem.

**Fix applied**: `core/logging_config.py` now resolves the log dir from
`Path(__file__).resolve().parent.parent / "data" / "logs"` — the canonical
location regardless of cwd.

---

### 4. Browser opened before the server was listening

**Symptom**: cold first launch on a slow disk could take 5–8 seconds for
Python to import all of `pandas`, `chromadb`, `pymupdf`. Meanwhile,
`START_APP.bat` opened the browser after a fixed 2-second delay. The user
saw "site can't be reached" then refreshed and it worked — confusing.

**Fix applied**: launcher now polls `/api/status` for up to 30 seconds
before opening the browser. Same fix in `start.sh` using `curl`.

---

### 5. Database `source_file` columns embed absolute paths from THIS machine

**Symptom**: If anyone copies `data/logistics.db` to another machine, every
`/files/<module>/<doc_id>` route returns 404 because the absolute paths
(`C:\Users\ROG STRIX\Documents\...`) don't exist there. The dashboard works
(no file access), but clicking "view PDF" fails silently.

**Status**: not blocking your friend's case (they'd start with empty DBs from
the installer). Documented in `INSTALLATION.md`. The proper fix is to store
relative paths in the DB and resolve against `BRUNS_DATA_DIR` at request
time. Tracked as a future improvement.

---

### 6. CRLF vs LF line endings

The repo has `.gitignore: ASCII text, with CRLF line terminators`. On a
fresh Linux clone via git, line endings get auto-converted by core.autocrlf,
which can occasionally produce broken shell scripts. We mitigate by:

- Including a `# !/usr/bin/env bash` shebang on every shell script
- `chmod +x install.sh start.sh diagnose.sh` in install instructions
- Using `set -euo pipefail` so any silent CRLF-induced parse failure becomes
  visible immediately

We could ship a `.gitattributes` to force LF for `*.sh`. Not done yet.

---

### 7. Console encoding crashes on non-UTF-8 terminals

Windows cmd.exe defaults to cp1252. Any French character (é, è, à) or
Arabic byte in a log line caused `UnicodeEncodeError` and silently killed
log writes — though logs to file (`bruns.log`) are always UTF-8.

**Fix applied**:
- `START_APP.bat` and `start.sh` now `set PYTHONUTF8=1` and
  `PYTHONIOENCODING=utf-8` before launching
- `core/diagnostics.py` has a `_safe()` wrapper that downgrades box-drawing
  + emoji to ASCII when stdout encoding isn't UTF-8

---

### 8. Werkzeug `secure_filename` strips non-ASCII

If an Algerian operator uploads `Réservé.pdf`, Werkzeug renames it to
`Reserve.pdf` before saving. This is intentional (security: prevents
directory traversal / filesystem-illegal characters) but undocumented.

**Status**: not a bug — documented behavior. Worth knowing for support
calls when an operator says "I uploaded the file with the right name".

---

### 9. `pytesseract` runs `tesseract --version` once per OCR call (was)

Already fixed under TD6 — the result is module-cached.

---

### 10. ChromaDB persistence directory not portable across versions

ChromaDB writes its on-disk index in a version-specific format. If the
recipient's `data/vector/` directory was created with a different ChromaDB
version, the new version refuses to open it. Symptom:
`chromadb.errors.IncompatibleSchemaError`.

**Workaround documented**: delete `data/vector/` and let the next document
upload recreate it. The vector index is a derived artifact — losing it
costs nothing except a re-embedding pass.

---

### 11. Ollama URL hardcoded to localhost

`_NL2SQL_SCHEMA` and the LLM client default to `http://localhost:11434`.
If the recipient runs Ollama on a different host (LAN-shared Ollama
deployment, GPU box), they need to set `OLLAMA_URL` env var. **Already
supported** but undocumented. Added to `INSTALLATION.md`.

---

### 12. `init_prompts()` failure is logged as warning, not fatal

If the prompt registration fails at startup (e.g. someone broke the
modules/* prompt syntax), the server boots fine, but every upload returns
`No prompt registered for module 'logistics' and doc_type 'UNKNOWN'`. The
warning is buried in `bruns.log`.

**Status**: surfaced by `check_server_startup()` in the diagnostic, which
imports the app and would catch a syntax error. Not changed to fatal because
that would prevent the operator browsing existing data when prompts are
broken.

---

## What the diagnostic now catches

`python -m core.diagnostics` runs **51 checks** (was 49 before this round).
Run `DIAGNOSE.bat` (or `./diagnose.sh`) and it prints a labeled pass/fail
report plus writes `data/logs/diagnose.txt` for sharing.

| Section | Checks |
|---------|--------|
| Python | Version, executable path |
| Environment | ROOT, PWD, BRUNS_* env vars |
| Repository layout | 12 critical files present |
| **Jinja2 templates** | **NEW**: every `render_template()` reference exists |
| Python dependencies | All 13 pip packages with version |
| Tesseract OCR | Binary location + 3 language packs |
| Ollama | Daemon reachability + llama3 model |
| Runtime directories | 7 data/ subdirs + writability |
| SQLite databases | Table presence in both DBs |
| Schema migrations | Applied state of all 5 migrations |
| Flask app startup | Import + GET / + GET /logistics |

---

## Remaining gaps (not yet fixed)

| Item | Severity | Notes |
|------|----------|-------|
| DB `source_file` is absolute path | Medium | Only matters if someone copies a populated `data/` between machines. Fix would require migration + path-resolution helper. |
| No `.gitattributes` for line endings | Low | Shell scripts use `set -euo pipefail` so silent CRLF damage becomes visible. |
| Diagnostic doesn't test an upload end-to-end | Medium | Would require seeding a fixture PDF + Ollama running. Out of scope for "is the install correct" check. |
| Diagnostic doesn't probe disk space | Low | A fresh `ollama pull llama3` needs 5 GB free; we don't check. |
| No CSRF on state-changing endpoints | Medium | Tracked as TD10 in `docs/09-ROADMAP-IMPROVEMENTS.md`; deferred to multi-user auth. |
| Fixed Werkzeug `secure_filename` strips French | Low | Documented; security-sensible default. |

---

## How to verify your friend's PC is now fixed

Have him:

1. `git pull` (gets the templates and the new .gitignore)
2. `INSTALL.bat` — re-runs idempotently, picks up new `pandas>=2.2,<4` pin
3. `DIAGNOSE.bat` — should print all green except possibly Ollama warning
4. `START_APP.bat` — server launches, browser opens at `localhost:7845`

If anything is still red, send `data/logs/diagnose.txt`. Every check is
labeled and includes its own remediation hint.
