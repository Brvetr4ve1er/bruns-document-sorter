# 02 — How It Works

End-to-end walkthrough: a PDF lands on disk, a structured row appears in
SQLite, and a Power BI dashboard refreshes. This document traces every step
with the exact file and line that implements it.

---

## The pipeline at a glance

```
PDF / image
    │
    ▼  core/pipeline/processor.py  PipelineProcessor.process_file()
    │
    ├─ Step 0 ── SHA-256 hash ──────────────────────────────────────────
    │            ↳ check extraction_cache table
    │            HIT + same prompt_version  → return cached JSON, skip LLM
    │            MISS or stale version      → continue
    │
    ├─ Step 1 ── Text extraction  (core/extraction/text_extractor.py)
    │            Strategy 1: PyMuPDF native text  (fast, works on digital PDFs)
    │            Strategy 2: Tesseract OCR  (scanned pages)
    │                        Pass 1: fra+eng
    │                        Pass 2: ara+fra+eng  if Arabic chars detected
    │                                             or first-pass yield < 40 chars
    │            Strategy 3: Ollama vision model  (if Tesseract unavailable)
    │            Special:    PassportEye + mrz lib for MRZ band  (travel only)
    │
    ├─ Step 2 ── Chunking  (core/extraction/chunker.py)
    │            Only if text > 3 000 chars AND file is PDF
    │            5-page windows, 1-page overlap
    │            Map: each chunk → LLM  |  Reduce: merge_chunk_results
    │
    ├─ Step 3 ── LLM extraction  (core/extraction/llm_client.py)
    │            POST to configured provider (Ollama/LMStudio/OpenAI/Anthropic)
    │            format="json" mode to reduce drift
    │            Retry on invalid JSON (corrective prompt + bad output included)
    │            Compute confidence score from critical-field coverage
    │
    ├─ Step 4 ── Rule-based validation  (core/validation/engine.py)
    │            5 rules for logistics; 0 for travel
    │            Violations logged; do NOT block storage (warnings only)
    │
    ├─ Step 5 ── Storage  (core/storage/repository.py)
    │            INSERT into documents table (raw text + LLM JSON + confidence)
    │            UPDATE extraction_cache (file_hash + result + prompt_version)
    │
    ├─ Step 6 ── Domain projection  (core/api/projections.py)
    │            LOGISTICS: upsert shipments, insert containers
    │            TRAVEL:    MRZ override → person match → documents_travel insert
    │
    └─ Step 7 ── Vector embedding  (core/search/vector_db.py + ChromaDB)
                 Non-blocking. ChromaDB failure → warning, not error.
```

---

## Step 0 — Cryptographic deduplication

**File:** `core/pipeline/processor.py:42–70`

Every file is SHA-256 hashed before anything else:

```python
h = hashlib.sha256()
with open(file_path, "rb") as f:
    while chunk := f.read(8192):
        h.update(chunk)
file_hash = h.hexdigest()
```

The hash is checked against `extraction_cache.file_hash`. If a matching row
exists **and** the stored `prompt_version` matches the current version registered
in `prompt_registry.py`, the cached `result_json` is returned immediately.
No text extraction, no LLM call. A clerk re-uploading a PDF they already
processed gets an instant response.

If the prompt was updated (version bumped in `modules/*/prompts.py`), the cache
entry is stale and full extraction re-runs — so operators can transparently
get the benefit of improved prompts without manual intervention.

---

## Step 1 — Text extraction

**File:** `core/extraction/text_extractor.py`

### Strategy selection per page

```
page.get_text() → len ≥ 30 chars?
    YES → use embedded text (Strategy 1, fast)
    NO  → image page, try OCR
          _tesseract_available()
              YES → _ocr_with_tesseract(page)
                    Pass 1: fra+eng
                    result: len < 40 chars OR Arabic Unicode detected?
                        YES → Pass 2: ara+fra+eng
                    return best result
              NO  → _ollama_vision_available()
                        YES → _ocr_with_ollama_vision(page, model)
                        NO  → empty string (page skipped)
```

### Arabic detection (P2-F)

The Arabic Unicode check covers three blocks:
- `U+0600–U+06FF` — Arabic main block
- `U+0750–U+077F` — Arabic Supplement
- `U+FB50–U+FDFF` — Arabic Presentation Forms-A
- `U+FE70–U+FEFF` — Arabic Presentation Forms-B

If any character falls in these ranges, or the first-pass yield is < 40 chars
(suggesting the English/French model is confused by the script), a second OCR
pass runs with `ara+fra+eng`. The longer result wins.

### Vision fallback

When Tesseract is unavailable, `_ollama_vision_available()` queries Ollama's
`/api/tags` endpoint and tries `llama3.2-vision`, `llava`, `llava:13b`,
`minicpm-v`, `moondream` in order. The prompt is:

