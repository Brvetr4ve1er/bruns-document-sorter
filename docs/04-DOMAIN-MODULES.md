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
2. Registering its prompts in `modules/<domain>/prompts.py`.
3. Adding a domain mode tile to `app.py`.
4. Getting its own SQLite file in `data/<domain>.db`.

No changes to `core/` are required. If they are, the abstraction in `core/`
is wrong — fix it before adding the domain.

---

## Logistics module

**Mission:** Replace the manual workflow of typing carrier-PDF data into a
49-column "Containers actifs" Excel.

### Documents handled

| Type | What it is | Triggers status change |
|------|-----------|------------------------|
| `BOOKING` | Booking confirmation from carrier | `status → BOOKED` |
| `DEPARTURE` | Departure notice (vessel left origin port) | `status → IN_TRANSIT` |
| `BILL_OF_LADING` (BL) | Bill of lading | `status → IN_TRANSIT` |

### Carriers normalized

Hard-coded canonical brands in the prompt (`modules/logistics/prompts.py`):

- CMA-CGM (matches: `CMA CGM`, `CMA-CGM`)
- MSC (matches: `MEDITERRANEAN SHIPPING COMPANY`, `MSC`)
- Ignazio Messina (matches: `IGNAZIO MESSINA`)
- Pyramid Lines
- Maersk
- Hapag-Lloyd
- Other (anything else, kept verbatim)

Adding a carrier = one line in the prompt + one line in the
normalizer. No schema changes.

### Container size canonicalization

The carrier PDFs use wildly inconsistent abbreviations. The prompt enforces
four canonical buckets:

| Carrier writes | We store |
|----------------|----------|
| `40' HIGH CUBE`, `40HC`, `40HQ`, `40 GP`, `40'ST`, `40' DRY` | `40 feet` |
| `20' HIGH CUBE`, `20HC`, `20 GP`, `20'ST`, `20' DRY` | `20 feet` |
| `40 RF`, `40 REEF`, `40 REF` | `40 feet refrigerated` |
| `20 RF`, `20 REEF`, `20 REF` | `20 feet refrigerated` |

This canonicalization is also re-applied at the validator level
(`core/normalization/codes.py::normalize_size`) — defense in depth.

### TAN as the primary key

