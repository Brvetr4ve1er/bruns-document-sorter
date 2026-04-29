# 05 — Data Model

This document is the single source of truth for what data BRUNs stores, how
it's shaped, and where it lives on disk.

## Database files

The platform uses **separate SQLite files per domain** for isolation. A bug
in the Travel pipeline cannot corrupt Logistics data and vice versa.

| File | Purpose | Lives in |
|------|---------|----------|
| `logistics.db` | All shipments, containers, audit cross-references | `data/` (or `BRUNS_DATA_DIR`) |
| `travel.db` | Persons, families, documents | `data/` |
| `queue.db` | Huey job queue persistence | `data/` |
| `chroma.sqlite3` | ChromaDB embeddings (managed by Chroma) | `data/chroma/` |

Why SQLite (and not Postgres):
- Single-file, zero install, zero ops.
- Power BI has native SQLite connector — but the Flask REST bridge is
  preferred (it works for any BI tool and exposes computed columns).
- Document volumes per customer are ~10k–100k rows per year. SQLite is
  comfortable up to ~10M rows for our query patterns.

---

## Logistics schema

### Table: `shipments`

One row per logical shipment (uniquely identified by TAN, fallback by
vessel + ETD). Updated as documents arrive over time.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `document_id` | INTEGER | FK to original PDF reference |
| `document_type` | TEXT | `BOOKING` / `DEPARTURE` / `BILL_OF_LADING` / `UNKNOWN` |
| `tan_number` | TEXT | `TAN/XXXX/YYYY` — primary UPSERT key |
| `item_description` | TEXT | Cargo description, free text, `clean_str` normalized |
| `shipping_company` | TEXT | Canonical brand: `CMA-CGM`, `MSC`, etc. |
| `port` | TEXT | Default `Port d'Alger` |
| `transitaire` | TEXT | Freight forwarder name |
| `vessel_name` | TEXT | UPPERCASE, fallback UPSERT key |
| `etd` | TEXT (ISO date) | Estimated/actual departure |
| `eta` | TEXT (ISO date) | Estimated/actual arrival |
| `status` | TEXT | `BOOKED` / `IN_TRANSIT` / `DELIVERED` / `UNKNOWN` |
| `source_file` | TEXT | Original filename for audit |
| `created_at` | TIMESTAMP | AuditMixin |
| `modified_at` | TIMESTAMP | AuditMixin |

Pydantic model: `core/schemas/logistics.py::Shipment`

### Table: `containers`

One row per container. Multiple containers can belong to one shipment.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `shipment_id` | INTEGER | FK → shipments.id, ON DELETE CASCADE |
| `container_number` | TEXT | ISO 6346 (4 letters + 7 digits) |
| `size` | TEXT | `40 feet` / `20 feet` / `40 feet refrigerated` / `20 feet refrigerated` |
| `seal_number` | TEXT | |
| `statut_container` | TEXT | `Réservé` / `En transit` / `Arrivé` / `Livré` / `Dépoté` / `Restitué` |
| `date_livraison` | TEXT (ISO date) | Operational, user-edited |
| `site_livraison` | TEXT | `Rouiba` / `Boudouaou` / etc. |
| `date_depotement` | TEXT (ISO date) | Operational |
| `date_debut_surestarie` | TEXT (ISO date) | Demurrage clock starts |
| `date_restitution_estimative` | TEXT (ISO date) | Estimated container return |
| `nbr_jours_surestarie_estimes` | INTEGER | |
| `nbr_jours_perdu_douane` | INTEGER | |
| `date_restitution` | TEXT (ISO date) | Actual return |
| `restitue_camion` | TEXT | Truck used for return |
| `restitue_chauffeur` | TEXT | Driver name |
| `centre_restitution` | TEXT | Return depot |
| `livre_camion` | TEXT | |
| `livre_chauffeur` | TEXT | |
| `montant_facture_check` | TEXT | `Yes` / `No` |
| `nbr_jour_surestarie_facture` | INTEGER | Days actually billed |
| `montant_facture_da` | REAL | Amount in Algerian Dinar |
| `n_facture_cm` | TEXT | Carrier invoice number |
| `commentaire` | TEXT | Free-text notes |
| `date_declaration_douane` | TEXT (ISO date) | |
| `date_liberation_douane` | TEXT (ISO date) | |
| `taux_de_change` | REAL | Exchange rate at billing |
| `created_at` | TIMESTAMP | |
| `modified_at` | TIMESTAMP | |

