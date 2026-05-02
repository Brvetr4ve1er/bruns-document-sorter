"""Bounding-box highlight colors for the annotated PDF view (P2-A).

Maps an extracted-field dotted path (e.g. "containers[0].seal_number") to a
PyMuPDF-compatible RGB tuple where each channel is a float in [0.0, 1.0].

The mapping is heuristic: substring matches against well-known concepts.
Adding a new category is one line in `BBOX_COLORS` plus one line in
`field_color()`.

Public API:
    BBOX_COLORS  : dict[str, tuple[float, float, float]]
    field_color(path: str) -> tuple[float, float, float]
"""
from __future__ import annotations

# Channels are floats in [0.0, 1.0] per PyMuPDF's add_highlight_annot API.
BBOX_COLORS: dict[str, tuple[float, float, float]] = {
    "tan":        (0.2, 0.5, 1.0),   # blue   — TAN reference
    "container":  (0.1, 0.8, 0.3),   # green  — container numbers
    "vessel":     (1.0, 0.6, 0.0),   # orange — vessel name
    "date":       (0.9, 0.9, 0.1),   # yellow — ETD/ETA/dates
    "carrier":    (0.8, 0.2, 0.8),   # purple — shipping company
    "port":       (0.2, 0.8, 0.8),   # cyan   — ports
    "default":    (1.0, 0.8, 0.0),   # amber  — fallback
}


def field_color(path: str) -> tuple[float, float, float]:
    """Return an RGB highlight colour for a given field path.

    First-match wins, so order the checks from most-specific to most-generic.
    """
    p = path.lower()
    if "tan" in p:
        return BBOX_COLORS["tan"]
    if "container_number" in p:
        return BBOX_COLORS["container"]
    if "vessel" in p or "navire" in p:
        return BBOX_COLORS["vessel"]
    if "date" in p or "etd" in p or "eta" in p:
        return BBOX_COLORS["date"]
    if "carrier" in p or "compagnie" in p:
        return BBOX_COLORS["carrier"]
    if "port" in p:
        return BBOX_COLORS["port"]
    return BBOX_COLORS["default"]
