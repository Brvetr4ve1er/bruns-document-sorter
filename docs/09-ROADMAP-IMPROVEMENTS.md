# 09 — Roadmap and Improvements

This is the engineering roadmap and the candid critique of what's currently
weak in the platform. Read it as a working document, not a marketing
roadmap — items are ordered by *honest* priority, not by what sells.

## Done (April 2026)

### ✅ Streamlit → Flask + HTMX + DaisyUI migration

| Phase | Scope | Status |
|-------|-------|--------|
| P1 | Flask HTML routes for read-only dashboard, DaisyUI 31-theme picker + HTMX via CDN | **Done** |
| P2 | `/upload` POST + `/process-status/<job_id>` HTMX polling, in-memory `job_tracker.py` | **Done** |
| P3 | Edit + Export + Settings + LLM-config modal as HTMX dialog | **Done** |
| P4 | Travel mode parity (Dashboard / Upload / Persons / Families / Documents) | **Done** |
| P5 | Streamlit decommissioned. Single-process Flask app on port 7845. | **Done** |

The codebase no longer contains `app.py` (root), `logistics_app/`, `travel_app/`,
`ui/`, `.streamlit/`, or `_legacy/`. All UI lives under `core/api/templates/`.
Test `tests/test_imports.py` enforces that nothing imports any of these
deleted package names ever again (they are listed as `GHOST_TARGETS`).

Path consolidation also done: `data/` is now the single home for
`logistics.db`, `travel.db`, `input/`, `logs/`, `exports/`, and the
hidden config files (`.llm_config.json`, `.launcher_prefs.json`).

### Active: This wiki

Everything in `docs/` is being kept current with the Flask architecture.

---

## Next (June–August 2026)

### N1 — In-memory `JobTracker` persistence

P2 of the migration introduces `core/api/job_tracker.py` — an in-memory
dict[str, Job]. **Problem:** restart the server, lose all in-flight jobs.

Improvement: back the tracker with `data/queue.db` (already a SQLite file in
the project for Huey). On startup, hydrate any incomplete jobs and resume.

Effort: ~1 day. Benefit: production-ready upload UX.

### N2 — Apache Parquet export endpoint

`/api/logistics/shipments_full.parquet` — 10× faster ingest into Power BI
than JSON pagination at >10k rows.

Effort: ~half day (pyarrow already a transitive dep via pandas).
Customer ask: yes, repeated.

### N3 — Computed BI columns moved into a SQL VIEW

Today the 49-column shape is computed at query time in
`core/api/server.py::logistics_shipments_full`. As the customer adds custom
columns, the SQL grows.

Improvement: define a SQLite VIEW `containers_actifs_export` that does the
JOIN + computed columns in pure SQL. The Flask route becomes a one-liner.

Benefit: the same view can be queried directly by Power BI's SQLite
connector for offline use.

Effort: ~1 day.

### N4 — Demurrage risk computation

`/api/logistics/risk/demurrage` — for every active container, compute
predicted exposure based on `etd → today` and historical carrier delay
distributions.

Math: for each carrier, learn `lambda` (avg delay days) from historical
shipments. For active container `c`, predict `delay = poisson(lambda_carrier)`.
Compute `exposure = max(0, predicted_arrival + dwell_avg - free_days) * rate_per_day`.

Effort: ~3 days. Marketing impact: high — this is a "wow demo" feature.

### N5 — LLM client fallback to cloud (premium tier)

`core/extraction/llm_client.py` exposes a `LLMClient` interface. Today there
is one implementation (Ollama). Add:

- `OpenAIClient` (uses `OPENAI_API_KEY` env var)
- `AnthropicClient` (uses `ANTHROPIC_API_KEY`)

Routing logic: try local Ollama first (free). On failure / low confidence,
escalate to cloud (paid). Audit log records which provider answered.

Why: enables the "premium accuracy" tier without touching local-first
positioning for the base product.

Effort: ~2 days.

---

## Later (Sep–Dec 2026)

### L1 — Human-in-the-loop review UI

Today the matcher's `REVIEW` status (0.60–0.85 score) is surfaced but the
UI for resolving the conflict is rudimentary. Build:

- Side-by-side comparison of new vs candidate person
- Highlight which fields matched, which didn't, with the breakdown scores
- Single-click merge / new-identity buttons
- Undo within 30 seconds (toast-based)