Pydantic model: `core/schemas/logistics.py::Container`

**Field origin breakdown:**

- **Extracted by LLM:** `container_number`, `size`, `seal_number`
- **Operational, user-edited:** Everything else

This separation matters: the extracted fields are immutable truth from the
source PDF; the operational fields are working data the user updates as
events happen.

### Table: `extraction_cache`

| Column | Type | Notes |
|--------|------|-------|
| `file_hash` | TEXT PRIMARY KEY | SHA-256 |
| `result_json` | TEXT | Full extraction JSON |
| `created_at` | TIMESTAMP | |

Hit rate is the metric to watch — high cache hit means the user is
re-uploading the same files (which is fine, and instant).

---

## Travel schema

### Table: `persons`

One row per resolved person identity. Same person across multiple cases =
one row.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `family_id` | INTEGER | FK → families.id (nullable if not yet grouped) |
| `full_name` | TEXT | As extracted |
| `normalized_name` | TEXT | Lowercase, diacritics stripped, parts sorted |
| `dob` | TEXT (ISO date) | |
| `nationality` | TEXT | ISO 3166 3-letter code preferred |
| `gender` | TEXT | `M` / `F` |
| `created_at` | TIMESTAMP | |
| `modified_at` | TIMESTAMP | |

Pydantic model: `core/schemas/person.py::Person`

`normalized_name` is the field the matcher operates on. Source-truth
`full_name` is preserved unchanged for display.

### Table: `families`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `family_name` | TEXT | |
| `head_person_id` | INTEGER | FK → persons.id |
| `case_reference` | TEXT | Visa case number / file number |
| `address` | TEXT | |
| `notes` | TEXT | |

Pydantic model: `core/schemas/person.py::Family`

### Table: `documents_travel`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `person_id` | INTEGER | FK → persons.id |
| `doc_type` | TEXT | `PASSPORT` / `ID_CARD` / `BIRTH_CERTIFICATE` / etc. |
| `document_number` | TEXT | |
| `expiry_date` | TEXT (ISO date) | |
| `source_file` | TEXT | |
| `mrz_raw` | TEXT | If MRZ extraction succeeded |
| `created_at` | TIMESTAMP | |
| `modified_at` | TIMESTAMP | |

---

## The "Containers actifs" 49-column export schema

The XLSX export is a **separate logical schema** — it's the shape the
customer's existing Power BI report consumes. It's a flat denormalization of
`shipments` JOIN `containers` plus computed columns.

Full column list lives in `modules/logistics/config.py::XLSX_COLUMNS`.

