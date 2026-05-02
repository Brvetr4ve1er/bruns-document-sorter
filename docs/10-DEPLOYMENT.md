# 10 — Deployment and Operations

How to install, run, troubleshoot, and back up BRUNs.

## Target environment

- Windows 10 / 11 (primary; only supported platform today)
- 16 GB RAM minimum (Ollama with llama3 fits in ~8 GB; the app + Power BI
  fits in the rest)
- 20 GB free disk (Ollama models ~5 GB, app ~500 MB, transient PDF storage)
- A modern x86_64 CPU (no GPU required; GPU accelerates Ollama but is optional)
- Local network access (for Power BI to hit the BI bridge over LAN)

## Install procedure

### Prerequisites (one-time)

1. **Python 3.11 or higher** from https://python.org. Tick "Add to PATH" during install.
   *(The project currently runs on 3.14 — any 3.11+ works.)*
2. **Tesseract OCR**: A bundled binary lives in `tesseract_bin/` and bundled
   language data lives in `tessdata/`. No separate install is normally needed.
   If the bundled binary doesn't work, run `install_tesseract.bat` to install
   the system-wide UB-Mannheim Windows build.
3. **Ollama**: download installer from https://ollama.com. After install:
   ```cmd
   ollama pull llama3
   ```
4. **Visual C++ Redistributable** — required by ChromaDB's ONNX runtime.
   Usually already installed; if ChromaDB fails to import, get it from Microsoft.

### Install the app

```cmd
INSTALL.bat
```

This creates a `.venv/` virtualenv and pip-installs `requirements.txt`. Run
it once after fresh checkout or after a `requirements.txt` change.

### First-run sanity check

```cmd
python -c "import fitz; import pytesseract; import requests; import flask; print('OK')"
```

If anything errors, see Troubleshooting below.

## Running the application

There is **one process** to start:

| Process | What it does | How to start |
|---------|--------------|--------------|
| **BRUNs Flask app** | HTML UI + JSON BI endpoints on port 7845 | `START_APP.bat` |
| **Ollama daemon** | Hosts the local LLM | Starts automatically after install; verify: `curl http://localhost:11434/api/tags` |

After `START_APP.bat`, the browser opens automatically at `http://localhost:7845/`.

> **Note:** There is no separate BI bridge process. `START_APP.bat` starts the
> Flask server which serves both the UI and the REST API on the same port (7845).
> `START_BI_CONNECTOR.bat` does the same thing — it's an alias.

> **Huey task queue:** `huey` is installed but not currently active. The upload
> flow uses in-memory threads. A `huey_consumer.py` command is NOT required.

### Port conflicts

| Default port | Used by | Override |
|--------------|---------|----------|
| 7845 | Flask app (UI + API) | `BRUNS_API_PORT=8000 python -m core.api.server` |
| 11434 | Ollama daemon | Ollama settings |

## Configuration

Three layers of configuration, in order of precedence (lowest first):

### Layer 1 — Defaults baked into code

`modules/logistics/config.py`, `modules/travel/config.py`. Edit only when
shipping a release.

### Layer 2 — Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `BRUNS_DATA_DIR` | Where SQLite databases live | `data/` |
| `BRUNS_API_PORT` | Flask server port | `7845` |
| `BRUNS_INPUT_DIR` | Where uploaded PDFs are saved | `data/input/` |
| `BRUNS_TRAVEL_INPUT_DIR` | Travel uploads directory | `data/input/travel/` |
| `BRUNS_LOGISTICS_DB` | Full path to logistics.db | `data/logistics.db` |
| `BRUNS_TRAVEL_DB` | Full path to travel.db | `data/travel.db` |
| `OLLAMA_URL` | Full Ollama generate URL | `http://localhost:11434/api/generate` |
| `OLLAMA_MODEL` | Default Ollama model | `llama3` |

Set in Windows: System Properties → Environment Variables → User variables.

### Layer 3 — UI settings (saved per-session)

Saved to `data/.llm_config.json` by the LLM config modal (⚙ LLM button in the
top navigation bar). Fields:

- `provider` (`ollama` / `openai` / `anthropic` / `lmstudio`)
- `base_url` (Ollama base URL)
- `port`
- `model`
- `api_key` (for cloud providers)
- `temperature`
- `timeout`

Also `data/.launcher_prefs.json` for last-used mode (logistics/travel).

## Backup

The whole product state is in `data/`. Back this up.

```powershell
# Daily backup script (Windows Task Scheduler)
$src  = "C:\Users\ROG STRIX\Documents\BRUNs logistics data scraper\data"
$dest = "D:\Backups\BRUNs\$(Get-Date -Format yyyy-MM-dd)"
Copy-Item -Path $src -Destination $dest -Recurse -Force
```

