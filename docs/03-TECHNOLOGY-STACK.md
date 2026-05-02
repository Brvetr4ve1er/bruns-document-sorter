# 03 — Technology Stack

Every dependency in `requirements.txt`, why it's there, and what it would cost
to swap it.

## Runtime stack at a glance

| Layer | Technology | Why this one |
|-------|------------|-------------|
| Language | Python 3.14 (project runs on 3.14; 3.11+ required by Pydantic v2) | Modern type hints, walrus operator, Pydantic v2 compatibility |
| UI | Flask 3.1 + HTMX 2.0 + DaisyUI 4.12 | Server-rendered, no build step, 31 themes via CDN |
| LLM runtime | Ollama (default `llama3`) | Local inference, zero API cost, data never leaves machine |
| PDF text | PyMuPDF (`fitz`) 1.27 | Fastest pure-Python PDF text extraction; lossless; bounding-box coords for PDF annotation |
| OCR | Tesseract via `pytesseract` 0.3 | Industry-standard OSS OCR; bundled in `tesseract_bin/`; 100+ languages in `tessdata/` |
| Image processing | Pillow 12.2 | Required by Tesseract and PassportEye |
| Passport MRZ | PassportEye 2.2 + `mrz` 0.6 | Deterministic MRZ band extraction — checksum-validated; no LLM needed |
| Validation | Pydantic v2.13 | Strict typed schemas with field-level normalization |
| Storage | SQLite (stdlib) | Zero-install, file-based, BI-friendly; WAL mode for concurrency |
| Vector search | ChromaDB 1.5 | Embedded, local; no separate service |
| Tabular ops | pandas 3.0 | Excel/CSV export, XLSX writer |
| Excel writer | openpyxl 3.1 | 49-column "Containers actifs" XLSX export with French headers |
| Fuzzy matching | RapidFuzz 3.14 | Fastest Levenshtein/token-set ratio implementation; used in `core/matching/engine.py` |
| HTTP | requests 2.33 | Calling the Ollama daemon |
| BI bridge | Flask 3.1 + flask-cors 5.0 | Local REST server for Power BI connections |
| Tests | pytest 9.0 | `tests/test_imports.py`, `test_phase1–4`, `test_phase8` |
| Job queue | huey 3.0 | **In requirements.txt but NOT currently used** — raw threads via `job_tracker.py` instead |

## Detailed reasoning per dependency

### `PyMuPDF==1.27.2.2` (imported as `fitz`)

**Role:** Native PDF text extraction, page rendering for OCR, PDF annotation
for the bounding-box overlay feature (`/files/<module>/<id>/annotated`).

**Why:** Five to ten times faster than pdfplumber; more accurate at preserving
reading order than pdfminer.six; exposes bounding-box coordinates used by the
annotated-PDF endpoint to draw field highlights.

**Watch-out:** AGPL-licensed. For a closed-source commercial sale this requires
a paid PyMuPDF Pro license. For local-install-only, this is acceptable.

### `pytesseract==0.3.13` + Tesseract binary

**Role:** OCR fallback for scanned PDFs and image documents.

**Why:** Tesseract is the only OSS OCR with quality competitive against AWS
Textract for Latin-alphabet documents. It supports Arabic and French out of the
box (relevant for the Algerian customer base).

**Bundled install:** The `tesseract_bin/` directory contains the Windows binary.
`tessdata/` contains language models for 100+ languages including `ara.traineddata`,
`fra.traineddata`, `eng.traineddata`. The extractor sets `TESSDATA_PREFIX` at
import time to point to the bundled `tessdata/`.

**Known issue:** `_tesseract_available()` in `text_extractor.py` calls
`pytesseract.get_tesseract_version()` on every OCR attempt (per page), which
spawns a subprocess each time. Should be cached at module load. Fix is tracked
in the roadmap.

### `Pillow==12.2.0`

**Role:** Image preprocessing before Tesseract / PassportEye.

**Why:** Hard dependency of both pytesseract and PassportEye. Cannot be removed.

### `passporteye==2.2.2` + `mrz==0.6.1`

**Role:** Locate and parse the MRZ (Machine Readable Zone) of passports and
ID cards.

**Why:** The MRZ is a fixed-format band at the bottom of every ICAO passport.
A specialist parser is dramatically more accurate than asking an LLM to read
it. PassportEye finds the band; the `mrz` library validates check digits and
extracts structured fields. This is the "specialist > generalist" principle:
use a deterministic parser when one exists.

### `requests==2.33.1`

**Role:** HTTP client to talk to the Ollama daemon at the configured endpoint.

**Why:** Stable, synchronous, simple. We are not bottlenecked on HTTP — we are
bottlenecked on LLM inference.

### `pydantic==2.13.2`

**Role:** Schema definition, input validation, field-level normalization.

**Why:** Pydantic v2 (rust-backed) is faster than v1 by an order of magnitude.
`field_validator(mode="before")` lets normalizers run before inter-field
validators — exactly what we need to canonicalize dirty LLM output before any
other field sees it.

