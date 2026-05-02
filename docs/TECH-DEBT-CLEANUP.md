# Tech Debt Cleanup Strategy

This document is a surgical playbook — ordered, safe, non-breaking. Each item
specifies exactly which files to touch, what the risk is, and how to verify it
worked. The order matters: some items unlock others.

**Guiding principle:** the live `data/logistics.db` and `data/travel.db` are
the source of truth for any schema question. They were created by
`database_logic/database.py` and have been patched manually. No code change
may assume a fresh DB — always run migrations before testing.

---

## Priority 0 — Before anything else (30 min total)

These two fixes take under 30 minutes combined and unblock everything else.
Do them first, in order, on a feature branch.

### 0-A: Fix `core/storage/migrations.py` (TD3)

**Why first:** Every other schema change needs a migration runner to land on
deployed instances. Until this exists, any schema patch requires someone to SSH
in and run ALTER TABLE by hand.

**File:** `core/storage/migrations.py`

Replace the stub with:

```python
from .db import get_connection

MIGRATIONS: list[tuple[str, str]] = [
    ("001_docs_reviewed_fields",
     "ALTER TABLE documents ADD COLUMN IF NOT EXISTS reviewed_at TEXT"),
    ("002_docs_reviewed_by",
     "ALTER TABLE documents ADD COLUMN IF NOT EXISTS reviewed_by TEXT"),
    ("003_families_case_status",
     "ALTER TABLE families ADD COLUMN IF NOT EXISTS case_status TEXT DEFAULT 'COLLECTING'"),
    ("004_families_next_action",
     "ALTER TABLE families ADD COLUMN IF NOT EXISTS next_action TEXT"),
    ("005_families_next_action_date",
     "ALTER TABLE families ADD COLUMN IF NOT EXISTS next_action_date TEXT"),
    ("006_documents_travel_original_doc_id",
     "ALTER TABLE documents_travel ADD COLUMN IF NOT EXISTS original_doc_id INTEGER"),
    ("007_indexes",
     "CREATE INDEX IF NOT EXISTS idx_docs_module ON documents(module);\n"
     "CREATE INDEX IF NOT EXISTS idx_shipments_eta ON shipments(eta);\n"
     "CREATE INDEX IF NOT EXISTS idx_containers_status ON containers(statut_container);\n"
     "CREATE INDEX IF NOT EXISTS idx_docs_confidence ON documents(confidence)"),
]


def run_migrations(db_path: str) -> list[str]:
    """Apply any pending migrations. Returns list of applied migration IDs."""
    conn = get_connection(db_path)
    applied = []
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        already = {r[0] for r in conn.execute("SELECT id FROM schema_version").fetchall()}
        for mid, sql in MIGRATIONS:
            if mid in already:
                continue
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(stmt)
                    except Exception as e:
                        print(f"[migrations] {mid}: {e} (continuing)")
            conn.execute("INSERT INTO schema_version (id) VALUES (?)", (mid,))
            conn.commit()
            applied.append(mid)
    finally:
        conn.close()
    return applied
```

Then call it in `core/api/server.py` at startup (before `app.run`):

```python
from core.storage.migrations import run_migrations
for db in [LOGISTICS_DB, TRAVEL_DB]:
    if os.path.exists(db):
        applied = run_migrations(db)
        if applied:
            print(f"[migrations] applied to {os.path.basename(db)}: {applied}")
```

**Verification:** `python -c "from core.storage.migrations import run_migrations; print(run_migrations('data/logistics.db'))"`
Should print `[]` (all already applied on the live DB).

**Risk:** None. `IF NOT EXISTS` + `IF NOT EXISTS` on column addition is safe.
SQLite 3.35+ supports `IF NOT EXISTS` on `ALTER TABLE ADD COLUMN`.

---

### 0-B: Fix TD4 — SQLite connection leak in processor.py

**File:** `core/pipeline/processor.py` — the `process_file` method

