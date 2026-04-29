import unicodedata
import re

def accent_strip(text: str) -> str:
    """Remove accents and diacritics from text."""
    if not text:
        return ""
    text = str(text)
    # NFD decomposes characters into base + accent, then filter out accents
    return "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def name_normalize(name: str) -> str:
    """Normalize a person's name: uppercase, stripped accents, clean whitespace."""
    if not name:
        return ""
    name = accent_strip(name).upper()
    # Replace non-word characters (except spaces/hyphens) with space
    name = re.sub(r'[^A-Z0-9\-\s]', ' ', name)
    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name
