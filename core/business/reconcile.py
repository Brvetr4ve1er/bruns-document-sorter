"""Cross-document reconciliation + JSON diffing utilities.

Two responsibilities, both pure-data:

1. `reconcile_siblings` — given a TAN and the current document's extracted
   JSON, find every other logistics document sharing that TAN and flag
   discrepancies in vessel name, ETD, ETA, container set, and gross weight
   (±5% tolerance). Used by the /logistics/documents/<id> page to surface
   data inconsistencies BEFORE the operator commits a Power BI export.

2. `flatten_diff` + `compute_diff` — turn nested LLM JSON into a flat
   {dotted_path: value} map and produce added/changed/removed keys for the
   re-extract diff modal.

Public API:
    reconcile_siblings(db_path, doc_id, tan, current) -> dict
    flatten_diff(d, prefix='') -> dict
    compute_diff(old, new) -> dict
"""
from __future__ import annotations

import json
import os

from core.storage.db import get_connection


# ─── Helpers ────────────────────────────────────────────────────────────────

def _get_containers(d: dict) -> dict:
    """Index containers by container_number for set comparison."""
    return {
        c.get("container_number"): c
        for c in (d.get("containers") or [])
        if c.get("container_number")
    }


def _parse_weight(raw):
    """Parse a free-text gross-weight value to float kilograms.

    Strips commas, spaces, and trailing 'kg'/'KG' so values like
    "15,288.0 kg" and "15288 KG" both produce 15288.0.
    """
    if raw is None:
        return None
    try:
        return float(
            str(raw).replace(",", "").replace(" ", "").split("kg")[0].split("KG")[0]
        )
    except (ValueError, TypeError):
        return None


# ─── Reconciliation ─────────────────────────────────────────────────────────