**Current (broken):**
```python
conn = get_connection(self.db_path)   # line 47
# ... many lines ...
conn.close()                           # line 134 — ONLY reached on success
except Exception as e:
    job.fail(str(e))
    # conn is never closed on exception
```

**Fix:** Wrap in a `try/finally`:
```python
conn = None
try:
    conn = get_connection(self.db_path)
    # ... all processing ...
    conn.close()
    conn = None
except Exception as e:
    job.fail(str(e))
    traceback.print_exc()
finally:
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
```

**Verification:** Upload a PDF with an intentionally broken LLM config
(wrong Ollama URL). The job should fail. `lsof -p <PID> | grep logistics.db`
should show no lingering file handles after the failure.

**Risk:** None. This is a pure correctness fix — no behavior change on the
success path.

---

## Priority 1 — Schema alignment (1 hour)

### 1-A: Fix TD1 — `shipments` DDL in core/storage/db.py

**Context:** The live `logistics.db` has `compagnie_maritime`, `document_type`.
`core/storage/db.py` creates `carrier`, `doc_type`. A fresh install fails.

**File:** `core/storage/db.py` — find the `CREATE TABLE IF NOT EXISTS shipments` block

Replace the columns section with:
```sql
CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tan TEXT UNIQUE,
    item_description TEXT,
    compagnie_maritime TEXT,
    port TEXT,
    transitaire TEXT,
    vessel TEXT,
    etd TEXT,
    eta TEXT,
    document_type TEXT,
    status TEXT,
    source_file TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    modified_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

Add to `MIGRATIONS` in `migrations.py` (already created in 0-A):
```python
("008_shipments_rename_carrier",
 "ALTER TABLE shipments RENAME COLUMN carrier TO compagnie_maritime"),
("009_shipments_rename_doc_type",
 "ALTER TABLE shipments RENAME COLUMN doc_type TO document_type"),
```

**Note:** SQLite supports `RENAME COLUMN` from version 3.25.0. The bundled
Python 3.14 ships with SQLite 3.43+, so this is safe.

**Verification:** Delete `data/logistics.db`, restart the app, verify the server
starts and `/api/status` returns `{"logistics": "ok"}`. Then restore the backup.

**Risk:** Medium — touching the schema definition. Mitigated by: migrations run
on existing DB first (live DB already has correct column names, migrations do
nothing), DDL only affects fresh installs.

---

## Priority 2 — Security fixes (2 hours)

These are quick wins with no UX impact.

### 2-A: Fix TD7 — NL2SQL forbidden keyword check

**File:** `core/api/server.py` — `ui_logistics_ask()` function (~line 1105)

Replace the current check:
```python
# current (insufficient)
if not sql_upper.startswith("SELECT"):
    return error_fragment(...)
```

With:
```python
FORBIDDEN_SQL_KEYWORDS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "TRUNCATE",
    "REPLACE", "UPSERT",
})

sql_tokens = set(re.findall(r'\b[A-Z]+\b', sql.upper()))
if not sql.strip().upper().startswith("SELECT"):
    return render_template("logistics/_ask_result.html",
                           error="Generated SQL must start with SELECT.",
                           rows=[], cols=[], sql=sql, question=question)
if sql_tokens & FORBIDDEN_SQL_KEYWORDS:
    blocked = sql_tokens & FORBIDDEN_SQL_KEYWORDS
    return render_template("logistics/_ask_result.html",
                           error=f"SQL contains forbidden keywords: {blocked}",
                           rows=[], cols=[], sql=sql, question=question)

conn = get_connection(LOGISTICS_DB)
try:
    conn.execute("PRAGMA query_only = ON")
    cursor = conn.execute(sql)
    # ...
finally:
    conn.close()
```

**Risk:** Low. Only affects the NL2SQL POST endpoint.

### 2-B: Fix TD9 — CORS restriction

**File:** `core/api/server.py` — top of file (~line 56)

```python
# Replace:
CORS(app, resources={r"/api/*": {"origins": "*"}})

