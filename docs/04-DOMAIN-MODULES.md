# 04 — Domain Modules

The platform is split into a domain-agnostic `core/` engine and one folder per
business domain in `modules/`. Each domain owns its prompts, configuration,
and any specialist parsers. Currently shipped: **Logistics** and **Travel**.

## Module pattern (template for new domains)

```
modules/<domain>/
├── __init__.py
├── config.py          ← model name, timeouts, output column lists, paths
├── prompts.py         ← LLM prompt templates registered with prompt_registry
├── pipeline.py        ← thin domain-specific orchestration (optional)
└── <specialist>.py    ← deterministic parsers if a deterministic format exists
                          (e.g. mrz_parser.py for Travel)
```

A domain plugs into the platform by:
1. Defining its Pydantic schemas in `core/schemas/<domain>.py`.
2. Registering its prompts in `modules/<domain>/prompts.py::init_prompts()`.
3. Adding upload + dashboard routes to `core/api/server.py` (or a Blueprint).
4. Adding a mode tile to `core/api/templates/mode_picker.html`.
5. Getting its own SQLite file in `data/<domain>.db`.

No changes to `core/` engine internals are required. If they are, the
abstraction in `core/` is wrong — fix it before adding the domain.

---

## Logistics module

**Mission:** Replace the manual workflow of typing carrier-PDF data into a
49-column "Containers actifs" Excel.

### Documents handled

| Type | What it is | Triggers status change |
|------|-----------|------------------------|
| `BOOKING` | Booking confirmation from carrier | `status → BOOKED` |
| `DEPARTURE` | Departure notice (vessel left origin port) | `status → IN_TRANSIT` |
| `BILL_OF_LADING` | Bill of lading | `status → IN_TRANSIT` |
| `ARRIVAL_NOTICE` | Avis d'arrivée | `status → ARRIVED` *(planned — see roadmap)* |
| `OTHER` | Anything else detected | No status change |

### Carriers normalized

Hard-coded canonical brands in the v2.0 prompt (`modules/logistics/prompts.py`):

- `CMA-CGM` (matches: `CMA CGM`, `CMA-CGM`, `CMACGM`)
- `MSC` (matches: `MEDITERRANEAN SHIPPING COMPANY`, `MSC`)
- `Ignazio Messina`
- `Pyramid Lines`
- `Maersk`
- `Hapag-Lloyd`
- `other` (anything not matched above — kept verbatim in `additional_fields`)

**Known issue:** Carriers like ONE, Zim, PIL, and Yang Ming fall into "other",
breaking analytics grouping for those carriers. A carrier lookup table that
preserves the raw name is a roadmap item.

### Container size canonicalization

The prompt enforces four canonical buckets:

| Carrier writes | We store |
|----------------|----------|
| `40' HIGH CUBE`, `40HC`, `40HQ`, `40 GP`, `40'ST`, `40' DRY`, `40HC` | `40 feet` |
| `20' HIGH CUBE`, `20HC`, `20 GP`, `20'ST`, `20' DRY` | `20 feet` |
| `40 RF`, `40 REEF`, `40 REFRIGERATED`, `40HQ RF` | `40 feet refrigerated` |
| `20 RF`, `20 REEF`, `20 REFRIGERATED` | `20 feet refrigerated` |

### TAN as the primary upsert key

