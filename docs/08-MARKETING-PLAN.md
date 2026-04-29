# 08 — Marketing Plan

This is a working marketing plan, not a slide deck. Every section is
opinionated and meant to be edited as evidence comes in. Treat as a hypothesis
to test, not a strategy to execute blindly.

## Positioning

**One-line positioning statement:**

> The local document-extraction engine for logistics and immigration teams
> who can't (or won't) send their PDFs to the cloud.

**Why this positioning works:**
- It claims a category ("local document-extraction engine") that has weak
  competition.
- It names two concrete verticals — credibility, not generic vapor.
- The negative ("can't or won't send to cloud") qualifies in the buyers who
  will say yes and disqualifies the ones who will haggle on price vs cloud
  AI.

**What we are NOT positioning as:**
- "AI for logistics" — too crowded, lumps us with TMS vendors.
- "OCR software" — undersells the validation, matching, and BI layers.
- "Document AI" — a Google/Microsoft category we cannot win.
- "ChatGPT for shipping" — no.

## Category framing

We are creating a small new category: **"on-prem document intelligence
appliance."** Nobody in our target geography is selling against us on
positioning yet, so we own the category framing if we move first.

The frame: it is not software, it is an *appliance*. Install once on a
laptop, runs forever, no subscription. This framing helps with:
- Procurement (one-time CAPEX vs SaaS OPEX preferred in many MENA finance
  departments).
