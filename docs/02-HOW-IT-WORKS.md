# 02 — How It Works

End-to-end walkthrough: a PDF lands on disk, a structured row appears in
SQLite, and a Power BI dashboard refreshes. This document traces every step.

## The pipeline at a glance

```
┌─────────────────────────────────────────────────────────────────────┐
│  PDF (booking.pdf)                                                  │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 0 — SHA-256 hash → check extraction_cache table               │
│  • Hit  → return cached JSON, skip LLM (saves 5-30s)                │
│  • Miss → continue                                                  │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1 — Text extraction                                           │
│  • PyMuPDF reads native PDF text                                    │
│  • If empty (scanned PDF) → Tesseract OCR fallback                  │
│  • For passports → PassportEye + mrz library for MRZ band           │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 2 — Chunking (only if text > 6000 chars)                      │
│  • core/extraction/chunker.py splits intelligently on page breaks   │
│  • Map: each chunk → LLM extract                                    │
│  • Reduce: merge_chunk_results consolidates                         │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 3 — LLM extraction (Ollama)                                   │
│  • Loads domain prompt: modules/logistics/prompts.py or travel/     │
│  • POST http://localhost:11434/api/generate                         │
│  • Model: llama3 (default), 180s timeout                            │
│  • Retry once on failure                                            │
│  • Parse JSON from response (strict, no markdown allowed)           │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 4 — Validation (Pydantic v2)                                  │
│  • core/schemas/{logistics,person}.py models                        │
│  • Field validators normalize on the way in:                        │
│      - container_number → "AAAU1234567"                             │
│      - dates → "YYYY-MM-DD"                                         │
│      - shipping_company → canonical brand                           │
│      - vessel_name → UPPER                                          │
│  • If validation fails, log and skip (do not pollute DB)            │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 5 — Identity resolution (Travel only)                         │
│  • core/matching/engine.py compares vs existing persons             │
│  • Weighted score: 60% name + 30% DOB + 10% nationality             │
│  • ≥ 0.85 → AUTO_MERGED                                             │
│  • ≥ 0.60 → REVIEW (flagged for human)                              │
│  • <  0.60 → NEW_IDENTITY                                           │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 6 — Storage (SQLite)                                          │
│  • core/storage/repository.py                                       │
│  • Logistics UPSERT key: TAN first, fallback to vessel + ETD        │
│  • Status lifecycle: BOOKING → BOOKED, DEPARTURE/BL → IN_TRANSIT    │
│  • Cache the extraction JSON for next time                          │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 7 — Audit + indexing                                          │
│  • core/audit/logger.py writes per-file JSON log to data/logs/      │
│  • core/search/vector_db.py embeds the doc into ChromaDB            │
│    for semantic search later                                        │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Result available via:                                              │
│  • Streamlit / Flask UI (live)                                      │
│  • REST endpoint http://localhost:7845/api/logistics/shipments      │
│  • Excel export (49-column "Containers actifs" format)              │
│  • CSV export                                                       │
│  • Power BI live connection                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Step-by-step detail

### Step 0 — Cryptographic deduplication

Implementation: `core/pipeline/processor.py::PipelineProcessor.process_file`

```python
file_hash = hashlib.sha256()
with open(file_path, 'rb') as f:
    while chunk := f.read(8192):
        file_hash.update(chunk)
file_hash_hex = file_hash.hexdigest()

cached = conn.execute(
    "SELECT result_json FROM extraction_cache WHERE file_hash=?",
    (file_hash_hex,)
).fetchone()
```

This is one of the most underrated features. A clerk re-uploading the same PDF
twice gets an instant response instead of waiting 30 seconds for Ollama. The
cache is **path-independent** — `booking_v1.pdf` and `final_booking.pdf` with
identical bytes share the same cache entry.

### Step 1 — Text extraction strategy

Implementation: `core/extraction/text_extractor.py`

Decision tree:
1. **Native PDF text** → PyMuPDF (`fitz.open(path).get_text()`) — fast, lossless.
2. **Scanned PDF (no extractable text)** → Tesseract OCR via pytesseract.
3. **Passport image** → PassportEye locates the MRZ band, then `mrz` library
   parses it deterministically (no LLM needed for the MRZ — it's a fixed
   format).

The LLM only ever sees the extracted text, never the raw PDF. This keeps the
prompt small and the cost predictable.

### Step 2 — Chunking (long documents)

Implementation: `core/extraction/chunker.py`

A 30-page bill of lading would blow past the LLM context window. The chunker:

1. Splits text on natural page boundaries from PyMuPDF.
2. Caps each chunk at ~6000 chars (model-safe).
3. Runs each chunk through the LLM (map step).
4. Merges results via `merge_chunk_results` — for logistics, this means
   concatenating container arrays and taking the first non-null value for
   shipment-level fields.

### Step 3 — LLM extraction

Implementation: `core/extraction/llm_client.py` + `modules/<domain>/prompts.py`

The prompt template is **strict and deterministic**:

```text
You are a strict logistics document parser. Read the document below and
return ONLY valid JSON — no markdown, no explanation.

Required JSON structure:
{
  "document_type": "BOOKING" | "DEPARTURE" | "BILL_OF_LADING",
  "tan_number": "TAN/XXXX/YYYY or null",
  ...
}

