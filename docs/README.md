# BRUNs Document Intelligence Platform — Project Wiki

> Last updated: 2026-05-02
> Maintainer: Antigravity (single-developer project)
> Status: **Active development** — all planned phases shipped; production hardening in progress

This is the canonical knowledge base for the **BRUNs Document Intelligence
Platform** — a fully-local, multi-domain document extraction and structured-data
pipeline for Algerian freight forwarders and immigration consultancies.

---

## Read this first

| # | Document | What you learn |
|---|----------|----------------|
| 1 | [01-OVERVIEW.md](01-OVERVIEW.md) | Product scope, every feature, architecture diagram |
| 2 | [02-HOW-IT-WORKS.md](02-HOW-IT-WORKS.md) | End-to-end pipeline with exact file + line references |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | Layer rules, module map, import boundaries |
| 4 | [05-DATA-MODEL.md](05-DATA-MODEL.md) | All SQLite schemas, column names, relationships |
| 5 | [06-API-REFERENCE.md](06-API-REFERENCE.md) | All 56 routes — BI endpoints + UI routes |
| 6 | [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) | Current state: done ✅, open tech debt, next features |
| 7 | [TECH-DEBT-CLEANUP.md](TECH-DEBT-CLEANUP.md) | Surgical cleanup strategy — ordered, safe, non-breaking |

Supporting docs:

| # | Document | Purpose |
|---|----------|---------|
| — | [03-TECHNOLOGY-STACK.md](03-TECHNOLOGY-STACK.md) | Every dependency and why |
| — | [04-DOMAIN-MODULES.md](04-DOMAIN-MODULES.md) | Logistics + Travel domain details |
| — | [07-USE-CASES.md](07-USE-CASES.md) | Real-world workflow examples |
| — | [08-MARKETING-PLAN.md](08-MARKETING-PLAN.md) | ICP, pricing, go-to-market |
| — | [10-DEPLOYMENT.md](10-DEPLOYMENT.md) | Install, run, troubleshoot |

---

## One-paragraph pitch

BRUNs ingests PDFs (booking confirmations, bills of lading, passports, ID cards)
on a local machine, extracts 50+ structured fields per document using a local LLM
(Ollama) and an Arabic-aware OCR fallback (Tesseract), validates against Pydantic
schemas, deduplicates via SHA-256, and serves the results through a live Flask API
that Power BI hits directly. The operator UI surfaces D&D risk, an NL2SQL query
bar, bounding-box PDF annotation, cross-document reconciliation, and a travel case
management system with family completeness gating.

**No cloud, no paid APIs, no data leaves the operator's machine.**

---

## Repository map

```
BRUNs logistics data scraper/
├── core/                          Engine + UI (single process, port 7845)
│   ├── api/
│   │   ├── server.py              All 56 Flask routes, 3 063 LOC  ← see TD8
│   │   ├── projections.py         LLM JSON → domain tables bridge
│   │   ├── llm_config.py          Provider registry (Ollama/LMStudio/OpenAI/Anthropic)
│   │   ├── job_tracker.py         In-memory job dict + threading.Thread spawner
│   │   └── templates/             Jinja2 templates (DaisyUI synthwave, 31 themes)
│   │       ├── base.html          Nav, themes, shortcuts, print CSS, LLM modal
│   │       ├── logistics/         16 templates (dashboard, docs, containers, etc.)
│   │       └── travel/            13 templates (persons, families, calendar, etc.)
│   ├── extraction/
│   │   ├── text_extractor.py      PyMuPDF + Tesseract (fra+eng + ara fallback) + vision
│   │   ├── llm_client.py          Provider-agnostic LLM call, retry, confidence scoring
│   │   ├── chunker.py             5-page sliding window for long PDFs
│   │   ├── prompt_registry.py     register_prompt / get_prompt / version management
│   │   ├── mrz_extract.py         PassportEye + mrz library for passport MRZ band
│   │   └── visual.py              PyMuPDF bounding-box annotation helper
│   ├── matching/
│   │   ├── engine.py              RapidFuzz fuzzy identity resolver  ← NOT YET WIRED (TD5)
│   │   ├── scorers.py             name(0.6) + dob(0.3) + nationality(0.1) weighted scoring
│   │   └── thresholds.py          AUTO_MERGE=0.92, REVIEW=0.75
│   ├── normalization/             codes.py, dates.py, names.py
│   ├── pipeline/
│   │   ├── processor.py           Steps 0–7: hash→cache→extract→validate→store→project→embed
│   │   ├── router.py              resolve LLM config + DB path + spawn processor
│   │   └── job.py                 Job dataclass (id, status, logs, retries)
│   ├── schemas/                   Pydantic models: Shipment, Container, Person, Document
│   ├── search/
│   │   └── vector_db.py           ChromaDB wrapper: embed + cosine search
│   ├── storage/
│   │   ├── db.py                  init_schema()  ← TD1: shipments DDL wrong column names
│   │   ├── repository.py          insert_document, get_document
│   │   ├── migrations.py          run_migrations() — 5 migrations registered
│   │   ├── paginator.py           paginated_query helper
│   │   └── exporters/             xlsx.py (49-col), csv.py, family_export.py
│   ├── business/                  Pure-function business logic (TD8 phase 1):
│   │   ├── bbox.py                field_color() — annotation palette
│   │   ├── charts.py              logistics_chart_data, travel_chart_data
│   │   ├── completeness.py        family_completeness, CASE_STATUS_FLOW
│   │   ├── demurrage.py           demurrage_info, calc_demurrage, free_days lookup
│   │   ├── exports.py             EXPORT_COLUMNS + run_query
│   │   ├── forms.py               flatten_for_form ⇄ set_nested
│   │   ├── nlsql.py               NL2SQL prompt + validate_select + generate_sql
│   │   ├── reconcile.py           reconcile_siblings + flatten/compute_diff
│   │   └── stats.py               dashboard counts + action panel
│   ├── logging_config.py          Centralised logging config (RotatingFileHandler)
│   ├── validation/engine.py       5 post-extraction rules for logistics
│   └── audit/logger.py            log_action → audit_log table
├── modules/
│   ├── logistics/
│   │   ├── prompts.py             LLM_PROMPT_TEMPLATE v2.0 (170-line schema)
│   │   └── config.py              XLSX_COLUMNS (the 49-col BI contract)
│   └── travel/
│       ├── prompts.py             Passport/ID extraction prompt
│       └── mrz_parser.py          MRZ field post-processing
├── data/                          Runtime (not in repo):
│   ├── logistics.db               shipments, containers, documents, audit_log, cache
│   ├── travel.db                  persons, families, documents_travel, audit_log, cache
│   ├── .llm_config.json           Active LLM provider (set via UI modal)
│   ├── input/                     Uploaded PDFs
│   ├── vector/                    ChromaDB persistence
│   ├── exports/                   Generated XLSX/CSV
│   └── logs/                      bruns.log + 5× rotated history (10 MB each)
├── tessdata/                      134 Tesseract language models (incl. ara.traineddata)
├── tesseract_bin/                 Bundled Tesseract binary (Windows x64)
├── tests/                         pytest: test_imports, test_phase1–4, test_phase8
└── docs/                          This wiki

(Legacy `logistics_app/`, `ui/`, `database_logic/`, `utils/` deleted under TD2.)
```

