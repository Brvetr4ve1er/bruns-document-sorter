# Architecture & Layer Rules

This document is the **single source of truth** for how packages in this repo
may import each other and what each module does. The import rules are enforced
by `tests/test_imports.py`.

---

## The system at a glance

A **single-process Flask app** on port 7845 serves both the operator HTML UI
and the JSON BI bridge. The extraction engine beneath it is fully UI-agnostic
and can be driven from a CLI or test harness without starting Flask.

```
┌──────────────────────────────────────────────────────────────────────┐
│  core/api/server.py                                                  │
│  2 368 LOC · 57 routes · Flask + HTMX + DaisyUI                      │
│                                                                      │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────────────┐  │
│  │  HTML UI routes  │  │  /api/* (REST)  │  │  /llm/* (config)  │  │
│  │  (operator UX)   │  │  (Power BI)     │  │  (modal + test)   │  │
│  └────────┬─────────┘  └────────┬────────┘  └────────────────────┘  │
│           │                     │                                    │
│  ┌────────▼─────────────────────▼──────────────────────────────┐    │
│  │  core/api/projections.py  ←  LLM JSON → domain tables       │    │
│  └────────────────────────────────────────────────────────────-┘    │
│           │                                                          │
│  ┌────────▼────────────────────────────────────────────────────┐    │
│  │  core/api/job_tracker.py  ←  in-memory job dict + threading │    │
│  └────────────────────────────────────────────────────────────-┘    │
└──────────────────────────────────────────────────────────────────────┘
           │
           ▼ pure-function helpers (TD8 phase 1 extracts — Flask-free)
┌──────────────────────────────────────────────────────────────────────┐
│  core/business/                                                      │
│    bbox.py          field_color() — bounding-box highlight palette   │
│    charts.py        logistics_chart_data, travel_chart_data          │
│    completeness.py  family case status flow + per-member checklist   │
│    demurrage.py     calc_demurrage, demurrage_info, free_days lookup │
│    exports.py       49-col EXPORT_COLUMNS + run_query                │
│    forms.py         flatten_for_form ⇄ set_nested (round-trip)       │
│    nlsql.py         NL2SQL prompt, validate_select, generate_sql     │
│    reconcile.py     reconcile_siblings, flatten_diff, compute_diff   │
│    stats.py         dashboard counts + operator action panel         │
└──────────────────────────────────────────────────────────────────────┘
           │ (called by)
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  core/pipeline/                                                      │
│    router.py       resolves LLM config + DB path, spawns processor   │
│    processor.py    steps 0–7: hash → extract → validate → store      │
│    job.py          Job dataclass (id, status, logs, retries)         │
│    queue.py        placeholder (Huey not active)                     │
└──────────┬───────────────────────────────────────────────────────────┘
           │ imports
    ┌──────┴──────────────────────────────────────────────────────────┐
    │  core/extraction/                                               │
    │    text_extractor.py   PyMuPDF + Tesseract + Ollama vision      │
    │    llm_client.py       provider-agnostic LLM call + retry       │
    │    chunker.py          5-page sliding window + merge            │
    │    prompt_registry.py  register_prompt / get_prompt / version   │
    │    mrz_extract.py      PassportEye + mrz library                │
    │    result.py           ExtractionResult dataclass               │
    │    visual.py           PyMuPDF bounding-box annotation helper   │
    ├─────────────────────────────────────────────────────────────────┤
    │  core/validation/                                               │
    │    engine.py           5 rules for logistics; 0 for travel      │
    ├─────────────────────────────────────────────────────────────────┤
    │  core/storage/                                                  │
    │    db.py               init_schema (TD1 fixed), get_connection  │
    │    repository.py       insert_document, get_document            │
    │    paginator.py        paginated_query helper                   │
    │    archiver.py         source-file archive management           │
    │    migrations.py       run_migrations (TD3 done — 5 ALTERs)     │
    │    exporters/          csv.py, xlsx.py, family_export.py        │
    ├─────────────────────────────────────────────────────────────────┤
    │  core/normalization/                                            │
    │    codes.py            container number, TAN, carrier, size     │
    │    dates.py            any format → ISO YYYY-MM-DD              │
    │    names.py            lowercase, diacritics strip              │
    ├─────────────────────────────────────────────────────────────────┤
    │  core/schemas/                                                  │
    │    logistics.py        Shipment + Container Pydantic models     │
    │    person.py           Person Pydantic model                    │
    │    document.py         Document Pydantic model                  │
    │    base.py             AuditMixin (created_at, modified_at)     │
    ├─────────────────────────────────────────────────────────────────┤
    │  core/matching/                                                 │
    │    engine.py           RapidFuzz fuzzy identity resolver        │
    │    scorers.py          name(0.6) + dob(0.3) + nationality(0.1)  │
    │    thresholds.py       AUTO_MERGE=0.85, REVIEW=0.60             │
    │    (TD5 wired — projections.py uses resolve_identity)           │
    ├─────────────────────────────────────────────────────────────────┤
    │  core/search/                                                   │
    │    vector_db.py        ChromaDB wrapper: embed + cosine search  │
    ├─────────────────────────────────────────────────────────────────┤
    │  core/audit/                                                    │
    │    logger.py           log_action → audit_log table             │
    └─────────────────────────────────────────────────────────────────┘
           │ domain config
    ┌──────┴──────────────────────────────────────────────────────────┐
    │  modules/                                                       │
    │    logistics/                                                   │
    │      prompts.py    LLM_PROMPT_TEMPLATE v2.0  (170-line schema) │
    │      config.py     XLSX_COLUMNS (49 col list), OLLAMA_MODEL    │
    │      pipeline.py   module-specific hooks (post-process)        │
    │    travel/                                                      │
    │      prompts.py    LLM_PROMPT_TEMPLATE for passports/IDs       │
    │      config.py     doc type mappings                           │
    │      mrz_parser.py MRZ field post-processing                   │
    │      pipeline.py   module-specific hooks                       │
    └─────────────────────────────────────────────────────────────────┘
```