**Critical pattern:** Every domain field has a normalizer. `container_number`
is regex-checked. Dates are ISO-normalized. Carrier names are canonicalized.
This is the contract that makes BI tools downstream trust the data.

### `chromadb==1.5.8`

**Role:** Local vector store for semantic document search.

**Why:** Embedded mode (no separate daemon). Every processed document is
embedded so users can search "cold-chain shipment from MSC arriving April"
instead of `WHERE vessel LIKE '%...'`.

**Cost:** Brings in ONNX runtime and sentence-transformers as transitives —
adds ~200MB to the install. Acceptable for a desktop app.

### `pandas==3.0.2`

**Role:** Dataframe operations for CSV/XLSX export.

**Why:** The XLSX export uses pandas + openpyxl for column ordering and French
header formatting.

### `openpyxl==3.1.5`

**Role:** Write the 49-column "Containers actifs" XLSX with French column
names in the exact order the customer's Power BI expects.

**Why:** Only Python library that produces a styled XLSX that Power BI's
auto-detection treats correctly.

### `huey==3.0.0` (installed but not used)

**Status:** In `requirements.txt` and `core/pipeline/queue.py` exists, but
the active upload flow uses `threading.Thread` via `core/api/job_tracker.py`.
Huey is not started, not called, and not wired.

**Original intent:** Background job queue (SQLite-backed) for processing 100+
PDFs without blocking the UI thread.

**Current reality:** In-memory thread dict in `job_tracker.py`. Huey remains
in requirements in case the migration to a real queue is completed. See
[09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) N1.

### `RapidFuzz==3.14.5`

**Role:** Fuzzy string matching in the identity resolution engine.

**Why:** C++-backed Levenshtein and token-set ratios. ~10x faster than
pure-Python `fuzzywuzzy`. Used in `core/matching/engine.py`.

**Current status:** `core/matching/engine.py` is complete and correct. It is
not yet called in `projections.py` — exact SQL match is used instead. The
RapidFuzz dependency is still necessary and correct.

### `Flask==3.1.3` + `flask-cors==5.0.1`

**Role:** Single-process app serving both the HTML operator UI and the JSON
REST API for Power BI.

**Why:** Flask is the smallest sensible HTTP server in the Python ecosystem.
flask-cors enables Power BI's browser-based fetching to cross the
origin boundary from the BI tool to `localhost:7845`.

**Current CORS scope:** `origins="*"` — all origins allowed on `/api/*`.
This is wider than necessary for a localhost-only tool. Should be restricted
to `localhost` and `127.0.0.1`. See [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md).

### `pytest==9.0.3`

**Role:** Test runner.

**Test files present:**
- `tests/test_imports.py` — layer-rule import boundary enforcement
- `tests/test_phase1.py` through `test_phase4.py`, `test_phase8.py` — feature tests
- `tests/_import_scan.py`, `_third_party_scan.py`, `_dead_code_scan.py` — analysis helpers

## What's deliberately NOT in the stack

| Tech | Why we don't use it |
|------|---------------------|
| FastAPI | Flask is simpler for our routes; we don't need async |
| Postgres | SQLite is sufficient at our document volumes; a single file is operationally beautiful |
| Redis | Huey's SQLite backend removes the need (when/if Huey is wired) |
| Docker | Customer base is non-technical Windows users; `.bat` launchers is the right packaging |
| OpenAI / Anthropic API | Local-first is a positioning pillar — cloud LLM is a future optional tier |
| AWS Textract / Azure Form Recognizer | Same — also defeats the cost argument |
| Celery | Overkill for desktop-scale concurrency |
| React / Vue / Svelte | HTMX gives us reactivity without a build step |
| Tailwind via npm | DaisyUI CDN bundle — zero Node dependency (offline offline-mode gap: see roadmap) |
| Authentication framework | Local single-user app; multi-user is explicitly deferred |
| Streamlit | Fully removed. `START_APP.bat` now starts Flask directly. |

## Hidden non-Python dependencies

These are NOT in `requirements.txt` but the app needs them:

1. **Tesseract OCR binary** — bundled in `tesseract_bin/`. If missing, the
   app falls back to Ollama vision. Install via `install_tesseract.bat` if
   needed.
2. **Ollama** — installed via the Ollama Windows installer. After install:
   ```cmd
   ollama pull llama3
   ```
3. **Visual C++ Redistributable** — required by ChromaDB's ONNX runtime.
   Bundled with most modern Windows installs.

## Python version

The project currently runs on Python 3.14 (evidenced by `cpython-314` cache
files). Pydantic v2 requires 3.8+; walrus operator (`:=`) in `processor.py`
requires 3.8+. No features beyond the standard library 3.10+ are known to be
required. The official minimum is **Python 3.11** to ensure Pydantic v2
`Annotated` patterns work cleanly.
