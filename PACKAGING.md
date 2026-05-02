# Packaging BRUNs for Distribution

How to ship BRUNs to a teammate, customer, or another machine — three
strategies in order of recommended use.

| Strategy | Audience | Setup on target | Bundle size | Maintenance cost |
|----------|----------|-----------------|-------------|------------------|
| **A. Portable ZIP** (recommended) | Operators, non-technical users | Unzip + double-click START.bat | 800 MB – 1.2 GB | Low — re-build with `MAKE_PORTABLE.bat` after each release |
| **B. Git clone + INSTALL.bat** | Developers, ops engineers | Clone → run installer → wait | small repo (~10 MB) + ~5 GB downloads | Low |
| **C. PyInstaller `.exe`** | One-file distribution | Single `.exe` double-click | 300–500 MB | High — PyInstaller breaks on every dependency upgrade |

For "my friend can't run it on his PC", **strategy A** (portable ZIP) is what
solves the problem and is what `MAKE_PORTABLE.bat` produces.

---

## Strategy A — Portable ZIP (recommended)

### What you ship

A single `BRUNs-Portable.zip` containing:

- `python\` — full Python 3.12 embeddable distribution (no install needed)
- `python\Lib\site-packages\` — all 13 pip dependencies pre-installed
- `tesseract_bin\` — bundled Tesseract OCR (Windows binaries + DLLs)
- `tessdata\` — language packs (eng, fra, ara)
- `core\`, `modules\` — application source code
- `data\` — pre-initialized empty SQLite databases + dirs
- `START.bat` — one-click launcher
- `DIAGNOSE.bat` — diagnostic script
- `README.txt` — operator instructions

### How to build

```cmd
MAKE_PORTABLE.bat
```

The script:
1. Downloads Python 3.12 embeddable from python.org (~10 MB)
2. Patches `python._pth` to enable `site-packages`
3. Bootstraps pip, installs all `requirements.txt` deps into `python\Lib\site-packages\`
4. Copies `core/`, `modules/`, `requirements.txt` into the bundle
5. Copies `tesseract_bin/` and `tessdata/` if they exist locally
6. Creates `data/` with pre-initialized SQLite databases (migrations run)
7. Writes `START.bat`, `DIAGNOSE.bat`, `README.txt`
8. Optionally zips into `dist\BRUNs-Portable.zip`

### What the recipient does

```
1. Unzip BRUNs-Portable.zip somewhere (Desktop, USB stick, anywhere).
2. Install Ollama from https://ollama.com/download (one-time, ~500 MB).
3. Run: ollama pull llama3   (one-time, ~4.7 GB).
4. Double-click START.bat.
```

That's it. No Python install, no pip, no admin rights.

### Why Ollama isn't bundled

Ollama is too large to fit in a sane ZIP:
- Ollama runtime: ~500 MB
- llama3 model: ~4.7 GB
- GPU drivers / CUDA: may be required for performance
- Total: ~5 GB minimum, plus driver-install logic that can't ship as data

Instead, the bundle's `START.bat` warns when Ollama isn't reachable and
gives the install URL.

### What's left for the recipient

| Task | Required? | Effort |
|------|-----------|--------|
| Unzip the bundle | yes | < 1 minute |
| Install Ollama | yes (for document processing) | 5 minutes |
| Pull llama3 model | yes | 10–30 minutes (depends on bandwidth) |
| Install Tesseract | **no** — bundled | — |
| Install Python | **no** — bundled | — |
| Install pip deps | **no** — bundled | — |

### Limitations

- **Windows only.** The Python embeddable distribution is per-OS; for Linux
  use a `.tar.gz` of a relocatable virtualenv, or just `git clone +
  install.sh` (strategy B).
- **64-bit only.** No 32-bit support.
- **Ollama is external.** Listed above.
- **First run creates new databases.** If you want to ship data, copy a
  pre-populated `logistics.db` / `travel.db` into `dist\BRUNs-Portable\data\`
  AFTER `MAKE_PORTABLE.bat` has finished.

---

## Strategy B — Git clone + installer (simplest for developers)

### What you ship

Just the repo URL.

### What the recipient does

```cmd
git clone https://github.com/Brvetr4ve1er/BRUNs-logistics-data-scraper.git
cd BRUNs-logistics-data-scraper
INSTALL.bat
START_APP.bat
```

The installer is fully scripted — see [INSTALLATION.md](INSTALLATION.md)
for what it does and how to troubleshoot. This is the same path used during
development.

### Pros

- Smallest "shipping" payload (just a git URL)
- Updates are `git pull` away
- Source is editable
- Works on Linux + macOS too (`./install.sh && ./start.sh`)

### Cons

- Recipient needs Python 3.10+ pre-installed
- Pip download takes 3–5 minutes on first run
- Tesseract install requires admin rights on Windows
- Not suitable for non-technical end users

---

## Strategy C — PyInstaller single `.exe`

This is **not currently supported** out of the box. The repository ships
with a `tesseract_bin\bruns.spec` file that hints at a previous attempt,
but PyInstaller has known compatibility issues with several of our deps:

- **chromadb** — embeds SQLite + onnxruntime; `--collect-all chromadb` needed
- **PyMuPDF** — has CFFI bindings that PyInstaller often misses
- **pytesseract** — needs Tesseract binary at a known path; bundling is fiddly
- **passporteye + scipy + skimage** — pulls in a 200+ MB numerical stack

If you really need a single `.exe`, the recipe is:

```cmd
pip install pyinstaller
pyinstaller ^
    --name BRUNs ^
    --onefile ^
    --noconsole ^
    --add-data "core\api\templates;core\api\templates" ^
    --add-data "core\api\static;core\api\static" ^
    --add-data "modules;modules" ^
    --add-data "tessdata;tessdata" ^
    --add-data "tesseract_bin;tesseract_bin" ^
    --collect-all chromadb ^
    --collect-all pytesseract ^
    --hidden-import=core.business.charts ^
    --hidden-import=core.business.demurrage ^
    --hidden-import=core.business.completeness ^
    --hidden-import=core.business.exports ^
    --hidden-import=core.business.forms ^
    --hidden-import=core.business.bbox ^
    --hidden-import=core.business.nlsql ^
    --hidden-import=core.business.reconcile ^
    --hidden-import=core.business.stats ^
    core\api\server.py
