# BRUNs Document Intelligence Platform — Project Wiki

> Last updated: 2026-04-28
> Maintainer: Antigravity (single-developer project)
> Status: Active development — Phase 1 of Streamlit → Flask UI migration in progress

This is the canonical knowledge base for the **BRUNs Document Intelligence Platform** —
a fully-local, multi-domain document extraction and structured-data pipeline built
around PDF ingestion, local LLMs, fuzzy entity matching, and BI-ready data egress.

If this is your first time opening this repo, read the documents in this order:

| # | Document | What you learn |
|---|----------|----------------|
| 1 | [01-OVERVIEW.md](01-OVERVIEW.md) | What this product is, who it's for, why it exists |
| 2 | [02-HOW-IT-WORKS.md](02-HOW-IT-WORKS.md) | End-to-end pipeline: PDF in → structured data out |
| 3 | [03-TECHNOLOGY-STACK.md](03-TECHNOLOGY-STACK.md) | Every dependency and the reason it's there |
| 4 | [04-DOMAIN-MODULES.md](04-DOMAIN-MODULES.md) | The Logistics and Travel domains explained |
| 5 | [05-DATA-MODEL.md](05-DATA-MODEL.md) | SQLite schemas, Pydantic models, relationships |
| 6 | [06-API-REFERENCE.md](06-API-REFERENCE.md) | Flask BI endpoints (Power BI / Tableau / Looker) |
| 7 | [07-USE-CASES.md](07-USE-CASES.md) | Where this fits in the real world |
| 8 | [08-MARKETING-PLAN.md](08-MARKETING-PLAN.md) | Positioning, ICP, pricing, go-to-market |
| 9 | [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) | Insights, V2 ideas, technical debt |
| 10 | [10-DEPLOYMENT.md](10-DEPLOYMENT.md) | Install, run, troubleshoot |

Plus the existing engineering reference:

- [ARCHITECTURE.md](ARCHITECTURE.md) — Layer rules and import boundaries (single source of truth for package dependencies)

---

## One-paragraph elevator pitch

BRUNs ingests PDF documents (booking confirmations, bills of lading, passports, ID
cards) on a local machine, extracts structured fields with a local LLM (Ollama)
and OCR fallback (Tesseract / PassportEye), validates everything against strict
Pydantic schemas, deduplicates via cryptographic hashing, resolves identity
conflicts via fuzzy matching (RapidFuzz), and serves the resulting database
through a Flask REST API that Power BI can connect to live. **No cloud, no paid
APIs, no data leaves the operator's machine.**

## Why this exists

Logistics operators in regulated markets (Algeria, North Africa, EU import/export
brokerages) spend hours per day re-typing data from PDF shipping documents into
Excel "Containers actifs" trackers — a 49-column workbook used industry-wide for
demurrage and customs accounting. Every field re-typed is a chance for a typo
that creates a real financial loss (a wrong restitution date can mean €500/day in
demurrage fines). The problem is identical in immigration consulting (passport
data → family files → visa applications).

This project automates the data entry, keeps the data on-prem (mandatory for
several customer segments), and pipes it into the BI tools the operators
already use.

## Repository map (at a glance)

```
BRUNs logistics data scraper/
├── core/                   ← Engine + UI (single tree, single process)
│   ├── api/                ← Flask + Jinja templates + HTMX (the UI)
│   │   ├── server.py       ← All routes (HTML + JSON BI) on port 7845
│   │   ├── llm_config.py   ← Provider config (4 backends)
│   │   ├── job_tracker.py  ← Background-job tracker for HTMX polling
│   │   └── templates/      ← DaisyUI synthwave (31 themes, no build step)
│   ├── extraction/         ← LLM client, text extractor, OCR, chunker
│   ├── matching/           ← Fuzzy identity resolution
│   ├── normalization/      ← Names, dates, codes
│   ├── pipeline/           ← Job, processor, queue, router
│   ├── schemas/            ← Pydantic models
│   ├── search/             ← ChromaDB vector search
│   ├── storage/            ← SQLite repository, paginator, exporters
│   └── validation/         ← Post-extraction validation
├── modules/                ← Domain-specific config + prompts
│   ├── logistics/          ← Shipping / container prompts
│   └── travel/             ← Passport / family prompts + MRZ parser
├── data/                   ← Live SQLite DBs (logistics.db, travel.db),
│                              uploads, logs, exports, hidden config
├── tesseract_bin/          ← Bundled Tesseract OCR
├── tessdata/               ← OCR language models
├── tests/                  ← Pytest + import-rule enforcement
└── docs/                   ← This wiki
```

Detailed map: [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Active workstreams

| Workstream | Owner | Status |
|------------|-------|--------|
| Streamlit → Flask + HTMX + DaisyUI synthwave UI migration | Other Claude session | Phase 1 in progress |
| Wiki documentation (this folder) | This Claude session | In progress |
| Power BI live-connection BI bridge | Already shipped (`core/api/server.py`) | Stable |
| Travel mode + MRZ parser | Shipped | Stable |

See [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) for what's next.