---

## Current implementation state (2026-05-02 — final cleanup pass)

| Subsystem | Status | Notes |
|-----------|--------|-------|
| Flask UI (57 routes) | ✅ All working | Port 7845 |
| Logistics pipeline (hash→LLM→DB) | ✅ Working | Steps 0–7 complete |
| Travel pipeline (MRZ→LLM→DB) | ✅ Working | Fuzzy matching wired (TD5) |
| Power BI REST bridge | ✅ Working | `/api/logistics/shipments_full` |
| D&D calculator | ✅ Working | Tiered CMA-CGM rates, per-container |
| Demurrage free_days from docs | ✅ Wired (N5) | Reads extracted_json, falls back to carrier default |
| NL2SQL "Ask your data" | ✅ Working | SELECT-gate hardened (TD7), `query_only` connection |
| Bounding-box PDF annotation | ✅ Working | PyMuPDF highlight overlays |
| Cross-document reconciliation | ✅ Working | 5 field checks across sibling docs |
| Review queue | ✅ Working | Confidence tiers, approve button |
| Re-extract with diff | ✅ Working | 3-column diff modal |
| Pipeline swimlane | ✅ Working | 6 status columns |
| Arabic OCR fallback | ✅ Working | Detects U+0600–U+06FF, re-runs ara+fra+eng |
| Tesseract availability caching | ✅ Done (TD6) | Module-level cache, no per-page subprocess |
| Semantic search (ChromaDB) | ✅ Working | Toggle in documents list |
| Global search `/search` | ✅ Working | Keyword + semantic, both modules |
| Travel calendar | ✅ Working | 12-month expiry heatmap |
| Family completeness gate | ✅ Working | Blocks status advance at < 100% |
| Family ZIP export | ✅ Working | Source files + CSV per family |
| Logistics analytics | ✅ Working | Chart.js (status/carriers/volume/transit) |
| Travel analytics | ✅ Working | Chart.js (status/types/nationalities/expiry) |
| Keyboard shortcuts | ✅ Working | `/`, `?`, `Esc`, `D/U/R/P/A/C/F` |
| Print-to-PDF CSS | ✅ Working | `@media print` on every page |
| Fuzzy identity matching | ✅ Wired (TD5) | RapidFuzz weighted scoring; AUTO_MERGE/REVIEW/NEW |
| Schema migrations | ✅ Done (TD3) | 5 migrations, idempotent, runs on startup |
| Structured logging | ✅ Done (TD12) | RotatingFileHandler at data/logs/bruns.log |
| CORS restriction | ✅ Done (TD9) | localhost-only, env-overridable |
| Offline UI assets | ✅ Done (TD11) | tailwind/daisyui/htmx/chart.js vendored locally |
| SQLite conn leak | ✅ Fixed (TD4) | processor.py wraps in `try/finally` |
| Fresh-install DB | ✅ Fixed (TD1) | db.py shipments DDL aligned with live schema |
| Dead code removal | ✅ Done (TD2) | logistics_app/, ui/, database_logic/, utils/ deleted |
| server.py size | 🟡 2 368 LOC | TD8 phase 1 done (-23%); phase 2 = blueprint split (deferred) |
| CSRF on state-changing endpoints | ⚠️ Open (TD10) | Deferred until multi-user auth (L2) |

For the prioritized fix plan, see **[TECH-DEBT-CLEANUP.md](TECH-DEBT-CLEANUP.md)**.
