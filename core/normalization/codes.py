import re

ALLOWED_CONTAINER_SIZES = {"40 feet", "20 feet", "40 feet refrigerated", "20 feet refrigerated"}

def container_number(v: str) -> str:
    """Normalize container number."""
    if not v:
        return ""
    v = str(v).strip().upper().replace(" ", "")
    # Returns raw string even if invalid so audit logs can catch the raw text
    return v

def normalize_size(v: str) -> str:
    """Normalize container size."""
    if not v:
        return "40 feet"
    s = str(v).strip().upper()
    reefer = any(kw in s for kw in ["RF", "REEF", "REF ", "REEFER"])
    is_40 = "40" in s
    is_20 = "20" in s
    if is_40 and reefer:
        return "40 feet refrigerated"
    if is_20 and reefer:
        return "20 feet refrigerated"
    if is_40:
        return "40 feet"
    if is_20:
        return "20 feet"
    return "40 feet"  # safest default

def normalize_seal(v: str) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("null", "n/a", "tba", "none", "-"):
        return None
    return s

def shipping_co(v: str) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    low = s.lower()
    if "cma" in low:
        return "CMA-CGM"
    if "msc" in low or "mediterranean shipping" in low:
        return "MSC"
    if "messina" in low or "ignazio" in low:
        return "Ignazio Messina"
    if "pyramid" in low:
        return "Pyramid Lines"
    if "maersk" in low:
        return "Maersk"
    if "hapag" in low:
        return "Hapag-Lloyd"
    if "cosco" in low:
        return "COSCO"
    if "evergreen" in low:
        return "Evergreen"
    return s or None

def normalize_tan(v: str) -> str | None:
    if v is None:
        return None
    s = str(v).strip().upper().replace(" ", "")
    if not s or s in ("NULL", "N/A"):
        return None
    # Try to match TAN/NNNN/YYYY format
    m = re.search(r"TAN[/\-]?(\d{3,4})[/\-]?(\d{4})", s)
    if m:
        return f"TAN/{m.group(1).zfill(4)}/{m.group(2)}"
    return s

def clean_str(v: str) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("null", "n/a", "none", "") else None
