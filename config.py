import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# When running as a PyInstaller EXE, use the directory next to the .exe
# (so data is writable and persists between runs).
# bruns_launcher.py sets BRUNS_DATA_DIR before importing config.
_data_root = os.environ.get("BRUNS_DATA_DIR") or os.path.join(BASE_DIR, "data")

INPUT_DIR = os.path.join(_data_root, "input")
LOGS_DIR  = os.path.join(_data_root, "logs")
DB_PATH   = os.path.join(_data_root, "logistics.db")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
OLLAMA_TIMEOUT = 180

# Target xlsx column order (matches "Containers actifs" sheet exactly)
XLSX_COLUMNS = [
    "(Ne pas modifier) Container",
    "(Ne pas modifier) Somme de contrôle de la ligne",
    "(Ne pas modifier) Modifié le",
    "N° Container",
    "N° TAN",
    "Item (N° TAN) (Commande)",
    "Compagnie maritime",
    "Port  (N° TAN) (Commande)",
    "Transitaire (N° TAN) (Commande)",
    "Date shipment",
    "Date accostage",
    "Statut Container",
    "Container size",
    "Date livraison",
    "Site livraison",
    "Date dépotement",
    "Modifié par",
    "Modifié le",
    "Date début Surestarie",
    "Date restitution estimative",
    "Nbr jours surestarie estimés",
    "Coût Surestaries Estimé (USD)",
    "Nbr jours perdu en douane",
    "Coût Surestaries Estimé (DZD)",
    "Nbr jours restants pour surestarie",
    "Nbr jours surestarie",
    "Coût Surestaries Réel (USD)",
    "Coût Surestaries Réel (DZD)",
    "Date réstitution",
    "Réstitué par (Camion)",
    "Réstitué par (Chauffeur)",
    "Centre de réstitution",
    "Check dépotement- restitution",
    "Check livraison-dépotement",
    "Check livraison-restitution",
    "Check Shipment-Accostage",
    "Créé le",
    "Créé par",
    "Check avis d'arrivée-restitution",
    "Taux de change*",
    "Livré par (Camion)",
    "Livré par (Chauffeur)",
    "Montant facturé (check)",
    "Nbr jour surestarie Facturé",
    "Montant facturé (DA)",
    "N° Facture compagnie maritime",
    "Commentaire",
    "Date declaration douane",
    "Date liberation douane",
]

LLM_PROMPT_TEMPLATE = """You are a strict logistics document parser. Read the document below and return ONLY valid JSON — no markdown, no explanation.

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
