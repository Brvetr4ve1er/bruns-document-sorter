"""LLM prompt templates for the Logistics domain.

One comprehensive prompt that captures EVERY field present across all
real-world shipping document types: Booking Confirmations, Departure
Notices, Bills of Lading, Arrival Notices, and Customs Declarations.

The schema is intentionally wide and nested. Fields not present in a given
document MUST be returned as null — never invent values. The downstream UI
shows whatever fields are present, so coverage > parsimony.
"""
from core.extraction.prompt_registry import register_prompt

LLM_PROMPT_TEMPLATE = """You are a strict shipping-document parser.

OUTPUT RULES — NON-NEGOTIABLE:
- Return ONLY a single valid JSON object. No markdown, no code fences, no commentary.
- If a field is missing or unreadable, use null. Never invent values.
- Dates ALWAYS in ISO format YYYY-MM-DD. Convert "11-Mar-26" -> "2026-03-11", "31 JAN 2026" -> "2026-01-31".
- Times: keep as separate ISO fields (e.g. "etd_time": "17:00") if useful.
- Numbers: numeric (15288.0, not "15288 KG") — strip units. Put units in a sibling _unit field if helpful.
- Container numbers: 4 letters + 7 digits (e.g. CMAU6761948). Strip whitespace.
- TAN: normalize to "TAN/XXXX/YYYY" form.

Capture EVERY field present in the document. The schema below shows the
canonical keys — but if the doc has additional fields not listed, include
them in `additional_fields` as an object. Do not drop information.

JSON SCHEMA:

{{
  "document_type": "BOOKING" | "DEPARTURE" | "BILL_OF_LADING" | "ARRIVAL_NOTICE" | "INVOICE" | "CUSTOMS_DECLARATION" | "OTHER",

  "_": "──── Reference numbers ────",
  "tan_number": "TAN/XXXX/YYYY (CNE/CNR/PON/MARKS reference)",
  "shipment_id": "internal shipment ID (e.g. S05970780)",
  "consol_id": "consolidation ID (e.g. C03599273)",
  "tracking_number": "tracking ref",
  "booking_number": "carrier booking # (e.g. ANT1989846)",
  "carrier_booking_reference": "another carrier-side ref",
  "house_bl": "house bill of lading number",
  "ocean_bl": "ocean bill of lading number",
  "bl_number": "if this IS a bill of lading, its number (e.g. CFA0869742)",
  "customer_reference": "customer-side ref",
  "voyage_number": "vessel voyage code (e.g. 0WM5AW1MA)",
  "service_name": "carrier service code (e.g. ALGA)",

  "_": "──── Parties ────",
  "shipper": {{
    "name": "company name",
    "address": "full multi-line address",
    "country": "country (full name or ISO)",
    "vat": "VAT or fiscal ID",
    "contact": "person name",
    "email": "contact email",
    "phone": "phone number"
  }},
  "consignee": {{
    "name": "...", "address": "...", "country": "...",
    "vat": null, "nif": "Algerian fiscal ID if present",
    "contact": null
  }},
  "notify_party": {{
    "name": "...", "address": "...", "country": "..."
  }},
  "transitaire": "freight forwarder name (e.g. CEVA, Orient Transport, Transit Messaoudi)",
  "carrier": "shipping company — normalize: CMA-CGM | MSC | Ignazio Messina | Pyramid Lines | Maersk | Hapag-Lloyd | COSCO | Evergreen | other",
  "customs_broker": "customs agent name if listed",

  "_": "──── Routing ────",
  "port_of_loading": {{
    "code": "ESVLC | BEANR | NLRTM | etc.",
    "name": "Valencia",
    "country": "Spain"
  }},
  "port_of_discharge": {{
    "code": "DZALG", "name": "Alger (Algiers)", "country": "Algeria"
  }},
  "place_of_receipt": "if different from POL",
  "final_destination": "if different from POD",
  "transhipment_ports": ["array of intermediate ports"],

  "_": "──── Vessel / dates ────",
  "vessel_name": "vessel name (uppercase) (e.g. CMA CGM ALEXANDER VON HUMBOLDT)",
  "imo_number": "Lloyds/IMO number",
  "etd": "YYYY-MM-DD",
  "etd_time": "HH:MM if printed",
  "eta": "YYYY-MM-DD",
  "eta_time": "HH:MM if printed",
  "atd": "actual time of departure (YYYY-MM-DD)",
  "ata": "actual time of arrival (YYYY-MM-DD)",
  "transit_days": "integer, if printed",
  "issue_date": "place_of_issue date (for BL)",
  "place_of_issue": "place of issue (e.g. CAIRO)",

  "_": "──── Cargo summary ────",
  "item_description": "short cargo description (e.g. 'Canette Al HEINEKEN 330ml STD')",
  "commodity": "GEN GENERAL / specific name",
  "hs_code": "harmonized code (e.g. 761290)",
  "undg": "UN dangerous goods code or null",
  "temp_controlled": true | false | null,
  "incoterm": "CFR / FOB / CIF / EXW / etc.",
  "freight_terms": "Prepaid / Collect / etc.",
  "place_of_payment": "...",
  "total_packages": "integer count",
  "package_type": "PLT | CTN | DRM | etc.",
  "total_gross_weight_kg": "numeric, total across all containers",
  "total_volume_m3": "numeric",

  "_": "──── Containers (one entry per physical box) ────",
  "containers": [
    {{
      "container_number": "AAAU1234567",
      "size": "40 feet" | "20 feet" | "40 feet refrigerated" | "20 feet refrigerated" | "40 feet HC",
      "size_raw": "40HC | 20'ST | 40HQ — exact value as printed",
      "seal_number": "seal string or null",
      "package_count": 21,
      "package_type": "PLT",
      "gross_weight_kg": 15288.0,
      "tare_weight_kg": 3700,
      "net_weight_kg": 14553,
      "volume_m3": 40.0,
      "hs_code": "701090",
      "goods_description": "250ML K2 EMPTY GLASS GREEN",
      "quantity_units": 88200
    }}
  ],

  "_": "──── Cut-off times (booking docs) ────",
  "cut_offs": {{
    "port_cut_off": "YYYY-MM-DD",
    "si_cut_off": "YYYY-MM-DD",
    "vgm_cut_off": "YYYY-MM-DD",
    "customs_cut_off": "YYYY-MM-DD",
    "earliest_receiving": "YYYY-MM-DD"
  }},
  "empty_pickup_location": "...",
  "full_return_location": "...",

  "_": "──── Demurrage terms (often listed in booking confirmations) ────",
  "demurrage_terms": "free text (e.g. 'First 15 days free. 16th-45th day USD 20/day for 20ft, USD 40/day for 40ft.')",
  "free_days": "integer (number of free demurrage days)",

  "_": "──── Anything else found in the document ────",
  "additional_fields": {{
    "any_extra_key_value_pairs_not_in_schema": "..."
  }}
}}

NORMALIZATION RULES:
- carrier: "CMA CGM" / "CMA-CGM" / "CMACGM" -> "CMA-CGM";
            "MEDITERRANEAN SHIPPING" / "MSC" -> "MSC";
            "IGNAZIO MESSINA" -> "Ignazio Messina";
            "MAERSK LINE" / "MAERSK" -> "Maersk";
            "HAPAG LLOYD" / "HAPAG-LLOYD" -> "Hapag-Lloyd"
- size: "40 HIGH CUBE" / "40HC" / "40HQ" / "40 GP" / "40'ST" / "40' DRY" -> "40 feet"
        "20 HIGH CUBE" / "20HC" / "20'ST" / "20' DRY" / "20 GP"           -> "20 feet"
        "40 RF" / "40 REEF" / "40 REFRIGERATED"                            -> "40 feet refrigerated"
        "20 RF" / "20 REEF" / "20 REFRIGERATED"                            -> "20 feet refrigerated"
- document_type:
    "Booking Confirmation" / "BKG CONFIRMATION" -> "BOOKING"
    "Departure Notice" / "Sea Departure Notice" -> "DEPARTURE"
    "Bill of Lading" / "BL" / "OCEAN BL" -> "BILL_OF_LADING"
    "Arrival Notice" / "Avis d'arrivée" -> "ARRIVAL_NOTICE"
    "Invoice" / "Facture" -> "INVOICE"
    "Customs Declaration" / "Déclaration en douane" / "DD" -> "CUSTOMS_DECLARATION"
- tan_number: look in CNE:, CNR:, PON:, MARKS AND NUMBERS, or header. Format: TAN/XXXX/YYYY
- One container entry per physical box. Do not merge multiple containers into one row.
- If the same field appears multiple times, take the most reliable / final value.

Document text:
---
{text}
---

Return only the JSON:"""

def init_prompts():
    register_prompt(
        module="logistics",
        doc_type="UNKNOWN",
        version="2.0",   # bumped — comprehensive schema
        template=LLM_PROMPT_TEMPLATE,
    )
