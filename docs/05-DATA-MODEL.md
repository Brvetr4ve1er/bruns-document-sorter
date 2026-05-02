# 05 — Data Model

This document is the single source of truth for what data BRUNs stores, how
it's shaped, and where it lives on disk.

> **Schema note (TD1 — partially fixed):** `core/storage/db.py::init_schema()`
> creates `shipments` with columns `carrier` and `doc_type`. The live
> `logistics.db` uses `compagnie_maritime` and `document_type`. The `documents`,
> `families`, and `documents_travel` DDLs are now correct (fixed). The
> `shipments` DDL mismatch remains — a fresh install still creates an unusable
> `shipments` table. Fix tracked in
> [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) as TD1.

---

## Database files

| File | Purpose | Lives in |
|------|---------|----------|
| `logistics.db` | All shipments, containers, documents, audit | `data/` (or `BRUNS_DATA_DIR`) |
| `travel.db` | Persons, families, travel documents | `data/` |
| `chroma.sqlite3` | ChromaDB embeddings (managed by Chroma) | `data/vector/` |

Why SQLite (and not Postgres):
- Single-file, zero install, zero ops.
- Power BI has native SQLite connector — but the Flask REST bridge is preferred.
- Document volumes per customer are ~10k–100k rows per year. SQLite is
  comfortable up to ~10M rows for these query patterns.

---

## Shared tables (both databases)

### Table: `documents`

One row per processed file. This is the audit-safe source of truth for every
extraction — it stores the raw text, the raw LLM JSON, and the confidence score.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `type` | TEXT | `BOOKING` / `DEPARTURE` / `PASSPORT` / `UNKNOWN` / etc. |
| `raw_text` | TEXT | Full extracted text passed to LLM |
| `extracted_json` | TEXT | Raw LLM response as JSON string |
| `confidence` | REAL | Per-module confidence score (0.0–1.0) |
| `source_file` | TEXT | Absolute path to original file |
| `module` | TEXT | `logistics` or `travel` |
| `created_at` | DATETIME | |
| `reviewed_at` | TEXT | Set when operator approves from the review queue |
| `reviewed_by` | TEXT | `'operator'` or user name (multi-user auth not yet implemented) |

### Table: `extraction_cache`

| Column | Type | Notes |
|--------|------|-------|
| `file_hash` | TEXT PRIMARY KEY | SHA-256 hex |
| `result_json` | TEXT | Full extraction JSON |
| `prompt_version` | TEXT | Version string from `register_prompt()`; cache is bypassed if version changed |
| `cached_at` | DATETIME | |
| `hit_count` | INTEGER | Incremented on each cache hit |

### Table: `jobs`

In-memory jobs are tracked in `job_tracker.py`. This table exists in the schema
but is not populated by the current flow (was intended for Huey persistence).

| Column | Type |
|--------|------|
| `id` | TEXT PRIMARY KEY |
| `type` | TEXT |
| `status` | TEXT |
| `input_json` | TEXT |
| `result_json` | TEXT |
| `logs_json` | TEXT |
| `created_at` | DATETIME |
| `completed_at` | DATETIME |
| `retries` | INTEGER |

### Table: `audit_log`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `action` | TEXT | `upload`, `edit`, `family_update`, etc. |
| `actor` | TEXT | `operator` or `system` |
| `entity_type` | TEXT | `documents`, `containers`, `families`, etc. |
| `entity_id` | TEXT | String ID of the affected row |
| `before_json` | TEXT | JSON snapshot before change |
| `after_json` | TEXT | JSON snapshot after change |
| `timestamp` | DATETIME | |

### Table: `file_index`

Maps file hashes to document IDs for deduplication tracking.

### Table: `validation_issues`