The `TAN` (Titre d'Acconage Numéroté) is the customs reference number that
follows a shipment from booking to discharge. Format: `TAN/XXXX/YYYY`.

UPSERT order in `logistics_app/database_logic/database.py::upsert_shipment`:
1. Match on `tan_number`. If found → UPDATE.
2. Else match on `(vessel_name, etd)` composite. If found → UPDATE.
3. Else → INSERT.

This means:
- A booking arrives → INSERT shipment with status `BOOKED`.
- A departure notice for the same TAN arrives later → UPDATE same row to
  `IN_TRANSIT`, fill in actual departure date.
- A BL arrives weeks later → UPDATE same row, attach container details.

The user sees one row per shipment that progresses through statuses, not
three rows per shipment that they have to mentally merge.

### The 49-column XLSX export

Implementation: `logistics_app/utils/xlsx_export.py`

The customer's Power BI was built on top of an Excel file called
"Containers actifs" with 49 specific French column names. We export the
identical column list, identical column order, identical column types — so
the existing Power BI report works without modification when fed our XLSX.

Column list lives in `modules/logistics/config.py::XLSX_COLUMNS`.

This is a **deliberate, customer-driven choice**. We could expose a cleaner
schema, but compatibility with the existing BI investment is the buying
trigger.

### Computed columns

Some columns in the export are computed from raw fields:

- `Coût Surestaries Estimé (USD)` = `nbr_jours_surestarie_estimes` × per-day
  rate from carrier rate cards (future feature)
- `Nbr jours restants pour surestarie` = `date_restitution_estimative` -
  `today`
- `Check dépotement-restitution` = days between unloading and container
  return

These computations live in the export layer, not in the schema, so the raw
DB stays normalized.

### Logistics edit flow

The Streamlit "Edit Container" page exposes 25+ operational fields organized
in four tabs:

| Tab | Fields |
|-----|--------|
| Status & Delivery | `statut_container`, `size`, `site_livraison`, delivery/dépotement/restitution dates |
| Transport | `livre_camion`, `livre_chauffeur`, `restitue_camion`, `restitue_chauffeur`, `centre_restitution` |
| Demurrage & Billing | `date_debut_surestarie`, days estimated/customs/billed, `taux_de_change`, `montant_facture_da`, `n_facture_cm` |
| Douane | `date_declaration_douane`, `date_liberation_douane`, `commentaire` |

These fields are NOT extracted from PDFs — they are operational data the user
adds after the container has cleared customs. The pipeline gets the shipment
into the system; the user fills in operational truth as it happens.

---

## Travel module

**Mission:** Build family-immigration case files from passport scans.

### Documents handled

| Type | Specialist parser? | LLM used? |
|------|-------------------|-----------|
| `PASSPORT` | Yes — PassportEye + `mrz` for MRZ band | Yes — for visual fields not in MRZ |
| `ID_CARD` | Yes — same MRZ checkers | Yes — for visual fields |
| `BIRTH_CERTIFICATE` | No | Yes — full LLM extraction |

### Why MRZ parsing first

The MRZ band on a passport encodes name, DOB, nationality, document number,
expiry date, and gender in a fixed-width OCR-friendly format with check
digits. A specialist parser:
- Validates check digits → catches OCR errors before they hit the DB.
- Extracts ISO 3166 nationality codes deterministically.
- Runs in microseconds.

Implementation: `modules/travel/mrz_parser.py`

```python
for Checker in [TD3, TD1, TD2, MRVA, MRVB]:
    try:
        checker = Checker(mrz_string)
        if checker:
            fields = checker.fields()
            return {...}
    except Exception:
        pass
```

It tries each checker in order (TD3 = passport, TD1 = ID card, etc.) and
returns the first valid parse.

### Identity resolution

This is the core differentiator vs "just OCR a passport" products.

Implementation: `core/matching/engine.py`

When a new passport is processed, we compute similarity vs every existing
`Person` record:

```
score = 0.6 * name_similarity (RapidFuzz on normalized names)
      + 0.3 * dob_similarity  (binary)
      + 0.1 * nationality_similarity (binary)
```

Three outcomes:

| Score | Status | What happens |
|-------|--------|--------------|
| ≥ 0.85 | `AUTO_MERGED` | New scan attached to existing person; case folder updates |
| 0.60 – 0.85 | `REVIEW` | Surfaces in match-review panel for human decision |
| < 0.60 | `NEW_IDENTITY` | New `Person` row inserted |

### Family construction

A `Family` record links multiple `Person` records via `family_id`. When
processing a multi-passport case bundle:

1. Each passport → `Person` row (after matching).
2. The user (or a future heuristic) groups them into a `Family`.
3. The `Family` has a `case_reference` for the immigration file.
4. Subsequent processing of related documents (birth certificates, marriage
   certificates) attaches to the same family.

This is the "second-brain" property of the Travel module: the same identities
flow naturally across cases instead of being copy-pasted.

### Document-types extension path

To add `MARRIAGE_CERTIFICATE`:
1. Add prompt in `modules/travel/prompts.py`:
   `register_prompt("travel", "MARRIAGE_CERTIFICATE", "1.0", PROMPT_MARRIAGE)`
2. Add a `MarriageCertificate` Pydantic model in `core/schemas/person.py` (or
   a new file).
3. Pipeline router (`core/pipeline/router.py`) gets a new case branch.
4. Done. No `core/` engine changes.

---

## Cross-domain features

Features the engine provides that any module can use:

### 1. Cryptographic dedup cache (`core/storage/db.py::extraction_cache` table)

Same file → same hash → cached result. Module-agnostic.

### 2. Per-file audit log (`core/audit/logger.py`)

Writes `data/logs/<filename>.json` with full extraction result, validation
status, DB action, errors. Module-agnostic.

### 3. Vector search (`core/search/vector_db.py`)

Every processed document gets embedded into ChromaDB. Search "container with
dangerous goods on MSC" or "passport expiring in 2027" — works across all
modules.

### 4. BI bridge (`core/api/server.py`)

Logistics endpoints already exist. Travel endpoints (`/api/travel/persons`,
`/api/travel/families`, `/api/travel/documents`) already exist. Adding a
new domain = adding new routes following the same pattern.

---

## Future domains on the consideration list

Not on the active roadmap but architecturally cheap to add:

| Domain | Document types | Specialist parser? |
|--------|----------------|-------------------|
| Healthcare referrals | Referral letter, prescription, lab report | None known |
| Legal case bundles | Court filing, brief, exhibit list | None known |
| HR onboarding | Diploma, employment certificate, reference letter | None known |
| Real estate | Title deed, valuation report, mortgage statement | None known |

The pattern is: if a customer in any of these spaces says "we have a 49-column
Excel that someone fills out by reading PDFs," BRUNs is the answer.
