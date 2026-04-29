from core.extraction.prompt_registry import register_prompt

LLM_PROMPT_TEMPLATE = """You are a strict logistics document parser.

OUTPUT RULES — NON-NEGOTIABLE:
- Return ONLY a single valid JSON object.
- No markdown, no code fences, no explanation, no trailing commentary.
- If a field is missing or unreadable, use null. Never invent values.
- Dates ALWAYS in ISO format YYYY-MM-DD. Convert "11-Mar-26" → "2026-03-11".

Required JSON structure:

Required JSON structure:
{{
  "document_type": "BOOKING" | "DEPARTURE" | "BILL_OF_LADING",
  "tan_number": "TAN/XXXX/YYYY or null",
  "item_description": "cargo / goods description (short)",
  "shipping_company": "CMA-CGM" | "MSC" | "Ignazio Messina" | "Pyramid Lines" | "Maersk" | "Hapag-Lloyd" | "other",
  "port": "Port d'Alger",
  "transitaire": "freight forwarder name or null (e.g. CEVA, Orient Transport, Transit Messaoudi)",
  "vessel_name": "vessel name (uppercase)",
  "etd": "YYYY-MM-DD or null",
  "eta": "YYYY-MM-DD or null",
  "containers": [
    {{
      "container_number": "AAAU1234567 (4 letters + 7 digits)",
      "size": "40 feet" | "20 feet" | "40 feet refrigerated" | "20 feet refrigerated",
      "seal_number": "seal string or null"
    }}
  ]
}}

RULES:
- document_type: "BOOKING" if title contains "Booking Confirmation"; "DEPARTURE" if "Departure Notice"; "BILL_OF_LADING" if "Bill of Lading" or "BL".
- tan_number: Look for TAN/XXXX/YYYY in CNE:, CNR:, PON:, MARKS AND NUMBERS, or header fields.
- shipping_company: normalize — "CMA CGM" or "CMA-CGM" → "CMA-CGM"; "MEDITERRANEAN SHIPPING" → "MSC"; "IGNAZIO MESSINA" → "Ignazio Messina".
- Size normalization:
    40' HIGH CUBE, 40HC, 40HQ, 40 GP, 40'ST, 40' DRY  →  "40 feet"
    20' HIGH CUBE, 20HC, 20 GP, 20'ST, 20' DRY        →  "20 feet"
    40 RF, 40 REEF, 40 REF                             →  "40 feet refrigerated"
    20 RF, 20 REEF, 20 REF                             →  "20 feet refrigerated"
- Dates: ALWAYS convert to YYYY-MM-DD. "11-Mar-26" → "2026-03-11". "18-Mar-26" → "2026-03-18".
- etd = "Actual Departure" or "ETD" or "Date shipment".
- eta = "Estimated Arrival" or "ETA" or "Date accostage".
- Return ONE entry per container. Do not merge or group.
- If a field is missing, use null (not empty string).

Document text:
---
{text}
---

Return only the JSON:"""

def init_prompts():
    register_prompt(
        module="logistics",
        doc_type="UNKNOWN",
        version="1.0",
        template=LLM_PROMPT_TEMPLATE
    )