> "This is a page from a document. Extract ALL visible text exactly as
> written, preserving layout. Return only the extracted text."

### Known issue (TD6)

`_tesseract_available()` calls `pytesseract.get_tesseract_version()` on every
invocation — one subprocess per page. On a 20-page scanned PDF, 20 version
checks run. The fix (a module-level `_TESSERACT_AVAILABLE: bool | None = None`
cache) is straightforward but not yet applied.

---

## Step 2 — Chunking

**File:** `core/extraction/chunker.py`

Only fires when `len(extracted_text) > CHUNKING_THRESHOLD_CHARS (3000)` AND
the input is a PDF (not a standalone image).

**Why chunking matters:** Carrier PDFs often contain 10–30 pages. Sending all
text to the LLM at once risks exceeding context windows and produces lower-quality
extractions as the model attends to everything equally.

**Map step:** Slide a 5-page window with 1-page overlap across the document.
Each chunk is independently submitted to the LLM.

**Reduce step (`merge_chunk_results`):** For scalar fields, the last non-null
value wins (later pages in a BL usually have more complete data). For list
fields (`containers`), results are concatenated with container-number
deduplication.

---

## Step 3 — LLM extraction

**File:** `core/extraction/llm_client.py`

### Provider routing

The provider is resolved at extraction time from `data/.llm_config.json` (set
via the LLM modal in the UI). Configuration is per-provider:

```
Ollama    → POST {base_url}:{port}/api/generate
LM Studio → POST {base_url}:{port}/v1/completions
OpenAI    → POST https://api.openai.com/v1/chat/completions  (Bearer key)
Anthropic → POST https://api.anthropic.com/v1/messages       (x-api-key header)
```

The `format="json"` parameter is sent to Ollama to force structured output.
For OpenAI/Anthropic, the system prompt explicitly demands "Return ONLY a
JSON object — no markdown, no code fences."

### Retry logic

```python
for attempt in range(2):
    try:
        raw = llm.generate(prompt)
        json.loads(_strip_code_fences(raw))  # validate
        return result
    except json.JSONDecodeError:
        # Corrective prompt includes the bad output
        prompt = f"That response was invalid JSON: {raw[:500]}\nFix it."
```

Two failures → exception → job fails with `JobStatus.FAILED`.

### Confidence scoring

After extraction, a per-module score is computed:

```python
_CONFIDENCE_FIELDS = {
    "logistics": ["tan_number", "vessel_name", "etd", "eta",
                  "shipping_company", "containers"],
    "travel":    ["document_type", "document_number", "full_name",
                  "dob", "nationality", "expiry_date"],
}
```

`score = filled_critical_fields / total_critical_fields`

A field is "filled" if it's non-null, non-empty string, and non-empty list.
Score < 0.60 → needs attention; 0.60–0.89 → review queue; ≥ 0.90 → auto-approved.

### Prompt structure (logistics, v2.0)

`modules/logistics/prompts.py` is a 170-line JSON schema instruction. Key
design choices:

- **Wide and nested**: captures every field across all document types
  (booking confirmations, departure notices, BLs, arrival notices)
- **Null contract**: "If a field is missing, return null. Never invent values."
- **Normalization in the prompt**: "Dates ALWAYS in ISO YYYY-MM-DD.
  Container numbers: 4 letters + 7 digits. TAN: normalize to TAN/XXXX/YYYY."
- **additional_fields catch-all**: any field not in the schema goes here
- **Version string**: `v2.0` — bumping this version invalidates all cache entries

---

## Step 4 — Validation

**File:** `core/validation/engine.py`

Five rules run for logistics extractions:

| Rule ID | Check | Severity |
|---------|-------|---------|
| `date_sequence` | ETD < ETA | error |
| `delivery_sequence` | delivery date ≥ ETA | warning |
| `surestarie_positive` | demurrage days ≥ 0 | warning |
| `container_number_format` | regex `^[A-Z]{3,4}\d{6,7}$` | error |
| `tan_number_format` | regex `^TAN/\d{4}/\d{4}$` | warning |

**Important:** validation failures do NOT block storage. A document with
format errors still gets saved — the operator sees the issues in the review
queue and can correct them manually. This is intentional: blocking on a
slightly malformed TAN would lose data the operator needs.

Travel module currently has zero validation rules (`validate_extraction`
returns an empty list). Travel-specific rules (passport expiry in the future,
MRZ check digit validation) are a gap worth filling.

---

## Step 5 — Storage

**File:** `core/storage/repository.py` + `core/storage/db.py`

