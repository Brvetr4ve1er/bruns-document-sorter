import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.storage.db import get_connection, init_schema
from core.storage.exporters.family_export import generate_family_tree

def test_phase4():
    print("Testing travel pipeline and export...")
    
    os.makedirs("tests/data", exist_ok=True)
    db_path = "tests/data/travel_test.db"
    
    if os.path.exists(db_path):
        os.remove(db_path)
    init_schema(db_path)
    
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO families (family_name, case_reference) VALUES ('Doe', 'CASE-123')")
    fam_id = cur.lastrowid
    
    cur.execute("INSERT INTO persons (family_id, full_name, normalized_name, dob) VALUES (?, 'John Doe', 'JOHN DOE', '1990-01-01')", (fam_id,))
    cur.execute("INSERT INTO persons (family_id, full_name, normalized_name, dob) VALUES (?, 'Jane Doe', 'JANE DOE', '1992-05-05')", (fam_id,))
    conn.commit()
    conn.close()
    
    print("DB seeded. Generating export...")
    zip_path = generate_family_tree(db_path, "tests/data")
    
    if zip_path and os.path.exists(zip_path):
        print(f"Gate passed! Export generated at: {zip_path}")
    else:
        print("Gate failed. Export not found.")

if __name__ == "__main__":
    test_phase4()