```

Result: `dist\BRUNs.exe`, ~400 MB, ~10 second startup.

### Why we don't recommend it

1. **Brittle.** Every `requirements.txt` bump risks a new PyInstaller
   collection issue. Running `pyinstaller` is a manual debug session.
2. **Slow startup.** PyInstaller unpacks itself to `%TEMP%` on every launch.
3. **Antivirus false positives.** Single-file `.exe`s built by PyInstaller
   are routinely flagged by Defender/SmartScreen. Code signing helps but
   costs $200–$400/year.
4. **No easier than Portable ZIP.** Both produce a "double-click and it
   runs" deliverable. The portable ZIP is cleaner because it's transparent —
   the recipient can see and edit individual files if they need to.

---

## Strategy D — Docker (Linux-only, advanced)

Useful for server deployment but overkill for desktop operators.

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y \
    tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -c "from core.storage.db import init_schema; \
    from core.storage.migrations import run_migrations; \
    init_schema('data/logistics.db'); init_schema('data/travel.db'); \
    run_migrations('data/logistics.db'); run_migrations('data/travel.db')"
EXPOSE 7845
CMD ["python", "-m", "core.api.server"]
```

```bash
docker build -t bruns:latest .
docker run -p 7845:7845 -v $(pwd)/data:/app/data bruns:latest
```

Ollama still runs externally — point at it with
`-e OLLAMA_URL=http://host.docker.internal:11434`.

We don't ship a `Dockerfile` in the repo because:
- Windows is the primary target (native or via WSL2)
- Operators don't want to install Docker
- It doesn't solve the "run on my friend's PC" use case

---

## Releasing a new version

When you ship an update, the upgrade story per strategy is:

| Strategy | How recipient updates |
|----------|----------------------|
| Portable ZIP | Send new ZIP. They overwrite the old folder, keeping `data\`. |
| Git clone | `git pull && INSTALL.bat` (idempotent — only does what's needed). |
| PyInstaller `.exe` | Replace the `.exe`. |
| Docker | `docker pull` + `docker run`. |

For Portable ZIP specifically, recipients should keep their `data\` folder
between upgrades. The launcher's bundled migrations runner handles any
schema changes automatically when they next start the app.

---

## Build pipeline (for maintainers)

The repo has scripts for every shipping path:

| Script | Purpose | Output |
|--------|---------|--------|
| `INSTALL.bat` / `install.sh` | First-run installer | Populated `.venv/`, `tessdata/`, initialised `data/` |
| `START_APP.bat` / `start.sh` | Launcher with self-repair | Browser at `localhost:7845` |
| `DIAGNOSE.bat` / `diagnose.sh` | Environment audit | Prints + writes `data/logs/diagnose.txt` |
| `MAKE_PORTABLE.bat` | Build portable ZIP | `dist/BRUNs-Portable/` + `dist/BRUNs-Portable.zip` |
| `install_tesseract.bat` | Auto-install Tesseract on Windows | Tesseract at `C:\Program Files\Tesseract-OCR\` |

For a release:

1. Run `pytest tests/ -q` — must be 5 passed / 1 skipped.
2. Run `MAKE_PORTABLE.bat` — produces the ZIP.
3. Test the ZIP on a clean VM (or another physical machine).
4. Tag the release: `git tag v1.X.0 && git push origin v1.X.0`.
5. Upload the ZIP as a GitHub release asset.
