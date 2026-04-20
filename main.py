import os
import sys

from config import INPUT_DIR
from parsers.pdf_extractor import extract_text
from agents.parser_agent import parse_document
from utils.validator import parse_and_validate
from utils.logger import log_result
from db.database import init_db, upsert_shipment


def process_file(pdf_path: str) -> dict:
    filename = os.path.basename(pdf_path)
    result = {"file": filename, "status": None, "db_action": None, "error": None}

    try:
        text = extract_text(pdf_path)
    except Exception as e:
        result["status"] = "EXTRACTION_FAILED"
        result["error"] = str(e)
        log_result(filename, None, False, "SKIP", str(e))
        print(f"  [SKIP] {filename}: extraction failed — {e}")
        return result

    if not text.strip():
        result["status"] = "EMPTY_PDF"
        log_result(filename, None, False, "SKIP", "empty text")
        print(f"  [SKIP] {filename}: no text")
        return result

    raw_response, llm_error = parse_document(text)
    if llm_error:
        result["status"] = "LLM_FAILED"
        result["error"] = llm_error
        log_result(filename, None, False, "SKIP", llm_error)
        print(f"  [SKIP] {filename}: LLM — {llm_error}")
        return result

    model, raw_dict, val_error = parse_and_validate(raw_response)
    if val_error or model is None:
        result["status"] = "VALIDATION_FAILED"
        result["error"] = val_error
        log_result(filename, raw_dict, False, "SKIP", val_error)
        print(f"  [SKIP] {filename}: validation — {val_error}")
        return result

    try:
        action, shipment_id = upsert_shipment(model, source_file=filename)
    except Exception as e:
        result["status"] = "DB_ERROR"
        result["error"] = str(e)
        log_result(filename, raw_dict, True, "ERROR", str(e))
        print(f"  [ERROR] {filename}: DB — {e}")
        return result

    result["status"] = "OK"
    result["db_action"] = action
    result["shipment_id"] = shipment_id
    result["data"] = raw_dict

    log_result(filename, raw_dict, True, action)
    cargo = model.item_description or "—"
    print(f"  [OK] {filename}: {action} #{shipment_id} | {model.tan_number or '—'} | "
          f"{model.shipping_company or '?'} | {len(model.containers)} container(s) | {cargo[:40]}")
    return result


def run(export_csv: bool = False, export_xlsx: bool = False):
    init_db()
    if not os.path.isdir(INPUT_DIR):
        print(f"Input dir missing: {INPUT_DIR}")
        return []
    pdf_files = [os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR)
                 if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"No PDFs in {INPUT_DIR}")
        return []
    print(f"\nProcessing {len(pdf_files)} file(s)…\n")
    results = [process_file(p) for p in sorted(pdf_files)]
    ok = sum(1 for r in results if r["status"] == "OK")
    print(f"\nDone: {ok}/{len(results)} succeeded.")

    if export_csv:
        from db.database import export_to_csv
        from config import DB_PATH
        path = DB_PATH.replace(".db", "_export.csv")
        export_to_csv(path)
        print(f"CSV: {path}")
    if export_xlsx:
        from utils.xlsx_export import export_xlsx as _xlsx
        from config import DB_PATH
        path = DB_PATH.replace(".db", "_export.xlsx")
        _xlsx(path)
        print(f"XLSX: {path}")
    return results


if __name__ == "__main__":
    run(export_csv="--csv" in sys.argv, export_xlsx="--xlsx" in sys.argv)
