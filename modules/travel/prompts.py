"""LLM prompt templates for the Travel domain.

Every prompt:
  - Has a strict drift-guard preamble ("Return ONLY a JSON object…")
  - Uses doubled braces `{{` / `}}` so str.format(text=...) doesn't choke
  - Maps to one specific document type so the LLM gets type-matched instructions

Coverage:
  PASSPORT, ID_CARD, VISA, BIRTH_CERT, MARRIAGE_CERT,
  BANK_STATEMENT, COMMERCIAL_REGISTRY, UNKNOWN (auto-detect)

Call init_prompts() exactly once at process startup.
"""
from core.extraction.prompt_registry import register_prompt

# ─── Drift-guard preamble (prepended to every prompt) ────────────────────────
DRIFT_GUARD = """You are a strict identity-document parser.

OUTPUT RULES — NON-NEGOTIABLE:
- Return ONLY a single valid JSON object.
- No markdown, no code fences, no explanation, no trailing commentary.
- If a field is missing or unreadable, use null. Never invent values.
- Dates ALWAYS in ISO format YYYY-MM-DD. If you only see "11-Mar-26", convert to "2026-03-11".
- Names: preserve exact spelling and accents from the document. Do not transliterate.
- Country: prefer ISO 3166-1 alpha-3 code (e.g. "DZA", "FRA", "USA"). Fall back to full English name only if the code is uncertain.

"""


# ─── Schemas per doc type ────────────────────────────────────────────────────

PROMPT_PASSPORT = DRIFT_GUARD + """Read this PASSPORT and return JSON matching this exact schema:

{{
  "document_type": "PASSPORT",
  "document_number": "passport number (typically letters + digits)",
  "full_name": "given names and surname combined",
  "given_names": "first/middle name(s) only",
  "surname": "family name only",
  "dob": "YYYY-MM-DD",
  "place_of_birth": "city, country" ,
  "nationality": "ISO 3166-1 alpha-3 code",
  "gender": "M" or "F",
  "issue_date": "YYYY-MM-DD",
  "expiry_date": "YYYY-MM-DD",
  "issuing_country": "ISO 3166-1 alpha-3 code",
  "issuing_authority": "authority name as printed",
  "mrz_line_1": "first MRZ line, exactly as printed (or null)",
  "mrz_line_2": "second MRZ line, exactly as printed (or null)"
}}

Document text:
---
{text}
---

Return only the JSON:"""


PROMPT_ID_CARD = DRIFT_GUARD + """Read this NATIONAL ID CARD and return JSON matching this exact schema:

{{
  "document_type": "ID_CARD",
  "document_number": "ID number",
  "full_name": "given names and surname combined",
  "given_names": "first/middle name(s) only",
  "surname": "family name only",
  "dob": "YYYY-MM-DD",
  "place_of_birth": "city, country",
  "nationality": "ISO 3166-1 alpha-3 code",
  "gender": "M" or "F",
  "issue_date": "YYYY-MM-DD",
  "expiry_date": "YYYY-MM-DD",
  "issuing_country": "ISO 3166-1 alpha-3 code",
  "issuing_authority": "authority name as printed",
  "father_name": "father's full name (if printed)",
  "mother_name": "mother's full name (if printed)"
}}

Document text:
---
{text}
---

Return only the JSON:"""


PROMPT_VISA = DRIFT_GUARD + """Read this VISA and return JSON matching this exact schema:

{{
  "document_type": "VISA",
  "document_number": "visa number / sticker number",
  "visa_type": "e.g. SCHENGEN, TOURIST, BUSINESS, STUDENT, WORK",
  "full_name": "holder's full name",
  "passport_number": "linked passport number (if printed)",
  "nationality": "holder's nationality (ISO 3166-1 alpha-3)",
  "issuing_country": "ISO 3166-1 alpha-3 code of issuing state",
  "issue_date": "YYYY-MM-DD",
  "expiry_date": "YYYY-MM-DD",
  "valid_from": "YYYY-MM-DD",
  "valid_until": "YYYY-MM-DD",
  "duration_of_stay_days": "integer or null",
  "number_of_entries": "SINGLE or MULTIPLE or DOUBLE",
  "place_of_issue": "city of issuing consulate"
}}

Document text:
---
{text}
---

Return only the JSON:"""


PROMPT_BIRTH_CERT = DRIFT_GUARD + """Read this BIRTH CERTIFICATE and return JSON matching this exact schema:

{{
  "document_type": "BIRTH_CERT",
  "certificate_number": "registry / certificate reference number",
  "full_name": "child's full name as registered",
  "dob": "YYYY-MM-DD",
  "place_of_birth": "city, country",
  "gender": "M or F",
  "father_name": "father's full name",
  "father_nationality": "ISO 3166-1 alpha-3 code",
  "mother_name": "mother's maiden name (if applicable)",
  "mother_nationality": "ISO 3166-1 alpha-3 code",
  "registry_office": "issuing registry / commune",
  "registration_date": "YYYY-MM-DD"
}}

Document text:
---
{text}
---

Return only the JSON:"""


