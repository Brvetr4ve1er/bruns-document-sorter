import os
import zipfile
import pandas as pd
from datetime import datetime
from ..db import get_connection

def generate_family_tree(db_path: str, output_root: str):
    """
    Generate physical folder tree per family, export family data to XLSX,
    and bundle it into a ZIP archive.
    """
    conn = get_connection(db_path)
    try:
        families_df = pd.read_sql_query("SELECT * FROM families", conn)
        if families_df.empty:
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = os.path.join(output_root, f"export_{timestamp}")
        os.makedirs(export_dir, exist_ok=True)
        
        for _, family in families_df.iterrows():
            family_name = str(family.get("family_name", f"Family_{family['id']}"))
            fam_dir = os.path.join(export_dir, family_name)
            os.makedirs(fam_dir, exist_ok=True)
            
            # Fetch persons
            persons_df = pd.read_sql_query(
                "SELECT * FROM persons WHERE family_id = ?", 
                conn, 
                params=(family['id'],)
            )
            
            # Create a summary Excel for the family
            excel_path = os.path.join(fam_dir, f"{family_name}_summary.xlsx")
            with pd.ExcelWriter(excel_path) as writer:
                persons_df.to_excel(writer, sheet_name="Persons", index=False)
                
        # Zip it up
        zip_path = os.path.join(output_root, f"travel_export_{timestamp}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(export_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=export_dir)
                    zipf.write(file_path, arcname)
                    
        return zip_path
    finally:
        conn.close()