---

## Import rules (enforced by tests/test_imports.py)

```
          core/api/           may import →  core/*  modules/*
          core/business/      may import →  core/storage  core/api/llm_config
          modules/            may import →  core/*
          core/pipeline/      may import →  core/extraction  core/storage
                                            core/validation  core/schemas
                                            core/api/projections
          core/extraction/    may import →  core/normalization  core/schemas
          core/storage/       may import →  (nothing internal — only stdlib/deps)
          core/matching/      may import →  core/schemas  core/normalization
          core/normalization/ may import →  (nothing internal)
          core/search/        may import →  (nothing internal)
          core/audit/         may import →  core/storage
```

**Forbidden:** `core/storage` importing `core/api`. `modules/` importing each
other. Any cycle involving `core/pipeline` or `core/business`.

---

## Directory reference

```
core/api/
  server.py           Flask routes only (2 368 LOC, 57 routes — TD8 phase 1 done,
                                          phase 2 = blueprint split, deferred)
  projections.py      LLM JSON → shipments/containers/persons/families/documents_travel
                       (uses core.matching.engine for fuzzy person resolution)
  llm_config.py       Provider registry + config load/save/test
  job_tracker.py      In-memory dict[str, Job] + threading.Thread spawner
  templates/
    base.html         Nav, theme switcher, LLM modal, keyboard shortcuts, print CSS
    mode_picker.html  / splash page
    global_search.html  /search
    logistics/
      dashboard.html        action center, stats, container table, NL2SQL
      document_detail.html  PDF preview, field editor, reconciliation panel
      documents.html        list + keyword/semantic search
      container_detail.html D&D bar, operational field form
      swimlane.html         column-per-status pipeline view
      review_queue.html     low-confidence queue
      analytics.html        Chart.js — status, carriers, volume, transit
      sheet.html            spreadsheet-style container table
      export.html           CSV/XLSX download triggers
      upload.html           multi-file upload
      settings.html         LLM config, clear input, purge jobs
      edit.html             legacy container edit (pre-detail-page)
      _ask_result.html      NL2SQL results fragment
      _edit_result.html     inline save feedback fragment
      _reextract_diff.html  re-extraction diff modal body
      _progress_row.html    HTMX upload progress row
    travel/
      dashboard.html        stats, expiry warnings, recent persons
      persons.html          person list + search
      person_detail.html    extracted fields, linked docs
      families.html         family cards with status badges
      family_detail.html    completeness gate, case flow, next action
      calendar.html         12-month expiry heatmap
      analytics.html        Chart.js — status, doc types, nationalities, timeline
      documents.html        travel document list
      document_detail.html  travel doc fields + MRZ data
      upload.html           travel file upload
      _save_result.html     inline save feedback
      _progress_row.html    HTMX upload progress
  static/                   TD11 — vendored UI assets (no CDN at runtime):
    tailwind.min.js         Tailwind play CDN bundle
    daisyui.min.css         DaisyUI 4.12.10 full theme bundle (31 themes)
    htmx.min.js             HTMX 2.0.3
    chart.min.js            Chart.js 4.4.4 UMD build

core/business/              Pure-function business logic (no Flask import).
                            Each function takes db_path or dicts; the routes
                            are thin wrappers around these.
  bbox.py             field_color() — bounding-box highlight palette mapper
  charts.py           logistics_chart_data, travel_chart_data (Chart.js series)
  completeness.py     family_completeness, REQUIRED_DOCS_BY_ROLE, CASE_STATUS_FLOW
  demurrage.py        calc_demurrage, demurrage_info, free_days_from_documents
                       (N5 wired — extracted free_days takes precedence)
  exports.py          EXPORT_COLUMNS (49-col XLSX schema), select_clause, run_query
  forms.py            flatten_for_form ⇄ set_nested (round-trip for edit form)
  nlsql.py            NL2SQL prompt + validate_select (TD7 hardened)
                       + generate_sql_from_question (LLM call)
  reconcile.py        reconcile_siblings (TAN cross-check),
                       flatten_diff + compute_diff (re-extract diff)
  stats.py            logistics_stats / action_panel / recent_*
                       travel_stats / recent_persons

core/logging_config.py   TD12 — RotatingFileHandler at data/logs/bruns.log
                          + console handler. configure_logging() called once
                          at server startup; idempotent.

core/extraction/
  text_extractor.py   PyMuPDF (Strategy 1) + Tesseract/Arabic (Strategy 2) + vision (3)
  llm_client.py       Provider-agnostic, format=json, retry, confidence scoring
  chunker.py          5-page window chunking for long PDFs
  prompt_registry.py  Global registry: register_prompt(module, doc_type, template, version)
  mrz_extract.py      PassportEye + mrz library — MRZ band extraction
  result.py           ExtractionResult(data, confidence, raw_text, validation_issues)
  visual.py           PyMuPDF: search_for(value) + add_highlight_annot(rect) per field

core/matching/                Wired into core/api/projections.py — TD5 done.
  engine.py           resolve_identity(new_person, candidates) → MatchResult
                       (status: AUTO_MERGED | REVIEW | NEW_IDENTITY)
  scorers.py          score_names (RapidFuzz token_set_ratio, 0.6 weight)
                      score_dob (exact match, 0.3 weight)
                      score_nationality (exact match, 0.1 weight)
  thresholds.py       AUTO_MERGE_THRESHOLD=0.85, REVIEW_THRESHOLD=0.60

core/storage/
  db.py               init_schema(db_path) — creates all tables (⚠ TD1: shipments DDL wrong)
  repository.py       insert_document, get_document
  paginator.py        paginated_query(conn, table, page, page_size, where, order_by)
  archiver.py         manage data/input/ archiving
  migrations.py       run_migrations() — 5 migrations registered (TD3 done)
  exporters/
    xlsx.py           generate "Containers actifs" 49-col workbook
    csv.py            flat CSV of all containers+shipments
    family_export.py  full family ZIP (persons + docs + Excel summary)

modules/logistics/config.py
  XLSX_COLUMNS        The 49 column names in order — this is the hard BI contract

data/  (runtime, not in repo)
  logistics.db        shipments, containers, documents, audit_log, extraction_cache
  travel.db           persons, families, documents_travel, audit_log, extraction_cache
  .llm_config.json    active LLM provider config (set via UI modal)
  input/logistics/    uploaded PDFs awaiting processing
  input/travel/       uploaded travel documents
  vector/             ChromaDB persistence directory
  exports/            generated XLSX/CSV files
  logs/               TD12 done — bruns.log + RotatingFileHandler 10MB×5
```