PROMPT_MARRIAGE_CERT = DRIFT_GUARD + """Read this MARRIAGE CERTIFICATE and return JSON matching this exact schema:

{{
  "document_type": "MARRIAGE_CERT",
  "certificate_number": "registry / certificate reference number",
  "marriage_date": "YYYY-MM-DD",
  "marriage_place": "city, country",
  "spouse_1_name": "first spouse's full name",
  "spouse_1_dob": "YYYY-MM-DD",
  "spouse_1_nationality": "ISO 3166-1 alpha-3 code",
  "spouse_2_name": "second spouse's full name",
  "spouse_2_dob": "YYYY-MM-DD",
  "spouse_2_nationality": "ISO 3166-1 alpha-3 code",
  "registry_office": "issuing registry / commune"
}}

Document text:
---
{text}
---

Return only the JSON:"""


PROMPT_BANK_STATEMENT = DRIFT_GUARD + """Read this BANK STATEMENT and return JSON matching this exact schema:

{{
  "document_type": "BANK_STATEMENT",
  "account_holder_name": "full name on the statement",
  "account_number": "IBAN or account # (last 4 digits OK if redacted)",
  "bank_name": "name of the bank",
  "bank_country": "ISO 3166-1 alpha-3 code",
  "currency": "ISO 4217 code (USD, EUR, DZD, MAD, etc.)",
  "statement_period_start": "YYYY-MM-DD",
  "statement_period_end": "YYYY-MM-DD",
  "opening_balance": "numeric or null",
  "closing_balance": "numeric or null",
  "average_balance": "numeric or null",
  "total_credits": "numeric or null",
  "total_debits": "numeric or null"
}}

Document text:
---
{text}
---

Return only the JSON:"""


PROMPT_COMMERCIAL_REGISTRY = DRIFT_GUARD + """Read this COMMERCIAL REGISTRY EXTRACT and return JSON matching this exact schema:

{{
  "document_type": "COMMERCIAL_REGISTRY",
  "registry_number": "company registration number",
  "company_name": "legal name of the company",
  "trade_name": "trading name (if different)",
  "legal_form": "SARL, SA, EURL, sole proprietorship, etc.",
  "incorporation_date": "YYYY-MM-DD",
  "share_capital": "numeric or null",
  "share_capital_currency": "ISO 4217 code",
  "headquarters_address": "registered office address",
  "country": "ISO 3166-1 alpha-3 code",
  "primary_activity": "main business activity",
  "manager_name": "registered manager / director full name",
  "manager_role": "title (e.g. Gerant, Directeur, President)",
  "registry_office": "issuing court / commercial registry"
}}

Document text:
---
{text}
---

Return only the JSON:"""


# Auto-detect fallback — first triages the doc type, then extracts.
PROMPT_UNKNOWN = DRIFT_GUARD + """The document type is unknown. First identify which of these it is:
PASSPORT, ID_CARD, VISA, BIRTH_CERT, MARRIAGE_CERT, BANK_STATEMENT, COMMERCIAL_REGISTRY, OTHER.

Then return JSON with this minimum schema, plus any other fields that are clearly readable:

{{
  "document_type": "one of PASSPORT|ID_CARD|VISA|BIRTH_CERT|MARRIAGE_CERT|BANK_STATEMENT|COMMERCIAL_REGISTRY|OTHER",
  "document_number": "main reference number on the document, or null",
  "full_name": "primary person's full name, or null",
  "dob": "YYYY-MM-DD or null",
  "nationality": "ISO 3166-1 alpha-3 code or null",
  "issue_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "issuing_country": "ISO 3166-1 alpha-3 code or null",
  "raw_summary": "one short sentence describing what this document is"
}}

Document text:
---
{text}
---

Return only the JSON:"""


# ─── Registration ────────────────────────────────────────────────────────────
def init_prompts():
    """Register all travel-domain prompts. Idempotent — safe to call repeatedly."""
    register_prompt("travel", "PASSPORT",            "1.1", PROMPT_PASSPORT)
    register_prompt("travel", "ID_CARD",             "1.1", PROMPT_ID_CARD)
    register_prompt("travel", "VISA",                "1.0", PROMPT_VISA)
    register_prompt("travel", "BIRTH_CERT",          "1.0", PROMPT_BIRTH_CERT)
    register_prompt("travel", "MARRIAGE_CERT",       "1.0", PROMPT_MARRIAGE_CERT)
    register_prompt("travel", "BANK_STATEMENT",      "1.0", PROMPT_BANK_STATEMENT)
    register_prompt("travel", "COMMERCIAL_REGISTRY", "1.0", PROMPT_COMMERCIAL_REGISTRY)
    register_prompt("travel", "UNKNOWN",             "1.0", PROMPT_UNKNOWN)