def reconcile_siblings(db_path: str, doc_id: int, tan: str, current: dict) -> dict:
    """Find sibling logistics docs sharing `tan` and flag discrepancies.

    Returns:
        {
            "siblings":      list of {id, type, basename, extracted},
            "discrepancies": list of {field, label, values, detail, severity},
            "summary":       human-readable summary string,
            "has_issues":    bool — True iff at least one discrepancy,
        }

    Discrepancy types: vessel_name, etd, eta, containers, weight.<container#>.
    Severity is "warning" by default; container-set mismatches and weight
    diffs > 15% are upgraded to "error".
    """
    if not tan or not os.path.exists(db_path):
        return {"siblings": [], "discrepancies": [],
                "summary": "No TAN — cannot reconcile", "has_issues": False}

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT id, type, source_file, extracted_json, confidence
               FROM documents
               WHERE module = 'logistics' AND id != ? AND extracted_json LIKE ?""",
            (doc_id, f"%{tan}%"),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"siblings": [], "discrepancies": [],
                "summary": "No other documents for this TAN", "has_issues": False}

    siblings = []
    for row in rows:
        try:
            sib_extracted = json.loads(row["extracted_json"] or "{}")
        except Exception:
            sib_extracted = {}
        # The LIKE filter can match TAN substrings, so guard with exact match.
        if sib_extracted.get("tan_number") != tan:
            continue
        siblings.append({
            "id":        row["id"],
            "type":      row["type"] or sib_extracted.get("document_type", "?"),
            "basename":  os.path.basename(row["source_file"] or ""),
            "extracted": sib_extracted,
        })

    if not siblings:
        return {"siblings": [], "discrepancies": [],
                "summary": "No other documents for this TAN", "has_issues": False}

    current_type = current.get("document_type") or "CURRENT"
    all_docs = [{"id": doc_id, "type": current_type, "extracted": current}] + siblings
    discrepancies: list[dict] = []

    # Check 1: vessel name
    vessels = {d["extracted"].get("vessel_name") for d in all_docs
               if d["extracted"].get("vessel_name")}
    if len(vessels) > 1:
        discrepancies.append({
            "field": "vessel_name",
            "label": "Vessel name",
            "values": {
                d["id"]: (d["extracted"].get("vessel_name") or "—") + f" [{d['type']}]"
                for d in all_docs if d["extracted"].get("vessel_name")
            },
            "detail": None,
            "severity": "warning",
        })

    # Check 2: ETD
    etds = {d["extracted"].get("etd") for d in all_docs if d["extracted"].get("etd")}
    if len(etds) > 1:
        discrepancies.append({
            "field": "etd",
            "label": "ETD",
            "values": {
                d["id"]: (d["extracted"].get("etd") or "—") + f" [{d['type']}]"
                for d in all_docs if d["extracted"].get("etd")
            },
            "detail": None,
            "severity": "warning",
        })

    # Check 3: ETA
    etas = {d["extracted"].get("eta") for d in all_docs if d["extracted"].get("eta")}
    if len(etas) > 1:
        discrepancies.append({
            "field": "eta",
            "label": "ETA",
            "values": {
                d["id"]: (d["extracted"].get("eta") or "—") + f" [{d['type']}]"
                for d in all_docs if d["extracted"].get("eta")
            },
            "detail": None,
            "severity": "warning",
        })

    # Check 4: container numbers must appear in every doc that lists containers
    container_sets = [set(_get_containers(d["extracted"]).keys()) for d in all_docs]
    non_empty_sets = [s for s in container_sets if s]
    if len(non_empty_sets) > 1:
        union_all = set().union(*non_empty_sets)
        common = set(non_empty_sets[0]).intersection(*non_empty_sets[1:])
        missing = union_all - common
        if missing:
            discrepancies.append({
                "field": "containers",
                "label": "Container numbers",
                "values": {
                    d["id"]: ", ".join(sorted(_get_containers(d["extracted"]).keys())) or "—"
                    for d in all_docs
                },
                "detail": f"{len(missing)} container(s) absent in some docs: {', '.join(sorted(missing))}",
                "severity": "error",
            })

    # Check 5: gross weight ±5% per container across doc pairs
    for i, doc_a in enumerate(all_docs):
        for doc_b in all_docs[i + 1:]:
            ca = _get_containers(doc_a["extracted"])
            cb = _get_containers(doc_b["extracted"])
            for cnum in set(ca) & set(cb):
                wa = _parse_weight(ca[cnum].get("gross_weight"))
                wb = _parse_weight(cb[cnum].get("gross_weight"))
                if wa and wb and wa > 0:
                    pct = abs(wa - wb) / wa * 100
                    if pct > 5:
                        discrepancies.append({
                            "field": f"weight.{cnum}",
                            "label": f"Weight — {cnum}",
                            "values": {
                                doc_a["id"]: f"{ca[cnum].get('gross_weight')} [{doc_a['type']}]",
                                doc_b["id"]: f"{cb[cnum].get('gross_weight')} [{doc_b['type']}]",
                            },
                            "detail": f"{pct:.1f}% difference",
                            "severity": "error" if pct > 15 else "warning",
                        })

    n = len(discrepancies)
    n_total = len(all_docs)
    if n == 0:
        summary = f"All consistent across {n_total} document(s) for {tan}"
    else:
        summary = f"{n} discrepanc{'y' if n == 1 else 'ies'} across {n_total} document(s)"

    return {
        "siblings": siblings,
        "discrepancies": discrepancies,
        "summary": summary,
        "has_issues": n > 0,
    }


# ─── JSON diffing for the re-extract modal ──────────────────────────────────

def flatten_diff(d, prefix: str = "") -> dict:
    """Flatten a nested dict/list to {dotted_path: scalar_value}.

    - Dict keys joined by '.': {"a": {"b": 1}} -> {"a.b": 1}
    - List entries indexed by '[i]': {"c": [{"x": 2}]} -> {"c[0].x": 2}
    - Schema-comment keys (those starting with '_' in the prompt) are dropped
      so they don't show up as "removed" diffs every re-extract.
    """
    out: dict = {}
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            sub = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                out.update(flatten_diff(v, sub))
            else:
                out[sub] = v
    elif isinstance(d, list):
        for i, item in enumerate(d):
            sub = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                out.update(flatten_diff(item, sub))
            else:
                out[sub] = item
    return out


def compute_diff(old: dict, new: dict) -> dict:
    """Return added / removed / changed keys for the operator to review."""
    flat_old = flatten_diff(old or {})
    flat_new = flatten_diff(new or {})
    added = {k: flat_new[k] for k in flat_new if k not in flat_old}
    removed = {k: flat_old[k] for k in flat_old if k not in flat_new}
    changed = {
        k: {"old": flat_old[k], "new": flat_new[k]}
        for k in flat_new
        if k in flat_old and flat_new[k] != flat_old[k]
    }
    return {
        "added":     added,
        "removed":   removed,
        "changed":   changed,
        "n_added":   len(added),
        "n_removed": len(removed),
        "n_changed": len(changed),
    }
