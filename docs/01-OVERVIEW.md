# 01 — Overview

## What BRUNs is

**BRUNs is a local-first document intelligence platform** for Algerian freight
forwarders and immigration consultancies. It turns operational PDFs — shipping
documents, passports, identity cards, customs paperwork — into clean structured
database rows without cloud dependencies, paid APIs, or vendor lock-in.

The entire platform runs as a **single Python process** on a Windows laptop.
One `START_APP.bat` starts everything: Flask UI, document pipeline, BI bridge.

---

## What it replaces

### Logistics workflow (before BRUNs)

A freight forwarder receives 2–4 PDFs per shipment from carriers (CMA-CGM, MSC,
Maersk, Ignazio Messina): booking confirmation, departure notice, bill of lading.
A clerk **re-types every field** into an Excel workbook called "Containers actifs"
— 49 columns including container numbers, vessel names, ETDs, ETAs, demurrage
start dates, exchange rates, customs dates. This workbook feeds Power BI.

Three failure modes that cost real money:
1. **Typos** — wrong container number → wrong container tracked in BI dashboards
2. **Missed demurrage windows** — clerk forgets `Date début Surestarie` →
   operator discovers the fine when the invoice arrives, not before
3. **Latency** — data only enters Power BI after the clerk batches yesterday's PDFs

### Travel workflow (before BRUNs)

