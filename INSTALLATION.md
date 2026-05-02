# Installation Guide

How to install BRUNs Document Intelligence Platform on a clean machine.

---

## TL;DR

**Windows:**
```cmd
git clone https://github.com/Brvetr4ve1er/BRUNs-logistics-data-scraper.git
cd BRUNs-logistics-data-scraper
INSTALL.bat
START_APP.bat
```

**Linux / macOS:**
```bash
git clone https://github.com/Brvetr4ve1er/BRUNs-logistics-data-scraper.git
cd BRUNs-logistics-data-scraper
chmod +x install.sh start.sh
./install.sh
./start.sh
```

The browser opens to `http://localhost:7845/`.

---

## Prerequisites

| Requirement | Why | How |
|-------------|-----|-----|
| **Python 3.10+** | Codebase uses `int \| None` type hints, modern dataclass syntax | [python.org/downloads](https://www.python.org/downloads/) — check "Add to PATH" on Windows |
| **Git** | Cloning the repo | [git-scm.com](https://git-scm.com/) |
| **~5 GB disk** | Python deps (1 GB) + Ollama llama3 model (4.7 GB) + bundled Tesseract data | — |
| **Ollama** *(runtime)* | Local LLM that powers extraction. Without it the UI runs but uploads fail | [ollama.com/download](https://ollama.com/download) |
| **Tesseract OCR** *(runtime)* | Scanned-PDF / image OCR fallback when PyMuPDF can't extract text | Auto-installed by `INSTALL.bat`, or `brew install tesseract` / `apt install tesseract-ocr` |

The installer scripts handle each of these. The list above is what they assume.

---

## What `INSTALL.bat` / `install.sh` does

7 idempotent steps. Re-running is safe — every check is a no-op when the
state is already correct.

| Step | Action | Output |
|------|--------|--------|
| 1 | Detect Python ≥ 3.10 on PATH | Aborts with download URL if missing |
| 2 | Create `.venv/` virtual environment | Skipped if it already exists |
| 3 | `pip install -r requirements.txt` into the venv | All transitive deps resolved |
| 4 | Locate Tesseract (bundled → system → install) and download `eng/fra/ara` language packs into `tessdata/` | Each `.traineddata` ~10–30 MB, fetched from `tesseract-ocr/tessdata` on GitHub |
| 5 | Probe Ollama at `http://localhost:11434`; offer to `ollama pull llama3` if missing | Warning only — install continues |
| 6 | Create `data/`, `data/input/`, `data/logs/`, `data/vector/`, `data/exports/` | Empty directories |
| 7 | Run `core.storage.db.init_schema()` then `core.storage.migrations.run_migrations()` for both databases | Creates `logistics.db` + `travel.db` ready for upload |

After step 7 the platform is fully bootstrapped. The first `START_APP.bat`
launch does **not** call the installer again — it only re-runs if `.venv/`
goes missing.

---

## What `START_APP.bat` / `start.sh` does

| Check | Failure handling |
|-------|------------------|
| Running from project root (`core/api/server.py` exists) | Aborts with "wrong directory" error |
| `.venv/` exists | Offers to run installer |
| `flask`, `pydantic`, `chromadb` import successfully | Re-runs installer to repair |
| Ollama is reachable | Warns, prompts to continue anyway |
| Port 7845 is free | Aborts with `netstat` / `lsof` hint |

On success: opens the browser at `http://localhost:7845/` after 2 s and
runs `python -m core.api.server` in the foreground.

---

## Manual install (if scripts don't work)

```bash
# 1. Python venv
python -m venv .venv

# 2. activate
#    Windows:
.venv\Scripts\activate
#    Linux/macOS:
source .venv/bin/activate

# 3. dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Tesseract — install system-wide:
#    Windows:  https://github.com/UB-Mannheim/tesseract/releases  (or run install_tesseract.bat)
#    macOS:    brew install tesseract
#    Linux:    sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara

# 5. Tesseract language packs (only if not bundled by your install)
mkdir -p tessdata
for lang in eng fra ara; do
  curl -fL -o "tessdata/${lang}.traineddata" \
    "https://github.com/tesseract-ocr/tessdata/raw/main/${lang}.traineddata"
done

# 6. Ollama
#    Install from: https://ollama.com/download
ollama pull llama3

# 7. data dirs + db init
mkdir -p data/input/logistics data/input/travel data/logs data/vector data/exports
python -c "from core.storage.db import init_schema; init_schema('data/logistics.db'); init_schema('data/travel.db')"
python -c "from core.storage.migrations import run_migrations; run_migrations('data/logistics.db'); run_migrations('data/travel.db')"

# 8. Launch
python -m core.api.server
```

---

## Troubleshooting

### "Python is not on PATH" / "python: command not found"

- **Windows:** Re-run the Python installer and tick **Add python.exe to PATH**.
  Or use `py -3.12` instead of `python` everywhere (`py` is the launcher
  installed by python.org).
- **macOS:** `brew install python@3.12`, then your shell rc file probably
  needs `export PATH="/opt/homebrew/bin:$PATH"`.
- **Linux:** `sudo apt install python3.12 python3.12-venv` (Ubuntu/Debian).

### "Microsoft Visual C++ 14.0 or greater is required"

Some pinned wheels (notably `chromadb`'s tokenizer) need a C compiler if a
prebuilt wheel isn't available for your Python version.

- **Easy fix:** stick to Python **3.12** instead of 3.13/3.14 — wheels are
  available for everything pinned in `requirements.txt`.
- **Manual fix:** install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  with the "Desktop development with C++" workload checked.

### "tesseract is not installed or it's not in your PATH"

The Python `pytesseract` package finds Tesseract via the `tesseract` exe.
After install, verify with `tesseract --version`. If installed but not on
PATH:

- **Windows:** the bundled `install_tesseract.bat` puts it at
  `C:\Program Files\Tesseract-OCR\`. Add that directory to PATH or set
  `pytesseract.pytesseract.tesseract_cmd` (the app already does this
  automatically).
- **Linux/macOS:** `which tesseract` should return a path. If empty,
  the package manager install didn't finish.

### "OperationalError: no such column" on first upload

The migration runner didn't complete. Re-run:
```bash
python -c "from core.storage.migrations import run_migrations; print(run_migrations('data/logistics.db'))"
```
Should print a list of newly applied migrations or `[]` if all are already
in place. If it errors, the live DB is in an unexpected state — restore
the most recent `data/logistics.db.pre-cleanup-*.bak` backup.

### "LLM not reachable" or "Connection refused on 11434"

Ollama isn't running.
```bash
ollama serve   # start the daemon (or restart the Ollama Desktop app)
ollama list    # confirm llama3 is there
ollama pull llama3   # if not
```
Then click **⚙ LLM** in the top-right of the UI and verify "Test connection".

### Port 7845 already in use

Another BRUNs instance (or unrelated process) holds the port.

**Windows:**
```cmd
netstat -aon | findstr :7845
taskkill /F /PID <pid>
```

**Linux/macOS:**
```bash
lsof -iTCP:7845 -sTCP:LISTEN
kill <pid>
```

Or change the port: `set BRUNS_API_PORT=7846` (Windows) /
`export BRUNS_API_PORT=7846` (bash) before launching.

### CORS blocked when Power BI is on a different machine

By default the app accepts requests only from `localhost` / `127.0.0.1`.
For LAN-machine access, set the env var before launching:
```cmd
set BRUNS_CORS_ORIGINS=http://10.0.0.5:*,http://192.168.1.20:*
START_APP.bat
```
(Comma-separated explicit origins. Wildcards in path/port are not regex-supported here.)

### "ImportError: DLL load failed" on Windows

A 32-bit Python is trying to load a 64-bit C extension (or vice versa).
Re-install Python from python.org choosing the **64-bit** installer, then
delete `.venv/` and re-run `INSTALL.bat`.

### App runs, but extracted data is wrong / extraction is hallucinated

Ollama is using a too-small or non-instruct model. Check **⚙ LLM** modal
and verify the active model is `llama3` (8B Instruct), not a tiny variant.
The platform's prompts assume an 8B-class instruct model.

---

## Uninstall / reset to clean state

To wipe everything except the source code:
```bash
# Delete the venv, runtime data, and all generated files.
# Windows:
rmdir /s /q .venv data tessdata
# Linux/macOS:
rm -rf .venv data tessdata
```
Then re-run `INSTALL.bat` / `install.sh` to rebuild.

To completely remove BRUNs from the machine, also:
- Uninstall Tesseract via Windows "Add or remove programs" (or `brew uninstall tesseract` / `apt remove tesseract-ocr`)
- Uninstall Ollama via the same mechanism (or remove `~/.ollama` directory)
- Delete the cloned repository directory

---

## What gets installed where

```
<project>/
  .venv/                  Python virtual environment (gitignored)
    Scripts/ or bin/
    Lib/site-packages/    All Python deps
  tessdata/               (gitignored, populated by installer)
    eng.traineddata
    fra.traineddata
    ara.traineddata
  data/                   (gitignored, runtime)
    logistics.db          Created by init_schema + migrations
    travel.db             Same
    input/                Uploaded PDFs awaiting processing
    logs/                 bruns.log + rotation
    vector/               ChromaDB persistence
    exports/              Generated XLSX/CSV
  core/api/static/        Vendored UI assets (in the repo, no download needed)
    tailwind.min.js
    daisyui.min.css
    htmx.min.js
    chart.min.js
```

System-level:
```
C:\Program Files\Tesseract-OCR\        (Windows, if installed via install_tesseract.bat)
/usr/bin/tesseract                     (Linux apt)
/opt/homebrew/bin/tesseract            (macOS Homebrew)
~/.ollama/                             Ollama models, including llama3 (~4.7 GB)
```
