from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td2 import TD2CodeChecker
from mrz.checker.td3 import TD3CodeChecker
from mrz.checker.mrva import MRVACodeChecker
from mrz.checker.mrvb import MRVBCodeChecker
from passporteye import read_mrz

def parse_mrz(image_path: str) -> dict | None:
    """Extract and parse MRZ data using PassportEye and mrz."""
    mrz_data = read_mrz(image_path)
    if not mrz_data:
        return None
        
    mrz_string = mrz_data.to_dict().get("raw_text", "").replace(" ", "").replace("\n", "")
    
    # Try different checkers
    for Checker in [TD3CodeChecker, TD1CodeChecker, TD2CodeChecker, MRVACodeChecker, MRVBCodeChecker]:
        try:
            checker = Checker(mrz_string)
            if checker:
                fields = checker.fields()
                return {
                    "document_type": getattr(fields, "document_type", "P"),
                    "nationality": getattr(fields, "nationality", ""),
                    "surname": getattr(fields, "surname", ""),
                    "names": getattr(fields, "name", ""),
                    "document_number": getattr(fields, "document_number", ""),
                    "dob": getattr(fields, "birth_date", ""),
                    "gender": getattr(fields, "sex", ""),
                    "expiry_date": getattr(fields, "expiry_date", ""),
                    "mrz_raw": mrz_string
                }
        except Exception:
            pass
            
    return {"mrz_raw": mrz_string}
