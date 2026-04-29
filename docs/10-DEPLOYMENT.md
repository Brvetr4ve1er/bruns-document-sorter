# 10 — Deployment and Operations

How to install, run, troubleshoot, and back up BRUNs.

## Target environment

- Windows 10 / 11 (primary; only supported platform today)
- 16 GB RAM minimum (Ollama with llama3 fits in ~8 GB; the app + Power BI
  fits in the rest)
- 20 GB free disk (Ollama models ~5 GB, app ~500 MB, transient PDF storage)
- A modern x86_64 CPU (no GPU required, but a recent one helps Ollama)
- Local network access (for Power BI to hit the BI bridge over LAN)

## Install procedure

### Prerequisites (one-time)

1. **Python 3.11 or 3.12** from https://python.org. Tick "Add to PATH" during install.
2. **Tesseract OCR**: run `install_tesseract.bat` from the repo root. This
   installs the UB-Mannheim Windows build to `C:\Program Files\Tesseract-OCR\`
   and pytesseract auto-detects it from the registry.
3. **Ollama**: download installer from https://ollama.com. After install:
   ```cmd
   ollama pull llama3
   ```
4. **Visual C++ Redistributable** — usually already installed. If ChromaDB
   fails to import, install it from Microsoft.

### Install the app

```cmd
INSTALL.bat
```

This creates a `.venv/` virtualenv and pip-installs `requirements.txt`. Run
it once after fresh checkout or after a `requirements.txt` change.

### First-run sanity check

```cmd
python -c "import streamlit; import fitz; import pytesseract; import requests; print('OK')"
```

If anything errors, see Troubleshooting below.

## Running the application

There are three things that may need to be running simultaneously:

| Process | Required? | How to start |
|---------|-----------|--------------|
| Ollama daemon | Yes | Auto-starts as a Windows service after install. Verify: `curl http://localhost:11434/api/tags` |
| BRUNs main UI | Yes | `START_APP.bat` (Streamlit on port 8501) |
| BI bridge / Flask | Yes if using Power BI | `START_BI_CONNECTOR.bat` (Flask on port 7845) |
| Huey background worker | Optional (large batches only) | `.venv\Scripts\huey_consumer.py core.pipeline.queue.task_queue` |

After P5 of the UI migration, Streamlit will be retired and the Flask server
will host both UI and API on a single port. `START_APP.bat` will start the
Flask server.

### Port conflicts

| Default port | Used by | Override |
|--------------|---------|----------|
| 8501 | Streamlit UI | Edit `START_APP.bat` |
| 7845 | Flask BI bridge | `BRUNS_API_PORT=8000 python -m core.api.server` |
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
| `BRUNS_API_PORT` | Flask BI bridge port | `7845` |
| `BRUNS_DEBUG` | Show full stack traces in UI | unset (off) |

Set in Windows: System Properties → Environment Variables → User variables.

### Layer 3 — UI settings (saved per-user)

Saved to `data/ui_settings.json` and `data/.launcher_prefs.json`. Edited
through the Settings page in the UI:

- Ollama URL
- Ollama model
- Ollama timeout
- Input directory (for batch processing)
- Logs directory
- Grid columns count

## Backup

The whole product state is in `data/`. Back this up.

```powershell
# Daily backup script (Windows Task Scheduler)
$src  = "C:\Users\ROG STRIX\Documents\BRUNs logistics data scraper\data"
$dest = "D:\Backups\BRUNs\$(Get-Date -Format yyyy-MM-dd)"
Copy-Item -Path $src -Destination $dest -Recurse -Force
```

What's in `data/`:
- `logistics.db` — production data
- `travel.db` — production data
- `queue.db` — Huey job queue (rebuildable, but useful to back up for
  in-flight jobs)
- `chroma/` — vector embeddings (rebuildable from documents)
- `logs/` — per-file audit JSON (the case-file evidence trail for Travel)
- `input/` — uploaded PDFs the user chose to keep

Recovery: stop the app, restore `data/` from backup, restart.

**Tip:** SQLite snapshots are easiest with the `.backup` SQL command, which
is atomic:

```cmd
sqlite3 data\logistics.db ".backup D:\Backups\BRUNs\logistics_2026-04-28.db"
```

This works while the app is running.

## Updating the application

```cmd
git pull
.venv\Scripts\activate
pip install -r requirements.txt
START_APP.bat
```

Schema migrations run automatically on app startup
(`core/storage/migrations.py`). Forward-only — never roll back.

## Troubleshooting

### "Ollama not detected" badge in the UI

1. Is Ollama running? `curl http://localhost:11434/api/tags`
2. Is the model installed? `ollama list` should include `llama3`.
3. Check `data/ui_settings.json` — is `ollama_url` correct?

### Tesseract not found

1. Is Tesseract installed? Check `C:\Program Files\Tesseract-OCR\tesseract.exe`.
2. If installed elsewhere, set the path in code (or PATH env var).
3. Re-run `install_tesseract.bat`.

### Flask BI bridge returns 500 errors

1. Check the Flask console output for the exception.
2. Is `data/logistics.db` present?
3. If permissions error, run as admin once to clear file locks (rare).

### "ImportError" on startup

Almost always means `requirements.txt` is out of sync with installed
packages. Solve:

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

1. Open Logs tab in the UI. The full LLM response is recorded.
2. If the model is consistently wrong, swap to a larger one:
   ```cmd
   ollama pull llama3:70b
   ```
   Then update Settings → Ollama Model.
3. If a specific carrier format is wrong, the prompt in
   `modules/logistics/prompts.py` likely needs an example added.

### Pydantic validation errors on every file

Means the LLM output schema drifted. Check:
1. Did you change the prompt without changing the schema?
2. Did you upgrade Pydantic without testing?

The Logs tab will show which field failed validation.

### SQLite database is locked

A second process has the DB open. Common causes:
- Running two instances of the app
- DB Browser for SQLite is open with the file
- A backup process is mid-flight

Solve: close the other process. SQLite uses file-level locking on Windows.

### Port 7845 already in use

Another Flask server is running. Find it:

```cmd
netstat -ano | findstr :7845
taskkill /PID <pid> /F
```

Or change the port: `set BRUNS_API_PORT=7846 && START_BI_CONNECTOR.bat`.

## Operating in a multi-user environment

Currently single-user by design. If you put two operators on one install:

- Both can see all data.
- Last write wins on container edits (no optimistic locking).
- Audit log doesn't capture which operator made which change (see
  [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md), L4).

For two operators on one machine, this is fine. For more, wait for the
multi-user feature or run separate installs per operator.

## Health monitoring

Manual today. Future: a `/health` endpoint that returns:

```json
{
  "status": "ok",
  "uptime_seconds": 12345,
  "queued_jobs": 2,
  "in_flight_jobs": 1,
  "completed_jobs_24h": 47,
  "failed_jobs_24h": 1,
  "cache_hit_rate_24h": 0.62,
  "ollama_reachable": true,
  "db_size_mb": {"logistics": 12.3, "travel": 5.1}
}
```

Build this in P2 alongside the JobTracker — it's free given the data the
tracker already has.

## Uninstalling

1. Stop all running BRUNs processes.
2. Delete the project directory.
3. (Optional) Uninstall Ollama from Windows Add/Remove Programs.
4. (Optional) Uninstall Tesseract.

`data/` is inside the project directory — back it up first if you want it.