RULES:
- Size normalization:
    40' HIGH CUBE, 40HC, 40HQ, 40 GP, 40'ST, 40' DRY  →  "40 feet"
    20 RF, 20 REEF, 20 REF                            →  "20 feet refrigerated"
- Dates: ALWAYS convert to YYYY-MM-DD. "11-Mar-26" → "2026-03-11".
- shipping_company: normalize — "CMA CGM" or "CMA-CGM" → "CMA-CGM";
  "MEDITERRANEAN SHIPPING" → "MSC".
```

Two design choices worth noting:

1. **Normalization happens at the prompt level AND at the validator level.**
   The prompt asks the LLM to canonicalize, and the Pydantic field validator
   re-canonicalizes (defense in depth).
2. **Fields that don't exist must be `null`, not empty strings.** This makes
   downstream validation unambiguous.

Retry policy: one retry on exception. If both attempts fail, log to
`data/logs/<filename>.json` and skip — do not corrupt the DB.

### Step 4 — Pydantic validation

Implementation: `core/schemas/logistics.py`, `core/schemas/person.py`

Field validators run automatically on instantiation:

```python
@field_validator("container_number", mode="before")
@classmethod
def norm_cnum(cls, v):
    return container_number(v)   # → core/normalization/codes.py
```

`container_number()` enforces the ISO 6346 pattern (4 letters + 7 digits) and
strips any spaces or dashes. If the input is malformed, the model raises
`ValidationError` and the file is rejected with a clear log entry.

### Step 5 — Identity resolution (Travel only)

Implementation: `core/matching/engine.py`

When a passport arrives, we compute:

```
total_score = 0.6 * name_similarity
            + 0.3 * dob_similarity
            + 0.1 * nationality_similarity
```

- `name_similarity` uses RapidFuzz on the **normalized** name (lowercase,
  diacritics stripped, name parts sorted alphabetically — see
  `core/normalization/names.py`).
- `dob_similarity` is binary (1.0 if equal, else 0.0).
- `nationality_similarity` is binary on 3-letter ISO codes.

Thresholds (`core/matching/thresholds.py`):

| Score | Status | Action |
|-------|--------|--------|
| ≥ 0.85 | `AUTO_MERGED` | Link to existing person, no UI prompt |
| 0.60 – 0.85 | `REVIEW` | Surface in match-review panel |
| < 0.60 | `NEW_IDENTITY` | Insert as new person |

### Step 6 — Storage and UPSERT keys

Implementation: `core/storage/repository.py` and
`logistics_app/database_logic/database.py::upsert_shipment`

Logistics UPSERT logic:
1. Try to match on `tan_number` (`TAN/XXXX/YYYY`). If found → UPDATE.
2. Else try to match on `(vessel_name, etd)` composite. If found → UPDATE.
3. Else → INSERT new shipment.

Status lifecycle:
- `BOOKING` document → status becomes `BOOKED`
- `DEPARTURE` or `BILL_OF_LADING` document → status becomes `IN_TRANSIT`
- Manual override available in the Edit page

This means the **same shipment** progresses through statuses as new documents
arrive over time — exactly mirroring how a real shipment moves from booking to
arrival.

### Step 7 — Audit and vector indexing

Per-file audit log (`core/audit/logger.py`) writes one JSON file per processed
PDF, recording the full extraction result, validation status, DB action, and
any errors. This is the "Logs" tab in the UI.

Vector indexing (`core/search/vector_db.py`) embeds the document text into a
ChromaDB collection so a user can later type "container with reefer arriving
April from Le Havre" and get hits across thousands of historical documents.

## What runs where

| Process | What it does | When it runs |
|---------|--------------|--------------|
| Streamlit UI (`app.py`) | Current main UI on port 8501 | Foreground, started by `START_APP.bat` |
| Flask BI server (`core/api/server.py`) | REST endpoints + (in P1) HTML UI on port 7845 | Foreground, started by `START_BI_CONNECTOR.bat` |
| Ollama daemon | Hosts the local LLM | Background service on port 11434 |
| Huey consumer (optional) | Background batch processor | `huey_consumer.py core.pipeline.queue.task_queue` |
| ChromaDB | Embedded inside the Python process | No separate daemon |

## Failure modes and fallbacks

| Failure | What happens |
|---------|--------------|
| Ollama not running | UI shows orange "Ollama not detected" badge, processing button disabled |
| LLM returns invalid JSON | One retry → log → skip. DB stays clean. |
| Pydantic validation fails | Log full error including which field → skip → user sees in Logs tab |
| PDF has no extractable text | OCR fallback fires automatically |
| Same file uploaded twice | Cache hit, instant return |
| Disk full | SQLite write fails → caught and logged → user sees DB_ERROR in Processing tab |
| Two shipments with same TAN but different containers | UPSERT updates the shipment row, container array is replaced atomically |

## Why this architecture is robust

1. **Separation of LLM and database.** The LLM never writes to SQLite. Pydantic
   stands between them.
2. **Idempotent ingestion.** Re-running the same PDF produces the same DB
   state. Cache + UPSERT guarantee this.
3. **No global mutable state in the pipeline.** Each PDF is a fresh `Job`
   object. Concurrent processing is safe (and is what enables the Huey queue).
4. **Domain logic is pluggable.** Adding a third domain (e.g., medical
   referrals) requires `modules/medical/{config,prompts,pipeline}.py` and
   `core/schemas/medical.py` — no changes to `core/`.
