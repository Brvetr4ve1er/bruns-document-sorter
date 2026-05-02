"""Travel-case completeness gate + status flow data.

Decides per-member required-document checklists and a family-wide
"can advance" gate that blocks status transitions until every member is
100% complete. The status flow itself is a constant ordered list so the
template can render it as a breadcrumb.

Public API:
    REQUIRED_DOCS_BY_ROLE  : dict[role -> list of required doc_type strings]
    CASE_STATUS_FLOW       : ordered case_status pipeline
    person_role(person_id, head_id) -> str
    family_completeness(conn, family_id) -> dict

`family_completeness` takes a sqlite connection so the route can include the
result in the same transaction it uses for other queries — avoids opening a
second connection per request.
"""
from __future__ import annotations

import sqlite3


# Per-role required document checklists. Missing role → "default" (PASSPORT only).
# Extend per customer requirements; this is the conservative baseline that
# matches what Algerian visa consultants typically request.
REQUIRED_DOCS_BY_ROLE: dict[str, list[str]] = {
    "head":    ["PASSPORT", "BIRTH_CERTIFICATE", "PROOF_OF_ADDRESS", "BANK_STATEMENT"],
    "spouse":  ["PASSPORT", "MARRIAGE_CERTIFICATE"],
    "child":   ["PASSPORT", "BIRTH_CERTIFICATE"],
    "default": ["PASSPORT"],
}

# Status pipeline. Advancing to IN_REVIEW or beyond is gated on
# can_advance == True (see family_completeness).
CASE_STATUS_FLOW: list[str] = [
    "COLLECTING", "READY", "IN_REVIEW", "SUBMITTED", "APPROVED", "REJECTED",
]


def person_role(person_id: int, head_id: int | None) -> str:
    """Heuristic role assignment.

    Currently only "head" vs "default" — spouse/child detection would need
    relationship metadata that isn't extracted yet. The required-docs map
    above already supports those buckets when role inference improves.
    """
    if head_id and person_id == head_id:
        return "head"
    return "default"


def family_completeness(conn: sqlite3.Connection, family_id: int) -> dict:
    """Compute per-member completeness and family-wide advancement gate.

    Returns:
        {
            "members": [
                {person_id, name, role, required, present, missing, pct}, ...
            ],
            "completeness_pct": int,    # 0-100, weighted by required-doc count
            "can_advance":      bool,   # True iff blockers is empty AND members > 0
            "blockers":         list[str],   # human-readable strings for the UI
        }
    """
    fam = conn.execute(
        "SELECT id, head_person_id FROM families WHERE id = ?",
        (family_id,),
    ).fetchone()
    if not fam:
        return {
            "members": [], "completeness_pct": 0,
            "can_advance": False, "blockers": [],
        }

    head_id = fam["head_person_id"]
    persons = conn.execute(
        "SELECT id, full_name FROM persons WHERE family_id = ? ORDER BY id",
        (family_id,),
    ).fetchall()

    members: list[dict] = []
    blockers: list[str] = []
    total_req = 0
    total_present = 0

    for p in persons:
        role = person_role(p["id"], head_id)
        required = REQUIRED_DOCS_BY_ROLE.get(role, REQUIRED_DOCS_BY_ROLE["default"])
        docs = conn.execute(
            "SELECT DISTINCT doc_type FROM documents_travel WHERE person_id = ?",
            (p["id"],),
        ).fetchall()
        present = {(d["doc_type"] or "").upper() for d in docs}
        missing = [r for r in required if r not in present]
        total_req += len(required)
        total_present += len(required) - len(missing)
        if missing:
            blockers.append(
                f"{p['full_name'] or 'Person #' + str(p['id'])}: missing {', '.join(missing)}"
            )
        members.append({
            "person_id": p["id"],
            "name":      p["full_name"],
            "role":      role,
            "required":  required,
            "present":   sorted(present),
            "missing":   missing,
            "pct": int(
                (len(required) - len(missing)) / len(required) * 100
            ) if required else 100,
        })

    pct = int(total_present / total_req * 100) if total_req else 100
    return {
        "members":          members,
        "completeness_pct": pct,
        "can_advance":      len(blockers) == 0 and len(members) > 0,
        "blockers":         blockers,
    }
