# Architecture & Layer Rules

This document is the **single source of truth** for how packages in this repo
may import each other. The rules are enforced by `tests/test_imports.py` —
breaking them fails the test suite.

> **Why this exists:** the project has two domains (logistics, travel) sharing a
> single core engine. Without enforced boundaries, "small" cross-cuts pile up
> until the system is impossible to refactor. This file + the import test
> physically prevent that.

---

## The system at a glance

A **single-process Flask app** (port 7845) serves both the HTML UI and the JSON
BI bridge. Everything UI-related lives under `core/api/`, and the engine
beneath it (`core/extraction`, `core/pipeline`, `core/storage`, etc.) is fully
UI-agnostic — runnable from a CLI, a notebook, or a future React frontend
without modification.

```
core/                    ← domain-agnostic engine
  ├─ api/                ← Flask routes + Jinja templates + HTMX (the UI)
  │   ├─ server.py       ← all HTML routes + JSON BI endpoints
  │   ├─ llm_config.py   ← provider config (Ollama / LM Studio / OpenAI / Anthropic)
  │   ├─ job_tracker.py  ← in-memory dict[str, Job] for HTMX progress polling
  │   └─ templates/      ← DaisyUI synthwave (CDN, no build step)
  ├─ extraction/         ← OCR (Tesseract) + LLM text extraction + chunking
  ├─ matching/           ← fuzzy entity resolution
  ├─ normalization/      ← canonical names / dates / codes
  ├─ pipeline/           ← orchestration: job, processor, queue, router
  ├─ schemas/            ← Pydantic base + per-domain schema loaders
  ├─ search/             ← ChromaDB vector search
  ├─ storage/            ← SQLite repository, paginator, exporters
  ├─ validation/         ← post-extraction validation engine
  └─ audit/              ← structured logging
modules/                 ← domain-specific config, prompts, pipeline shims
  ├─ logistics/          ← shipments, containers, TAN
  └─ travel/             ← passports, families, ID docs (incl. MRZ parser)
config/                  ← shared runtime config (currently a stub package)
data/                    ← live SQLite databases + uploads + logs
tests/                   ← pytest suite + import-rule enforcement
```

---

## Layer rules

The dependency direction is strictly downward. **Lower layers may not import
upper layers.**

| Layer | May import | May NOT import |
|---|---|---|
| `core/api/` | its sibling `core/*` modules, `modules/`, stdlib, third-party | nothing further up (this is the top of the stack) |
| `core/` (engine, excluding api) | its own subpackages, stdlib, third-party | `modules/`, `core.api` |
| `modules/` | `core/`, stdlib, third-party | `core.api`, anything UI-shaped |
| `tests/` | anything (engine + UI) | — |
| `config/` | leaf — imports nothing internal | — |

### Forbidden ghost imports

The following package names are **deleted** and must never appear in any
import statement. Doing so fails the import-rule test:

- `streamlit`
- `logistics_app`
- `travel_app`
- `ui`
- `_legacy`
- `components`

If you find one, it's a stale reference left over from the
Streamlit→Flask migration — clean it up.

### Why these rules

- **`core/` (engine) cannot reach into `modules/` or `core.api`** → guarantees
  the engine is reusable and unit-testable in isolation. If the engine ever
  needs domain knowledge, that's a sign the abstraction is wrong — push the
  domain-specific bit into `modules/<domain>/` instead.
- **`modules/` cannot reach `core.api`** → keeps domain logic headless. A
  future CLI consumer can use `modules/logistics` without dragging Flask in.
- **Tests can import anything** so they can stress every boundary.

---

## Adding a new package

1. Decide which layer it belongs to (look at what it imports — that's its
   layer).
2. If it doesn't fit cleanly: split it. A package straddling two layers is
   the most common source of architectural rot.
3. Add it to the layer table above if it's a new top-level package.
4. Run `pytest tests/test_imports.py` to confirm.

## Adding a new domain (after travel)

1. `modules/<new_domain>/` — config, prompts, pipeline shim, optional
   domain-specific parsers.
2. `core/api/templates/<new_domain>/` — Jinja templates (mirror the
   `logistics/` and `travel/` subtrees).
3. `core/api/server.py` — add the routes (dashboard / upload / list / etc.).
4. `core/schemas/<new_domain>.py` — Pydantic models.
5. `data/<new_domain>.db` — separate SQLite file (created on first use).
6. New tile on the mode picker (`mode_picker.html`).

**No changes to engine `core/*` should be required.** If they are, the
abstraction needs work first.

---

## Validating the rules

```bash
pytest tests/test_imports.py -v
```

Two helper scripts (not tests — runnable directly):

```bash
python tests/_import_scan.py        # full cross-package import graph
python tests/_third_party_scan.py   # what's actually imported from PyPI
python tests/_dead_code_scan.py     # potential orphan modules (review by hand)
```
