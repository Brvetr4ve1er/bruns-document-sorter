# 08 — Comparative Study: BRUNs vs. The Industry

> **Purpose:** A structured analysis of how BRUNs compares to commercial IDP
> platforms, open-source alternatives, and logistics SaaS tools. Maps what the
> app does well, what is missing, antipatterns to avoid, UX patterns worth
> adopting, and a prioritised feature roadmap grounded in both codebase analysis
> and live competitive research.
>
> **Research scope:** Nanonets, Rossum, Docsumo, Hypatos, Instabase, ABBYY
> FlexiCapture, Veryfi, Azure Document Intelligence, AWS Textract, Google
> Document AI, Docling (IBM), Unstructured.io, Paperless-ngx, LlamaIndex,
> Flexport, project44, Shipwell, Transporeon, e2open, Shipamax, Klearstack,
> Affinda, Unstract — cross-referenced against `core/schemas/logistics.py`,
> `modules/logistics/prompts.py`, `core/storage/db.py`, `core/api/server.py`,
> `modules/logistics/config.py`.

---

## Table of Contents

1. [Competitive Landscape Map](#1-competitive-landscape-map)
2. [Data Fields — What Is Missing](#2-data-fields--what-is-missing)
3. [Document Types — What Is Not Processed](#3-document-types--what-is-not-processed)
4. [Workflow Patterns — What Competitors Do Right](#4-workflow-patterns--what-competitors-do-right)
5. [Power BI / Analytics — Industry Expectations](#5-power-bi--analytics--industry-expectations)
6. [Antipatterns — What Not to Copy](#6-antipatterns--what-not-to-copy)
7. [UX Patterns Worth Adopting](#7-ux-patterns-worth-adopting)
8. [Feature Roadmap — Ranked by Value](#8-feature-roadmap--ranked-by-value)
9. [Summary: The DO / DON'T Map](#9-summary-the-do--dont-map)
10. [Sources](#10-sources)

---

## 1. Competitive Landscape Map

### Category A — Commercial IDP Platforms

These are the direct functional competitors. They all solve the same core
problem: extract structured data from semi-structured or unstructured documents
at scale.

| Platform | Approach | Cloud / Local | Key Strength | Key Weakness |
|---|---|---|---|---|
| **Rossum** | ML + HITL review UI | Cloud only | Best-in-class review UX, active learning | Expensive, no offline |
| **Nanonets** | Fine-tuned models per doc type | Cloud only | High accuracy on consistent layouts | Per-page pricing |
| **Docsumo** | Pre-trained + custom models | Cloud only | Strong logistics templates | Vendor lock-in |
| **Hypatos** | Cognitive process automation | Cloud only | AP invoice focus | Weak on shipping docs |
| **ABBYY FlexiCapture** | Rule-based + ML | On-premise possible | High accuracy, mature platform | Complex setup, expensive |
| **Instabase** | AI + human review workflows | Cloud only | Cross-field validation | Enterprise price point |
| **Veryfi** | Mobile OCR + API | Cloud | Fast mobile capture | Generic fields, poor BOL |
| **Azure Document Intelligence** | Pre-built + custom models | Cloud + local (containers) | Microsoft ecosystem native | Cost per page |
| **AWS Textract** | Key-value + table extraction | Cloud only | Strong table detection | Manual field mapping |
| **Google Document AI** | Pre-trained + custom processors | Cloud only | 200+ language support | GCP dependency |

**BRUNs position:** Local-first, zero per-page cost, Ollama-backed, fully
offline. This is genuinely differentiated. No commercial IDP platform operates
without cloud and without per-transaction cost. BRUNs wins on cost, privacy,
and offline capability. It competes on accuracy and workflow completeness.

---

### Category B — Open Source / Self-Hosted Alternatives

| Project | What It Does | What BRUNs Can Learn |
|---|---|---|
| **Paperless-ngx** | Document management + OCR tagging | Inbox pattern, auto-tagging by doc type, full-text search |
| **Docling (IBM)** | Layout-aware PDF → structured JSON | Table cell preservation — replace pdfminer for BOL tables |
| **Unstructured.io** | Semantic chunking + preprocessing | Pre-process before LLM: strip headers/footers, isolate tables |
| **LlamaIndex** | LLM document query framework | Dual-model challenge pattern for high-stakes fields |
| **invoice2data** | Template-driven invoice extraction | YAML template library per carrier — pattern for per-carrier prompt variants |

**BRUNs position:** None of these do what BRUNs does end-to-end. The combination
of domain-specific prompts + Pydantic validation + demurrage tracking +
Power BI REST export + local LLM is unique in open source.

**Key insight on Docling:** In 2025 benchmarks, Docling achieved 97.9% accuracy
on complex table extraction from PDFs — significantly better than pdfminer for
multi-container BOL tables. The current PyMuPDF extractor may be merging
container rows that Docling would correctly separate. This is worth testing
on real documents before any other extraction improvement.

---

### Category C — Logistics SaaS Platforms

These are not IDP tools — they are logistics management platforms that include
document handling as a feature.

| Platform | Core Product | What BRUNs Can Learn |
|---|---|---|
| **Flexport** | Digital freight forwarding | Shipment thread view — all docs for one BL as a timeline |
| **project44** | Supply chain visibility | Alert system for ETA changes + milestone events |
| **Shipwell** | TMS | Exception management, carrier scorecards, BOL validation |
| **Transporeon** | Transport procurement | Carrier performance KPIs, dock scheduling |
| **e2open** | Global supply chain | EDI integration as future input source |
| **Shipamax** | Port document automation | Arrival notice as primary demurrage trigger |

**Key insight from logistics SaaS:** these platforms organise around
**shipment events** (milestones), not individual documents. A shipment has a
lifecycle of events; documents are evidence of those events. BRUNs currently
organises around documents and infers shipment state. The feature roadmap
should progressively move toward event-first thinking.

---

## 2. Data Fields — What Is Missing

The current extraction prompt (`modules/logistics/prompts.py`) extracts ~40%
of the fields that professional IDP tools extract from the same Bill of Lading.

### 2.1 Core Trade Document Fields

These appear on every BOL and booking confirmation. None are currently
extracted by the LLM prompt.

| Field | Document Source | Why It Matters |
|---|---|---|
| `bl_number` | Bill of Lading | Primary document identifier for customs, banks, TMS systems |
| `booking_reference` | Booking Confirmation | Links booking to subsequent docs in the same shipment |
| `voyage_number` | All docs | Precise vessel-departure identifier; links to carrier AIS data |
| `vessel_imo` | BOL, departure notice | Unique vessel ID — vessel names repeat, IMO does not |
| `scac_code` | BOL header | Standard Carrier Alpha Code — 2–4 letters, unique per carrier |
| `port_of_loading` | All docs | Hardcoded `Port d'Alger` today — must be dynamic |
| `port_of_discharge` | All docs | Not captured at all |
| `transshipment_port` | BOL (some routes) | Intermediate port for connecting routes |
| `place_of_receipt` | BOL | Multimodal inland origin point |
| `place_of_delivery` | BOL | Multimodal inland destination point |
| `shipper_name` | BOL | Exporter of record |
| `consignee_name` | BOL | Importer of record (often your client) |
| `notify_party` | BOL | Bank or customs agent to notify on arrival |
| `freight_terms` | BOL | Prepaid / Collect — who owes the freight |
| `incoterms` | BOL, commercial invoice | FOB / CIF / DAP etc. — determines liability split |

### 2.2 Cargo Fields (BOL and Packing List)

| Field | Why It Matters |
|---|---|
| `gross_weight_kg` | Customs declaration, port dues, vehicle load planning |
| `net_weight_kg` | Commercial invoice reconciliation |
| `volume_cbm` | Port storage fees often calculated per CBM |
| `package_count` | Customs check: declared vs. actual count |
| `cargo_description_full` | Full commodity text (current: single summary string) |
| `hs_code` | Harmonised System code — critical for customs duty calculation |
| `dangerous_goods_flag` | IMDG class if applicable — legal requirement |

### 2.3 Commercial / Financial Fields

| Field | Why It Matters |
|---|---|
| `freight_amount` | Cost tracking, dispute evidence |
| `freight_currency` | USD vs. EUR vs. DZD |
| `demurrage_free_days` | Per-carrier, per-container — the foundation of demurrage calc |
| `demurrage_rate_usd_per_day` | Per-carrier rate card — currently entered manually |
| `thc_amount` | Terminal Handling Charge — port side cost |

### 2.4 Fields Currently Manual — That Could Be Auto-Extracted

These fields exist in the schema as manual entry. The gap is that they appear
on specific document types that are not yet parsed.

| Field | Source Document | Currently |
|---|---|---|
| `date_debut_surestarie` | Arrival Notice | Manual |
| `date_declaration_douane` | Customs Declaration | Manual |
| `date_liberation_douane` | Customs Release (Mainlevée) | Manual |
| `n_facture_cm` | Demurrage Invoice | Manual |
| `montant_facture_da` | Demurrage Invoice | Manual |
| `nbr_jour_surestarie_facture` | Demurrage Invoice | Manual |

---

## 3. Document Types — What Is Not Processed

Current document types: `BOOKING`, `DEPARTURE`, `BILL_OF_LADING`.

### 3.1 Missing Document Types — Priority Order

| Document | Algerian Term | Priority | What It Unlocks |
|---|---|---|---|
| **Arrival Notice** | Avis d'arrivée | **Critical** | Accurate demurrage clock start. Without this, every demurrage calculation is estimated. |
| **Packing List** | Liste de colisage | **High** | Weight, CBM, package count — fills the entire cargo data gap |
| **Delivery Order** | Bon de livraison / D.O. | **High** | Authorises container release — auto-fills delivery fields |
| **Demurrage Invoice** | Facture surestaries | **High** | Auto-fills `n_facture_cm`, `montant_facture_da`, `nbr_jour_surestarie_facture` |
| **Customs Declaration** | DAU / DUM | **Medium** | Auto-fills `date_declaration_douane`, HS codes |
| **Customs Release** | Bon à enlever / Mainlevée | **Medium** | Auto-fills `date_liberation_douane` |
| **Commercial Invoice** | Facture commerciale | **Medium** | Cargo value, freight costs |
| **Certificate of Origin** | Certificat d'origine | **Low** | Country of origin — import duty relevance |
| **Dangerous Goods Decl.** | DGD / MSDS | **When needed** | Legal compliance — do not skip if cargo is classified |

### 3.2 The Arrival Notice Priority Explained

In Algerian port operations, the demurrage-free period starts from the date
the **avis d'arrivée** is issued, not the vessel's ETA. Without parsing this
document, every demurrage calculation in the system is based on a date the
operator had to estimate or enter manually.

Adding Arrival Notice requires:
1. A `ARRIVAL_NOTICE` prompt in `modules/logistics/prompts.py`
2. A new field: `date_avis_arrivee` on the `shipments` table
3. A new status transition: `IN_TRANSIT → ARRIVED`
4. Demurrage calculation updated to use `date_avis_arrivee` as clock start

---

## 4. Workflow Patterns — What Competitors Do Right

### 4.1 Human-in-the-Loop (HITL) Review — The Biggest Gap

Every serious IDP platform (Rossum, Nanonets, Docsumo, ABBYY, Instabase) uses
a side-by-side review interface as its core UX:

```
┌────────────────────────┬────────────────────────────────┐
│   PDF VIEWER           │   EXTRACTED FIELDS             │
│   (yellow highlight    │                                │
│   on each field        │  BL Number:   [BL-MSCX12345]  │
│   source location)     │  Vessel:      [MSC ANNA]  ✅   │
│                        │  ETD:         [2026-04-15] ✅   │
│   [Page 1 of 3]        │  Container:   [MSCU1234567] ⚠️ │
│                        │  HS Code:     [null]       🔴  │
│                        │  Confidence:  94% / 3 flags    │
└────────────────────────┴────────────────────────────────┘
              [APPROVE]  [CORRECT & SAVE]  [SKIP]
```

**Current state in BRUNs:** The PDF highlight viewer exists in
`ui/components/highlight_viewer.py` but is only wired to the travel module
(MRZ). Logistics extraction commits directly to the database with no review
step. In a financial tracking tool where demurrage invoices reach six figures,
silent extraction errors are a real financial risk.

**What to build:** A logistics review queue. After LLM extraction, every doc
lands in `status = PENDING_REVIEW`. Operator opens it, sees extracted JSON
alongside the highlighted PDF, corrects wrong fields, then approves. Only then
does the data commit. The `validation_issues` table already exists — this
just needs a UI surface.

---

### 4.2 Shipment Thread / Document Timeline

Flexport and project44 organise every interaction around **the shipment**, not
the document. For any TAN/BL, you see a complete lifecycle:

```
TAN/0234/2025  ──  MSC ANNA  ──  Marseille → Alger  ──  MSCU1234567

  ✅ Apr 02  Booking Confirmation received     [BK-92341]
  ✅ Apr 08  Bill of Lading issued             [BL-MSCX12345]
  ✅ Apr 14  Departure Notice received         [ETD: Apr 15]
  ✅ Apr 28  Arrival Notice issued             [Avis — demurrage clock starts]
  ⏳ Apr 29  Customs declaration filed         [DAU-2025-...]
  ⬜ May 02  Container delivered (expected)
  ⬜ May 03  Container restituted (expected)
```

**Current state:** All documents for a TAN are linked via `shipment_id` but
no UI shows this sequence. The user reconstructs it mentally from separate
records.

---

### 4.3 Exception / Alert Management

project44 and Shipwell have an **exception dashboard** as their primary view:
a list of shipments requiring attention, sorted by urgency. BRUNs has all the
data to calculate these; only the surface is missing.

| Alert Type | Trigger | Current Status |
|---|---|---|
| Demurrage active | Past free period, not restituted | Data exists, no alert |
| Demurrage approaching | Free period ends within 2 days | Data exists, no alert |
| BOL missing | Shipment BOOKED > 7 days, no BOL | Data exists, no alert |
| Customs overdue | `date_declaration_douane` > 5 days open | Data exists, no alert |
| Delivery overdue | Past `date_restitution_estimative` | Data exists, no alert |
| Orphaned booking | No DEPARTURE/BOL linked after 14 days | Data exists, no alert |

---

### 4.4 Confidence Score + Active Learning Loop

Nanonets and Rossum track confidence **per field**, not per document. Fields
below a threshold (~80%) are automatically flagged. When a human corrects a
field, the correction becomes a **few-shot example** injected into subsequent
prompts. The extraction loop self-improves.

**Current state in BRUNs:**
- `confidence` column on `documents` table — document-level only
- `confidence_scorer.py` exists in `logistics_app/utils/` — not wired to review
- No per-field confidence
- No correction-to-few-shot pipeline

---

### 4.5 Duplicate Detection Beyond Content Hash

Current deduplication: SHA256 of file content. Correctly catches identical
files. Competitors also detect **semantic duplicates** — same BOL rescanned at
different DPI, or same booking resent with only the timestamp changed.
ChromaDB is already integrated and this is precisely its use case.

---

## 5. Power BI / Analytics — Industry Expectations

### 5.1 Standard Logistics KPIs

Every logistics analytics platform pre-calculates these. BRUNs currently
serves raw rows and leaves all calculations to Power BI. The gap: Power BI
users should not need to write DAX formulas for industry-standard metrics.

| KPI | Formula | Served by BRUNs? |
|---|---|---|
| Average demurrage days per carrier | `AVG(days) GROUP BY carrier` | No |
| Average port dwell time | `AVG(date_restitution - eta)` | No |
| Demurrage cost USD | `over_days × rate_per_day` | No (fields exist) |
| Demurrage cost DZD | `cost_usd × taux_de_change` | No (fields exist) |
| Customs clearance duration | `AVG(liberation - declaration)` | No |
| Transit time | `AVG(eta - etd)` | No |
| Schedule reliability | `COUNT(actual_eta ≤ eta) / COUNT(*)` | No |
| Container turn time | `AVG(date_restitution - date_livraison)` | No |
| Carrier invoice accuracy | `(invoiced_days - actual_days) / actual_days` | No |
| Volume by carrier (TEU/month) | `COUNT containers GROUP BY carrier, month` | No |

### 5.2 Recommended Analytics Endpoint

```python
# Recommended: GET /api/analytics/kpis?period=90d
{
  "period_days": 90,
  "generated_at": "2026-04-28T12:00:00",
  "shipments": {
    "total": 142, "booked": 23, "in_transit": 41, "delivered": 78
  },
  "demurrage": {
    "containers_active": 8,
    "total_days_current": 34,
    "estimated_cost_usd": 18200,
    "estimated_cost_dzd": 2457000,
    "avg_days_per_carrier": { "MSC": 3.2, "CMA-CGM": 2.8, "Maersk": 1.9 }
  },
  "performance": {
    "avg_transit_days": 12.4,
    "avg_customs_clearance_days": 4.1,
    "avg_port_dwell_days": 7.8,
    "on_time_vessel_pct": 0.71
  }
}
```

### 5.3 Power BI Star Schema — Industry Standard

The current API exports flat joined rows. Power BI performs best with a star
schema. Implementing this as a dedicated view or API endpoint eliminates the
need for any Power BI data transformation.

```
                    ┌─────────────┐
                    │  dim_time   │
                    └──────┬──────┘
                           │
┌──────────────┐    ┌──────┴──────────┐    ┌──────────────┐
│  dim_carrier │────│  fact_shipments │────│  dim_vessel  │
└──────────────┘    └──────┬──────────┘    └──────────────┘
                           │
              ┌────────────┼────────────┐
       ┌──────┴──┐   ┌─────┴───┐  ┌────┴──────┐
       │dim_port │   │dim_cont │  │dim_commod.│
       └─────────┘   └─────────┘  └───────────┘

fact_shipments grain: one row per container per voyage
Columns: shipment_key, booking_date, etd, eta, actual_arrival,
         free_time_days, demurrage_start, demurrage_end,
         demurrage_days, cost_usd, cost_dzd,
         customs_declaration_date, customs_clearance_date,
         delivery_date, depot_return_date,
         carrier_invoice_number, invoiced_days, invoiced_amount,
         [+ all FK references to dimension tables]
```

### 5.4 Current Schema Field Gaps vs. Power BI Template Standard

```
Shipment Table:
  ✅ TAN / internal reference        ❌ BL number
  ✅ Vessel name                     ❌ Booking reference
  ✅ Shipping company (carrier)      ❌ Shipper / consignee names
  ✅ ETD / ETA                       ❌ Port of loading (dynamic)
  ✅ Status                          ❌ Port of discharge
  ✅ Port (static)                   ❌ Voyage number / SCAC code
                                     ❌ Actual arrival date (vs. ETA)
                                     ❌ Incoterms

Container Table:
  ✅ Container number                ❌ Gross weight (kg)
  ✅ Size (4 types)                  ❌ Volume (CBM)
  ✅ Seal number                     ❌ HS code
  ✅ Demurrage start date            ❌ Demurrage rate per day
  ✅ Demurrage days (estimated)      ❌ Free days per carrier
  ✅ Customs dates                   ❌ Port charges / THC
  ✅ Delivery info (truck/driver)    ❌ Package count
```

---

## 6. Antipatterns — What Not to Copy

| Antipattern | Who Does It | Why It's Bad | BRUNs Status |
|---|---|---|---|
| **Cloud-only processing** | All SaaS IDPs | Fails at port with poor connectivity; trade doc privacy risk | ✅ Correctly avoided |
| **Per-page / per-doc pricing** | Nanonets, Azure, AWS | Cost unpredictable at scale | ✅ Correctly avoided |
| **Auto-commit without review queue** | Simple OCR tools | Silent extraction errors corrupt financial records | ⚠️ Gap for logistics |
| **Single global extraction model** | Most tools | Generic models fail on carrier-specific BOL layouts | ✅ Domain-specific prompts |
| **Vendor lock-in on model provider** | Azure Doc AI, Rossum | Model deprecations break workflows | ✅ Ollama swap-friendly |
| **Manual field mapping per template** | Old ABBYY, Kofax | Time-consuming per new carrier format | ✅ LLM handles variation |
| **No audit trail** | Simple tools | Can't trace why a field changed | ✅ `audit_log` table exists |
| **Rebuilding shared logic per domain** | Many tools | Divergence, maintenance debt | ✅ Shared `core/` is correct |
| **Confidence score at doc level only** | Basic tools | Field-level errors pass silently | ⚠️ Currently doc-level only |
| **No exception surfacing** | Many tools | Operators miss costly deadlines | ⚠️ Data exists, no surface |
| **Timezone-naive date handling** | Common mistake | ETD/ETA span multiple timezones | ⚠️ Dates stored as strings |
| **No idempotency beyond TAN upsert** | Common mistake | Docs without TAN may create duplicates | ⚠️ Needs BL number as fallback key |
| **Over-normalizing carrier names in prompt** | This app | 7 carriers hardcoded → "other" for ONE, Zim, PIL, Yang Ming — breaks analytics | ⚠️ Fix: extract raw, normalize via lookup table |
| **Hardcoded port default** | This app | Missing port → silently becomes "Port d'Alger" — wrong for Oran/Annaba docs | ⚠️ Fix: leave null, flag for review |
| **Blocking UI during LLM inference** | This app | 30s Ollama call freezes Streamlit for all users | ⚠️ Use Huey queue + polling |
| **Single LLM pass without cross-field validation** | Most simple tools | ETD > ETA (departure after arrival) passes silently | ⚠️ Add business rule validation layer |
| **Dumping raw LLM output to production** | Simple tools | Plausible-looking but wrong values (digit transposition) bypass Pydantic | ⚠️ Add ISO checksum + range checks |

---

## 7. UX Patterns Worth Adopting

### 7.1 The Triage Dashboard (Rossum / Nanonets pattern)

The landing page should not be a data table. It should be an **action list**:
documents requiring review, alerts requiring attention, deadlines approaching.

```
┌─────────────────────────────────────────────────────────┐
│  PENDING REVIEW  (3)    ALERTS  (5)    PROCESSING  (12) │
├─────────────────────────────────────────────────────────┤
│  🔴  MSCU1234567  — Demurrage active  — Day 4 of 0 free │
│  🟡  TCKU9876543  — BOL missing  — Booking 9 days old   │
│  🟡  HLCU4561234  — Customs: 6 days pending clearance   │
│  🟢  CMAU2345678  — Review required  — BL extracted     │
│  🟢  MSDU3456789  — Review required  — Booking          │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Side-by-Side PDF Review (Rossum pattern)

The highest-ROI UX investment. Every extracted field should:
1. Be clickable — clicking highlights its source location in the PDF
2. Show confidence — green / amber / red border on the input field
3. Be editable — operator corrects directly, no re-upload
4. Track the diff — what was extracted vs. what was corrected

### 7.3 Keyboard-First Navigation (Linear / Raycast pattern)

Operators processing 50+ documents per day need keyboard shortcuts:

| Key | Action |
|---|---|
| `J` / `K` | Navigate between documents in review queue |
| `A` | Approve current document |
| `E` | Jump to first editable / flagged field |
| `Tab` | Next field |
| `Shift+Tab` | Previous field |
| `Ctrl+Enter` | Save and advance to next document |
| `S` | Skip to next (defer review) |

### 7.4 Status Pipeline View (Kanban-lite)

Replace the flat table with containers as cards in a horizontal pipeline:

```
BOOKING → IN_TRANSIT → ARRIVED → CUSTOMS → DELIVERED → RESTITUTED
  (23)       (41)         (8)       (12)      (31)         (67)
```

Clicking a stage filters to that stage. A "Move to" action button handles
manual status corrections when documents lag behind physical reality.

### 7.5 Inline Demurrage Counter

On any container card in ARRIVED or CUSTOMS state, show a live counter:

```
MSCU1234567  |  40ft  |  MSC
Free days used: ████████░░  8/10
⚡ 2 free days remaining  |  Overage rate: $420/day
```

### 7.6 Document Source Breadcrumb

Every data field in the UI should trace to its source:

```
Vessel:  MSC ANNA
         📄 from: BOOKING_MSC_2025_04_02.pdf
         ↳ extracted 2026-04-02  •  confidence 97%  •  [view in PDF]
```

This builds operator trust and makes suspicious values easy to verify.

### 7.7 Smart Upload Inbox (Paperless-ngx pattern)

Documents land in an inbox state. The system classifies them (BOOKING /
DEPARTURE / BOL / ARRIVAL_NOTICE / UNKNOWN), routes them to the appropriate
extraction prompt, then moves them to PROCESSED or PENDING_REVIEW. Files that
cannot be classified go to UNRECOGNIZED with an alert — they do not silently
disappear into the input folder.

### 7.8 Alternate Candidate Display (Rossum / Azure pattern)

When confidence is low, show 2–3 alternate candidates rather than just the
top pick. The reviewer selects from alternatives instead of retyping:

```
Container number:  MSCU1234567  [94%]
                   MSCU12345678 [61%]  ← pick this one?
                   MSCU123456   [38%]
```

Achievable with Ollama by asking the LLM for a `candidates` array per field.

---

## 8. Feature Roadmap — Ranked by Value

Priority weighted by: data quality impact, financial risk reduction, operator
time saved, and implementation effort.

---

### Tier 1 — Fix Fundamental Gaps (1–2 days each)

These should be done before any new features. They are core data quality fixes.

#### T1-0: ISO 6346 Container Number Checksum Validation

Container numbers follow a deterministic checksum (ISO 6346). Implement it as
a pure-Python validator (~30 lines) in `core/normalization/codes.py` and call
it inside `Container.norm_cnum`. Numbers that fail the checksum are flagged
for review rather than silently accepted.

```python
def container_checksum_valid(cn: str) -> bool:
    """ISO 6346 check digit algorithm."""
    letters = "0ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    vals    = {c: i for i, c in enumerate(letters)}
    cn = cn.upper().replace(" ", "")
    if len(cn) != 11: return False
    total = sum(vals.get(c, 0) * (2**i) for i, c in enumerate(cn[:10]))
    check = (total % 11) % 10
    return check == int(cn[10])
```

**Impact:** Eliminates the most common class of extraction errors (digit
transposition, OCR misread). Zero LLM involvement — pure deterministic check.
**Effort:** 2 hours.

---

#### T1-1: Expand LLM Extraction Prompt

Add to `modules/logistics/prompts.py`:

```
bl_number, booking_reference, voyage_number, scac_code,
port_of_loading, port_of_discharge,
shipper_name, consignee_name, notify_party,
freight_terms (PREPAID|COLLECT), incoterms,
gross_weight_kg, volume_cbm, package_count,
hs_code, dangerous_goods (true|false)
```

Also fix the carrier normalization antipattern: extract the raw company name
from the document and store it in a new `carrier_raw` field. Apply
normalization via a lookup table with user-editable mappings — not a hardcoded
list of 7 carriers that collapses ONE, Zim, PIL, and Yang Ming into "other."

**Impact:** Doubles the data captured per document. Unlocks all downstream
features. Fixes analytics gaps for non-major carriers.
**Effort:** 1 day (prompt engineering + schema migration).

---

#### T1-2: Add Arrival Notice Document Type

Add `ARRIVAL_NOTICE` to document types with a dedicated prompt extracting:
- `date_avis_arrivee`
- `reference_avis`
- Container list confirmation

Update demurrage calculation to use `date_avis_arrivee` as clock start.
Add status transition: `IN_TRANSIT → ARRIVED`. Remove the hardcoded port
default — missing port should be `null`, not `"Port d'Alger"`.

**Impact:** All demurrage calculations become accurate. Removes last manual
date entry for demurrage tracking.
**Effort:** 1 day.

---

#### T1-3: Demurrage Cost Auto-Calculator

Implement using existing fields + new carrier config table:

```python
def calculate_demurrage(container, carrier_config):
    start    = container.date_debut_surestarie
    end      = container.date_restitution or date.today()
    days     = (end - start).days
    over     = max(0, days - carrier_config.free_days)
    cost_usd = over * carrier_config.rate_usd_per_day
    cost_dzd = cost_usd * (container.taux_de_change or 1)
    return DemurrageCalc(
        days=days, over_days=over,
        cost_usd=cost_usd, cost_dzd=cost_dzd
    )
```

**Impact:** Eliminates manual cost calculation. Directly reduces financial
errors and makes XLSX export columns auto-populated.
**Effort:** 1 day (carrier config table + calculation + API surfacing).

---

### Tier 2 — Core Workflow Improvements (2–4 days each)

#### T2-1: HITL Review Queue for Logistics

After LLM extraction, documents land in `PENDING_REVIEW`. The review page
shows the PDF on the left with extraction highlights, extracted JSON as an
editable form on the right. Operator approves or corrects. Corrections log
to a `corrections` table for the few-shot feedback loop (T3-2).

**Impact:** Prevents silent data corruption. Highest safety improvement.
**Effort:** 3 days.

---

#### T2-2: Exception / Alert Dashboard

A dedicated view for containers/shipments that need attention, by urgency:

- 🔴 Active demurrage (past free period, not restituted)
- 🟠 Approaching demurrage (free period ends within 2 days)
- 🟡 BOL missing (BOOKED > 7 days)
- 🟡 Customs overdue (declaration open > 5 days)
- 🟡 Delivery overdue (past `date_restitution_estimative`)
- 🔵 Review queue (documents pending approval)

**Impact:** Operators stop missing costly deadlines.
**Effort:** 2 days (calculation logic + dashboard widget).

---

#### T2-3: Shipment Thread / Document Timeline

For any TAN/BL number, show all related documents as a chronological timeline
with processing status and key extracted dates. Makes the document-to-shipment
relationship visible and auditable.

**Impact:** Reduces time to audit a shipment's history from minutes to seconds.
**Effort:** 2 days.

---

#### T2-4: Analytics API Endpoints

Add `/api/analytics/kpis` and `/api/analytics/carrier-performance` that
pre-calculate standard logistics KPIs server-side. Power BI reports become
single-endpoint pulls instead of complex joined queries.

**Impact:** Reduces Power BI report build time. Makes the API valuable to
non-technical users without DAX knowledge.
**Effort:** 2 days.

---

### Tier 3 — Quality and Intelligence (3–5 days each)

#### T3-1: Per-Field Confidence Scores

Change extraction output format to include confidence per field:

```json
{
  "bl_number":  { "value": "MSCX1234567", "confidence": 0.97 },
  "eta":        { "value": "2026-04-28",  "confidence": 0.89 },
  "hs_code":    { "value": null,          "confidence": 0.00 }
}
```

Fields below 0.80 confidence are automatically routed to the review queue.
Confidence proxy: ask the LLM to self-rate certainty per field, or use a
second LLM pass agreement check (T3-4).

**Impact:** Focuses human review time on fields that actually need it.
**Effort:** 3 days.

---

#### T3-2: Correction → Few-Shot Improvement Loop

When a reviewer corrects a field, log it with document context to a
`corrections` table. Inject the last 3–5 corrections as few-shot examples
into the next extraction prompt:

```
# Correction log entry:
# Original text: "ETD: 15-Apr-26"
# Extracted:     "2025-04-15"   ← year error
# Corrected:     "2026-04-15"
# → Inject as few-shot example for date parsing
```

**Impact:** Extraction accuracy self-improves on carrier-specific quirks.
**Effort:** 3 days.

---

#### T3-3: Semantic Duplicate Detection via ChromaDB

Use the existing ChromaDB integration to detect semantically similar documents
(same BOL rescanned at lower resolution, or same booking resent with cosmetic
changes). Flag as potential duplicate before processing.

**Impact:** Prevents double-counting of containers and shipments.
**Effort:** 2 days.

---

#### T3-4: Dual-LLM Challenge Pattern

Run extraction with two different Ollama models (e.g., `llama3` + `mistral`).
For critical fields (container numbers, BL numbers, dates) where they
disagree, route to review queue. Where they agree, auto-accept with higher
confidence.

```python
def dual_extract(text, field_names):
    result_a = llm_extract(text, model="llama3")
    result_b = llm_extract(text, model="mistral")
    for field in field_names:
        if result_a[field] != result_b[field]:
            flag_for_review(field, result_a[field], result_b[field])
```

**Impact:** Significantly reduces LLM hallucinations on critical identifiers.
No human input required for cases where models agree.
**Effort:** 2 days.

---

#### T3-5: Docling for Table-Heavy PDFs

Replace or augment PyMuPDF with IBM's Docling library for documents that
contain container tables. Docling achieves ~98% table cell accuracy in 2025
benchmarks — significantly better than pdfminer for multi-container BOLs where
rows are currently being merged.

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result    = converter.convert(pdf_path)
# result.document.export_to_markdown() or .export_to_dict()
# passes clean table-structured text to the LLM
```

**Impact:** Cleaner input text for the LLM → higher extraction accuracy on
multi-container documents. Worth testing against real documents first.
**Effort:** 1 day (integration + testing on real BOL samples).

---

### Tier 4 — Differentiating Features (1 week+ each)

#### T4-1: Email Ingestion Pipeline

Watch a designated IMAP mailbox for PDF attachments. Auto-classify and route
to logistics or travel pipeline based on filename patterns and content. No
manual upload needed for documents arriving by email.

**Stack:** `imaplib` (stdlib) + `email` (stdlib) + existing `core.pipeline.router`.

**Impact:** Eliminates the manual upload step for the majority of documents
that arrive by email from shipping companies.
**Effort:** 3–4 days.

---

#### T4-2: Carrier Rate Card Database

A configuration table storing per-carrier rules:

| Column | Type | Example |
|---|---|---|
| `carrier_name` | TEXT | `MSC` |
| `free_days_20ft` | INT | `7` |
| `free_days_40ft` | INT | `7` |
| `rate_usd_per_day_20ft` | REAL | `25.00` |
| `rate_usd_per_day_40ft` | REAL | `35.00` |
| `detention_rate_usd` | REAL | `20.00` |

Drives T1-3 (auto cost calc) and T2-4 (carrier performance analytics).
Editable via a simple admin UI.

**Impact:** Removes the last major manual data entry requirement.
**Effort:** 2 days.

---

#### T4-3: Mobile-Responsive Operator View

Operators check container status from phones at the port. A minimal read-only
Flask template view showing:
- Active containers with status and demurrage counter
- Alert list (approaching deadlines)
- Container search by number

Read-only is sufficient for field use.

**Impact:** Extends the app to field use. Operators stop needing a laptop at
the port.
**Effort:** 3–4 days.

---

#### T4-4: Packing List Parsing

A new document type `PACKING_LIST` with a prompt extracting:
- Line-item cargo descriptions with per-item weight and CBM
- Package count per container
- HS codes per line item

Links to the container record via container number.

**Impact:** Fills the entire cargo weight / volume / HS code data gap in a
single document type addition.
**Effort:** 3 days.

---

#### T4-5: Power BI Star Schema View

Add a `GET /api/analytics/star-schema` endpoint (or a set of SQLite VIEWs)
that expose the data as a proper star schema (see Section 5.3). Power BI
users connect once and never need to configure joins or write DAX for standard
KPIs.

**Effort:** 2 days.

---

#### T4-6: Freight Invoice Audit Module

A new document type `FREIGHT_INVOICE`. Prompt extracts: invoice number,
carrier, BL reference, container list, charged days, rate per day, currency,
total amount. The module then:

1. Matches the BL reference to an existing shipment
2. Compares invoiced days vs. calculated demurrage days
3. Compares invoiced rate vs. rate card (T4-2)
4. Flags discrepancies: overbilling, wrong rate, wrong container count

**Why this matters:** Industry data shows 2–15% of transport budgets leak via
carrier billing errors. This module converts the app from a tracking tool into
a cost audit tool.
**Effort:** 4–5 days.

---

#### T4-7: Sanctioned Party Screening

Cross-reference extracted shipper/consignee names against:
- OFAC SDN list (US Treasury — free XML, updated daily)
- EU/UN consolidated sanctions lists (free download)

Fully local implementation — the lists are public XML downloads. Flag any
name match (fuzzy, using existing RapidFuzz integration) for manual review
before the shipment record is committed.

**Why this matters:** Algerian import/export operations intersect with
international trade compliance. This is a feature cloud platforms charge
significantly for; BRUNs can do it locally with public data.
**Effort:** 3 days.

---

#### T4-8: AIS Vessel ETA Enrichment

Using extracted voyage number + vessel name, query MarineTraffic or
VesselFinder free-tier API once daily to get current vessel position and
revised ETA. Update the `eta` field in the DB and trigger a re-evaluation
of demurrage estimates.

**Impact:** Turns the app from a document archive into a live tracking tool.
**Effort:** 3–4 days. **Caveat:** requires internet connectivity for the
enrichment step (the core processing remains offline).

---

## 9. Summary: The DO / DON'T Map

```
╔══════════════════════════════════════╦══════════════════════════════════════╗
║  DO — Keep or Build                  ║  DON'T — Avoid                       ║
╠══════════════════════════════════════╬══════════════════════════════════════╣
║  Local Ollama — stay offline         ║  Auto-commit logistics without HITL  ║
║  SHA256 content cache                ║  Cloud dependency for core logic      ║
║  Pydantic schema validation          ║  Hardcoded "Port d'Alger" default     ║
║  Audit log — surface it in the UI    ║  Missing BL / booking ref extraction  ║
║  ChromaDB — use for semantic dedupe  ║  Doc-level confidence only            ║
║  Demurrage fields — add calculator   ║  No alerts despite having the data    ║
║  Huey async queue — keep it          ║  No shipment timeline / thread view   ║
║  WAL mode SQLite — keep it           ║  7-carrier hardcode → "other" rest    ║
║  Shared core/ architecture           ║  No carrier rate card = manual calc   ║
║  Arrival Notice — add it first       ║  Flat table as landing page           ║
║  ISO 6346 checksum — cheapest fix    ║  Single LLM pass, no cross-field val  ║
║  HITL review queue — port to         ║  Per-field confidence = blind spots   ║
║    logistics from travel             ║  Packing list ignored = no weight     ║
║  Pre-calc analytics API              ║  No few-shot correction feedback loop ║
║  Docling for BOL tables              ║  Blocking UI during LLM inference     ║
║  Dual-LLM challenge for critical     ║  No idempotency beyond TAN upsert     ║
║    fields                            ║                                       ║
╚══════════════════════════════════════╩══════════════════════════════════════╝
```

### Quick Win Sprint (1 week, highest ROI)

If only one sprint is available before the next production use:

1. **T1-0** — ISO 6346 checksum validation (2 hours — eliminates a class of silent errors)
2. **T1-1** — Expand LLM prompt: BL number, POL/POD, shipper, consignee, weight, HS code
3. **T1-2** — Add Arrival Notice document type + accurate demurrage clock start
4. **T1-3** — Auto-calculate demurrage cost using carrier rate config
5. **T2-2** — Exception/alert dashboard widget

These five changes fix the most expensive data quality gaps, eliminate the
primary source of missed demurrage deadlines, and give operations a live
exception view — all without touching the core pipeline architecture.

---

## 10. Sources

| Source | Used For |
|---|---|
| [Docsumo: Data Extraction from Bill of Lading](https://www.docsumo.com/blogs/data-extraction/from-bill-of-lading) | BOL field standards |
| [Nanonets: Bill of Lading OCR API](https://nanonets.com/ocr-api/bill-of-lading-ocr) | Field extraction patterns |
| [Rossum: AI Confidence Thresholds](https://knowledge-base.rossum.ai/docs/using-ai-confidence-thresholds-for-automation-in-rossum) | HITL routing thresholds |
| [Instabase: Validating Documents](https://docs.instabase.com/automate/validating-documents) | Cross-field validation patterns |
| [Parseur: HITL Best Practices](https://parseur.com/blog/hitl-best-practices) | Review queue UX |
| [Mavik Labs: HITL Review Queue 2026](https://www.maviklabs.com/blog/human-in-the-loop-review-queue-2026/) | Review queue patterns |
| [Procycons: PDF Extraction Benchmark 2025](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/) | Docling vs Unstructured vs LlamaParse accuracy |
| [Paperless-ngx GitHub](https://github.com/paperless-ngx/paperless-ngx) | Inbox / tagging patterns |
| [Unstract: Open Source Doc Extraction with Ollama](https://unstract.com/blog/open-source-document-data-extraction-with-unstract-deepseek/) | Local LLM patterns |
| [Unstract: Logistics Document Processing 2026](https://unstract.com/blog/document-processing-in-logistics/) | Logistics IDP landscape |
| [PackageX: IDP in Logistics](https://packagex.io/blog/document-processing-in-logistics) | Logistics workflow patterns |
| [Astera: IDP in Logistics and Transportation](https://www.astera.com/type/blog/intelligent-document-processing-in-logistics-and-transportation/) | Feature landscape |
| [SparkCo: AWS Textract vs Azure Doc Intel](https://sparkco.ai/blog/aws-textract-vs-azure-document-intelligence-a-deep-dive) | Platform comparison |
| [Geopostcodes: Power BI Logistics Dashboard](https://www.geopostcodes.com/blog/power-bi-logistics-dashboard/) | KPI standards |
| [Enterprise DNA: Power BI Logistics Sample](https://blog.enterprisedna.co/power-bi-sample-dashboard-using-logistics-data/) | Star schema patterns |
| [Ardem: Freight Audit with Agentic AI](https://ardem.com/bpo/freight-audit-payment-agentic-ai-for-rate-and-invoice-errors/) | Freight invoice audit |
| [Shipamax: Automated Document Processing](https://shipamax.com/logistics-document-processing/) | Arrival notice patterns |
| [Klearstack: OCR in Logistics 2025](https://klearstack.com/ocr-in-logistics) | Logistics IDP overview |
| [Affinda: IDP for Logistics](https://www.affinda.com/blog/intelligent-document-processing-logistics) | Field standards |
| ISO 6346 standard | Container number checksum algorithm |

---

*Document version 2.0 — 2026-04-28*
*Cross-referenced against: `core/schemas/logistics.py`, `modules/logistics/prompts.py`,*
*`core/storage/db.py`, `core/api/server.py`, `modules/logistics/config.py`*