| Column | Type |
|--------|------|
| `id` | INTEGER PRIMARY KEY |
| `issue_type` | TEXT NOT NULL |
| `field_name` | TEXT |
| `issue_desc` | TEXT NOT NULL |
| `severity` | TEXT (`warning` / `error`) |
| `resolved` | BOOLEAN |
| `resolution_note` | TEXT |
| `shipment_id` | INTEGER (FK) |
| `container_id` | INTEGER (FK) |
| `created_at` | DATETIME |
| `resolved_at` | DATETIME |

---

## Logistics schema

### Table: `shipments`

One row per logical shipment. Updated as multiple documents for the same TAN
arrive over time.

> **Column names are the legacy schema from `database_logic/database.py`.**
> These are the actual column names in the live `logistics.db`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `tan` | TEXT UNIQUE | `TAN/XXXX/YYYY` — primary upsert key |
| `item_description` | TEXT | Cargo description |
| `compagnie_maritime` | TEXT | Canonical carrier: `CMA-CGM`, `MSC`, etc. |
| `port` | TEXT | Default `Port d'Alger` |
| `transitaire` | TEXT | Freight forwarder name |
| `vessel` | TEXT | Vessel name (UPPERCASE) |
| `etd` | TEXT (ISO date) | Estimated/actual departure |
| `eta` | TEXT (ISO date) | Estimated/actual arrival |
| `document_type` | TEXT | `BOOKING` / `DEPARTURE` / `BILL_OF_LADING` / `UNKNOWN` |
| `status` | TEXT | `BOOKED` / `IN_TRANSIT` / `UNKNOWN` |
| `source_file` | TEXT | Absolute path to original PDF |
| `created_at` | TEXT | |
| `modified_at` | TEXT | |

### Table: `containers`

One row per container. Multiple containers can belong to one shipment.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `shipment_id` | INTEGER | FK → shipments.id, ON DELETE CASCADE |
| `container_number` | TEXT NOT NULL | ISO 6346 format |
| `size` | TEXT | `40 feet` / `20 feet` / `40 feet refrigerated` / `20 feet refrigerated` |
| `seal_number` | TEXT | |
| `statut_container` | TEXT | `BOOKED` / `IN_TRANSIT` / `ARRIVED` / `DELIVERED` / `RESTITUTED` |
| `date_livraison` | TEXT (ISO date) | Operational — user-edited |
| `site_livraison` | TEXT | |
| `date_depotement` | TEXT (ISO date) | Operational |
| `date_debut_surestarie` | TEXT (ISO date) | Demurrage clock starts |
| `date_restitution_estimative` | TEXT (ISO date) | Estimated return |
| `nbr_jours_surestarie_estimes` | INTEGER | |
| `nbr_jours_perdu_douane` | INTEGER | |
| `date_restitution` | TEXT (ISO date) | Actual return |
| `restitue_camion` | TEXT | |
| `restitue_chauffeur` | TEXT | |
| `centre_restitution` | TEXT | |
| `livre_camion` | TEXT | |
| `livre_chauffeur` | TEXT | |
| `montant_facture_check` | TEXT | `Yes` / `No` |
| `nbr_jour_surestarie_facture` | INTEGER | |
| `montant_facture_da` | REAL | |
| `n_facture_cm` | TEXT | Carrier invoice number |
| `commentaire` | TEXT | |
| `date_declaration_douane` | TEXT (ISO date) | |
| `date_liberation_douane` | TEXT (ISO date) | |
| `taux_de_change` | REAL | DZD/USD exchange rate at billing |
| `created_at` | TEXT | |
| `modified_at` | TEXT | |

**UNIQUE constraint:** `(shipment_id, container_number)` — prevents duplicate
containers within a shipment.

**Field origin breakdown:**
- **Extracted by LLM:** `container_number`, `size`, `seal_number`, initial `statut_container`
- **Operational, user-edited:** all date/driver/demurrage/billing fields

---

## Travel schema

### Table: `persons`