```python
doc_id = insert_document(db_path, {
    "type":           doc_type,
    "raw_text":       full_text,
    "extracted_json": json.dumps(extracted_data),
    "confidence":     confidence_score,
    "source_file":    file_path,
    "module":         module,
})
```

This is the **audit-safe source of truth**. Every extraction permanently
stores the raw LLM JSON, the raw text, and the confidence score. Even if
projections or normalizations are wrong, the original LLM output is always
recoverable.

The `extraction_cache` is updated after every non-cached extraction:
`(file_hash, result_json, prompt_version)`. On re-upload of the same file,
the cache check fires first and returns the stored result instantly.

---

## Step 6 — Domain projection

**File:** `core/api/projections.py`

This module bridges the generic `documents` table to the domain-specific
tables the UI and BI layer actually query.

### Logistics projection (`_project_logistics`)

```
extracted_data  ──→  parse TAN, vessel, carrier, ETD, ETA, containers
                ──→  find existing shipment by exact TAN match
                         FOUND  → UPDATE modified fields on existing row
                         NOT FOUND → INSERT new shipments row
                ──→  for each container in extracted_data["containers"]:
                         check (shipment_id, container_number) uniqueness
                         UNIQUE → INSERT containers row
                         EXISTS → skip (idempotent)
```

**Column names used:** `tan`, `compagnie_maritime`, `vessel`, `document_type`
(legacy schema from `database_logic/database.py` — these are what the live DB
actually has, NOT what `core/storage/db.py::init_schema()` creates — see TD1).

**Upsert key:** TAN is the primary upsert key. If a Booking Confirmation and
a Departure Notice for the same shipment both arrive, the second document
updates the existing row rather than creating a duplicate.

### Travel projection (`_project_travel`)

```
extracted_data + source_file
    ──→  run MRZ extraction on source_file  (PassportEye + mrz library)
         MRZ values OVERRIDE LLM values for:
             full_name, dob, doc_number, expiry_date, nationality, gender
    ──→  normalize full_name → normalized_name (lowercase, whitespace-collapsed)
    ──→  SELECT id FROM persons WHERE normalized_name = ?
         FOUND  → reuse person_id  (⚠ exact match only — fuzzy engine not yet wired)
         NOT FOUND → INSERT persons row
    ──→  INSERT documents_travel (person_id, family_id, doc_type, doc_number,
                                  expiry_date, mrz_raw, original_doc_id)
```

**Known gap (TD5):** `core/matching/engine.py` implements full RapidFuzz-based
fuzzy identity resolution with weighted name/DOB/nationality scoring and
AUTO_MERGE/REVIEW/NEW_IDENTITY thresholds. It is complete but not called here.
The exact-match `WHERE normalized_name = ?` is a placeholder. Name variations
("Mohammed AbdelKader" ≠ "Mohamed Abdelkader") silently create duplicate
person rows.

---

## Step 7 — Vector embedding

**File:** `core/search/vector_db.py` (ChromaDB wrapper)

```python
combined_text = f"Module: {module}\nStructured Data: {json.dumps(extracted)}\nRaw Text: {raw[:2000]}"
collection.upsert(documents=[combined_text], metadatas=[metadata], ids=[f"doc_{doc_id}"])
```

The ChromaDB collection uses cosine similarity (`hnsw:space: cosine`). The
`VectorSearchEngine.search()` method filters by module and returns ranked
document IDs.

The `/logistics/documents?semantic=1` toggle and `/search` route both use
this index. If ChromaDB is unavailable or the index is empty, both fall back
to SQL LIKE matching without error.

---

## Upload flow (UI side)

```
POST /logistics/upload
    │
    ├─ Save uploaded file to data/input/logistics/<hash>_<filename>
    ├─ job_tracker.submit_job(file_path, module, doc_type)
    │       ↳ generates UUID job_id
    │       ↳ spawns threading.Thread → pipeline/router.route_file()
    │           ↳ _resolve_llm_settings() reads data/.llm_config.json
    │           ↳ PipelineProcessor(llm_client, db_path).process_file(...)
    │               ↳ Steps 0–7 above
    │
    └─ Returns HTMX fragment with job_id for polling
           ↳ HTMX polls GET /logistics/process-status/<job_id> every 2s
           ↳ Fragment updates until status = DONE or FAILED
```

**Job lifecycle (in memory only):** `job_tracker.py` stores `dict[str, Job]`
in process memory. Server restart loses job history. The `jobs` SQLite table
exists in the schema but is not written to — this was intended for Huey
persistence (Huey is in `requirements.txt` but inactive).

---

## Demurrage & Detention calculator

**File:** `core/api/server.py::_demurrage_info()` and `_calc_demurrage()`

The calculator runs when a container detail page loads or a swimlane renders.
It does not persist results — calculated on every request.