Effort: ~3 days once Flask UI is the substrate.

### L2 — Bounding-box overlay on the PDF

`PyMuPDF` already exposes word-level bounding boxes. Overlay the extracted
field on the original PDF as a yellow highlight, click-to-jump from the
extracted-data panel to the PDF location.

This is the "verification time → seconds" feature mentioned in the README's
roadmap. It's also a killer demo.

Effort: ~3–5 days. Touches PDF rendering in the Flask UI.

### L3 — OData v4 endpoint

Power BI / Excel have first-class OData connectors (better than the generic
"Web" connector — pagination, filtering, schema discovery handled
automatically).

`/api/logistics/odata/$metadata` + `/api/logistics/odata/Shipments?$filter=...`

Effort: ~5 days. There's a `flask-odata` package but it's stale; might
need a hand-rolled implementation.

### L4 — Multi-user auth (deferred — only if multi-tenant)

Currently single-user. If we ever sell to teams of 5+ on shared install:

- Basic auth at the Flask layer, password hashing in `data/auth.db`.
- Per-user audit log entries (`Modifié par` column finally fillable).
- Role split: `viewer` / `operator` / `admin`.

Effort: ~5 days. Deliberately deferred — most customers are single-operator.

### L5 — Healthcare domain plug-in (proof of platform claim)

Implements `modules/healthcare/` as a forcing function for the "1 day per
new domain" target. Likely first stab at a referral letter parser.

Effort: ~7 days for the first version, less if the Phase-1 architectural
hardening lands first.

---

## Tech debt and architectural critique

### TD1 — Two parallel pipelines exist

`logistics_app/app.py::process_pdf_file()` and
`core/pipeline/processor.py::PipelineProcessor.process_file()` are two
implementations of the same flow. The first is what Streamlit calls today.
The second is the cleaner, OOP, cache-aware version intended to be the
single path.

**Resolution:** Phase 5 of the UI migration kills Streamlit, which kills
the first implementation. Until then they co-exist. Risk: a fix made in one
doesn't propagate to the other. Mitigation: make the wrapper trivial — the
Streamlit version should just call the Pipeline.

Priority: medium (becomes irrelevant after P5).

### TD2 — Schema is duplicated between Pydantic and SQLite

`core/schemas/logistics.py::Container` (Pydantic) and the `containers` table
(SQL DDL in `core/storage/migrations.py`) are hand-kept in sync. Adding a
field requires touching two places.

**Resolution options:**
- (a) Generate SQL from Pydantic via SQLModel — adds a dep, changes the
  storage layer significantly.
- (b) Add a test that scans both definitions and fails CI on mismatch.

(b) is the right call. Effort: 1 day. Priority: medium-high — prevents real
bugs.

### TD3 — `_legacy/` and the dual `app.py` confusion

There's `app.py` at root (new mode-selector entry point), `logistics_app/app.py`
(monolithic Streamlit), and a `_legacy/` directory. New contributors get
confused about which file to read.

**Resolution:** After P5, delete `logistics_app/app.py` and `_legacy/`.
Document in the wiki. Progress on this is unblocked by the Flask migration.

