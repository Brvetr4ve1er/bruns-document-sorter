import re

def date_normalize(v: str) -> str | None:
    """Normalize various date formats into ISO8601 (YYYY-MM-DD)."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("null", "n/a", "", "none"):
        return None
    
    # Already YYYY-MM-DD?
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
        
    # Try DD-MMM-YY (e.g. "11-Mar-26")
    months = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
              "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
              "nov": "11", "dec": "12"}
    m = re.match(r"^(\d{1,2})[-/\s]([A-Za-z]{3,})[-/\s](\d{2,4})", s)
    if m:
        day, mon, year = m.groups()
        mon_num = months.get(mon.lower()[:3])
        if mon_num:
            if len(year) == 2:
                year = "20" + year
            return f"{year}-{mon_num}-{day.zfill(2)}"
            
    # Try DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
        
    return None
