import sqlite3
import os

def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a configured SQLite connection."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    # Enforce foreign keys
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_schema(db_path: str):
    """Initialize the schema for a fresh database."""
    conn = get_connection(db_path)
    try:
        # Core tables
        conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT DEFAULT 'UNKNOWN',
            raw_text TEXT,
            extracted_json TEXT,
            confidence REAL DEFAULT 0.0,
            source_file TEXT,
            module TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            reviewed_by TEXT
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            type TEXT,
            status TEXT,
            input_json TEXT,
            result_json TEXT,
            logs_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            retries INTEGER DEFAULT 0
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            actor TEXT,
            entity_type TEXT,
            entity_id TEXT,
            before_json TEXT,
            after_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT,
            filename TEXT,
            module TEXT,
            document_id INTEGER,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS extraction_cache (
            file_hash TEXT PRIMARY KEY,
            result_json TEXT,
            prompt_version TEXT,
            cached_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            hit_count INTEGER DEFAULT 0
        )
        """)
        
        # Logistics Tables
        # NOTE (TD1 fix): column names match the LIVE database that the
        # server queries. The legacy v3.0 scraper used these exact names; do
        # not rename without coordinating with projections.py + server.py.
        # In particular:
        #   shipments.compagnie_maritime  (not "carrier")
        #   shipments.document_type       (not "doc_type")
        #   containers.statut_container   (not "statut")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tan TEXT,
            item_description TEXT,
            compagnie_maritime TEXT,
            port TEXT DEFAULT 'Port d''Alger',
            transitaire TEXT,
            vessel TEXT,
            etd TEXT,
            eta TEXT,
            document_type TEXT,
            status TEXT DEFAULT 'UNKNOWN',
            source_file TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            modified_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS containers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            container_number TEXT NOT NULL,
            size TEXT,
            seal_number TEXT,
            statut_container TEXT,
            date_livraison TEXT,
            site_livraison TEXT,
            date_depotement TEXT,
            date_debut_surestarie TEXT,
            date_restitution_estimative TEXT,
            nbr_jours_surestarie_estimes INTEGER DEFAULT 0,
            nbr_jours_perdu_douane INTEGER DEFAULT 0,
            date_restitution TEXT,
            restitue_camion TEXT,
            restitue_chauffeur TEXT,
            centre_restitution TEXT,
            livre_camion TEXT,
            livre_chauffeur TEXT,
            montant_facture_check TEXT DEFAULT 'No',
            nbr_jour_surestarie_facture INTEGER DEFAULT 0,
            montant_facture_da REAL DEFAULT 0,
            n_facture_cm TEXT,
            commentaire TEXT,
            date_declaration_douane TEXT,
            date_liberation_douane TEXT,
            taux_de_change REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            modified_at TEXT DEFAULT CURRENT_TIMESTAMP,
            modified_by TEXT,
            FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
            UNIQUE (shipment_id, container_number)
        )
        """)
        
        # Travel Tables
        conn.execute("""
        CREATE TABLE IF NOT EXISTS families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_name TEXT,
            head_person_id INTEGER,
            case_reference TEXT,
            address TEXT,
            notes TEXT,
            case_status TEXT DEFAULT 'COLLECTING',
            next_action TEXT,
            next_action_date TEXT
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER,
            full_name TEXT,
            normalized_name TEXT,
            dob TEXT,
            nationality TEXT,
            gender TEXT,
            FOREIGN KEY (family_id) REFERENCES families(id)
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS documents_travel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            family_id INTEGER,
            doc_type TEXT,
            doc_number TEXT,
            expiry_date TEXT,
            mrz_raw TEXT,
            original_doc_id INTEGER,
            FOREIGN KEY (person_id) REFERENCES persons(id),
            FOREIGN KEY (family_id) REFERENCES families(id),
            FOREIGN KEY (original_doc_id) REFERENCES documents(id)
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_a_id INTEGER,
            entity_b_id INTEGER,
            score REAL,
            status TEXT,
            resolved_by TEXT,
            resolved_at DATETIME
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS validation_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_type TEXT NOT NULL,
            field_name TEXT,
            issue_desc TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            resolved BOOLEAN DEFAULT 0,
            resolution_note TEXT,
            shipment_id INTEGER,
            container_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            FOREIGN KEY (shipment_id) REFERENCES shipments(id),
            FOREIGN KEY (container_id) REFERENCES containers(id)
        )
        """)
        
        conn.commit()
    finally:
        conn.close()
