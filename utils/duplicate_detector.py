"""IMPROVEMENT 1: Duplicate Detection & Merge"""
import sqlite3
from database_logic.database import get_connection, register_file_hash, get_file_hash
from utils.file_hasher import compute_file_hash


def is_duplicate_file(file_path: str, filename: str) -> tuple[bool, str | None]:
    """Check if file is a duplicate. Returns (is_duplicate, cached_extraction)."""
    try:
        file_hash = compute_file_hash(file_path)
        existing_hash = get_file_hash(filename)

        if existing_hash and existing_hash == file_hash:
            # Exact duplicate by hash
            return True, None

        # Register new hash
        is_new = register_file_hash(filename, file_hash)
        return not is_new, None
    except Exception as e:
        print(f"Duplicate check error: {e}")
        return False, None


def find_duplicate_containers(container_number: str, exclude_container_id: int = None) -> list:
    """Find containers with the same number (potential duplicates)."""
    conn = get_connection()
    if exclude_container_id:
        rows = conn.execute(
            """SELECT id, shipment_id, container_number, statut_container, created_at
               FROM containers
               WHERE container_number = ? AND id != ?
               ORDER BY created_at DESC""",
            (container_number, exclude_container_id)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, shipment_id, container_number, statut_container, created_at
               FROM containers
               WHERE container_number = ?
               ORDER BY created_at DESC""",
            (container_number,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def merge_containers(primary_id: int, secondary_ids: list, keep_newer: bool = True):
    """Merge secondary containers into primary. Returns count merged."""
    conn = get_connection()
    count = 0
    with conn:
        for sec_id in secondary_ids:
            # Get both records
            primary = conn.execute("SELECT * FROM containers WHERE id = ?", (primary_id,)).fetchone()
            secondary = conn.execute("SELECT * FROM containers WHERE id = ?", (sec_id,)).fetchone()

            if not primary or not secondary:
                continue

            # Merge operational fields (prefer non-null)
            updates = {}
            for field in ["date_livraison", "site_livraison", "date_depotement", "date_restitution",
                         "restitue_camion", "restitue_chauffeur", "centre_restitution",
                         "livre_camion", "livre_chauffeur", "date_declaration_douane",
                         "date_liberation_douane", "commentaire", "taux_de_change"]:
                if secondary[field] and not primary[field]:
                    updates[field] = secondary[field]

            # Apply merged updates
            if updates:
                cols = ", ".join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [primary_id]
                conn.execute(f"UPDATE containers SET {cols} WHERE id = ?", values)

            # Delete secondary
            conn.execute("DELETE FROM containers WHERE id = ?", (sec_id,))
            count += 1
    conn.close()
    return count
