from rapidfuzz import fuzz
from typing import Optional

def score_names(name_a: str, name_b: str) -> float:
    """Returns a score between 0.0 and 1.0."""
    if not name_a or not name_b:
        return 0.0
    # Use token set ratio to handle middle names and out-of-order words
    return fuzz.token_set_ratio(name_a.upper(), name_b.upper()) / 100.0

def score_dob(dob_a: Optional[str], dob_b: Optional[str]) -> float:
    """Exact match on DOB is a strong indicator."""
    if not dob_a or not dob_b:
        return 0.5  # Neutral if missing
    return 1.0 if dob_a == dob_b else 0.0

def score_nationality(nat_a: Optional[str], nat_b: Optional[str]) -> float:
    if not nat_a or not nat_b:
        return 0.5
    return 1.0 if nat_a.upper() == nat_b.upper() else 0.0
