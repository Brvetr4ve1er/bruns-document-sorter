# 07 — Use Cases

Concrete situations where BRUNs is the right answer, ranked by buying
likelihood.

## Tier 1 — Validated, real customers

### Use case 1.1 — Algerian freight forwarder

**Customer profile:** 5–50 person freight forwarder in Algiers, Oran, or
Annaba. Handles import/export through Port d'Alger or Port d'Oran. Uses
Power BI for management dashboards, Excel "Containers actifs" tracker as
the operational source of truth.

**Pain today:**
- 1–2 clerks spend 2–4 hours per day re-typing PDF data into Excel.
- Demurrage fines from missed `Date début Surestarie` entries cost ~€500–€2000
  per incident, multiple times per month.
- BI dashboard is 24h stale because data only enters after end-of-day batching.
- Carriers (CMA-CGM, MSC, Ignazio Messina) all use different terminology — a
  new clerk needs 2 weeks to learn the naming conventions.

**What BRUNs does:**
- Replaces the typing with drag-and-drop or batch directory ingestion.
- Auto-fills the 49-column XLSX in the customer's exact format.
- Live Power BI connection — dashboard refreshes within seconds of a PDF
  arriving.
- All carrier terminology canonicalized at the prompt + validator layer.

**Buying trigger:** Single demurrage incident pays for the software for a
year. After that it's pure margin.

**Sales conversation:** "Show me a typical PDF you receive. Here's what your
Excel looks like 30 seconds later."

### Use case 1.2 — Family immigration consultancy (Algeria → France)

**Customer profile:** 2–10 person consultancy helping Algerian families
build visa case files for France, Canada, Belgium. Each case = 5–15 family
members × 3–8 documents per member.

**Pain today:**
- Each new case starts with photocopying passports and re-typing into a
  Word template.
