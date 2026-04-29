# 03 — Technology Stack

Every dependency in `requirements.txt`, why it's there, and what it would cost
to swap it.

## Runtime stack at a glance

| Layer | Technology | Why this one |
|-------|------------|-------------|
| Language | Python 3.11+ | Mandatory for Pydantic v2 features and modern type hints |
| UI (current) | Streamlit 1.56 | Fastest path to a working dashboard; trades flexibility for speed |
| UI (target) | Flask + HTMX + DaisyUI | See [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) — full operator UI |
| LLM runtime | Ollama (default `llama3`) | Local inference, zero API cost, data never leaves machine |
| PDF text | PyMuPDF (`fitz`) | Fastest pure-Python PDF text extraction; lossless |
| OCR | Tesseract via `pytesseract` | Industry-standard OSS OCR; bundled installer ships with the app |
| Image processing | Pillow | Required by Tesseract and PassportEye for normalization |
| Passport MRZ | PassportEye + `mrz` | Deterministic MRZ band extraction — no LLM needed |
| Validation | Pydantic v2.13 | Strict typed schemas with field-level normalization |
| Storage | SQLite (stdlib) | Zero-install, file-based, BI-friendly |
| Vector search | ChromaDB 1.5 | Embedded, local; no separate vector DB service |
| Tabular ops | pandas 3.0 | Excel/CSV export, dataframe transforms in UI |
| Excel writer | openpyxl 3.1 | Required for the 49-column "Containers actifs" XLSX export |
| Job queue | Huey 3.0 (SQLite-backed) | Lets the UI stay responsive during 100-doc batches |
| Fuzzy matching | RapidFuzz 3.14 | Fastest Levenshtein/token-set ratio implementation in Python |
| HTTP | requests 2.33 | Talking to the Ollama daemon |
| BI bridge | Flask 3.1 + flask-cors 5.0 | Local REST server for Power BI connections |
| Tests | pytest 9.0 | Unit + import-rule enforcement (`tests/test_imports.py`) |

## Detailed reasoning per dependency

### `streamlit==1.56.0`

**Role:** Current main UI (dashboard, processing, edit forms, exports).

**Why:** Streamlit lets one developer ship a working data-app in a weekend. For
a single-developer project that needed to validate the pipeline with real
operators before committing to a frontend stack, this was correct.

**Cost of staying:** Streamlit's CSS injection model fights you on anything
beyond the default look. Widget internals (file uploaders, sliders) resist
deep theming. This is the reason the Flask + HTMX + DaisyUI migration is
underway.

**Replacement plan:** Phase 5 of the migration removes Streamlit from
`requirements.txt` entirely. Until then it stays.

### `PyMuPDF==1.27.2.2` (imported as `fitz`)

**Role:** Native PDF text extraction.

**Why:** Five to ten times faster than pdfplumber, more accurate at preserving
reading order than pdfminer.six, and exposes bounding-box coordinates needed
for the future "highlight-on-PDF" verification view.

**Watch-out:** AGPL-licensed. For a closed-source commercial sale this would
require a paid PyMuPDF Pro license. For local-install-only sale this is
acceptable.

### `pytesseract==0.3.13` + Tesseract binary

**Role:** OCR fallback for scanned PDFs and image documents.

**Why:** Tesseract is the only OSS OCR with quality competitive against AWS
Textract / Azure Form Recognizer for Latin-alphabet documents. It supports
Arabic and French out of the box (relevant for the Algerian customer base).

**Bundled install:** `install_tesseract.bat` (the launcher in the repo) handles
the binary install — a major UX issue for non-technical operators.

### `Pillow==12.2.0`

**Role:** Image preprocessing (binarization, deskew) before Tesseract /
PassportEye.

**Why:** Hard dependency of both pytesseract and PassportEye. Cannot be
removed.

### `passporteye==2.2.2` + `mrz==0.6.1`

**Role:** Locate and parse the MRZ (Machine Readable Zone) of passports and ID
cards.

**Why:** The MRZ is a fixed-format band at the bottom of every ICAO passport.
A specialist parser is dramatically more accurate than asking an LLM to read
it. PassportEye finds the band, the `mrz` library validates check digits and
extracts the structured fields.

**Specialist > generalist principle:** When a deterministic parser exists for
a domain, use it instead of the LLM. Reserve the LLM for the unstructured
visual fields (name spelling, address, etc.).

### `requests==2.33.1`

**Role:** HTTP client to talk to the Ollama daemon at
`http://localhost:11434/api/generate`.

**Why:** Stable, synchronous, simple. We are not bottlenecked on HTTP — we are
bottlenecked on LLM inference. Async would not help.

### `pydantic==2.13.2`

**Role:** Schema definition, validation, normalization.

**Why:** Pydantic v2 (rust-backed) is faster than v1 by an order of magnitude
and supports the `field_validator` decorator with `mode="before"`, which is
exactly what we need to canonicalize incoming LLM output before any other
field interacts with it.

