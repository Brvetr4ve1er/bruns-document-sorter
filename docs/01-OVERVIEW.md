# 01 — Overview

## What BRUNs is

**BRUNs is a local-first document intelligence platform.** It turns operational
PDFs (shipping documents, identity documents, customs paperwork) into clean,
structured database rows — without sending anything to the cloud, without paid
APIs, and without a vendor lock-in surface.

The platform ships as a single Python application that runs on a normal Windows
laptop. It bundles:

- A PDF text extractor (PyMuPDF)
- A local LLM client (Ollama, default model `llama3`)
- An OCR fallback for scanned/image PDFs (Tesseract via `pytesseract`)
- A passport-MRZ specialist parser (PassportEye + `mrz` library)
- A typed validation layer (Pydantic v2)
- A SQLite-based storage layer with isolated databases per domain
- A vector search engine for semantic queries (ChromaDB)
- A fuzzy entity resolution engine (RapidFuzz)
- A Flask REST API for live BI tool connections (Power BI, Tableau, Looker)
- A web UI (currently Streamlit, migrating to Flask + HTMX + DaisyUI)

## The problem it solves

### Concrete problem (Logistics)

A small-to-medium freight forwarder in Algeria handles ~40 container shipments
per week. For each shipment, they receive 2–4 PDFs from carriers (CMA-CGM, MSC,
Maersk, Ignazio Messina): booking confirmation, departure notice, bill of
lading. A clerk re-types the data into an Excel file called **"Containers
actifs"** — 49 columns of fields like `N° TAN`, `N° Container`, `Date début
Surestarie`, `Site livraison`, `Centre de réstitution`, `Nbr jour surestarie
Facturé`, `Taux de change`.

This Excel is then opened in Power BI for management dashboards: which
containers are in demurrage, which carriers are slowest, what's the total
exposure in DZD this month.

The current process has three failure modes that cost real money:

1. **Typos.** A wrong container number means the wrong shipment shows the wrong
   status. Customers get told their cargo is at port when it's already been
   delivered, or vice versa.
2. **Missed demurrage windows.** If a clerk forgets to enter `Date début
   Surestarie`, the system can't compute days remaining, and the operator finds
   out about a fine when it's already on the invoice.
3. **Latency.** Data only enters the BI tool after the clerk batches up
   yesterday's PDFs. Management sees yesterday's truth, not today's.

### Concrete problem (Travel)

A family-immigration consultant in Algeria builds visa case files. Each case
includes scans of passports, ID cards, birth certificates for every family
member. The same person appears across multiple cases (a parent listed on a
child's case, a sibling listed on a sponsor's case). Identity duplication
across cases is currently solved with copy-paste from previous case folders, and
spelling drift creates "two people" in the file system who are actually the same
person.

### What BRUNs does about it

For logistics:
- Drop the carrier PDF into the upload zone or batch directory.
- The pipeline extracts `tan_number`, `vessel_name`, `etd`, `eta`, all
  containers and their seals/sizes.
- The result is upserted into SQLite using a deterministic key (`TAN` first,
  fallback to `vessel + ETD`).
- Power BI sees the new row within seconds via the live REST endpoint.
- Excel export to the exact 49-column "Containers actifs" format remains
  available for handoff to teams that still want a workbook.

For travel:
- Drop the passport scan in.
- Tesseract + PassportEye extract the MRZ, the LLM extracts the visual fields,
  Pydantic normalizes everything.
- Fuzzy matching (RapidFuzz) compares the new person against existing records.
  If similarity ≥ 0.85, auto-merge. If 0.60 ≤ score < 0.85, flag for human
  review.
- The case folder builds itself.

## Who it's for

**Primary buyers (in priority order):**

1. **Freight forwarders / customs brokers** in markets where data sovereignty
   matters (Algeria, Tunisia, Morocco, EU operators handling regulated goods).
2. **Immigration consultancies and visa agencies** handling family files where
   the same identities recur across cases.
3. **Mid-market manufacturing importers** who want to track their own container
   exposure without buying SAP-level TMS software.
4. **Power BI consultancies** who want a "data plumbing" layer for clients who
   are stuck on Excel.

**Secondary expansion candidates:**

- Healthcare clinics ingesting referral letters (same architecture, different
  prompts and schemas).
- Legal firms processing case bundles.
- Any company with a 49-column Excel that humans manually populate from PDFs.

## Why local-first matters

Three non-negotiable reasons the architecture refuses cloud dependencies:

1. **Customer trust.** Customs, immigration, and shipping data are commercially
   sensitive. Customers in many markets will not allow this data to leave their
   premises. A local install removes the conversation.
2. **Cost.** No per-document fee. Once installed, marginal cost of processing
   document #100,000 is the electricity to run Ollama.
3. **Resilience.** Works in offline environments — port offices with sketchy
   internet, customs warehouses, on-premises bonded zones.

This is also why the BI bridge is a **local Flask server**, not a hosted
service. Power BI's "Web" connector hits `http://localhost:7845/api/...` —
nothing crosses the WAN.

## What it explicitly is NOT

- **Not a TMS** (Transport Management System). It does not book shipments, it
  reads documents about shipments.
- **Not an OCR product.** OCR is one of several internal capabilities. Selling
  it as "OCR software" undersells it.
- **Not a SaaS.** It is a local install. There is no multi-tenant cloud version
  on the roadmap.
- **Not a generic LLM wrapper.** Every domain has hand-tuned prompts, strict
  Pydantic schemas, deterministic normalizers, and a fuzzy matcher. The LLM is
  one component, not the product.

## The value, in one sentence

> BRUNs replaces the clerk-typing-into-Excel workflow with a local pipeline
> that produces the same Excel file (or a live BI connection) automatically,
> with the data sovereignty guarantees the cloud-based competition cannot
> match.
