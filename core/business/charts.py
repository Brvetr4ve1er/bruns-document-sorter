"""Pre-aggregated chart data for the analytics dashboards.

Pure SQL aggregations — no Flask, no HTML rendering. Produces structures
shaped for Chart.js consumption: lists of {"label": ..., "value": ...}.

Public API:
    logistics_chart_data(db_path) -> dict
    travel_chart_data(db_path) -> dict
"""
from __future__ import annotations

import logging
import os
from datetime import date

from core.storage.db import get_connection

log = logging.getLogger(__name__)


def logistics_chart_data(db_path: str) -> dict:
    """Aggregate counts for /logistics/analytics. Returns 4 chart series:

    - by_status:           container status mix
    - by_carrier:          top 10 carriers by container count
    - shipments_by_month:  last 12 months of shipment volume
    - transit_by_carrier:  avg days from ETD to ETA, per carrier
    """
    out: dict = {
        "by_status": [], "by_carrier": [],
        "shipments_by_month": [], "transit_by_carrier": [],
    }
    if not os.path.exists(db_path):
        return out

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT COALESCE(NULLIF(statut_container, ''), 'UNKNOWN') AS status,
                      COUNT(*) AS n
               FROM containers GROUP BY status ORDER BY n DESC"""
        ).fetchall()
        out["by_status"] = [{"label": r["status"], "value": r["n"]} for r in rows]

        rows = conn.execute(
            """SELECT COALESCE(NULLIF(s.compagnie_maritime, ''), 'UNKNOWN') AS carrier,
                      COUNT(c.id) AS n
               FROM containers c JOIN shipments s ON s.id = c.shipment_id
               GROUP BY carrier ORDER BY n DESC LIMIT 10"""
        ).fetchall()
        out["by_carrier"] = [{"label": r["carrier"], "value": r["n"]} for r in rows]

        rows = conn.execute(
            """SELECT substr(created_at, 1, 7) AS ym, COUNT(*) AS n
               FROM shipments WHERE created_at IS NOT NULL
               GROUP BY ym ORDER BY ym DESC LIMIT 12"""
        ).fetchall()
        # Reversed so charts render oldest → newest left-to-right.
        out["shipments_by_month"] = list(reversed(
            [{"label": r["ym"], "value": r["n"]} for r in rows]
        ))

        rows = conn.execute(
            """SELECT COALESCE(NULLIF(s.compagnie_maritime, ''), 'UNKNOWN') AS carrier,
                      AVG(julianday(s.eta) - julianday(s.etd)) AS avg_days,
                      COUNT(*) AS n
               FROM shipments s
               WHERE s.etd IS NOT NULL AND s.eta IS NOT NULL
                 AND s.etd != '' AND s.eta != ''
               GROUP BY carrier HAVING n >= 1 ORDER BY avg_days DESC LIMIT 10"""
        ).fetchall()
        out["transit_by_carrier"] = [
            {"label": r["carrier"], "value": round(r["avg_days"] or 0, 1)}
            for r in rows if r["avg_days"] is not None
        ]
    finally:
        conn.close()
    return out


def travel_chart_data(db_path: str) -> dict:
    """Aggregate counts for /travel/analytics. Returns 4 chart series:

    - by_status:        family case status distribution
    - by_doc_type:      top 10 document types
    - by_nationality:   top 10 nationalities
    - expiry_timeline:  document expiry density for the next 12 months
    """
    out: dict = {
        "by_status": [], "by_doc_type": [],
        "by_nationality": [], "expiry_timeline": [],
    }
    if not os.path.exists(db_path):
        return out

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT COALESCE(NULLIF(case_status, ''), 'COLLECTING') AS s,
                      COUNT(*) AS n FROM families GROUP BY s ORDER BY n DESC"""
        ).fetchall()
        out["by_status"] = [{"label": r["s"], "value": r["n"]} for r in rows]

        rows = conn.execute(
            """SELECT COALESCE(NULLIF(doc_type, ''), 'UNKNOWN') AS t, COUNT(*) AS n
               FROM documents_travel GROUP BY t ORDER BY n DESC LIMIT 10"""
        ).fetchall()
        out["by_doc_type"] = [{"label": r["t"], "value": r["n"]} for r in rows]

        rows = conn.execute(
            """SELECT COALESCE(NULLIF(nationality, ''), 'UNKNOWN') AS n_, COUNT(*) AS n
               FROM persons GROUP BY n_ ORDER BY n DESC LIMIT 10"""
        ).fetchall()
        out["by_nationality"] = [{"label": r["n_"], "value": r["n"]} for r in rows]

        # Expiry timeline — pre-fill 12 monthly buckets so the chart always
        # has the same x-axis even when most months are empty.
        today = date.today()
        buckets = []
        for i in range(12):
            y = today.year + ((today.month - 1 + i) // 12)
            m = ((today.month - 1 + i) % 12) + 1
            buckets.append({"key": f"{y:04d}-{m:02d}", "value": 0})
        bk = {b["key"]: b for b in buckets}
        rows = conn.execute(
            """SELECT substr(expiry_date, 1, 7) AS ym, COUNT(*) AS n
               FROM documents_travel
               WHERE expiry_date IS NOT NULL AND expiry_date != ''
               GROUP BY ym"""
        ).fetchall()
        for r in rows:
            if r["ym"] in bk:
                bk[r["ym"]]["value"] = r["n"]
        out["expiry_timeline"] = [
            {"label": b["key"], "value": b["value"]} for b in buckets
        ]
    finally:
        conn.close()
    return out
