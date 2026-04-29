"""
Core repository for all DB CRUD operations.
"""
from .db import get_connection

def insert_document(db_path: str, doc_data: dict) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO documents (type, raw_text, extracted_json, confidence, source_file, module)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                doc_data.get("type", "UNKNOWN"),
                doc_data.get("raw_text"),
                doc_data.get("extracted_json"),
                doc_data.get("confidence", 0.0),
                doc_data.get("source_file"),
                doc_data.get("module")
            )
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_document(db_path: str, doc_id: int) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