# With:
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:7845",
    "http://127.0.0.1:7845",
    r"http://localhost:*",
    r"http://127.0.0.1:*",
]}})
```

**Risk:** Low on single-machine installs. If the customer uses Power BI from
a different machine on the same LAN, they'll need to add their machine's IP
to the origins list — document this in `docs/10-DEPLOYMENT.md`.

---

## Priority 3 — Performance fixes (30 min)

### 3-A: Fix TD6 — Cache `_tesseract_available()` result

**File:** `core/extraction/text_extractor.py` (~line 121)

```python
# Add at module level (after imports):
_TESSERACT_AVAILABLE: bool | None = None

# Replace the function:
def _tesseract_available() -> bool:
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is None:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            _TESSERACT_AVAILABLE = True
        except Exception:
            _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE
```

**Impact:** 20-page scanned PDF goes from 20 subprocess spawns to 1.

**Risk:** None. The cached result is set at module import time and never
changes during a process lifetime.

---

## Priority 4 — Wire the fuzzy matching engine (TD5)

This is the highest-value feature gap. The engine is complete. The wiring
requires changes to one function.

**File:** `core/api/projections.py` — `_project_travel()` function

**Current (broken):**
```python
# Exact string match — silently creates duplicates on name variation
row = conn.execute(
    "SELECT id FROM persons WHERE normalized_name = ?",
    (normalized,)
).fetchone()
```

**Target:**
```python
from core.matching.engine import resolve_identity, MatchResult
from core.schemas.person import Person

# Build candidate person object
new_person = Person(
    normalized_name=normalized,
    dob=extracted.get("dob"),
    nationality=extracted.get("nationality"),
)

# Fetch candidates by prefix (fast narrow-down before fuzzy comparison)
prefix = normalized[:4] if len(normalized) >= 4 else normalized
candidates_rows = conn.execute(
    """SELECT id, normalized_name, dob, nationality
       FROM persons WHERE normalized_name LIKE ? LIMIT 100""",
    (prefix + "%",)
).fetchall()

candidates = [
    Person(id=r["id"], normalized_name=r["normalized_name"],
           dob=r["dob"], nationality=r["nationality"])
    for r in candidates_rows
]

result: MatchResult = resolve_identity(new_person, candidates)

if result.status == "AUTO_MERGED":
    person_id = result.matched_person_id
    # Optionally log the merge to audit_log
elif result.status == "REVIEW":
    # Insert into matches table for human review, use matched_id tentatively
    try:
        conn.execute(
            """INSERT INTO matches (entity_a_id, entity_b_id, score, status)
               VALUES (NULL, ?, ?, 'PENDING')""",
            (result.matched_person_id, result.score),
        )
    except Exception:
        pass
    # Use the candidate as a tentative match rather than inserting a duplicate
    person_id = result.matched_person_id
else:  # NEW_IDENTITY
    # Insert new person
    cur = conn.execute(
        """INSERT INTO persons (full_name, normalized_name, dob, nationality, gender)
           VALUES (?, ?, ?, ?, ?)""",
        (full_name, normalized, extracted.get("dob"),
         extracted.get("nationality"), extracted.get("gender")),
    )
    person_id = cur.lastrowid