What's in `data/`:
- `logistics.db` — production logistics data
- `travel.db` — production travel data
- `vector/` — ChromaDB vector embeddings (rebuildable from documents)
- `logs/` — per-file extraction audit JSON
- `input/` — uploaded PDFs (user choice to keep or clear)
- `.llm_config.json` — LLM provider settings (contains API keys if cloud provider used)
- `.launcher_prefs.json` — UI preferences

Recovery: stop the app, restore `data/` from backup, restart.

**Tip:** SQLite live backup (works while app is running):
```cmd
sqlite3 data\logistics.db ".backup D:\Backups\BRUNs\logistics_backup.db"
```

## Updating the application

```cmd
git pull
.venv\Scripts\activate
pip install -r requirements.txt
START_APP.bat
```

> **Schema migration note:** `core/storage/migrations.py` currently does nothing
> (`pass` body). Schema changes are currently manual. If the server throws
> `OperationalError: no such column`, the DB schema needs a manual `ALTER TABLE`.
> See [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) TD3.

## Troubleshooting

### "Ollama not detected" / LLM not responding

1. Is Ollama running? `curl http://localhost:11434/api/tags`
2. Is the model installed? `ollama list` should include `llama3`.
3. Check LLM config: click ⚙ LLM in the navbar, verify the URL and model name.

### Tesseract not found / OCR not working

1. Check `tesseract_bin/tesseract.exe` exists in the repo root.
2. Check `tessdata/` contains `eng.traineddata`, `fra.traineddata`, `ara.traineddata`.
3. If bundled binary fails on your system: run `install_tesseract.bat` to
   install the system Tesseract at `C:\Program Files\Tesseract-OCR\`.
4. The app will fall back to Ollama vision if Tesseract is completely absent.

### Flask server returns 500 errors

1. Check the console output for the exception traceback.
2. If `OperationalError: no such column: reviewed_at` — the DB schema is stale.
   Manual fix: `sqlite3 data\logistics.db "ALTER TABLE documents ADD COLUMN reviewed_at TEXT"`
3. Is `data/logistics.db` present and readable?

### "ImportError" on startup

```cmd
.venv\Scripts\activate
pip install -r requirements.txt --upgrade
```

If still broken, nuke the venv:
```cmd
rmdir /S /Q .venv
INSTALL.bat
```

### LLM returns garbage / wrong fields

1. Open the document detail page → the Logs section shows the full LLM response.
2. Try a larger model: `ollama pull llama3:70b`, then update Settings → LLM.
3. If a specific carrier format is consistently wrong, the prompt in
   `modules/logistics/prompts.py` needs an example added.

### Pydantic validation errors on every file

The LLM output schema drifted. Check:
1. Did the prompt version change without updating the cache? Clear the cache
   from Settings → Purge extraction cache.
2. Is the prompt asking for fields the model doesn't know about?

### SQLite database is locked

A second process has the DB open. Common causes:
- Running two instances of the app
- DB Browser for SQLite has the file open
- A backup is mid-flight

SQLite WAL mode reduces but does not eliminate locking. Solve: close the other
process.

### Port 7845 already in use

```cmd
netstat -ano | findstr :7845
taskkill /PID <pid> /F
```

Or change the port: `set BRUNS_API_PORT=7846 && START_APP.bat`.

### Duplicate persons in the Travel module

The fuzzy identity matching engine (`core/matching/engine.py`) is built but not
yet wired. Name variations create duplicate Person rows. This is a known gap —
see [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) TD5. Workaround:
manually merge person records via the Persons detail edit form.

## Operating in a multi-user environment

Currently single-user by design. If two operators use one install:
- Both see all data.
- Last write wins on container edits (no optimistic locking).
- Audit log records `actor = "operator"` for all edits (no per-user identity).

For two operators on one machine, this is acceptable. For more, run separate
installs per operator until the multi-user auth feature is built.

## Health monitoring

`GET /api/status` returns the basic DB health check.

A richer `/health` endpoint is planned:
```json
{
  "status": "ok",
  "uptime_seconds": 12345,
  "active_jobs": 2,
  "completed_jobs_24h": 47,
  "failed_jobs_24h": 1,
  "ollama_reachable": true,
  "db_size_mb": {"logistics": 12.3, "travel": 5.1}
}
```

## Uninstalling

1. Stop all running BRUNs processes.
2. Back up `data/` if you want to keep processed documents.
3. Delete the project directory.
4. (Optional) Uninstall Ollama from Windows Add/Remove Programs.
5. (Optional) Uninstall system Tesseract if installed.