The `TAN` (Titre d'Acconage Numéroté) is the customs reference that follows a
shipment from booking to discharge. Format: `TAN/XXXX/YYYY`.

Upsert order in `core/api/projections.py::_project_logistics`:
1. Match on `tan` (exact, case-sensitive). If found → skip INSERT.
2. No vessel+ETD fallback in the current projection code (that logic lives in
   the legacy `database_logic/database.py::upsert_shipment` which is dead code).
3. Else → INSERT new shipment row.

Status derivation:
- `document_type == "BOOKING"` → `status = "BOOKED"`
- `document_type == "DEPARTURE"` → `status = "IN_TRANSIT"`
- Anything else → `status = "UNKNOWN"`

### The projection column names

The live `logistics.db` uses the schema defined in `database_logic/database.py`
(legacy, but authoritative for the live database). Column names the server
queries — and that must match the DB — are:

| Column | Not |
|--------|-----|
| `tan` | ~~`tan_number`~~ |
| `compagnie_maritime` | ~~`shipping_company`~~ |
| `vessel` | ~~`vessel_name`~~ |
| `document_type` | ~~`doc_type`~~ |
| `item_description` | ~~`item`~~ |
| `source_file` | — |
| `created_at`, `modified_at` | — |

`core/storage/db.py::init_schema()` creates a **different** column set
(`carrier`, `doc_type` instead of `compagnie_maritime`, `document_type`).
This is the dual-schema bug — see [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) TD1.

### XLSX export

Implementation: `core/storage/exporters/xlsx.py`

Produces the 49-column "Containers actifs" workbook with French column names.
The customer's Power BI report was built on this exact column list — any rename
breaks it. This is the hard integration contract.

### Demurrage calculation

Implementation: `core/api/server.py::_demurrage_info()` and `_calc_demurrage()`

A tiered carrier rate structure is hardcoded (CMA-CGM rates from actual BL
CFA0869742). Rates for other carriers use the same tiers as a default.
The LLM prompt now extracts `free_days` and `demurrage_terms` from documents,
but the projection layer does not yet read these back into the calculation —
the hardcoded per-carrier free-day defaults are used instead. Fixing this is
tracked in the roadmap.

---

## Travel module

**Mission:** Build family-immigration case files from passport scans.

### Documents handled

| Type | Specialist parser? | LLM used? |
|------|-------------------|-----------|
| `PASSPORT` | Yes — PassportEye + `mrz` for MRZ band | Yes — for visual fields |
| `ID_CARD` | Yes — same MRZ checkers | Yes — for visual fields |
| `BIRTH_CERTIFICATE` | No | Yes — full LLM extraction |
| `VISA` | No | Yes |
| Others (`UNKNOWN`) | No | Yes |

### Why MRZ parsing first

The MRZ band on a passport encodes name, DOB, nationality, document number,
expiry date, and gender in a fixed-width OCR-friendly format with check digits.
A specialist parser:
- Validates check digits → catches OCR errors before they hit the DB.
- Extracts ISO 3166 nationality codes deterministically.
- Runs in milliseconds.

In the projection (`core/api/projections.py::_project_travel`), MRZ data
**overrides LLM data** for the fields where MRZ has it — LLM keeps any extra
fields (issue_date, place_of_birth, etc.) that MRZ doesn't cover.

### Identity resolution — current state

**What exists:** `core/matching/engine.py` implements `resolve_identity()` with
RapidFuzz-based fuzzy matching:

```
score = 0.6 × name_similarity (RapidFuzz token-set ratio on normalized names)
      + 0.3 × dob_similarity  (binary: 1.0 if equal, 0.0 if different)
      + 0.1 × nationality_similarity (binary on 3-letter ISO codes)
```

Thresholds (`core/matching/thresholds.py`):
- ≥ 0.85 → `AUTO_MERGED`
- ≥ 0.60 → `REVIEW`
- < 0.60 → `NEW_IDENTITY`

**What's wired:** `projections.py` currently uses a plain SQL query:
```python
SELECT id FROM persons WHERE normalized_name = ?
```
This is exact equality only. The fuzzy matching engine is complete but **not
called**. This means name variations (transliteration drift, spelling differences)
create duplicate person rows.

Wiring the matching engine is the highest-priority improvement for the Travel
module. See [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md).

### Family construction

A `Family` record links multiple `Person` records via `family_id`. The families
table has case management fields: `case_status` (COLLECTING/READY/IN_REVIEW/
SUBMITTED/APPROVED/REJECTED), `next_action`, `next_action_date`, `head_person_id`.

The family completeness gate (`core/api/server.py::_family_completeness`) checks
required documents per role (head/spouse/child/default) and blocks case
advancement if any required document type is missing.

Per-family ZIP export is available at `/travel/families/<id>/export`, bundling
all source files by member plus a CSV summary.

---

## Cross-domain features

Features the engine provides that any module can use:

### 1. Cryptographic dedup cache (`extraction_cache` table)

Same file + same prompt version → cached result. Module-agnostic. The cache
stores `file_hash`, `result_json`, and `prompt_version` — stale caches from
old prompt versions are automatically bypassed.

### 2. Per-file audit log (`core/audit/logger.py`)

Writes `data/logs/<filename>_<timestamp>.json` with full extraction result,
validation status, DB action, errors. Module-agnostic.

### 3. Vector search (`core/search/vector_db.py`)

Every processed document gets embedded into ChromaDB. Search "container with
dangerous goods on MSC" or "passport expiring in 2027" — works across all
modules.

### 4. BI bridge (`core/api/server.py`)

Logistics endpoints: `/api/logistics/shipments`, `/api/logistics/containers`,
`/api/logistics/shipments_full` (the primary Power BI endpoint).
Travel endpoints: `/api/travel/persons`, `/api/travel/families`,
`/api/travel/documents`. Adding a new domain = adding routes following this
pattern.

### 5. NL2SQL ("Ask your data")

The logistics dashboard exposes a natural-language query box. User types a
question; the configured LLM converts it to a SELECT query; the app executes
it and renders the result. Security: only SELECT statements are allowed
(prefix-checked — a more robust guard is tracked in the roadmap).

### 6. PDF annotation view

`/files/<module>/<doc_id>/annotated` renders a PNG of the source PDF with
extracted field values highlighted. Uses PyMuPDF's text search + annotation API.
Clicking a field in the detail view can jump to its location in the PDF.

---

## Future domains on the consideration list

| Domain | Document types | Specialist parser? |
|--------|----------------|-------------------|
| Healthcare referrals | Referral letter, prescription, lab report | None known |
| Legal case bundles | Court filing, brief, exhibit list | None known |
| HR onboarding | Diploma, employment certificate, reference letter | None known |
| Real estate | Title deed, valuation report, mortgage statement | None known |

The cost-of-new-domain is ~3 days for a competent developer today. Target: ~1
day with a code-gen template.