| # | Column (French) | Source | Computed? |
|---|----------------|--------|-----------|
| 1 | `(Ne pas modifier) Container` | `containers.id` (formatted) | yes |
| 2 | `(Ne pas modifier) Somme de contrôle de la ligne` | hash | yes |
| 3 | `(Ne pas modifier) Modifié le` | `containers.modified_at` | no |
| 4 | `N° Container` | `containers.container_number` | no |
| 5 | `N° TAN` | `shipments.tan_number` | no |
| 6 | `Item (N° TAN) (Commande)` | `shipments.item_description` | no |
| 7 | `Compagnie maritime` | `shipments.shipping_company` | no |
| 8 | `Port (N° TAN) (Commande)` | `shipments.port` | no |
| 9 | `Transitaire (N° TAN) (Commande)` | `shipments.transitaire` | no |
| 10 | `Date shipment` | `shipments.etd` | no |
| 11 | `Date accostage` | `shipments.eta` | no |
| 12 | `Statut Container` | `containers.statut_container` | no |
| 13 | `Container size` | `containers.size` | no |
| 14 | `Date livraison` | `containers.date_livraison` | no |
| 15 | `Site livraison` | `containers.site_livraison` | no |
| 16 | `Date dépotement` | `containers.date_depotement` | no |
| 17 | `Modifié par` | (operator name, future feature) | no |
| 18 | `Modifié le` | `containers.modified_at` | no |
| 19 | `Date début Surestarie` | `containers.date_debut_surestarie` | no |
| 20 | `Date restitution estimative` | `containers.date_restitution_estimative` | no |
| 21 | `Nbr jours surestarie estimés` | `containers.nbr_jours_surestarie_estimes` | no |
| 22 | `Coût Surestaries Estimé (USD)` | days × USD rate | yes |
| 23 | `Nbr jours perdu en douane` | `containers.nbr_jours_perdu_douane` | no |
| 24 | `Coût Surestaries Estimé (DZD)` | USD × `taux_de_change` | yes |
| 25 | `Nbr jours restants pour surestarie` | `date_restitution_estimative - today` | yes |
| 26 | `Nbr jours surestarie` | actual demurrage days | yes |
| 27 | `Coût Surestaries Réel (USD)` | actual × USD rate | yes |
| 28 | `Coût Surestaries Réel (DZD)` | USD × `taux_de_change` | yes |
| 29 | `Date réstitution` | `containers.date_restitution` | no |
| 30 | `Réstitué par (Camion)` | `containers.restitue_camion` | no |
| 31 | `Réstitué par (Chauffeur)` | `containers.restitue_chauffeur` | no |
| 32 | `Centre de réstitution` | `containers.centre_restitution` | no |
| 33 | `Check dépotement-restitution` | `date_restitution - date_depotement` | yes |
| 34 | `Check livraison-dépotement` | `date_depotement - date_livraison` | yes |
| 35 | `Check livraison-restitution` | `date_restitution - date_livraison` | yes |
| 36 | `Check Shipment-Accostage` | `eta - etd` | yes |
| 37 | `Créé le` | `containers.created_at` | no |
| 38 | `Créé par` | (operator name, future feature) | no |
| 39 | `Check avis d'arrivée-restitution` | computed | yes |
| 40 | `Taux de change*` | `containers.taux_de_change` | no |
| 41 | `Livré par (Camion)` | `containers.livre_camion` | no |
| 42 | `Livré par (Chauffeur)` | `containers.livre_chauffeur` | no |
| 43 | `Montant facturé (check)` | `containers.montant_facture_check` | no |
| 44 | `Nbr jour surestarie Facturé` | `containers.nbr_jour_surestarie_facture` | no |
| 45 | `Montant facturé (DA)` | `containers.montant_facture_da` | no |
| 46 | `N° Facture compagnie maritime` | `containers.n_facture_cm` | no |
| 47 | `Commentaire` | `containers.commentaire` | no |
| 48 | `Date declaration douane` | `containers.date_declaration_douane` | no |
| 49 | `Date liberation douane` | `containers.date_liberation_douane` | no |

**Why we keep this schema unchanged:** The customer's Power BI report has 49
DAX measures keyed to these exact column names. Renaming any of them breaks
the report. This is the integration contract.

---

## Normalization rules (the "data quality" layer)

Implementation: `core/normalization/`

| Module | What it normalizes |
|--------|---------------------|
| `names.py::name_normalize` | Lowercase, strip diacritics, sort name parts alphabetically |
| `dates.py::date_normalize` | Any input format → ISO `YYYY-MM-DD` |
| `codes.py::container_number` | ISO 6346 enforcement (4 letters + 7 digits) |
| `codes.py::normalize_size` | The container-size canonicalization table |
| `codes.py::normalize_seal` | Strip whitespace, uppercase |
| `codes.py::shipping_co` | Canonical carrier brand |
| `codes.py::normalize_tan` | `TAN/XXXX/YYYY` enforcement |
| `codes.py::clean_str` | Trim, collapse whitespace, strip control chars |

These run **automatically on Pydantic model instantiation** (via
`field_validator(mode="before")`). The application code can never bypass
them — even if the LLM returns dirty data, the model rejects or normalizes
before write.

---

## Migration strategy

Implementation: `core/storage/migrations.py`

Schema changes are forward-only migrations. On startup, the storage layer
runs `init_db()` which:
1. Creates tables if they don't exist.
2. Runs each migration script in version order.
3. Records applied migrations in a `migrations` table.

**Backwards compatibility:** New columns are added with defaults so old code
keeps working. We never DROP a column in a release — we deprecate it for
one cycle, then remove. (Today this is a discipline, not enforced — see
[09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md).)