---

## Dead code

The pre-migration Streamlit-era directories (`logistics_app/`, `ui/`,
`database_logic/`, `utils/`) were deleted under TD2. The
`tests/test_imports.py` `GHOST_TARGETS` set will catch any future stale
import that tries to reference them.

---

## Test layout

```
tests/
  test_imports.py      Layer-rule boundary enforcement (import graph check)
  test_phase1.py       Phase 1: action panel, confidence routing, activity feed
  test_phase2.py       Phase 2: demurrage, NL2SQL, bounding box, swimlane
  test_phase3.py       Phase 3: travel calendar, family completeness
  test_phase4.py       Phase 4: global search, keyboard shortcut routes
  test_phase8.py       Phase 8: misc integration tests
  fixtures/
    smoke.pdf          Minimal test PDF
  stress_data/
    doc_*.txt          Synthetic document texts for load testing
    logistics_test.db  Pre-populated test DB
    travel_test.db     Pre-populated travel test DB
  _import_scan.py      Helper: full cross-package import graph
  _third_party_scan.py Helper: what PyPI packages are actually imported
  _dead_code_scan.py   Helper: detect orphan modules
```

Current test run: **5 passed, 1 skipped**. Coverage is light — the test suite
covers import boundaries and basic HTTP smoke tests but no unit tests for
business logic (demurrage, reconciliation, matching engine).