Priority: low (it's confusing but not actively breaking things).

### TD4 — No CI / no automated test runs

`tests/` exists with `test_imports.py` (the layer-rule enforcer) but nothing
runs it on commit. The single developer must remember to `pytest` before
pushing.

**Resolution:** Add a `.github/workflows/ci.yml` that runs `pytest -v` on
every push. Effort: 30 minutes. Priority: high — catches the import-rule
violations that cause the dual-pipeline mess.

### TD5 — Settings persistence is scattered

UI settings live in `data/ui_settings.json`. App settings in
`data/.launcher_prefs.json`. Onboarding state inline in `logistics_app/app.py`.
Three different storage patterns for "user preferences."

**Resolution:** A single `core/config/preferences.py` with one read, one
write, typed via a Pydantic model. Migrate the three sources during P5.

Effort: 1 day. Priority: low until P5.

### TD6 — Flask server has no error envelope

Routes return `jsonify(...)` directly. On exception, Flask returns the
default 500 HTML. BI tools don't handle this gracefully.

**Resolution:** Add an error handler that always returns
`{"error": "...", "code": "..."}` JSON, even on 500. Standard Flask
`@app.errorhandler(Exception)`.

Effort: 1 hour. Priority: high (cheap, catches real BI tool bugs).

### TD7 — No structured logging

`core/audit/logger.py` writes per-file JSON files. The Flask server does
`print()`. There's no unified log stream a sysadmin could `tail`.

**Resolution:** Adopt `structlog` (already a transitive dep), pipe everything
to `data/logs/app.jsonl` in JSONL format. Per-file audit logs stay (they're
the case-file evidence trail for Travel module).

Effort: half day. Priority: medium.

---

## Insights from analyzing the codebase

These are observations that don't slot neatly into "roadmap" or "tech debt"
but matter for product direction:

### Insight 1 — The Excel format IS the API

The 49-column "Containers actifs" XLSX is not a quaint legacy artifact. It
is the *integration contract* with the customer's existing Power BI report.
Treating it as a first-class output (not a "simpler alternative" to the
REST API) clarifies a lot:

- Schema changes that break the XLSX shape must be versioned carefully.
- New computed columns added by customers should live in the XLSX export
  layer, not the database.
- The XLSX writer should arguably be a separate microservice some day —
  it's the most-touched output and the most fragile.

### Insight 2 — The cache hit rate is the real KPI

A clerk who re-uploads the same 50 PDFs at end of week is a feature, not a
bug. Cache hits = instant feedback = happy clerk. The first metric to
expose in the UI dashboard should be "cache hit rate this week."

### Insight 3 — Identity resolution is the moat (Travel module)

OCR + LLM is commoditized. What is NOT commoditized is the fuzzy matcher
that figures out "this passport for Mohammed AbdelKader b. 1985-03-12 is
the same person as the Mohammed Abdul-Khader on case #4521 from 2 years
ago." This is the feature that makes the Travel module sticky. Invest more
here.

### Insight 4 — Local-first is a 5-year posture, not a fad

The trend in MENA enterprise software is *toward* on-prem and local-first,
not away from it. Data sovereignty laws (Algeria's Loi 18-07, similar in
Morocco and Tunisia) make cloud-first SaaS structurally disadvantaged.
Don't dilute the local-first positioning for short-term sales.

### Insight 5 — The competitor is the clerk, not other software

Every customer has a clerk doing this manually today. The pitch is never
"better than competitor X" — it's "stop paying €600/mo for typing." Every
piece of marketing collateral should center on this.

### Insight 6 — French language is non-trivial

Every prompt, every UI string, every export column is in French. This is a
moat against US/UK competitors who would need a localization pass. It is
also a constraint: the LLM has to handle French + technical terms (CNE,
PON, MARKS AND NUMBERS) gracefully. Spend time on prompt translation and
testing.

### Insight 7 — The Flask BI bridge is the most under-marketed feature

We have a live REST API that Power BI connects to in 3 clicks. This is the
killer feature for the BI consultancy ICP. The README mentions it as
"future roadmap" — it's already built. Update the README.

(Action item for this Claude session: noted, will be cross-referenced.)

### Insight 8 — Two AI sessions on the same codebase is a real risk

Currently active: this session writing docs, parallel session migrating the
UI. The git status already shows file moves and renames. Without
coordination protocol:

- Imports break in unpredictable ways.
- Refactors collide.
- Both sessions claim the work is done while integration is broken.

Suggested protocol (informal):
- Owner-of-area declared at session start (e.g., "this session owns
  `docs/` and never touches `core/`").
- Before any file move/rename, one session checks the other isn't
  currently editing it.
- A coordination note (`COORDINATION.md` or similar) at root tracks active
  workstreams.

This is not a software problem; it's a workflow problem. Worth explicit
attention.

---

## Things explicitly NOT on the roadmap

| Idea | Why not |
|------|---------|
| Mobile app | The buyer uses a Windows laptop. Mobile is a distraction. |
| Multi-tenant SaaS | Conflicts with local-first positioning. |
| Email ingestion (auto-fetch carrier emails) | Mentioned in old README but security blast radius is huge. Defer indefinitely. |
| Generic document QA chatbot | Not the product. |
| Custom LLM training | Llama3 + good prompts is sufficient. Custom training is a $$$ rabbit hole. |
| Marketplace of community-contributed prompts | Premature; we have ~5 customers. |