```

**Thresholds** (`core/matching/thresholds.py`):
- `AUTO_MERGE_THRESHOLD = 0.92` → same person, merge silently
- `REVIEW_THRESHOLD = 0.75` → possible match, queue for human review
- Below `REVIEW_THRESHOLD` → new identity

**Prerequisite:** Make sure the `matches` table exists. Add to `MIGRATIONS`:
```python
("010_create_matches_table", """
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_a_id INTEGER,
        entity_b_id INTEGER,
        score REAL,
        status TEXT DEFAULT 'PENDING',
        resolved_by TEXT,
        resolved_at TEXT
    )
"""),
```

**Risk:** Medium. This changes behavior for every travel upload. Test on a
fresh `travel_test.db` before touching production. The AUTO_MERGE path is
safe. The REVIEW path is conservative (uses the candidate rather than creating
a duplicate).

**Effort:** 1 day (including writing tests).

---

## Priority 5 — Dead code removal (TD2)

Only do this after TD1 is fully resolved (the live DB is no longer dependent
on `database_logic/` being present as a reference).

### 5-A: Delete dead directories

```bash
# After verifying the live DB is fully migrated:
git rm -r logistics_app/
git rm -r ui/
git rm -r utils/   # old utility layer, not imported by core/
```

**Preserve:** `database_logic/database.py` as a `database_logic/README.md`
comment file that documents the legacy schema, then delete the Python file.

**Prerequisite:** `core/storage/db.py::init_schema()` must produce a DB that
the server can actually use (TD1 fixed). Run `python -c "from core.storage.db
import init_schema; import tempfile, os; f=tempfile.mktemp()+'.db';
init_schema(f); print('OK'); os.unlink(f)"` and verify no errors.

**Risk:** Low after TD1 is fixed. Run `tests/test_imports.py` to confirm
nothing in `core/` imports from these directories.

---

## Priority 6 — Structured logging (TD12, 4 hours)

Replace all `print()` calls with `logging` throughout `core/`.

**Approach:**
1. Add to `core/__init__.py` or a new `core/logging_config.py`:
```python
import logging, logging.handlers, os

def configure_logging(log_dir: str = "data/logs"):
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "bruns.log"),
        maxBytes=10_000_000, backupCount=5,
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s — %(message)s"
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler,
                        logging.StreamHandler()])
```

2. Call `configure_logging()` at app startup in `server.py`.

3. In each module, replace `print(...)` with:
```python
import logging
log = logging.getLogger(__name__)
log.info(...)    # was print(f"  [extractor] ...")
log.warning(...) # was print(f"  [extractor] WARNING: ...")
log.error(...)   # was print(f"  [extractor] error: ...")
```

**Files to touch:** `core/extraction/text_extractor.py`,
`core/pipeline/processor.py`, `core/api/projections.py`,
`core/audit/logger.py`, `core/search/vector_db.py`.

**Risk:** Low. Pure logging infrastructure — no business logic touched.

---

## Priority 7 — Offline-capable UI (TD11, 1 hour)

Current CDN dependencies loaded on every page:
- Tailwind CSS (`https://cdn.tailwindcss.com`)
- DaisyUI CSS (`https://cdn.jsdelivr.net/npm/daisyui@4.12.10/...`)
- HTMX (`https://unpkg.com/htmx.org@2.0.3`)
- Chart.js (`https://cdn.jsdelivr.net/npm/chart.js@4.4.4/...`)
- Google Fonts (Inter)

**Fix (no Node, no build step):**

```bash
# From repo root:
mkdir -p core/api/static

curl -L "https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css" \
     -o core/api/static/daisyui.min.css

curl -L "https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js" \
     -o core/api/static/htmx.min.js

curl -L "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js" \
     -o core/api/static/chart.min.js

# For Tailwind: use the standalone CLI binary (no Node required)
# https://github.com/tailwindlabs/tailwindcss/releases  → tailwindcss-windows-x64.exe
# Run: tailwindcss-windows-x64.exe --input src/input.css --output core/api/static/tailwind.min.css --minify
# OR use the pre-built CDN play build (larger but zero config):
curl -L "https://cdn.tailwindcss.com/3.4.0" -o core/api/static/tailwind.min.js

# For Inter font: download WOFF2 files or use system-ui fallback (already in CSS)
```

Then update `core/api/templates/base.html` to reference
`{{ url_for('static', filename='...') }}` instead of CDN URLs.

Add `core/api/static/` to `.gitignore` with a note: "regenerate with
`make vendor-ui`". Add a `Makefile` target.

**Risk:** Low. Font fallback (`system-ui`) covers the worst case.

---

## Priority 8 — server.py decomposition (TD8, 3–4 days)