- Same person across multiple cases (parent on child's case, sibling on
  sponsor's case) creates duplicate identities the consultant has to mentally
  reconcile.
- Spelling drift in transliteration of Arabic names creates "two people"
  who are the same person.

**What BRUNs does:**
- MRZ parser extracts passport data deterministically.
- Identity resolution engine catches the same person across cases (≥0.85
  auto-merge, 0.60–0.85 review).
- Family construction groups people into case folders.
- Audit log is the case file evidence trail.

**Buying trigger:** First time the consultant catches a duplicate identity
the system flagged that they would have missed.

---

## Tier 2 — Strong adjacent fit

### Use case 2.1 — Mid-market manufacturing importer

**Customer profile:** 50–500 person manufacturer importing raw materials.
Doesn't have an SAP-level TMS but has enough container traffic that Excel
is breaking down (~50–200 containers per month).

**Pain today:**
- Procurement team is the de-facto BRUNs target — they manually track
  containers in Excel because the freight forwarder's portal is opaque.
- No live visibility into where containers are right now.
- Demurrage costs absorbed silently because no one is computing them
  monthly.

**What BRUNs does:**
- Same as 1.1, but the buyer is the importer, not the forwarder.
- Forwarders email PDFs → procurement drops them in BRUNs → live BI.

**Buying trigger:** "We don't trust the forwarder's tracking portal" — every
importer has said this.

### Use case 2.2 — Customs brokerage

**Customer profile:** Customs broker managing declarations for multiple
clients. 100–500 declarations per month.

**Pain today:**
- Each declaration requires extracting data from the bill of lading,
  invoice, packing list, and certificate of origin.
- Currently re-typing into the customs system (PrePaiement, ASYCUDA, etc.).

**What BRUNs does:**
- Same extraction pipeline, different output target.
- Custom export module to the customs system's CSV import format.

**Buying trigger:** Time per declaration drops from ~30min to ~5min.

### Use case 2.3 — Power BI consultancy serving Excel-bound clients

**Customer profile:** BI consultancy with logistics or healthcare clients
who are stuck on Excel manual entry.

**Pain today:**
- Consultancy can build any Power BI report — but garbage-in-garbage-out
  with Excel manual entry.
- Their client refuses cloud APIs (regulatory, cost, or trust).

**What BRUNs does:**
- White-label or partner-installed at the client.
- BI consultancy keeps building reports; BRUNs cleans the data plumbing.

**Buying trigger:** Consultancy wins more deals because they can answer
"yes" to "can we get this data automated?"

---

## Tier 3 — Architecturally compatible, not yet validated

### Use case 3.1 — Healthcare clinic ingesting referral letters

**Customer profile:** Medium clinic receiving 10–50 referral letters per
day from GPs.

**Pain today:**
- Receptionist re-types patient data, referring physician, presenting
  complaint into the clinic's EMR.

**What BRUNs would do:**
- New `medical` domain in `modules/`.
- Pydantic schema for `Referral`.
- Prompt for referral-letter format.
- Output: EMR-format CSV import or HL7 FHIR JSON.

**Risk:** PHI handling is heavily regulated. Local-first is the right
posture, but the audit trail needs hardening before this is sellable.

### Use case 3.2 — Legal firm processing case bundles

**Customer profile:** Litigation firm handling court bundles (PDFs of
filings, exhibits, correspondence).

**Pain today:**
- Paralegals build "deal bibles" or "trial bundles" by manually indexing
  PDFs.

**What BRUNs would do:**
- New `legal` domain.
- Extraction of dates, parties, document types, page numbers.
- Output: trial bundle index + searchable archive (vector search already
  built).

**Risk:** Document complexity is much higher than logistics. LLM accuracy
ceiling is lower. Probably needs human-in-the-loop UI for correction.

### Use case 3.3 — HR onboarding document verification

**Customer profile:** HR team onboarding 20+ people per month in countries
where credentials must be verified.

**Pain today:**
- Diplomas, employment certificates, reference letters all manually entered
  into HRIS.

**What BRUNs would do:**
- New `hr` domain.
- Extraction of degree, institution, dates, employer, role.
- Identity resolution to merge data from multiple documents about the same
  candidate.

**Risk:** Document templates vary wildly across countries. Prompt engineering
effort is significant.

---

## Anti-use-cases (where this is the wrong tool)

| Scenario | Why BRUNs is wrong |
|----------|---------------------|
| Real-time API feeds (no PDFs) | The pipeline is PDF-shaped. Use a normal ETL tool. |
| Documents requiring human-level reasoning (contracts, technical specs) | LLM accuracy on these is too low for unattended use. |
| Multi-tenant SaaS with thousands of users | Architecture is single-tenant local install. Re-architecting for SaaS would change ~70% of the code. |
| Highly variable document templates with no consistent fields | The Pydantic schema enforcement assumes the documents share a structural backbone. |
| Workflows requiring document GENERATION (not just extraction) | Out of scope. |

---

## Geographic considerations

**Strongest immediate fit:**
- Algeria, Tunisia, Morocco — French-speaking + data sovereignty mandates +
  no GDPR-compliant local SaaS competition.
- France (overseas territories DOM-TOM that have similar PDF workflows).
- Lebanon, Jordan — multilingual, document-heavy, Excel-bound.

**Second wave:**
- EU operators handling regulated goods (pharma, chemical, dangerous goods)
  who need on-prem audit trails.
- Anglophone Africa (Kenya, Nigeria, Egypt) where the "local install +
  Power BI" pattern matches existing tech buying.

**Wrong fit:**
- US — buyers expect SaaS, will not install local software.
- China — competitive landscape dominated by domestic vendors.
- India — price sensitivity and SaaS dominance.

---

## What changes per use case

The architecture lets us reuse ~90% of the codebase per new use case. What
changes:

| Layer | What changes per use case |
|-------|---------------------------|
| `core/` | Nothing |
| `core/schemas/` | One new schema file |
| `modules/<domain>/` | Prompts + config |
| `core/api/server.py` | A few new endpoints |
| `ui/pages/<domain>/` | New pages, but layout primitives are reused |
| `data/` | A new DB file |

This is the cost-of-new-domain we keep pushing toward zero. Today it's ~3
days for a competent developer. Target: ~1 day with a code-gen template.