**Critical pattern:** Every domain field on every schema has a normalizer.
`vessel_name` is uppercased. `container_number` is regex-checked. `etd`/`eta`
are date-normalized. This is the contract that lets BI tools downstream
trust the data.

### `chromadb==1.5.8`

**Role:** Local vector store for semantic document search.

**Why:** Embedded mode (no separate daemon), good Python API, integrates
cleanly with sentence-transformer embeddings. Lets the user search "cold-chain
shipment from MSC arriving April" instead of `WHERE vessel LIKE '%...'`.

**Cost:** Brings in ONNX runtime and sentence-transformers as transitives —
adds ~200MB to the install. Acceptable for a desktop app.

### `pandas==3.0.2`

**Role:** Dataframe operations for UI tables, CSV export, Excel export.

**Why:** Streamlit's `st.dataframe()` and `st.download_button()` for CSV both
expect pandas. Once you have pandas in the build, every dataframe-shaped
operation gets cheaper.

**Future:** When Streamlit goes away, evaluate dropping pandas in favor of
sqlite3 + manual rendering. Pandas alone is ~80MB in the install.

### `openpyxl==3.1.5`

**Role:** Generate the 49-column "Containers actifs" XLSX with column widths,
header styling, and the exact French column names the customer's Power BI
expects.

**Why:** It's the only Python library that can produce a styled XLSX that
Power BI's auto-detection treats correctly. CSV is easier but loses formatting.

### `huey==3.0.0`

**Role:** Background job queue (SQLite-backed) for batch processing.

**Why:** When a user drops 100 PDFs at once, the UI thread cannot block on
30s × 100 of LLM inference. Huey lets the consumer process them in the
background and the UI poll for status. SQLite-backed means no Redis
dependency.

**Currently:** Optional. The synchronous `process_pdf_file()` path still
exists for small batches.

### `RapidFuzz==3.14.5`

**Role:** Fuzzy string matching in the identity resolution engine.

**Why:** C++-backed implementation of Levenshtein and token-set ratios. ~10x
faster than the pure-Python `fuzzywuzzy`. We compute O(N) similarity scores
per new person against the existing person table — performance matters as the
table grows.

### `Flask==3.1.3` + `flask-cors==5.0.1`

**Role:** Local REST server for Power BI / Tableau / Looker live connections.

**Why:** Power BI's "Web" connector hits HTTP endpoints. Flask is the
smallest sensible HTTP server in the Python ecosystem; flask-cors enables
cross-origin requests so a browser-based BI tool on a different port can call
the API.

**Future:** This same Flask process is what will host the new HTMX + DaisyUI
UI. No second framework added — just more routes.

### `pytest==9.0.3`

**Role:** Test runner.

**Why:** Standard. The killer test is `tests/test_imports.py`, which scans
the import graph and fails CI if any module breaks the layer rules in
[ARCHITECTURE.md](ARCHITECTURE.md). This is what stops the codebase from
rotting.

## What's deliberately NOT in the stack

| Tech | Why we don't use it |
|------|---------------------|
| FastAPI | Flask is simpler for our routes; we don't need async |
| Postgres | SQLite is sufficient at our document volumes; a single file is operationally beautiful |
| Redis | Huey's SQLite backend removes the need |
| Docker | Customer base is non-technical Windows users; `.bat` launchers + `.exe` bundle is the right packaging |
| OpenAI / Anthropic API | Local-first is a positioning pillar (see [01-OVERVIEW.md](01-OVERVIEW.md)) |
| AWS Textract / Azure Form Recognizer | Same — also defeats the cost argument |
| Celery | Overkill for desktop-scale concurrency; Huey is sufficient |
| React / Vue / Svelte | HTMX gives us reactivity without a build step |
| Tailwind via npm | DaisyUI ships a CDN bundle — zero Node dependency |
| Authentication framework | Local single-user app; multi-user is explicitly out of scope (see [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md)) |

## Hidden non-Python dependencies

These are NOT in `requirements.txt` but the app needs them:

1. **Tesseract OCR binary** — installed via `install_tesseract.bat` from the
   UB-Mannheim Windows build. Path is auto-detected from the registry.
2. **Ollama** — installed via the Ollama Windows installer. Default
   `localhost:11434`. The user must run `ollama pull llama3` once.
3. **Visual C++ Redistributable** — required by ChromaDB's ONNX runtime.
   Bundled with most modern Windows installs.

## Why Python 3.11+

- Pydantic v2's `Annotated` patterns work cleanly only on 3.11+.
- `match` statements in the pipeline router (Python 3.10+).
- Walrus operator (`:=`) used in `core/pipeline/processor.py` for streaming
  hash chunks (Python 3.8+ but combined with the above).

3.12 is preferred. 3.13 has not been validated against the ChromaDB ONNX
combination at time of writing.
