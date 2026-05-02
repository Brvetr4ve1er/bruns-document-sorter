"""Dashboard statistics + operator action-panel counts.

Pure SQL aggregations consumed by the logistics + travel dashboard templates.
All functions take an explicit db_path so they're trivially testable against
fixture databases.

Public API:
    logistics_stats(db_path)            -> dict (4 counts)
    logistics_recent_activity(db_path, limit=15) -> list[dict]
    logistics_action_panel(db_path)     -> dict (4 action-card counts)
    logistics_recent_containers(db_path, limit=25) -> list[dict]
    travel_stats(db_path)               -> dict (5 counts)
    travel_recent_persons(db_path, limit=25) -> list[dict]
"""
from __future__ import annotations

import os

from core.storage.db import get_connection


# ─── Logistics ──────────────────────────────────────────────────────────────

def logistics_stats(db_path: str) -> dict:
    """Counts for the logistics dashboard hero. Returns zeroes if DB missing."""
    if not os.path.exists(db_path):
        return {"shipments": 0, "containers": 0, "booked": 0, "in_transit": 0}
    conn = get_connection(db_path)
    try:
        s = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        c = conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0]
        b = conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status='BOOKED'"
        ).fetchone()[0]
        t = conn.execute(
            "SELECT COUNT(*) FROM containers WHERE statut_container IN ('IN_TRANSIT','EN_ROUTE')"
        ).fetchone()[0]
        return {"shipments": s, "containers": c, "booked": b, "in_transit": t}
    finally:
        conn.close()


def logistics_recent_activity(db_path: str, limit: int = 15) -> list[dict]:
    """P1-D: recent audit_log entries surfaced on the dashboard sidebar."""
    if not os.path.exists(db_path):
        return []
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT id, action, actor, entity_type, entity_id, timestamp
               FROM audit_log
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # audit_log table missing on a freshly-initialised DB — non-fatal.
        return []
    finally:
        conn.close()


def logistics_action_panel(db_path: str) -> dict:
    """P1-A: four operator action-card counts.

    Cards:
      review     — docs with confidence < 0.90 not yet reviewed
      dnd_risk   — containers with ETA past + no delivery + no restitution
      gaps       — containers delivered but missing customs declaration date
      on_track   — total minus the above (rough estimate)
    """
    panel = {"review": 0, "dnd_risk": 0, "gaps": 0, "on_track": 0}
    if not os.path.exists(db_path):
        return panel
    conn = get_connection(db_path)
    try:
        panel["review"] = conn.execute(
            """SELECT COUNT(*) FROM documents
               WHERE module = 'logistics'
                 AND (confidence IS NULL OR confidence < 0.90)
                 AND reviewed_at IS NULL"""
        ).fetchone()[0]

        # ETA in the past, container not yet delivered or restituted.
        panel["dnd_risk"] = conn.execute(
            """SELECT COUNT(*) FROM containers c
               JOIN shipments s ON s.id = c.shipment_id
               WHERE s.eta IS NOT NULL
                 AND s.eta < date('now')
                 AND (c.date_livraison IS NULL OR c.date_livraison = '')
                 AND (c.date_restitution IS NULL OR c.date_restitution = '')"""
        ).fetchone()[0]

        # Delivered without a customs declaration date — operator must fill it.
        panel["gaps"] = conn.execute(
            """SELECT COUNT(*) FROM containers
               WHERE (date_livraison IS NOT NULL AND date_livraison != '')
                 AND (date_declaration_douane IS NULL OR date_declaration_douane = '')"""
        ).fetchone()[0]

        total = conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0]
        panel["on_track"] = max(0, total - panel["dnd_risk"] - panel["gaps"])
    except Exception:
        # Schema not yet initialised — fall back to zeroes
        pass
    finally:
        conn.close()
    return panel


def logistics_recent_containers(db_path: str, limit: int = 25) -> list[dict]:
    """Most-recent containers with shipment context, denormalised for the table."""
    if not os.path.exists(db_path):
        return []
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT c.id, c.container_number, c.size, c.seal_number,
                      c.statut_container, s.tan, s.compagnie_maritime,
                      s.port, s.etd, s.eta, s.source_file
               FROM containers c
               JOIN shipments s ON s.id = c.shipment_id
               ORDER BY c.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Travel ────────────────────────────────────────────────────────────────

def travel_stats(db_path: str) -> dict:
    """Counts for the travel dashboard hero."""
    if not os.path.exists(db_path):
        return {"persons": 0, "families": 0, "documents": 0,
                "expired_passports": 0, "unmatched_docs": 0}
    conn = get_connection(db_path)
    try:
        p = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        f = conn.execute("SELECT COUNT(*) FROM families").fetchone()[0]
        d = conn.execute("SELECT COUNT(*) FROM documents_travel").fetchone()[0]
        ex = conn.execute(
            """SELECT COUNT(*) FROM documents_travel
               WHERE UPPER(doc_type) LIKE 'PASSPORT%'
                 AND expiry_date IS NOT NULL
                 AND expiry_date < date('now')"""
        ).fetchone()[0]
        un = conn.execute(
            "SELECT COUNT(*) FROM documents_travel WHERE person_id IS NULL"
        ).fetchone()[0]
        return {"persons": p, "families": f, "documents": d,
                "expired_passports": ex, "unmatched_docs": un}
    finally:
        conn.close()


def travel_recent_persons(db_path: str, limit: int = 25) -> list[dict]:
    """Most-recent persons with family + doc-count context."""
    if not os.path.exists(db_path):
        return []
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT p.id, p.full_name, p.dob, p.nationality, p.gender,
                      f.family_name,
                      (SELECT COUNT(*) FROM documents_travel WHERE person_id = p.id) AS n_docs
               FROM persons p
               LEFT JOIN families f ON f.id = p.family_id
               ORDER BY p.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
