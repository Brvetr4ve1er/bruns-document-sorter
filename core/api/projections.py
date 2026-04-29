"""Domain projection layer.

The engine pipeline saves the LLM result into the generic `documents` table
(blob of JSON). The dashboards, however, query domain-specific tables
(`persons`, `documents_travel`, `families` for travel; `shipments`, `containers`
for logistics).

This module bridges that gap: after every successful extraction, project the
flat LLM dict into the domain tables. Without this, the dashboards stay empty
even though `documents` fills up.

Public API:
    project(module, db_path, doc_id, extracted_data) -> dict
        Returns a small summary like {"persons_inserted": 1, "docs_inserted": 1}
        Always swallows errors per row — the projection should never fail
        a successful extraction.

Note: this module reads the LIVE schema (which is a hybrid of legacy
logistics_app + engine init_schema). It tolerates missing optional columns
via INSERT-with-only-known-columns.
"""
from __future__ import annotations

import json
import os
import sqlite3

from core.storage.db import get_connection


# ─── Travel projection ─────────────────────────────────────────────────────────
def _norm_name(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(name.strip().lower().split())


def _project_travel(conn: sqlite3.Connection, doc_id: int, d: dict) -> dict:
    """Project a travel-document extraction into persons + documents_travel.

    For passports / ID cards / visas, runs MRZ extraction directly on the
    source file and merges the deterministic MRZ values OVER the LLM dict —
    MRZ wins because it's checksum-validated. The LLM keeps any extra fields
    it found that MRZ doesn't cover (issue_date, place_of_birth, etc.).
    """
    # ── MRZ override (deterministic) ─────────────────────────────────────────
    src = d.get("_source_file")
    mrz_summary = None
    if src and os.path.isfile(src):
        try:
            from core.extraction.mrz_extract import extract_mrz
            mrz = extract_mrz(src, min_score=40)
            if mrz:
                mrz_summary = {
                    "score":   mrz["mrz_valid_score"],
                    "name":    mrz.get("full_name"),
                    "dob":     mrz.get("dob"),
                    "doc_no":  mrz.get("document_number"),
                }
                # MRZ wins for these fields where MRZ has it
                for k in ("document_type", "document_number", "full_name",
                          "given_names", "surname", "dob", "nationality",
                          "sex", "expiry_date", "issuing_country",
                          "mrz_line_1", "mrz_line_2"):
                    v = mrz.get(k)
                    if v not in (None, ""):
                        d[k] = v
        except Exception as e:
            mrz_summary = {"error": f"{type(e).__name__}: {e}"}

    full_name = (d.get("full_name") or "").strip() or None
    dob = (d.get("dob") or "").strip() or None
    nationality = (d.get("nationality") or "").strip() or None
    gender = (d.get("gender") or d.get("sex") or "").strip() or None
    normalized = _norm_name(full_name)

    # Try to find an existing person with the same normalized name + dob.
    person_id = None
    if normalized:
        match_sql = "SELECT id FROM persons WHERE normalized_name = ?"
        params: tuple = (normalized,)
        if dob:
            match_sql += " AND (dob = ? OR dob IS NULL)"
            params = (normalized, dob)
        row = conn.execute(match_sql, params).fetchone()
        if row:
            person_id = row[0]

    inserted_person = 0
    if person_id is None:
        cur = conn.execute(
            """INSERT INTO persons (full_name, normalized_name, dob, nationality, gender)
               VALUES (?, ?, ?, ?, ?)""",
            (full_name, normalized or None, dob, nationality, gender),
        )
        person_id = cur.lastrowid
        inserted_person = 1

    # Insert the document_travel row.
    doc_type = (d.get("document_type") or "UNKNOWN").strip().upper()
    doc_number = d.get("document_number") or d.get("doc_number") or None
    expiry = d.get("expiry_date") or d.get("expiry") or None
    mrz1 = d.get("mrz_line_1") or ""
    mrz2 = d.get("mrz_line_2") or ""
    mrz_raw = (mrz1 + ("\n" if mrz1 and mrz2 else "") + mrz2) or None

    conn.execute(
        """INSERT INTO documents_travel
                (person_id, family_id, doc_type, doc_number, expiry_date, mrz_raw, original_doc_id)
           VALUES (?, NULL, ?, ?, ?, ?, ?)""",
        (person_id, doc_type, doc_number, expiry, mrz_raw, doc_id),
    )
    out = {"persons_inserted": inserted_person, "docs_inserted": 1, "person_id": person_id}
    if mrz_summary:
        out["mrz"] = mrz_summary
    return out


# ─── Logistics projection ──────────────────────────────────────────────────────
# The live data/logistics.db uses the LEGACY logistics_app schema for shipments
# (compagnie_maritime, item_description, source_file, document_type, status,
# created_at, modified_at) and containers (statut_container, ...). We INSERT
# with those column names so dashboards keep reading from the same tables.

def _project_logistics(conn: sqlite3.Connection, doc_id: int, d: dict) -> dict:
    """Project a logistics-document extraction into shipments + containers."""
    tan = d.get("tan_number") or d.get("tan") or None
    vessel = d.get("vessel_name") or d.get("vessel") or None
    carrier = d.get("shipping_company") or d.get("carrier") or None
    port = d.get("port") or None
    transitaire = d.get("transitaire") or None
    item = d.get("item_description") or d.get("item") or None
    etd = d.get("etd") or None
    eta = d.get("eta") or None
    doctype = (d.get("document_type") or "UNKNOWN").strip().upper()
    status = "BOOKED" if doctype == "BOOKING" else (
        "IN_TRANSIT" if doctype == "DEPARTURE" else "UNKNOWN"
    )

    # ── Find existing shipment by TAN (idempotent on re-extraction) ──
    shipment_id = None
    if tan:
        row = conn.execute("SELECT id FROM shipments WHERE tan = ?", (tan,)).fetchone()
        if row:
            shipment_id = row[0]

    inserted_shipment = 0
    if shipment_id is None:
        # The legacy `shipments` table has these columns (see migrated schema)
        cur = conn.execute(
            """INSERT INTO shipments
                  (tan, item_description, compagnie_maritime, port, transitaire,
                   vessel, etd, eta, document_type, status, source_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tan, item, carrier, port, transitaire, vessel, etd, eta,
             doctype, status, d.get("_source_file")),
        )
        shipment_id = cur.lastrowid
        inserted_shipment = 1

    # ── Insert each container ──
    inserted_containers = 0
    for c in (d.get("containers") or []):
        cn = (c.get("container_number") or "").strip() or None
        if not cn:
            continue
        # Skip if container already attached to this shipment
        existing = conn.execute(
            "SELECT id FROM containers WHERE shipment_id = ? AND container_number = ?",
            (shipment_id, cn),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """INSERT INTO containers
                  (shipment_id, container_number, size, seal_number, statut_container)
               VALUES (?, ?, ?, ?, ?)""",
            (shipment_id, cn, c.get("size"), c.get("seal_number"), "BOOKED"),
        )
        inserted_containers += 1

    return {
        "shipments_inserted":  inserted_shipment,
        "containers_inserted": inserted_containers,
        "shipment_id":         shipment_id,
    }


# ─── Public dispatcher ─────────────────────────────────────────────────────────
def project(module: str, db_path: str, doc_id: int,
            extracted_data: dict | str) -> dict:
    """Project a single extraction into domain tables. Never raises.

    extracted_data may be a dict OR a JSON string (the engine sometimes passes
    one, sometimes the other depending on whether you read it from the Job or
    from the documents table).
    """
    if isinstance(extracted_data, str):
        try:
            extracted_data = json.loads(extracted_data)
        except Exception:
            return {"error": "invalid extracted_data JSON"}

    if not isinstance(extracted_data, dict):
        return {"error": f"unsupported extracted_data type: {type(extracted_data).__name__}"}

    try:
        conn = get_connection(db_path)
        try:
            if module == "travel":
                summary = _project_travel(conn, doc_id, extracted_data)
            elif module == "logistics":
                summary = _project_logistics(conn, doc_id, extracted_data)
            else:
                return {"error": f"unknown module: {module}"}
            conn.commit()
            return summary
        finally:
            conn.close()
    except Exception as e:
        # Never let projection failures surface as job failures — extraction
        # already succeeded by the time we get here.
        return {"error": f"{type(e).__name__}: {e}"}