This is the largest refactor and should be last — it touches every test and
every import. Do it on a dedicated branch with a full CI run before merging.

**Target structure:**
```
core/api/
  __init__.py      create_app() factory
  blueprints/
    logistics.py   /logistics/* routes + helpers
    travel.py      /travel/* routes + helpers
    api.py         /api/* JSON endpoints
    files.py       /files/* serving + annotated PNG
    llm.py         /llm/* config modal
    search.py      /search
  business/
    demurrage.py   _calc_demurrage, _demurrage_info, _DEFAULT_FREE_DAYS, _CMA_CGM_TIERS
    nlsql.py       _generate_sql_from_question, _NL2SQL_SCHEMA, _NL2SQL_SYSTEM
    reconcile.py   _reconcile_siblings, _flatten_diff, _compute_diff
    completeness.py _family_completeness, REQUIRED_DOCS_BY_ROLE, CASE_STATUS_FLOW
    charts.py      _logistics_chart_data, _travel_chart_data
    stats.py       _logistics_stats, _travel_stats, _logistics_action_panel
  server.py        Thin: create_app() + register blueprints + app.run()
```

**Approach:**
1. Extract `business/` modules first — these have no Flask imports and are
   pure functions. Easiest to test in isolation.
2. Extract `blueprints/` next — move routes file by file, run smoke tests
   after each.
3. Rename/update `server.py` last.

**Risk:** High if done carelessly. Mitigate with:
- One blueprint per PR
- Run the full smoke test after each PR: `curl localhost:7845/<route>`
- Keep `server.py` as a re-exporting shim until all blueprints are merged

---

## Items deliberately deferred

| Item | Reason |
|------|--------|
| CSRF protection (TD10) | Requires `flask-wtf` dep + token in every HTMX `hx-headers`. Medium effort, low risk on single-machine install. Wire after multi-user auth (L2). |
| Multi-user auth (L2) | Single-operator use case currently. Design review required before adding auth. |
| OData v4 (L3) | Power BI JSON endpoint works. OData adds complexity without solving a real operator pain. |
| `N8 Cloud LLM fallback` | Requires careful key management. Worth adding when a customer explicitly asks for cloud escalation. |

---

## Cleanup order summary

```
Week 1 (safe, non-breaking)
  0-A  migrations.py runner          30 min
  0-B  processor.py conn leak        10 min
  3-A  tesseract cache               10 min
  2-A  NL2SQL forbidden keywords     1 hour
  2-B  CORS restriction              5 min

Week 2 (schema work)
  1-A  shipments DDL in db.py        1 hour  (test on fresh DB!)

Week 3 (feature wire)
  4    fuzzy identity matching       1 day

Week 4 (cleanup)
  5-A  delete dead directories       1 hour  (only after week 2 verified)

Week 5–6 (infrastructure)
  6    structured logging            4 hours
  7    vendor UI assets              1 hour

Weeks 7–10 (decomposition)
  8    server.py → blueprints        3–4 days
```

---

## How to verify nothing broke

After each step, run this checklist:

```bash
# 1. Import check (no circular deps, no layer violations)
python -m pytest tests/test_imports.py -q

# 2. Full pytest
python -m pytest tests/ -q

# 3. Server smoke test
python -m core.api.server &
sleep 3
for url in /api/status /logistics /logistics/documents /logistics/swimlane \
           /logistics/analytics /travel /travel/calendar /travel/analytics \
           /search?q=test; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:7845$url)
  printf "%-40s %s\n" "$url" "$code"
done
pkill -f "core.api.server"

# 4. Fresh DB test (only after TD1 fix)
python -c "
import tempfile, os
from core.storage.db import init_schema
from core.storage.migrations import run_migrations
f = tempfile.mktemp() + '.db'
init_schema(f)
run_migrations(f)
from core.storage.db import get_connection
conn = get_connection(f)
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('tables:', tables)
conn.close(); os.unlink(f)
"
```