One row per resolved person identity.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `family_id` | INTEGER | FK → families.id (nullable) |
| `full_name` | TEXT | As extracted — preserved for display |
| `normalized_name` | TEXT | Lowercase, whitespace-collapsed — used for matching |
| `dob` | TEXT (ISO date) | |
| `nationality` | TEXT | ISO 3166 3-letter code preferred |
| `gender` | TEXT | `M` / `F` |

**Matching:** `projections.py` currently does exact `normalized_name` SQL match.
`core/matching/engine.py` has full fuzzy matching but is not yet called.

### Table: `families`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `family_name` | TEXT | |
| `head_person_id` | INTEGER | FK → persons.id |
| `case_reference` | TEXT | Visa case / file number |
| `address` | TEXT | |
| `notes` | TEXT | |
| `case_status` | TEXT | `COLLECTING` / `READY` / `IN_REVIEW` / `SUBMITTED` / `APPROVED` / `REJECTED` |
| `next_action` | TEXT | Free-text next step |
| `next_action_date` | TEXT | ISO date |

### Table: `documents_travel`

One row per travel document (passport, ID, visa, birth certificate, etc.).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `person_id` | INTEGER | FK → persons.id (nullable if not yet matched) |
| `family_id` | INTEGER | FK → families.id (nullable) |
| `doc_type` | TEXT | `PASSPORT` / `ID_CARD` / `BIRTH_CERTIFICATE` / etc. |
| `doc_number` | TEXT | |
| `expiry_date` | TEXT (ISO date) | |
| `mrz_raw` | TEXT | Raw MRZ lines if extracted |
| `original_doc_id` | INTEGER | FK → documents.id — links to generic documents table |

### Table: `matches`

Records identity resolution results for human review.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `entity_a_id` | INTEGER | |
| `entity_b_id` | INTEGER | |
| `score` | REAL | Similarity score |
| `status` | TEXT | `PENDING` / `MERGED` / `REJECTED` |
| `resolved_by` | TEXT | |
| `resolved_at` | DATETIME | |

---

## The "Containers actifs" 49-column export schema

The XLSX export is a flat denormalization of `shipments JOIN containers` plus
computed columns. Full column list lives in `modules/logistics/config.py::XLSX_COLUMNS`.

This shape is the hard integration contract with the customer's Power BI report.
No column may be renamed or reordered without versioning the export.

---

## Normalization rules (the data quality layer)

Implementation: `core/normalization/`

| Module | What it normalizes |
|--------|---------------------|
| `names.py::name_normalize` | Lowercase, strip diacritics, sort name parts alphabetically |
| `dates.py::date_normalize` | Any input format → ISO `YYYY-MM-DD` |
| `codes.py::container_number` | ISO 6346 enforcement (4 letters + 7 digits) |
| `codes.py::normalize_size` | Container-size canonicalization |
| `codes.py::normalize_seal` | Strip whitespace, uppercase |
| `codes.py::shipping_co` | Canonical carrier brand |
| `codes.py::normalize_tan` | `TAN/XXXX/YYYY` enforcement |
| `codes.py::clean_str` | Trim, collapse whitespace, strip control chars |

These run on Pydantic model instantiation (via `field_validator(mode="before")`).
They normalize incoming LLM output before write — dirty data cannot bypass them.

---

## Migration strategy — current state

Implementation: `core/storage/migrations.py`

**Current state:** The migration function body is literally `pass`. No migrations
run automatically on startup. Schema changes have been managed manually (evidenced
by `data/logistics.db.pre-schema-fix.bak`).

A proper migration system is planned:

```python
# Target implementation
def run_migrations(db_path: str):
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            id TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for migration_id, sql in MIGRATIONS:
        applied = {r[0] for r in conn.execute("SELECT id FROM schema_version").fetchall()}
        if migration_id not in applied:
            conn.execute(sql)
            conn.execute("INSERT INTO schema_version (id) VALUES (?)", (migration_id,))
            conn.commit()
```

Until this is implemented, schema changes are applied manually. Do not rely on
`run_migrations()` being called or having any effect.
