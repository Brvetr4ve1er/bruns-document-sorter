import sqlite3
import os
import json
from datetime import datetime
from config import DB_PATH
from models.schema import ShipmentData

# Shipment-level status derived from doc_type
STATUS_MAP = {
    "BOOKING": "BOOKED",
    "DEPARTURE": "IN_TRANSIT",
    "BILL_OF_LADING": "IN_TRANSIT",
    "UNKNOWN": "UNKNOWN",
}

# Per-container status (French — matches xlsx "Statut Container" values)
CONTAINER_STATUS_MAP = {
    "BOOKING": "Réservé",
    "DEPARTURE": "En transit",
    "BILL_OF_LADING": "En transit",
    "UNKNOWN": "En transit",
}


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS shipments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                tan                 TEXT UNIQUE,
                item_description    TEXT,
                compagnie_maritime  TEXT,
                port                TEXT DEFAULT 'Port d''Alger',
                transitaire         TEXT,
                vessel              TEXT,
                etd                 TEXT,
                eta                 TEXT,
                document_type       TEXT,
                status              TEXT DEFAULT 'UNKNOWN',
                source_file         TEXT,
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                modified_at         TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS containers (
                id                           INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_id                  INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
                container_number             TEXT NOT NULL,
                size                         TEXT,
                seal_number                  TEXT,
                statut_container             TEXT,
                -- operational fields (filled in manually via UI)
                date_livraison               TEXT,
                site_livraison               TEXT,
                date_depotement              TEXT,
                date_debut_surestarie        TEXT,
                date_restitution_estimative  TEXT,
                nbr_jours_surestarie_estimes INTEGER DEFAULT 0,
                nbr_jours_perdu_douane       INTEGER DEFAULT 0,
                date_restitution             TEXT,
                restitue_camion              TEXT,
                restitue_chauffeur           TEXT,
                centre_restitution           TEXT,
                livre_camion                 TEXT,
                livre_chauffeur              TEXT,
                montant_facture_check        TEXT DEFAULT 'No',
                nbr_jour_surestarie_facture  INTEGER DEFAULT 0,
                montant_facture_da           REAL DEFAULT 0,
                n_facture_cm                 TEXT,
                commentaire                  TEXT,
                date_declaration_douane      TEXT,
                date_liberation_douane       TEXT,
                taux_de_change               REAL DEFAULT 0,
                created_at                   TEXT DEFAULT CURRENT_TIMESTAMP,
                modified_at                  TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(shipment_id, container_number)
            );

            -- IMPROVEMENT 1: File Duplicate Detection
            CREATE TABLE IF NOT EXISTS file_hashes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT UNIQUE,
                file_hash   TEXT NOT NULL,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- IMPROVEMENT 3, 9: Confidence Scores by field
            CREATE TABLE IF NOT EXISTS confidence_scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id    INTEGER NOT NULL REFERENCES containers(id) ON DELETE CASCADE,
                field_name      TEXT NOT NULL,
                confidence      REAL DEFAULT 0.0,
                extracted_value TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- IMPROVEMENT 8: Change Audit Log
            CREATE TABLE IF NOT EXISTS change_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id    INTEGER NOT NULL REFERENCES containers(id) ON DELETE CASCADE,
                field_name      TEXT NOT NULL,
                old_value       TEXT,
                new_value       TEXT,
                changed_by      TEXT DEFAULT 'system',
                changed_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- IMPROVEMENT 5: Smart Filter Presets
            CREATE TABLE IF NOT EXISTS filter_presets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                preset_name     TEXT UNIQUE NOT NULL,
                filter_config   TEXT NOT NULL,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used_at    TEXT
            );

            -- IMPROVEMENT 6: Document Classification
            CREATE TABLE IF NOT EXISTS document_classification (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_id         INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
                doc_type            TEXT,
                predicted_category  TEXT,
                confidence          REAL DEFAULT 0.0,
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- IMPROVEMENT 7: Validation Issues Tracking
            CREATE TABLE IF NOT EXISTS validation_issues (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id        INTEGER REFERENCES containers(id) ON DELETE CASCADE,
                shipment_id         INTEGER REFERENCES shipments(id) ON DELETE CASCADE,
                issue_type          TEXT NOT NULL,
                field_name          TEXT,
                issue_description   TEXT,
                severity            TEXT DEFAULT 'warning',
                is_resolved         INTEGER DEFAULT 0,
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- IMPROVEMENT 16: Cache Extraction Results
            CREATE TABLE IF NOT EXISTS extraction_cache (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash       TEXT UNIQUE,
                extraction_results TEXT NOT NULL,
                cached_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                hit_count       INTEGER DEFAULT 0
            );

            -- IMPROVEMENT 14: Processing Stats
            CREATE TABLE IF NOT EXISTS processing_stats (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type        TEXT UNIQUE,
                success_count   INTEGER DEFAULT 0,
                fail_count      INTEGER DEFAULT 0,
                total_processed INTEGER DEFAULT 0,
                avg_extract_time_ms REAL DEFAULT 0,
                last_updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- IMPROVEMENT 11: Batch Operations Tracking
            CREATE TABLE IF NOT EXISTS batch_operations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id        TEXT UNIQUE NOT NULL,
                operation_type  TEXT NOT NULL,
                status          TEXT DEFAULT 'pending',
                total_items     INTEGER DEFAULT 0,
                completed_items INTEGER DEFAULT 0,
                failed_items    INTEGER DEFAULT 0,
                metadata        TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at    TEXT
            );

            -- IMPROVEMENT 2: Background Processing Queue
            CREATE TABLE IF NOT EXISTS processing_queue (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path       TEXT NOT NULL,
                status          TEXT DEFAULT 'pending',
                priority        INTEGER DEFAULT 0,
                retry_count     INTEGER DEFAULT 0,
                error_message   TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at      TEXT,
                completed_at    TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_shipments_tan ON shipments(tan);
            CREATE INDEX IF NOT EXISTS idx_containers_num ON containers(container_number);
            CREATE INDEX IF NOT EXISTS idx_confidence_container ON confidence_scores(container_id);
            CREATE INDEX IF NOT EXISTS idx_changelog_container ON change_log(container_id);
            CREATE INDEX IF NOT EXISTS idx_validation_container ON validation_issues(container_id);
            CREATE INDEX IF NOT EXISTS idx_batch_ops_status ON batch_operations(status);
            CREATE INDEX IF NOT EXISTS idx_processing_queue_status ON processing_queue(status);
        """)
    conn.close()


def _find_shipment(conn: sqlite3.Connection, shipment: ShipmentData) -> sqlite3.Row | None:
    if shipment.tan_number:
        row = conn.execute("SELECT * FROM shipments WHERE tan = ?", (shipment.tan_number,)).fetchone()
        if row:
            return row
    if shipment.vessel_name and shipment.etd:
        row = conn.execute(
            "SELECT * FROM shipments WHERE vessel = ? AND etd = ?",
            (shipment.vessel_name, shipment.etd),
        ).fetchone()
        return row
    return None


def _upsert_containers(conn: sqlite3.Connection, shipment_id: int, shipment: ShipmentData):
    container_status = CONTAINER_STATUS_MAP.get(shipment.document_type, "En transit")
    now = datetime.utcnow().isoformat(timespec="seconds")
    for c in shipment.containers:
        # Only overwrite statut/seal/size if they're empty, so manual ops updates aren't clobbered.
        conn.execute(
            """INSERT INTO containers
                 (shipment_id, container_number, size, seal_number, statut_container, modified_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(shipment_id, container_number) DO UPDATE SET
                 size         = COALESCE(containers.size, excluded.size),
                 seal_number  = COALESCE(containers.seal_number, excluded.seal_number),
                 modified_at  = excluded.modified_at""",
            (shipment_id, c.container_number, c.size, c.seal_number, container_status, now),
        )


def upsert_shipment(shipment: ShipmentData, source_file: str = None) -> tuple[str, int]:
    conn = get_connection()
    new_status = STATUS_MAP.get(shipment.document_type, "UNKNOWN")
    now = datetime.utcnow().isoformat(timespec="seconds")

    try:
        with conn:
            existing = _find_shipment(conn, shipment)

            if existing:
                shipment_id = existing["id"]
                conn.execute(
                    """UPDATE shipments SET
                         tan                = COALESCE(?, tan),
                         item_description   = COALESCE(?, item_description),
                         compagnie_maritime = COALESCE(?, compagnie_maritime),
                         port               = COALESCE(?, port),
                         transitaire        = COALESCE(?, transitaire),
                         vessel             = COALESCE(?, vessel),
                         etd                = COALESCE(?, etd),
                         eta                = COALESCE(?, eta),
                         document_type      = ?,
                         status             = ?,
                         source_file        = COALESCE(?, source_file),
                         modified_at        = ?
                       WHERE id = ?""",
                    (shipment.tan_number, shipment.item_description, shipment.shipping_company,
                     shipment.port, shipment.transitaire, shipment.vessel_name,
                     shipment.etd, shipment.eta, shipment.document_type, new_status,
                     source_file, now, shipment_id),
                )
                _upsert_containers(conn, shipment_id, shipment)
                return "UPDATE", shipment_id
            else:
                cur = conn.execute(
                    """INSERT INTO shipments
                         (tan, item_description, compagnie_maritime, port, transitaire,
                          vessel, etd, eta, document_type, status, source_file,
                          created_at, modified_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (shipment.tan_number, shipment.item_description, shipment.shipping_company,
                     shipment.port or "Port d'Alger", shipment.transitaire,
                     shipment.vessel_name, shipment.etd, shipment.eta,
                     shipment.document_type, new_status, source_file, now, now),
                )
                shipment_id = cur.lastrowid
                _upsert_containers(conn, shipment_id, shipment)
                return "INSERT", shipment_id
    finally:
        conn.close()


def update_container(container_id: int, fields: dict):
    """Update any operational field on a container. Fields dict keys must match column names."""
    if not fields:
        return
    fields = {k: v for k, v in fields.items() if k not in ("id", "shipment_id", "container_number")}
    fields["modified_at"] = datetime.utcnow().isoformat(timespec="seconds")
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [container_id]
    conn = get_connection()
    with conn:
        conn.execute(f"UPDATE containers SET {cols} WHERE id = ?", values)
    conn.close()


def export_to_csv(output_path: str):
    import csv
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.id AS shipment_id, s.tan, s.item_description, s.compagnie_maritime,
               s.port, s.transitaire, s.vessel, s.etd, s.eta, s.status,
               c.id AS container_id, c.container_number, c.size, c.seal_number,
               c.statut_container, c.date_livraison, c.site_livraison,
               c.date_depotement, c.date_restitution, c.restitue_chauffeur,
               c.commentaire
        FROM containers c
        JOIN shipments s ON s.id = c.shipment_id
        ORDER BY s.id, c.id
    """).fetchall()
    conn.close()
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            for r in rows:
                writer.writerow(dict(r))


# ══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 1: File Duplicate Detection
# ══════════════════════════════════════════════════════════════════════════════

def register_file_hash(filename: str, file_hash: str) -> bool:
    """Register a file hash. Returns True if new, False if duplicate."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO file_hashes (filename, file_hash) VALUES (?, ?)",
                (filename, file_hash)
            )
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_file_hash(filename: str) -> str | None:
    """Get cached file hash if exists."""
    conn = get_connection()
    row = conn.execute("SELECT file_hash FROM file_hashes WHERE filename = ?", (filename,)).fetchone()
    conn.close()
    return row[0] if row else None


# ══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 3, 9: Confidence Scoring
# ══════════════════════════════════════════════════════════════════════════════

def record_confidence_score(container_id: int, field_name: str, confidence: float, extracted_value: str = None):
    """Record extraction confidence for a specific field."""
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO confidence_scores (container_id, field_name, confidence, extracted_value)
               VALUES (?, ?, ?, ?)""",
            (container_id, field_name, confidence, extracted_value)
        )
    conn.close()


def get_container_confidence(container_id: int) -> dict:
    """Get average confidence for a container across all fields."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT field_name, confidence FROM confidence_scores WHERE container_id = ?",
        (container_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return {"avg_confidence": 0.0, "fields": {}}
    confidences = {r[0]: r[1] for r in rows}
    avg = sum(v for v in confidences.values()) / len(confidences)
    return {"avg_confidence": avg, "fields": confidences}


# ══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 8: Change Audit Log
# ══════════════════════════════════════════════════════════════════════════════

def log_change(container_id: int, field_name: str, old_value: str, new_value: str, changed_by: str = "system"):
    """Log a change to a container field."""
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO change_log (container_id, field_name, old_value, new_value, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            (container_id, field_name, old_value, new_value, changed_by)
        )
    conn.close()


def get_container_history(container_id: int) -> list:
    """Get full change history for a container."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT field_name, old_value, new_value, changed_by, changed_at
           FROM change_log WHERE container_id = ? ORDER BY changed_at DESC""",
        (container_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 5: Smart Filter Presets
# ══════════════════════════════════════════════════════════════════════════════

def save_filter_preset(preset_name: str, filter_config: dict) -> bool:
    """Save a filter preset."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO filter_presets (preset_name, filter_config) VALUES (?, ?)",
                (preset_name, json.dumps(filter_config))
            )
        conn.close()
        return True
    except Exception:
        conn.close()
        return False


def get_filter_preset(preset_name: str) -> dict | None:
    """Load a filter preset."""
    conn = get_connection()
    row = conn.execute("SELECT filter_config FROM filter_presets WHERE preset_name = ?", (preset_name,)).fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


def list_filter_presets() -> list:
    """List all saved filter presets."""
    conn = get_connection()
    rows = conn.execute("SELECT preset_name, created_at, last_used_at FROM filter_presets ORDER BY preset_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_filter_preset(preset_name: str):
    """Delete a filter preset."""
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM filter_presets WHERE preset_name = ?", (preset_name,))
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 7: Validation Issues
# ══════════════════════════════════════════════════════════════════════════════

def record_validation_issue(issue_type: str, field_name: str, issue_desc: str, severity: str = "warning",
                           container_id: int = None, shipment_id: int = None):
    """Record a validation issue."""
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO validation_issues (container_id, shipment_id, issue_type, field_name, issue_description, severity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (container_id, shipment_id, issue_type, field_name, issue_desc, severity)
        )
    conn.close()


def get_unresolved_issues(container_id: int = None) -> list:
    """Get unresolved validation issues."""
    conn = get_connection()
    if container_id:
        rows = conn.execute(
            """SELECT * FROM validation_issues
               WHERE is_resolved = 0 AND container_id = ? ORDER BY severity DESC, created_at DESC""",
            (container_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM validation_issues
               WHERE is_resolved = 0 ORDER BY severity DESC, created_at DESC"""
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 14: Processing Stats
# ══════════════════════════════════════════════════════════════════════════════

def increment_processing_stat(doc_type: str, success: bool, extract_time_ms: float = 0):
    """Update processing statistics."""
    conn = get_connection()
    with conn:
        existing = conn.execute("SELECT * FROM processing_stats WHERE doc_type = ?", (doc_type,)).fetchone()
        if existing:
            success_cnt = existing[2] + (1 if success else 0)
            fail_cnt = existing[3] + (0 if success else 1)
            total = existing[4] + 1
            avg_time = (existing[5] * (total - 1) + extract_time_ms) / total
            conn.execute(
                """UPDATE processing_stats
                   SET success_count = ?, fail_count = ?, total_processed = ?, avg_extract_time_ms = ?, last_updated_at = CURRENT_TIMESTAMP
                   WHERE doc_type = ?""",
                (success_cnt, fail_cnt, total, avg_time, doc_type)
            )
        else:
            conn.execute(
                """INSERT INTO processing_stats (doc_type, success_count, fail_count, total_processed, avg_extract_time_ms)
                   VALUES (?, ?, ?, ?, ?)""",
                (doc_type, 1 if success else 0, 0 if success else 1, 1, extract_time_ms)
            )
    conn.close()


def get_processing_stats() -> dict:
    """Get overall processing statistics."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM processing_stats ORDER BY doc_type").fetchall()
    conn.close()
    return {r[1]: dict(r) for r in rows}  # Key by doc_type
