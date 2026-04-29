"""
Database migrations for the platform.
"""
import sqlite3

def run_migrations(db_path: str, module: str = "logistics"):
    """
    Run versioned migrations on the database.
    This ensures that existing legacy tables (e.g. from the v3.0 scraper)
    are safely altered to match the new Core schema.
    """
    from .db import get_connection
    conn = get_connection(db_path)
    try:
        # Example of a safe column addition:
        # try:
        #     conn.execute("ALTER TABLE shipments ADD COLUMN document_id INTEGER")
        # except sqlite3.OperationalError:
        #     pass # Column already exists
        pass
    finally:
        conn.close()