### Inputs
- `eta` (ISO date) from the associated shipment row
- `date_restitution` or `date_livraison` from the container row (earliest wins)
- `taux_de_change` from the container row (default 135 DZD/USD)
- Carrier name → free days lookup
- Container size → tiered rate selection

### Tiered rate tables (CMA-CGM, from real BL clause)

```
Days 1–15:   free
Days 16–45:  $20/day (20ft) / $40/day (40ft)
Days 46–60:  $40/day (20ft) / $80/day (40ft)
Days 61–90:  $60/day (20ft) / $110/day (40ft)
Days 91+:    $80/day (20ft) / $140/day (40ft)
```

Default free days: CMA-CGM=15, MSC=14, Maersk=12, others=14.

### Risk levels

```
days_over_free > 30   → critical
days_over_free > 14   → high
days_over_free > 0    → medium
days_remaining ≤ 3    → low
else                  → none
```

### Known gap (N5/N6)

The LLM prompt already extracts `free_days` and `demurrage_terms` from BL
documents. `_demurrage_info()` ignores them and uses hardcoded defaults. Wiring
the extracted `free_days` value would make the calculator accurate without
operator intervention.

Also, the clock currently starts from `eta` (estimated arrival). The correct
clock start is `date_avis_arrivee` (arrival notice date), which is only available
once the ARRIVAL_NOTICE document type is added to the logistics prompt.

---

## Cross-document reconciliation

**File:** `core/api/server.py::_reconcile_siblings()`

Triggered on every document detail page load (not cached — runs per request).

```
1. Get TAN from current document's extracted_json
2. Query: SELECT * FROM documents WHERE extracted_json LIKE '%{TAN}%' AND id != {current}
3. Parse each sibling's extracted_json and verify tan_number matches exactly
4. Compare across all documents sharing this TAN:
   - vessel_name: set of distinct values → len > 1 → discrepancy
   - etd: set of distinct values → len > 1 → discrepancy
   - eta: set of distinct values → len > 1 → discrepancy
   - container_numbers: union vs intersection → absent containers flagged
   - gross_weight per container: parse numeric, compare pairwise, flag if > 5% diff
5. Return {siblings, discrepancies, summary, has_issues}
```

---

## NL2SQL ("Ask your data")

**File:** `core/api/server.py::_generate_sql_from_question()` + `ui_logistics_ask()`

```
User question (French or English)
    │
    ├─ Build prompt: _NL2SQL_SYSTEM (compact schema description) + question
    │
    ├─ POST to configured Ollama/cloud model
    │
    ├─ Safety gate: strip_code_fences → startswith("SELECT")
    │   FAIL → return error fragment
    │
    └─ conn.execute(generated_sql).fetchmany(50)
       → render _ask_result.html (results table + SQL disclosure)
```

The schema description injected into the prompt:
```
shipments: id, tan, item_description, compagnie_maritime, port, transitaire,
  vessel, etd, eta, document_type, status, source_file, created_at
containers: id, shipment_id, container_number, size, seal_number,
  statut_container, date_livraison, ...
JOIN: containers c JOIN shipments s ON s.id = c.shipment_id
```

**Known gap (TD7):** The `startswith("SELECT")` check is bypassable with
`SELECT 1; DROP TABLE containers;`. No forbidden-keyword list, no
`PRAGMA query_only` connection constraint applied yet.

---

## Failure modes and fallbacks

| Failure | Behavior |
|---------|----------|
| Ollama not running | Upload succeeds; job fails with "LLM not reachable" logged |
| LLM returns invalid JSON | Corrective retry fires; second failure → job FAILED |
| Tesseract unavailable | Tries Ollama vision; if neither → page skipped, extraction with partial text |
| PDF has no embedded text | OCR chain fires |
| Same file re-uploaded (same prompt version) | Cache hit → instant return, no LLM call |
| Same file re-uploaded (prompt changed) | Cache miss → fresh extraction |
| Exception during processing | SQLite connection NOT closed (TD4 — connection leak) |
| Same TAN in two documents | Idempotent: second extraction updates shipment, skips duplicate containers |
| Person name variation in travel | Creates duplicate Person row (fuzzy engine not wired — TD5) |
| ChromaDB unavailable | Vector embedding skipped (non-fatal warning) |
| Semantic search with empty index | Falls back to SQL LIKE silently |

---

## What runs where

| Process | What | Start |
|---------|------|-------|
| Flask (core.api.server) | HTML UI + REST API on port 7845 | `START_APP.bat` |
| Ollama daemon | Local LLM host on port 11434 | Background service |
| ChromaDB | Embedded inside Flask process | No separate daemon needed |
| Tesseract | Spawned as subprocess per OCR call | No daemon |
