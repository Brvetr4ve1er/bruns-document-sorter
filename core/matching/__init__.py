from .engine import resolve_identity, MatchResult, calculate_similarity
from .scorers import score_names, score_dob, score_nationality
from .thresholds import AUTO_MERGE_THRESHOLD, REVIEW_THRESHOLD

__all__ = [
    "resolve_identity",
    "MatchResult",
    "calculate_similarity",
    "score_names",
    "score_dob",
    "score_nationality",
    "AUTO_MERGE_THRESHOLD",
    "REVIEW_THRESHOLD"
]