- Trust (physical/local thing > something running in someone's data center).
- Pricing (perpetual license + maintenance vs per-seat SaaS).

## Ideal Customer Profile (ICP)

### Primary ICP — Algerian freight forwarder

| Attribute | Value |
|-----------|-------|
| Industry | Freight forwarding, customs brokerage |
| Headcount | 5–50 |
| Geography | Algeria (Algiers, Oran, Annaba, Bejaia) |
| Language | French primary, Arabic secondary |
| Tech stack | Excel, Power BI, on-prem Windows |
| Containers/month | 50–500 |
| Decision maker | Owner-operator or operations director |
| Tech sophistication | Low to medium — they install software, not write it |
| Trigger event | Latest demurrage fine, or a clerk just quit |
| Budget | €1,000–€5,000 one-time, or €100–€500/mo |

### Secondary ICP — Visa consultancy

| Attribute | Value |
|-----------|-------|
| Industry | Immigration consultancy |
| Headcount | 2–10 |
| Geography | Algeria, Tunisia, Morocco, France (Maghrebi diaspora consultancies) |
| Cases/month | 20–100 |
| Decision maker | Owner |
| Tech sophistication | Low |
| Trigger event | Hiring 2nd or 3rd consultant — process must scale |
| Budget | €500–€2,000 one-time |

### Disqualification criteria (do not pursue)

- US-based companies (will demand SaaS).
- Anyone asking "do you have a SOC 2 report?" on first call (out of scope).
- Anyone with <10 docs/month (manual is cheaper for them).
- Companies with existing TMS/CRM that already handles this (we'd be a
  feature for them, not a product).

## Pricing strategy

Three options, in order of seller preference:

### Option A — Perpetual license + annual maintenance (recommended)

| Tier | Price | What's included |
|------|-------|-----------------|
| **Operator** | €1,500 one-time + €300/yr maintenance | Logistics OR Travel module, single install, email support |
| **Pro** | €3,000 one-time + €600/yr maintenance | Both modules, single install, BI bridge, priority support |
| **Site license** | €8,000 one-time + €1,500/yr maintenance | Unlimited installs at one site, custom domain plugin, on-site setup day |

Maintenance includes: bug fixes, prompt updates as carriers change formats,
LLM model upgrades, schema migrations.

### Option B — Subscription

| Tier | Price/mo |
|------|----------|
| Operator | €99 |
| Pro | €199 |
| Site | €499 |

Use when CAPEX is impossible or the customer wants a trial period.

### Option C — Per-document

€0.05–€0.10 per processed document, billed monthly. Use only when the
customer demands it. We don't promote this because it conflicts with the
"appliance" framing.

### What we don't charge for

- Updates to carrier prompts (constant — happens 5–10 times/year)
- Bug fixes
- LLM model swaps
- Schema migrations within a major version

This is a moat: a competitor cannot match support velocity from a
vendor-with-a-license model unless they're also tiny and nimble.

## Go-to-market motion

### Phase 1 (months 1–3) — Founder-led sales, 5–10 customers

- Direct outreach to 50 freight forwarders in Algiers via LinkedIn + cold
  email in French.
- Live demo by founder using customer's actual PDF (always ask: "send me one
  of your real documents in advance, I'll prep it").
- Free 30-day pilot. Install on their laptop, set up Power BI together.
- Conversion target: 20% of demos → pilot, 50% of pilots → paid.

**Win criteria for Phase 1:**
- ≥ 5 paying customers.
- ≥ 1 case study with named customer logo and ROI number.
- ≥ 3 testimonials suitable for the website.

### Phase 2 (months 4–9) — Channel + content, 25–50 customers

- Partnership with 1–2 Algerian Power BI consultancies (revenue share or
  referral fee).
- Bi-weekly French-language content on LinkedIn: "How to compute demurrage
  exposure in Power BI", "Reading a CMA-CGM bill of lading", "Why your
  Excel tracker is leaking money".
- Conference presence at Algerian logistics events (LogiMag, Salon
  Maritime).
- Reseller agreement with one IT services firm in Algiers for site-license
  installs.

**Win criteria for Phase 2:**
- 1+ active channel partner producing 30%+ of pipeline.
- Content pipeline producing 10+ qualified inbound leads/month.
- ≥ 25 paying customers.

### Phase 3 (months 10–18) — Vertical expansion + adjacent geography

- Launch the Travel module's identity-resolution as a separate marketed
  product (different buyer = different funnel).
- Expand to Tunisia and Morocco (same Francophone, same data sovereignty
  posture).
- Pilot the healthcare or legal domain with one anchor customer.

**Win criteria for Phase 3:**
- 75–100 paying customers across both modules.
- One adjacent vertical with ≥ 5 customers (proof point for "platform").
- One non-Algeria deployment.

## Channels

| Channel | Phase | Why it works for our ICP |
|---------|-------|--------------------------|
| LinkedIn (French content) | 1, 2 | Decision makers in MENA logistics live on LinkedIn |
| Direct cold email (FR) | 1 | Standard for B2B in this market; founder credibility per email |
| Local logistics events | 2 | Trust is built face-to-face; one good event = quarter of pipeline |
| Power BI consultancy partnerships | 2 | They already sell to our buyer |
| WhatsApp Business | 1, 2 | Primary B2B channel in Algeria; have a number on the website |
| Customer referrals | 2, 3 | The community is small; one happy customer ≈ 3 leads |
| Paid search (Google FR) | Skip | High CPC, low conversion in this segment |
| Cold calling | Skip | Founder-time better spent on demos |
| Trade publications | 3 | Once we have 25+ customers, write the case studies |

## Content calendar (sample — first quarter)

Frequency: 1 LinkedIn post/week, 1 long-form article/month, 1 video/month.

| Week | Topic | Format |
|------|-------|--------|
| 1 | "5 façons dont les transitaires algériens perdent de l'argent en surestaries" | LinkedIn post + long-form |
| 2 | "Comment lire un Bill of Lading CMA-CGM (et ce qu'il vous coûte de l'oublier)" | LinkedIn post |
| 3 | "Vidéo : importer 50 PDFs en 30 secondes vers Power BI" | YouTube video + LinkedIn |
| 4 | "Étude de cas : [Customer X] économise 8h/semaine de saisie" | Long-form |
| 5 | "Ollama + Pydantic : comment fonctionne BRUNs sous le capot" | Technical post (LinkedIn) — recruits dev mindshare |
| ... | ... | ... |

## Competitive landscape

| Competitor | Their angle | Our advantage |
|-----------|-------------|---------------|
| **AWS Textract / Azure Form Recognizer** | Cloud OCR APIs | Local install, no per-doc cost, no data egress |
| **CargoWise / Magaya** (TMS) | Full freight management suite | We're 1/100th the price, install in an hour, plug into existing Excel |
| **Custom Power BI consultancies** | Bespoke reports | We do the data plumbing they don't want to build |
| **Excel + clerk** (status quo) | Cheap, familiar | We are 10× faster, no typos, BI-native |
| **Generic "AI for logistics" SaaS** | Brand recognition | We are local, French-language, niche-specialist |

The status quo (Excel + clerk) is the real competitor. Beating cloud
products is easy positioning; beating "we already do this with a clerk" is
the actual sales conversation.

**Counter-argument scripts:**

> "We already have a clerk doing this for €600/month."
> *"For €1,500 once you keep the clerk for higher-value work and stop paying
> demurrage. Show me last quarter's demurrage invoices and I'll quantify
> the ROI."*

> "Why not just use ChatGPT?"
> *"ChatGPT can't connect to your Power BI, doesn't validate the data, and
> sends every shipment to OpenAI. Three reasons that disqualify it before we
> even compare accuracy."*

> "Why not Azure Form Recognizer? Microsoft is trustworthy."
> *"Microsoft is trustworthy and €0.10 per page. Your 5,000 pages/month is
> €500/month forever. BRUNs is €1,500 once."*

## Brand and visual identity

The synthwave / DaisyUI direction in the Phase-1 UI migration is not a
mistake — it is a positioning choice:

- Logistics software UI is universally beige. Standing out visually is free
  marketing.
- "Operator terminal" aesthetic implies competence and seriousness — opposite
  of "AI startup landing page slop."
- It looks handmade, not template-built. Buyers in this market value
  personal touch.

Brand colors (proposed):
- Background: `#0D0D0D` (near-black)
- Primary accent: `#FF006E` (hot magenta — synthwave canonical)
- Secondary accent: `#00F5FF` (electric cyan)
- Success: `#AAFF00` (acid green)
- Body text: `#E6E9F2` (soft white)

Tone of voice: blunt, technical, French. No emoji except sparingly (✓, ⚠).
No "🚀" anywhere. We are not a Silicon Valley pitch deck.

## Marketing metrics to track

| Metric | Why it matters | Target by month 6 |
|--------|----------------|-------------------|
| Inbound demo requests/month | Pipeline health | ≥ 10 |
| Demo → pilot conversion | Demo quality | ≥ 30% |
| Pilot → paid conversion | Product fit | ≥ 50% |
| ARR | Revenue | €30k–€80k |
| Customer count | Logo count | 25–40 |
| Referral rate | Customer love | ≥ 1 referral per 5 customers |
| LinkedIn follower count (FR) | Awareness | ≥ 1,000 |
| Avg implementation time | Onboarding pain | ≤ 4 hours |

## Why this plan can fail (red team)

Honest failure modes to monitor:

1. **Algerian freight forwarders won't pay €1,500 upfront.** Mitigation:
   subscription option exists; pilot before payment.
2. **The single-developer support load capsizes during scale.** Mitigation:
   reseller channel, async support via documentation, video onboarding.
3. **A large vendor (CargoWise) ships a competing local-install lightweight
   product.** Mitigation: we win on French-language localization, Maghreb
   specificity, and price for at least 18–24 months.
4. **Ollama + llama3 accuracy plateaus and customers ask for cloud LLM
   fallback.** Mitigation: design the LLM client as a swappable interface
   (already done in `core/extraction/llm_client.py`); fallback to Claude or
   GPT-4 as a paid premium tier.
5. **The Travel use case requires regulatory certifications we don't have.**
   Mitigation: don't pursue immigration before logistics has product-market
   fit; use logistics revenue to fund any required certs.