A visa consultant assembles family case files with passport scans for every
member. The same person appears across multiple cases (parent on child's case,
sibling on sponsor's case). Identity resolution is done with copy-paste from
previous folders. Spelling drift creates "two people" in the file system who
are the same person.

---

## What the platform actually does

### Logistics module

```
Upload PDF → hash → cache check → text extract → LLM extract → validate
    → store in documents → project into shipments/containers → Power BI ready
```

- Extracts 50+ fields: TAN, BL number, vessel, IMO, carrier, port, ETD, ETA,
  all containers with sizes/seals, demurrage terms, free days, exchange rates
- Deduplicates by TAN (same shipment across Booking + Departure + BL → one row)
- Calculates demurrage risk per container: days at port, days over free time,
  USD/DZD cost estimate using tiered carrier rate tables
- Surfaces D&D at-risk containers in the operator action center

### Travel module

```
Upload scan → hash → MRZ extract → LLM extract → normalize → match person
    → store in persons/families/documents_travel → case management
```

- PassportEye + `mrz` library extract the MRZ band before the LLM sees the image
- MRZ-validated values override LLM values for name, DOB, doc number, expiry
- Person identity matching (currently: exact normalized-name SQL; fuzzy engine
  built in `core/matching/engine.py`, not yet wired)
- Family completeness gate: required-docs checklist per role (head/spouse/child),
  blocks case status advancement until 100% complete

---

## Full feature inventory

### Operator UI (Flask + HTMX + DaisyUI)

| Feature | Route | Description |
|---------|-------|-------------|
| Mode picker | `/` | Choose logistics or travel mode |
| Logistics dashboard | `/logistics` | Action center, stats, container table, NL2SQL |
| Operator action center | `/logistics` | 4-card strip: review queue, D&D risk, gaps, on-track |
| NL2SQL "Ask your data" | `/logistics` → POST `/logistics/ask` | Plain text → SQL → results table |
| Activity feed | `/logistics` | Last 20 audit log entries |
| Document list | `/logistics/documents` | All uploaded docs, keyword + semantic search |
| Document detail | `/logistics/documents/<id>` | PDF with bounding-box highlights, all extracted fields editable, re-extract diff, cross-doc reconciliation |
| Bounding box visualization | `/files/logistics/<id>/annotated` | PyMuPDF highlights each extracted value on the source PDF page |
| Re-extract with diff | modal on document detail | Fresh extraction vs stored, 3-column diff (added/changed/removed) |
| Cross-doc reconciliation | panel on document detail | Flags vessel/ETD/ETA/container/weight discrepancies across docs sharing same TAN |
| Review queue | `/logistics/review` | Documents below 0.90 confidence not yet operator-approved |
| Container detail | `/logistics/containers/<id>` | D&D countdown bar, all operational fields editable |
| D&D countdown bar | container detail | Days at port vs free days, USD/DZD cost, progress bar, risk color |
| Pipeline swimlane | `/logistics/swimlane` | Columns: BOOKED → IN_TRANSIT → ARRIVED → DELIVERED → RESTITUTED; D&D risk border color |
| Spreadsheet view | `/logistics/sheet` | All containers as filterable table |
| Logistics analytics | `/logistics/analytics` | Status mix, carrier volumes, monthly shipments, avg transit time (Chart.js) |
| Export | `/logistics/export`, `/logistics/export.csv`, `/logistics/export.xlsx` | 49-column "Containers actifs" format |
| Settings | `/logistics/settings` | Clear input dir, purge jobs, LLM config |
| Upload | `/logistics/upload` | Multi-file, doc type selector, HTMX progress polling |
| Travel dashboard | `/travel` | Stats: persons, families, documents, expiry warnings |
| Persons list | `/travel/persons` | Search by name/nationality |
| Person detail | `/travel/persons/<id>` | All extracted fields, linked documents |
| Families list | `/travel/families` | Case status, next action, member count |
| Family detail | `/travel/families/<id>` | Completeness gate, case status flow, next action, linked docs |
| Family ZIP export | `/travel/families/<id>/export` | All source files + CSV summary in ZIP |
| Expiry heatmap | `/travel/calendar` | 12-month grid, heat = expiry density, click to drill |
| Travel analytics | `/travel/analytics` | Case status, doc types, nationalities, expiry timeline (Chart.js) |
| Document list | `/travel/documents` | All travel documents |
| Travel document detail | `/travel/documents/<id>` | Fields + MRZ data |
| Travel upload | `/travel/upload` | Same multi-file upload as logistics |
| Global search | `/search` | Hybrid keyword + ChromaDB semantic across both modules |
| Print-to-PDF | every page | `@media print` CSS strips nav/glass, forces white bg |
| Keyboard shortcuts | every page | `/` search, `?` help, `Esc` close, `D/U/R/P/A` navigation |
| Theme switcher | every page | 31 DaisyUI themes, persisted to localStorage |
| LLM config modal | every page | Configure provider (Ollama/LMStudio/OpenAI/Anthropic), test connection |

### REST API (BI bridge)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/status` | Health check — returns DB existence per module |
| `GET /api/logistics/shipments` | Paginated shipment rows |
| `GET /api/logistics/containers` | Paginated container rows |
| `GET /api/logistics/shipments_full` | ⭐ Flat container+shipment join, primary Power BI endpoint |
| `GET /api/travel/persons` | Paginated person rows |
| `GET /api/travel/families` | All family rows |
| `GET /api/travel/documents` | Paginated travel document rows |

### LLM providers supported

| Provider | Type | Auth |
|----------|------|------|
| Ollama | Local (default) | None |
| LM Studio | Local | None |
| OpenAI | Cloud | API key |
| Anthropic | Cloud | API key |

---

## Architecture in one diagram

```
Browser
  │ HTTP (port 7845)
  ▼
┌────────────────────────────────────────────────────────────┐
│  Flask app  (core/api/server.py, 3 063 LOC, 56 routes)     │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │  HTML UI     │  │  REST BI API  │  │  LLM modal      │  │
│  │  (HTMX/DaisyUI) │  (/api/*)    │  │  (/llm/*)       │  │
│  └──────┬───────┘  └───────┬───────┘  └─────────────────┘  │
│         │                  │                                 │
│  ┌──────▼───────────────────▼──────────────────────────┐    │
│  │  projections.py  ←  domain-specific table bridge    │    │
│  └──────────────────────────┬───────────────────────────┘   │
└─────────────────────────────│──────────────────────────────-┘
                              │
              ┌───────────────▼──────────────────┐
              │  SQLite databases (data/)         │
              │  • logistics.db                   │
              │  • travel.db                      │
              │  • vector/ (ChromaDB)             │
              └───────────────────────────────────┘

Upload flow:
  POST /*/upload  →  job_tracker.submit_job()
                  →  threading.Thread → pipeline/router.py
                  →  processor.py  (hash → cache → extract → validate → store)
                  →  projections.py (→ domain tables)
                  →  vector_db.py  (→ ChromaDB embedding)
  HTMX polls /*/process-status/<job_id>  →  SSE-like progress display
```

---

## Why local-first matters

1. **Data sovereignty.** Algerian Loi 18-07, plus industry-wide sensitivity
   around customs and trade data, means many customers will not allow this data
   off-premises. A local install removes the conversation.
2. **Cost.** No per-document fee. Processing document #100,000 costs electricity
   to run Ollama, nothing else.
3. **Resilience.** Port offices, customs warehouses, and bonded zones often have
   unreliable internet. The platform works fully offline.
4. **BI integration.** Power BI's "Web" connector hits `http://localhost:7845/api/...`.
   Nothing crosses the WAN.

---

## What BRUNs explicitly is not

- **Not a TMS.** It reads documents about shipments; it does not book shipments.
- **Not OCR software.** OCR is one internal capability. The product is structured
  data extraction + a live BI bridge.
- **Not a SaaS.** Local install only. No multi-tenant cloud version on the roadmap.
- **Not a generic LLM wrapper.** Every domain has hand-tuned prompts, strict
  Pydantic schemas, deterministic normalizers, and a fuzzy matcher. The LLM is
  one component, not the product.

## The value, one sentence

> BRUNs replaces the clerk-typing-into-Excel workflow with a local pipeline
> that produces the same 49-column Excel file (or a live Power BI connection)
> automatically — with data sovereignty guarantees no cloud competitor can match.
