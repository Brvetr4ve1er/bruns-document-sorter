"""LLM client — calls the configured LLM endpoint and parses the response.

Resilience features:
  - format="json" sent to Ollama (forces valid-JSON output, large drift reduction)
  - JSON-parse retry: if first response isn't valid JSON, ask the LLM again
    with a corrective prompt that includes the bad output
  - Per-module confidence scoring: each domain weighs different fields, so
    a travel passport doesn't get scored against logistics keys
  - Cleans up markdown code fences if the LLM returns them anyway
"""
import json
import requests
from datetime import datetime, timezone
from .result import ExtractionResult
from .prompt_registry import get_prompt


# Per-module "important fields" used to compute a confidence score.
# A field is "filled" if it's present and not null/empty/empty-list/empty-dict.
_CONFIDENCE_FIELDS = {
    "logistics": ["tan_number", "vessel_name", "etd", "eta",
                  "shipping_company", "containers"],
    "travel":    ["document_type", "document_number", "full_name",
                  "dob", "nationality", "expiry_date"],
}


def _strip_code_fences(s: str) -> str:
    """Remove ```json ... ``` wrappers if the LLM ignored the no-markdown rule."""
    s = s.strip()
    if s.startswith("```"):
        parts = s.split("```", 2)
        body = parts[1] if len(parts) > 1 else s
        body = body.strip()
        if body.startswith(("json", "JSON")):
            body = body[4:].strip()
        if body.endswith("```"):
            body = body[:-3].strip()
        return body
    return s


def _confidence(module: str, data: dict) -> float:
    fields = _CONFIDENCE_FIELDS.get(module)
    if not fields:
        # Unknown module — fall back to "any field is good"
        fields = list(data.keys()) or [""]
    if not fields:
        return 0.0
    filled = sum(1 for f in fields if data.get(f) not in (None, "", [], {}))
    return round(filled / len(fields), 3)


class LLMClient:
    """Generic Ollama-style /api/generate client.

    Future cloud-provider variants (OpenAI, Anthropic) should subclass and
    override `_post_generate` only.
    """

    def __init__(self, ollama_url: str, model: str, timeout: int = 120,
                 temperature: float = 0.1, num_ctx: int = 8192):
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.num_ctx = num_ctx

    def _post_generate(self, prompt: str, force_json: bool = True) -> str:
        """POST to Ollama and return raw response string. Raises on transport error."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }
        if force_json:
            # Ollama-supported JSON-mode hint. Drastically reduces drift.
            payload["format"] = "json"

        r = requests.post(self.ollama_url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("response", "")

    def extract(self, text: str, module: str, doc_type: str = "UNKNOWN") -> ExtractionResult:
        prompt_version, template = get_prompt(module, doc_type)
        prompt = template.format(text=text)

        # ── Attempt 1: format=json + drift-guard prompt ──
        try:
            raw = self._post_generate(prompt, force_json=True)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"LLM request failed: {e}")

        clean = _strip_code_fences(raw)
        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            # ── Attempt 2: corrective retry ──
            retry_prompt = (
                "Your previous response was not valid JSON. "
                "You MUST return ONLY a single valid JSON object — no prose, "
                "no markdown, no code fences. The previous response was:\n\n"
                f"{raw[:2000]}\n\n"
                "Now return the same data as a clean JSON object:"
            )
            try:
                raw_retry = self._post_generate(retry_prompt, force_json=True)
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"LLM retry request failed: {e}")
            clean = _strip_code_fences(raw_retry)
            try:
                data = json.loads(clean)
                raw = raw_retry
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Failed to parse LLM JSON response after retry: {e}\n"
                    f"Original: {raw[:500]}\nRetry: {raw_retry[:500]}"
                )

        return ExtractionResult(
            data=data,
            confidence=_confidence(module, data),
            prompt_version=prompt_version,
            model=self.model,
            timestamp=datetime.now(timezone.utc),
            raw_response=raw,
            doc_type=doc_type,
        )
