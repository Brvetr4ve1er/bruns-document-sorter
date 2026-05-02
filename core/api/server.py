"""
core/api/server.py

Live REST API + HTML UI server.

API endpoints (port 7845, JSON, for Power BI / external):
    GET /api/status
    GET /api/logistics/shipments?page=1&page_size=50
    GET /api/logistics/containers?...
    GET /api/logistics/shipments_full?...
    GET /api/travel/persons|families|documents

HTML UI routes (same port, server-rendered + HTMX):
    GET /                  → mode picker (splash)
    GET /logistics         → logistics dashboard
    GET /travel            → travel dashboard (P4 — placeholder for now)

Start with:
    python -m core.api.server
    or
    python core/api/server.py
"""

import json
import os
import sys

from flask import Flask, jsonify, request, abort, render_template
from flask_cors import CORS

# Allow running from root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.storage.paginator import paginated_query
from core.storage.db import get_connection

# ─── Bootstrap: register every domain's LLM prompts at server startup ─────────
# Without this, the extraction pipeline raises
#   "No prompt registered for module 'X' and doc_type 'UNKNOWN'"
# at the first upload. The modules define init_prompts() but don't auto-call it.
try:
    from modules.logistics.prompts import init_prompts as _init_logistics_prompts
    _init_logistics_prompts()
except Exception as _e:
    print(f"[WARN] failed to register logistics prompts: {_e}")
try:
    from modules.travel.prompts import init_prompts as _init_travel_prompts
    _init_travel_prompts()
except Exception as _e:
    print(f"[WARN] failed to register travel prompts: {_e}")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False   # serve French chars as UTF-8, not \uXXXX escapes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Both databases live at <repo>/data/ — one canonical location.
DATA_DIR     = os.environ.get("BRUNS_DATA_DIR", os.path.join(ROOT_DIR, "data"))
LOGISTICS_DB = os.environ.get("BRUNS_LOGISTICS_DB",
                              os.path.join(DATA_DIR, "logistics.db"))
TRAVEL_DB    = os.environ.get("BRUNS_TRAVEL_DB",
                              os.path.join(DATA_DIR, "travel.db"))

PAGE_SIZE_MAX  = 200   # hard cap — prevents BI tools from dumping the whole DB in one shot


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _page_params():
    try:
        page      = max(1, int(request.args.get("page", 1)))
        page_size = min(PAGE_SIZE_MAX, max(1, int(request.args.get("page_size", 50))))
    except (ValueError, TypeError):
        abort(400, "page and page_size must be integers")
    return page, page_size

def _rows_to_dicts(rows: list) -> list[dict]:
    """Convert sqlite3.Row objects to plain JSON-serializable dicts."""
    return [dict(r) for r in rows]

def _paginated_response(conn, table, page, page_size, where="", order_by="id DESC", params=()):
    result = paginated_query(conn, table, page, page_size, where, order_by, params)
    return jsonify({
        "data":        _rows_to_dicts(result["rows"]),
        "pagination": {
            "page":        result["page"],
            "page_size":   result["page_size"],
            "total":       result["total"],
            "total_pages": result["total_pages"],
            "has_next":    result["has_next"],
            "has_prev":    result["has_prev"],
        }
    })


# ─── System Health ─────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    checks = {}
    for label, db_path in [("logistics", LOGISTICS_DB), ("travel", TRAVEL_DB)]:
        checks[label] = "ok" if os.path.exists(db_path) else "missing"
    return jsonify({"status": "online", "databases": checks})


# ─── Logistics Endpoints ───────────────────────────────────────────────────────

@app.route("/api/logistics/shipments")
def logistics_shipments():
    if not os.path.exists(LOGISTICS_DB):
        return jsonify({"data": [], "pagination": {}}), 200
    page, page_size = _page_params()
    status = request.args.get("status")          # optional filter
    where  = "status = ?" if status else ""
    params = (status,)      if status else ()
    conn   = get_connection(LOGISTICS_DB)
    try:
        return _paginated_response(conn, "shipments", page, page_size, where, "id DESC", params)
    finally:
        conn.close()


@app.route("/api/logistics/containers")
def logistics_containers():
    if not os.path.exists(LOGISTICS_DB):
        return jsonify({"data": [], "pagination": {}}), 200
    page, page_size = _page_params()
    status = request.args.get("status")
    where  = "statut_container = ?" if status else ""
    params = (status,)              if status else ()
    conn   = get_connection(LOGISTICS_DB)
    try:
        return _paginated_response(conn, "containers", page, page_size, where, "id DESC", params)
    finally:
        conn.close()


# ─── Logistics: Flat denormalized view (one row per container) ─────────────────
# This is the primary endpoint for Power BI — no joins needed on the BI side.

@app.route("/api/logistics/shipments_full")
def logistics_shipments_full():
    """Flat JOIN of shipments + containers — one row per container, all columns."""
    if not os.path.exists(LOGISTICS_DB):
        return jsonify({"data": [], "pagination": {}}), 200

    page, page_size = _page_params()
    offset = (page - 1) * page_size

    conn = get_connection(LOGISTICS_DB)
    try:
        # Optional filters
        status    = request.args.get("status")
        carrier   = request.args.get("carrier")
        tan       = request.args.get("tan")

        where_clauses = []
        params = []
        if status:
            where_clauses.append("s.status = ?")
            params.append(status)
        if carrier:
            where_clauses.append("s.compagnie_maritime = ?")
            params.append(carrier)
        if tan:
            where_clauses.append("s.tan LIKE ?")
            params.append(f"%{tan}%")

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total = conn.execute(
            f"SELECT COUNT(*) FROM containers c JOIN shipments s ON s.id = c.shipment_id {where_sql}",
            params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT
                s.id                    AS shipment_id,
                c.id                    AS container_id,
                c.container_number      AS "N° Container",
                s.tan                   AS "N° TAN",
                s.item_description      AS "Item",
                s.compagnie_maritime    AS "Compagnie maritime",
                s.port                  AS "Port",
                s.transitaire           AS "Transitaire",
                s.vessel                AS "Navire",
                s.etd                   AS "Date shipment",
                s.eta                   AS "Date accostage",
                s.status                AS "Statut Expédition",
                s.document_type         AS "Type document",
                c.statut_container      AS "Statut Container",
                c.size                  AS "Container size",
                c.seal_number           AS "N° Seal",
                c.date_livraison        AS "Date livraison",
                c.site_livraison        AS "Site livraison",
                c.date_depotement       AS "Date dépotement",
                c.date_debut_surestarie AS "Date début Surestarie",
                c.date_restitution_estimative AS "Date restitution estimative",
                c.nbr_jours_surestarie_estimes AS "Nbr jours surestarie estimés",
                c.nbr_jours_perdu_douane       AS "Nbr jours perdu en douane",
                c.date_restitution      AS "Date réstitution",
                c.restitue_camion       AS "Réstitué par (Camion)",
                c.restitue_chauffeur    AS "Réstitué par (Chauffeur)",
                c.centre_restitution    AS "Centre de réstitution",
                c.livre_camion          AS "Livré par (Camion)",
                c.livre_chauffeur       AS "Livré par (Chauffeur)",
                c.montant_facture_check AS "Montant facturé (check)",
                c.nbr_jour_surestarie_facture AS "Nbr jour surestarie Facturé",
                c.montant_facture_da    AS "Montant facturé (DA)",
                c.taux_de_change        AS "Taux de change",
                c.n_facture_cm          AS "N° Facture compagnie maritime",
                c.commentaire           AS "Commentaire",
                c.date_declaration_douane   AS "Date declaration douane",
                c.date_liberation_douane    AS "Date liberation douane",
                s.source_file           AS "Source",
                c.created_at            AS "Créé le",
                c.modified_at           AS "Modifié le"
            FROM containers c
            JOIN shipments s ON s.id = c.shipment_id
            {where_sql}
            ORDER BY c.id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset]
        ).fetchall()

        total_pages = max(1, -(-total // page_size))  # ceiling division
        return jsonify({
            "data": _rows_to_dicts(rows),
            "pagination": {
                "page":        page,
                "page_size":   page_size,
                "total":       total,
                "total_pages": total_pages,
                "has_next":    page < total_pages,
                "has_prev":    page > 1,
            },
        })
    finally:
        conn.close()


# ─── Travel Endpoints ──────────────────────────────────────────────────────────

@app.route("/api/travel/persons")
def travel_persons():
    if not os.path.exists(TRAVEL_DB):
        return jsonify({"data": [], "pagination": {}}), 200
    page, page_size = _page_params()
    nationality = request.args.get("nationality")
    where  = "nationality = ?" if nationality else ""
    params = (nationality,)    if nationality else ()
    conn   = get_connection(TRAVEL_DB)
    try:
        return _paginated_response(conn, "persons", page, page_size, where, "id DESC", params)
    finally:
        conn.close()


@app.route("/api/travel/families")
def travel_families():
    if not os.path.exists(TRAVEL_DB):
        return jsonify({"data": [], "pagination": {}}), 200
    page, page_size = _page_params()
    conn = get_connection(TRAVEL_DB)
    try:
        return _paginated_response(conn, "families", page, page_size)
    finally:
        conn.close()


@app.route("/api/travel/documents")
def travel_documents():
    if not os.path.exists(TRAVEL_DB):
        return jsonify({"data": [], "pagination": {}}), 200
    page, page_size = _page_params()
    doc_type = request.args.get("doc_type")
    where    = "doc_type = ?" if doc_type else ""
    params   = (doc_type,)    if doc_type else ()
    conn     = get_connection(TRAVEL_DB)
    try:
        return _paginated_response(conn, "documents_travel", page, page_size, where, "id DESC", params)
    finally:
        conn.close()


# ─── HTML UI ──────────────────────────────────────────────────────────────────
# Server-rendered pages with DaisyUI (CDN) + HTMX (CDN). No build step.
# Lives alongside the JSON API on the same port (default 7845).

def _logistics_stats() -> dict:
    """Counts for the logistics dashboard hero. Returns zeroes if DB missing."""
    if not os.path.exists(LOGISTICS_DB):
        return {"shipments": 0, "containers": 0, "booked": 0, "in_transit": 0}
    conn = get_connection(LOGISTICS_DB)
    try:
        s = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        c = conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0]
        b = conn.execute("SELECT COUNT(*) FROM shipments WHERE status='BOOKED'").fetchone()[0]
        t = conn.execute(
            "SELECT COUNT(*) FROM containers WHERE statut_container IN ('IN_TRANSIT','EN_ROUTE')"
        ).fetchone()[0]
        return {"shipments": s, "containers": c, "booked": b, "in_transit": t}
    finally:
        conn.close()


def _logistics_recent_containers(limit: int = 25) -> list[dict]:
    """Most-recent containers with shipment context, denormalized."""
    if not os.path.exists(LOGISTICS_DB):
        return []
    conn = get_connection(LOGISTICS_DB)
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.container_number, c.size, c.seal_number,
                   c.statut_container, s.tan, s.compagnie_maritime,
                   s.port, s.etd, s.eta, s.source_file
            FROM containers c
            JOIN shipments s ON s.id = c.shipment_id
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.route("/")
def ui_mode_picker():
    """Splash — pick logistics or travel."""
    return render_template("mode_picker.html")


@app.route("/logistics")
def ui_logistics_dashboard():
    """Logistics dashboard — read-only in P1."""
    return render_template(
        "logistics/dashboard.html",
        mode="logistics",
        stats=_logistics_stats(),
        containers=_logistics_recent_containers(25),
    )


# ─── Travel mode (P4) ─────────────────────────────────────────────────────────
def _travel_stats() -> dict:
    if not os.path.exists(TRAVEL_DB):
        return {"persons": 0, "families": 0, "documents": 0,
                "expired_passports": 0, "unmatched_docs": 0}
    conn = get_connection(TRAVEL_DB)
    try:
        p = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        f = conn.execute("SELECT COUNT(*) FROM families").fetchone()[0]
        d = conn.execute("SELECT COUNT(*) FROM documents_travel").fetchone()[0]
        # Expired passports: doc_type starts with 'PASSPORT' and expiry_date < today
        ex = conn.execute(
            """SELECT COUNT(*) FROM documents_travel
               WHERE UPPER(doc_type) LIKE 'PASSPORT%'
                 AND expiry_date IS NOT NULL
                 AND expiry_date < date('now')"""
        ).fetchone()[0]
        # Unmatched: documents without a person_id
        un = conn.execute(
            "SELECT COUNT(*) FROM documents_travel WHERE person_id IS NULL"
        ).fetchone()[0]
        return {"persons": p, "families": f, "documents": d,
                "expired_passports": ex, "unmatched_docs": un}
    finally:
        conn.close()


def _travel_recent_persons(limit: int = 25) -> list[dict]:
    if not os.path.exists(TRAVEL_DB):
        return []
    conn = get_connection(TRAVEL_DB)
    try:
        rows = conn.execute(
            """SELECT p.id, p.full_name, p.dob, p.nationality, p.gender,
                      f.family_name,
                      (SELECT COUNT(*) FROM documents_travel WHERE person_id = p.id) AS n_docs
               FROM persons p
               LEFT JOIN families f ON f.id = p.family_id
               ORDER BY p.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.route("/travel")
def ui_travel_dashboard():
    return render_template(
        "travel/dashboard.html",
        mode="travel",
        stats=_travel_stats(),
        persons=_travel_recent_persons(20),
        db_present=os.path.exists(TRAVEL_DB),
    )


@app.route("/travel/upload", methods=["GET"])
def ui_travel_upload():
    return render_template("travel/upload.html", mode="travel")


@app.route("/travel/upload", methods=["POST"])
def ui_travel_upload_post():
    files = request.files.getlist("files")
    doc_type = request.form.get("doc_type", "UNKNOWN")
    if not files:
        return render_template("logistics/_upload_error.html",
                               error="No files received"), 400

    travel_input = os.environ.get(
        "BRUNS_TRAVEL_INPUT_DIR",
        os.path.join(ROOT_DIR, "data", "input", "travel"),
    )
    os.makedirs(travel_input, exist_ok=True)

    submitted = []
    for f in files:
        if not f or not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        safe_name = secure_filename(f.filename) or f"upload{ext}"
        unique_name = f"{secrets.token_hex(4)}_{safe_name}"
        save_path = os.path.join(travel_input, unique_name)
        f.save(save_path)
        job_id = job_tracker.submit_job(save_path, module="travel", doc_type=doc_type)
        submitted.append({"job_id": job_id, "filename": safe_name})

    if not submitted:
        return render_template("logistics/_upload_error.html",
                               error="No accepted files (allowed: .pdf, .png, .jpg, .jpeg, .webp)"), 400

    # Use a travel-specific progress fragment so polling hits /travel/process-status/
    return render_template("travel/_upload_progress.html", jobs=submitted)


@app.route("/travel/process-status/<job_id>")
def ui_travel_process_status(job_id: str):
    job = job_tracker.get_job(job_id)
    if not job:
        return f'<div class="alert alert-error">Job {job_id} not found</div>', 404
    return render_template(
        "travel/_progress_row.html",
        job=job,
        percent=job_tracker.progress_percent(job),
    )


@app.route("/travel/persons")
def ui_travel_persons():
    if not os.path.exists(TRAVEL_DB):
        return render_template("travel/persons.html", mode="travel",
                               persons=[], q="", total=0, db_present=False)
    q = (request.args.get("q") or "").strip()
    conn = get_connection(TRAVEL_DB)
    try:
        if q:
            rows = conn.execute(
                """SELECT p.id, p.full_name, p.dob, p.nationality, p.gender,
                          f.family_name,
                          (SELECT COUNT(*) FROM documents_travel WHERE person_id=p.id) AS n_docs
                   FROM persons p LEFT JOIN families f ON f.id=p.family_id
                   WHERE p.full_name LIKE ? OR p.nationality LIKE ?
                      OR f.family_name LIKE ?
                   ORDER BY p.id DESC LIMIT 200""",
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT p.id, p.full_name, p.dob, p.nationality, p.gender,
                          f.family_name,
                          (SELECT COUNT(*) FROM documents_travel WHERE person_id=p.id) AS n_docs
                   FROM persons p LEFT JOIN families f ON f.id=p.family_id
                   ORDER BY p.id DESC LIMIT 200"""
            ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        return render_template("travel/persons.html", mode="travel",
                               persons=[dict(r) for r in rows], q=q,
                               total=total, db_present=True)
    finally:
        conn.close()


@app.route("/travel/families")
def ui_travel_families():
    if not os.path.exists(TRAVEL_DB):
        return render_template("travel/families.html", mode="travel",
                               families=[], db_present=False)
    conn = get_connection(TRAVEL_DB)
    try:
        rows = conn.execute(
            """SELECT f.id, f.family_name, f.case_reference, f.address, f.notes,
                      (SELECT COUNT(*) FROM persons WHERE family_id=f.id) AS n_persons,
                      (SELECT COUNT(*) FROM documents_travel WHERE family_id=f.id) AS n_docs
               FROM families f
               ORDER BY f.id DESC"""
        ).fetchall()
        return render_template("travel/families.html", mode="travel",
                               families=[dict(r) for r in rows], db_present=True)
    finally:
        conn.close()


# ─── File serve + detail pages (split view + live edit) ──────────────────────
import mimetypes
from flask import send_file


def _doc_db_for_module(module: str) -> str:
    return TRAVEL_DB if module == "travel" else LOGISTICS_DB


@app.route("/files/<module>/<int:doc_id>")
def ui_serve_original_file(module: str, doc_id: int):
    """Serve the original uploaded file referenced by documents.id.

    Security: only files referenced by an existing row are served — no
    arbitrary path access.
    """
    if module not in ("travel", "logistics"):
        abort(404)
    db = _doc_db_for_module(module)
    if not os.path.exists(db):
        abort(404)
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT source_file FROM documents WHERE id = ? AND module = ?",
            (doc_id, module),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row["source_file"]:
        abort(404)
    path = row["source_file"]
    if not os.path.isfile(path):
        abort(404, f"Source file moved or deleted: {os.path.basename(path)}")
    mime, _ = mimetypes.guess_type(path)
    return send_file(path, mimetype=mime or "application/octet-stream")


def _fetch_travel_doc_detail(travel_doc_id: int) -> dict | None:
    """Pull a documents_travel row + its linked documents row + person."""
    if not os.path.exists(TRAVEL_DB):
        return None
    conn = get_connection(TRAVEL_DB)
    try:
        row = conn.execute(
            """
            SELECT
                dt.id              AS travel_id,
                dt.original_doc_id AS doc_id,
                dt.doc_type        AS doc_type,
                dt.doc_number      AS doc_number,
                dt.expiry_date     AS expiry_date,
                dt.mrz_raw         AS mrz_raw,
                dt.person_id       AS person_id,
                dt.family_id       AS family_id,
                p.full_name        AS person_name,
                p.dob              AS person_dob,
                p.nationality      AS person_nationality,
                p.gender           AS person_gender,
                d.source_file      AS source_file,
                d.extracted_json   AS extracted_json,
                d.confidence       AS confidence,
                d.created_at       AS created_at
            FROM documents_travel dt
            LEFT JOIN persons   p ON p.id = dt.person_id
            LEFT JOIN documents d ON d.id = dt.original_doc_id
            WHERE dt.id = ?
            """,
            (travel_doc_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@app.route("/travel/documents/<int:travel_doc_id>", methods=["GET"])
def ui_travel_document_detail(travel_doc_id: int):
    detail = _fetch_travel_doc_detail(travel_doc_id)
    if not detail:
        abort(404, f"Travel document {travel_doc_id} not found")
    parsed_extracted: dict = {}
    if detail.get("extracted_json"):
        try:
            parsed_extracted = json.loads(detail["extracted_json"])
        except Exception:
            parsed_extracted = {}
    return render_template(
        "travel/document_detail.html",
        mode="travel",
        d=detail,
        extracted=parsed_extracted,
        ext=os.path.splitext(detail.get("source_file") or "")[1].lower(),
        basename=os.path.basename(detail.get("source_file") or ""),
    )


@app.route("/travel/documents/<int:travel_doc_id>", methods=["POST"])
def ui_travel_document_update(travel_doc_id: int):
    """Inline-edit handler. Updates documents_travel + the JSON in documents."""
    if not os.path.exists(TRAVEL_DB):
        abort(404)
    fields = {
        "doc_type":    (request.form.get("doc_type") or "").strip().upper() or None,
        "doc_number":  (request.form.get("doc_number") or "").strip() or None,
        "expiry_date": (request.form.get("expiry_date") or "").strip() or None,
        "mrz_raw":     (request.form.get("mrz_raw") or "").strip() or None,
    }
    conn = get_connection(TRAVEL_DB)
    try:
        # Update domain row
        conn.execute(
            """UPDATE documents_travel
                  SET doc_type    = ?,
                      doc_number  = ?,
                      expiry_date = ?,
                      mrz_raw     = ?
                WHERE id = ?""",
            (fields["doc_type"], fields["doc_number"],
             fields["expiry_date"], fields["mrz_raw"], travel_doc_id),
        )
        # Mirror into the source documents.extracted_json so re-projecting
        # (or BI export) sees the corrected values too.
        link = conn.execute(
            "SELECT original_doc_id FROM documents_travel WHERE id = ?",
            (travel_doc_id,),
        ).fetchone()
        if link and link["original_doc_id"]:
            existing = conn.execute(
                "SELECT extracted_json FROM documents WHERE id = ?",
                (link["original_doc_id"],),
            ).fetchone()
            data = {}
            if existing and existing["extracted_json"]:
                try:
                    data = json.loads(existing["extracted_json"])
                except Exception:
                    data = {}
            for k, v in fields.items():
                if v is not None:
                    if k == "doc_number":
                        data["document_number"] = v
                    elif k == "doc_type":
                        data["document_type"] = v
                    elif k == "expiry_date":
                        data["expiry_date"] = v
                    elif k == "mrz_raw":
                        data["mrz_raw"] = v
            conn.execute(
                "UPDATE documents SET extracted_json = ? WHERE id = ?",
                (json.dumps(data), link["original_doc_id"]),
            )
        conn.commit()
        return render_template("travel/_save_result.html", ok=True,
                               msg=f"Saved — {sum(1 for v in fields.values() if v is not None)} field(s) updated.")
    except Exception as e:
        return render_template("travel/_save_result.html", ok=False,
                               msg=f"Save failed: {type(e).__name__}: {e}")
    finally:
        conn.close()


@app.route("/travel/persons/<int:person_id>", methods=["GET"])
def ui_travel_person_detail(person_id: int):
    if not os.path.exists(TRAVEL_DB):
        abort(404)
    conn = get_connection(TRAVEL_DB)
    try:
        person = conn.execute(
            """SELECT p.id, p.full_name, p.dob, p.nationality, p.gender,
                      p.family_id, f.family_name
               FROM persons p
               LEFT JOIN families f ON f.id = p.family_id
               WHERE p.id = ?""",
            (person_id,),
        ).fetchone()
        if not person:
            abort(404, f"Person {person_id} not found")
        docs = conn.execute(
            """SELECT id, doc_type, doc_number, expiry_date, original_doc_id
               FROM documents_travel
               WHERE person_id = ?
               ORDER BY id DESC""",
            (person_id,),
        ).fetchall()
        return render_template(
            "travel/person_detail.html",
            mode="travel",
            person=dict(person),
            docs=[dict(d) for d in docs],
        )
    finally:
        conn.close()


@app.route("/travel/persons/<int:person_id>", methods=["POST"])
def ui_travel_person_update(person_id: int):
    if not os.path.exists(TRAVEL_DB):
        abort(404)
    fields = {
        "full_name":   (request.form.get("full_name") or "").strip() or None,
        "dob":         (request.form.get("dob") or "").strip() or None,
        "nationality": (request.form.get("nationality") or "").strip() or None,
        "gender":      (request.form.get("gender") or "").strip() or None,
    }
    normalized = (fields["full_name"] or "").lower().strip() or None
    conn = get_connection(TRAVEL_DB)
    try:
        conn.execute(
            """UPDATE persons
                  SET full_name = ?, normalized_name = ?,
                      dob = ?, nationality = ?, gender = ?
                WHERE id = ?""",
            (fields["full_name"], normalized,
             fields["dob"], fields["nationality"], fields["gender"], person_id),
        )
        conn.commit()
        return render_template("travel/_save_result.html", ok=True,
                               msg=f"Person saved — {sum(1 for v in fields.values() if v) } field(s).")
    except Exception as e:
        return render_template("travel/_save_result.html", ok=False,
                               msg=f"Save failed: {type(e).__name__}: {e}")
    finally:
        conn.close()


@app.route("/travel/documents")
def ui_travel_documents():
    if not os.path.exists(TRAVEL_DB):
        return render_template("travel/documents.html", mode="travel",
                               documents=[], doc_type_filter="", db_present=False)
    dt = (request.args.get("type") or "").strip()
    conn = get_connection(TRAVEL_DB)
    try:
        if dt:
            rows = conn.execute(
                """SELECT d.id, d.doc_type, d.doc_number, d.expiry_date,
                          p.full_name, p.nationality, f.family_name
                   FROM documents_travel d
                   LEFT JOIN persons p ON p.id = d.person_id
                   LEFT JOIN families f ON f.id = d.family_id
                   WHERE d.doc_type = ?
                   ORDER BY d.id DESC LIMIT 300""", (dt,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT d.id, d.doc_type, d.doc_number, d.expiry_date,
                          p.full_name, p.nationality, f.family_name
                   FROM documents_travel d
                   LEFT JOIN persons p ON p.id = d.person_id
                   LEFT JOIN families f ON f.id = d.family_id
                   ORDER BY d.id DESC LIMIT 300"""
            ).fetchall()
        return render_template("travel/documents.html", mode="travel",
                               documents=[dict(r) for r in rows],
                               doc_type_filter=dt, db_present=True)
    finally:
        conn.close()


# ─── Settings (P3.4) ──────────────────────────────────────────────────────────
def _settings_overview() -> dict:
    """Collect read-only environment + config info for the settings page."""
    cfg_path = os.path.join(ROOT_DIR, "data", ".llm_config.json")
    cfg_present = os.path.exists(cfg_path)
    return {
        "data_dir":         DATA_DIR,
        "logistics_db":     LOGISTICS_DB,
        "logistics_db_ok":  os.path.exists(LOGISTICS_DB),
        "logistics_db_size": os.path.getsize(LOGISTICS_DB) if os.path.exists(LOGISTICS_DB) else 0,
        "travel_db":        TRAVEL_DB,
        "travel_db_ok":     os.path.exists(TRAVEL_DB),
        "travel_db_size":   os.path.getsize(TRAVEL_DB) if os.path.exists(TRAVEL_DB) else 0,
        "input_dir":        INPUT_DIR,
        "input_dir_ok":     os.path.isdir(INPUT_DIR),
        "input_count":      len([f for f in os.listdir(INPUT_DIR)
                                 if os.path.isfile(os.path.join(INPUT_DIR, f))])
                            if os.path.isdir(INPUT_DIR) else 0,
        "llm_cfg_path":     cfg_path,
        "llm_cfg_present":  cfg_present,
        "llm_cfg":          llm_config.load_config() if cfg_present else llm_config.DEFAULT_CONFIG,
        "active_jobs":      len([j for j in job_tracker.list_recent(50)
                                 if j.status in ("PENDING", "PROCESSING")]),
        "recent_jobs":      job_tracker.list_recent(10),
    }


@app.route("/logistics/settings", methods=["GET"])
def ui_logistics_settings():
    return render_template(
        "logistics/settings.html",
        mode="logistics",
        s=_settings_overview(),
    )


@app.route("/logistics/settings/clear-input", methods=["POST"])
def ui_logistics_clear_input():
    """Delete files in the input directory (already-processed PDFs).
    Does NOT delete from the database."""
    if not os.path.isdir(INPUT_DIR):
        return render_template("logistics/_settings_result.html",
                               ok=False, msg="Input directory not found")
    deleted = 0
    for fn in os.listdir(INPUT_DIR):
        p = os.path.join(INPUT_DIR, fn)
        if os.path.isfile(p):
            try:
                os.remove(p); deleted += 1
            except Exception:
                pass
    return render_template("logistics/_settings_result.html",
                           ok=True, msg=f"Deleted {deleted} input file(s)")


@app.route("/logistics/settings/purge-jobs", methods=["POST"])
def ui_logistics_purge_jobs():
    job_tracker._JOBS.clear()
    return render_template("logistics/_settings_result.html",
                           ok=True, msg="Cleared in-memory job history")


# ─── LLM config modal (P3.1) ──────────────────────────────────────────────────
from core.api import llm_config


@app.route("/llm/config", methods=["GET"])
def ui_llm_config_form():
    """Returns the modal body. HTMX swaps it into #llm_modal_body."""
    cfg = llm_config.load_config()
    return render_template(
        "llm/_modal_form.html",
        cfg=cfg,
        providers=llm_config.PROVIDERS,
        models=[],
        status=None,
    )


@app.route("/llm/test", methods=["POST"])
def ui_llm_test_connection():
    cfg = _llm_cfg_from_form(request.form)
    ok, msg, models = llm_config.test_connection(cfg)
    return render_template(
        "llm/_modal_form.html",
        cfg=cfg,
        providers=llm_config.PROVIDERS,
        models=models,
        status={"ok": ok, "msg": msg},
    )


@app.route("/llm/save", methods=["POST"])
def ui_llm_save():
    cfg = _llm_cfg_from_form(request.form)
    try:
        llm_config.save_config(cfg)
        return render_template(
            "llm/_modal_form.html",
            cfg=cfg,
            providers=llm_config.PROVIDERS,
            models=[],
            status={"ok": True, "msg": "Saved to data/.llm_config.json"},
        )
    except Exception as e:
        return render_template(
            "llm/_modal_form.html",
            cfg=cfg,
            providers=llm_config.PROVIDERS,
            models=[],
            status={"ok": False, "msg": f"Save failed: {e}"},
        )


def _llm_cfg_from_form(form) -> dict:
    """Coerce a multipart/form-encoded request into the cfg dict shape."""
    return {
        "provider":    form.get("provider", "ollama"),
        "base_url":    form.get("base_url", "http://localhost").strip(),
        "port":        int(form.get("port", 11434) or 11434),
        "model":       form.get("model", "").strip(),
        "api_key":     form.get("api_key", "").strip(),
        "temperature": float(form.get("temperature", 0.1) or 0.1),
        "timeout":     int(form.get("timeout", 120) or 120),
    }


# ─── Upload + HTMX progress polling (P2) ──────────────────────────────────────
import secrets
from werkzeug.utils import secure_filename
from core.api import job_tracker

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
INPUT_DIR = os.environ.get(
    "BRUNS_INPUT_DIR",
    os.path.join(ROOT_DIR, "data", "input"),
)


@app.route("/logistics/upload", methods=["GET"])
def ui_logistics_upload():
    return render_template("logistics/upload.html", mode="logistics")


@app.route("/logistics/upload", methods=["POST"])
def ui_logistics_upload_post():
    """HTMX-aware upload handler. Spawns a job per file; returns the polling fragment."""
    files = request.files.getlist("files")
    if not files:
        return render_template("logistics/_upload_error.html",
                               error="No files received"), 400

    os.makedirs(INPUT_DIR, exist_ok=True)
    submitted = []

    for f in files:
        if not f or not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        # Prefix with a short random hash so concurrent uploads of identical
        # filenames don't clobber each other on disk.
        safe_name = secure_filename(f.filename) or f"upload{ext}"
        unique_name = f"{secrets.token_hex(4)}_{safe_name}"
        save_path = os.path.join(INPUT_DIR, unique_name)
        f.save(save_path)
        job_id = job_tracker.submit_job(save_path, module="logistics")
        submitted.append({"job_id": job_id, "filename": safe_name})

    if not submitted:
        return render_template("logistics/_upload_error.html",
                               error="No accepted files (allowed: .pdf, .png, .jpg, .jpeg, .webp)"), 400

    return render_template("logistics/_upload_progress.html", jobs=submitted)


@app.route("/logistics/process-status/<job_id>")
def ui_logistics_process_status(job_id: str):
    """HTMX polling target. Returns a single job's progress row."""
    job = job_tracker.get_job(job_id)
    if not job:
        return f'<div class="alert alert-error">Job {job_id} not found</div>', 404
    return render_template(
        "logistics/_progress_row.html",
        job=job,
        percent=job_tracker.progress_percent(job),
    )


# ─── Edit container (P3.2) ────────────────────────────────────────────────────
EDITABLE_FIELDS = {
    # Status & Delivery
    "statut_container":        "text",
    "date_livraison":          "date",
    "site_livraison":          "text",
    "livre_camion":            "text",
    "livre_chauffeur":         "text",
    # Transport
    "container_number":        "text",
    "size":                    "text",
    "seal_number":             "text",
    "date_depotement":         "date",
    "date_restitution":        "date",
    "restitue_camion":         "text",
    "restitue_chauffeur":      "text",
    "centre_restitution":      "text",
    # Demurrage & Billing
    "date_debut_surestarie":   "date",
    "date_restitution_estimative": "date",
    "nbr_jours_surestarie_estimes": "number",
    "nbr_jour_surestarie_facture":  "number",
    "montant_facture_check":   "number",
    "montant_facture_da":      "number",
    "taux_de_change":          "number",
    "n_facture_cm":            "text",
    # Douane
    "date_declaration_douane": "date",
    "date_liberation_douane":  "date",
    "nbr_jours_perdu_douane":  "number",
    # Notes
    "commentaire":             "textarea",
}


def _fetch_container_row(container_id: int) -> dict | None:
    if not os.path.exists(LOGISTICS_DB):
        return None
    conn = get_connection(LOGISTICS_DB)
    try:
        row = conn.execute(
            """
            SELECT c.*, s.tan, s.compagnie_maritime, s.port, s.vessel,
                   s.etd, s.eta, s.source_file
            FROM containers c JOIN shipments s ON s.id = c.shipment_id
            WHERE c.id = ?
            """,
            (container_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@app.route("/files/logistics/shipment/<int:shipment_id>")
def ui_serve_logistics_shipment_file(shipment_id: int):
    """Serve the source PDF for a shipment (looked up from shipments.source_file)."""
    if not os.path.exists(LOGISTICS_DB):
        abort(404)
    conn = get_connection(LOGISTICS_DB)
    try:
        row = conn.execute(
            "SELECT source_file FROM shipments WHERE id = ?", (shipment_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row or not row["source_file"]:
        abort(404, "No source file recorded for this shipment")
    path = row["source_file"]
    if not os.path.isfile(path):
        # Try looking in trial_files and data/input as fallback
        base = os.path.basename(path)
        for search_dir in ("data/trial_files", "data/input", "fresh documents/logistics documents"):
            candidate = os.path.join(ROOT_DIR, search_dir, base)
            if os.path.isfile(candidate):
                path = candidate
                break
        else:
            abort(404, f"Source file not found: {base}")
    mime, _ = mimetypes.guess_type(path)
    return send_file(path, mimetype=mime or "application/pdf")


@app.route("/logistics/containers/<int:container_id>", methods=["GET"])
def ui_logistics_container_detail(container_id: int):
    """Split-view: original PDF on the left, editable form + Copy JSON on the right."""
    row = _fetch_container_row(container_id)
    if not row:
        abort(404, f"Container {container_id} not found")
    # Build the extracted JSON for display + copy button
    extracted_json = json.dumps(
        {k: v for k, v in row.items() if v is not None},
        indent=2,
        default=str,
        ensure_ascii=False,
    )
    # Find shipment_id for the file-serve route
    conn = get_connection(LOGISTICS_DB)
    try:
        ship = conn.execute(
            "SELECT id, source_file FROM shipments WHERE id = "
            "(SELECT shipment_id FROM containers WHERE id = ?)",
            (container_id,),
        ).fetchone()
        shipment_id = ship["id"] if ship else None
        source_file = ship["source_file"] if ship else None
        source_basename = os.path.basename(source_file) if source_file else None
        ext = os.path.splitext(source_file or "")[1].lower()
    finally:
        conn.close()
    has_file = bool(source_file)
    return render_template(
        "logistics/container_detail.html",
        mode="logistics",
        c=row,
        fields=EDITABLE_FIELDS,
        extracted_json=extracted_json,
        shipment_id=shipment_id,
        source_basename=source_basename,
        has_file=has_file,
        ext=ext,
    )


@app.route("/logistics/containers/<int:container_id>", methods=["POST"])
def ui_logistics_container_update(container_id: int):
    """HTMX inline-edit for a container row."""
    if not os.path.exists(LOGISTICS_DB):
        abort(404)
    updates: dict = {}
    for name, kind in EDITABLE_FIELDS.items():
        if name not in request.form:
            continue
        raw = request.form.get(name, "").strip()
        if raw == "":
            updates[name] = None
        elif kind == "number":
            try:
                updates[name] = float(raw)
            except ValueError:
                updates[name] = None
        else:
            updates[name] = raw
    if not updates:
        return render_template("logistics/_edit_result.html",
                               ok=False, msg="No fields to update",
                               container_id=container_id)
    conn = get_connection(LOGISTICS_DB)
    try:
        cols = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [container_id]
        conn.execute(
            f"UPDATE containers SET {cols}, modified_at = datetime('now') WHERE id = ?",
            params,
        )
        conn.commit()
        return render_template("logistics/_edit_result.html",
                               ok=True, msg=f"Saved — {len(updates)} field(s) updated.",
                               container_id=container_id)
    except Exception as e:
        return render_template("logistics/_edit_result.html",
                               ok=False, msg=f"DB error: {e}",
                               container_id=container_id)
    finally:
        conn.close()


@app.route("/logistics/edit/<int:container_id>", methods=["GET"])
def ui_logistics_edit(container_id: int):
    row = _fetch_container_row(container_id)
    if not row:
        abort(404, f"Container {container_id} not found")
    return render_template(
        "logistics/edit.html",
        mode="logistics",
        c=row,
        fields=EDITABLE_FIELDS,
    )


# ─── Export (P3.3) ────────────────────────────────────────────────────────────
import csv
import io
from flask import Response

# Column registry: (sql_alias, display_label). Order matters — controls XLSX/CSV order.
EXPORT_COLUMNS = [
    ("container_number",     "N° Container"),
    ("tan",                  "N° TAN"),
    ("item_description",     "Item"),
    ("compagnie_maritime",   "Compagnie maritime"),
    ("port",                 "Port"),
    ("transitaire",          "Transitaire"),
    ("vessel",               "Navire"),
    ("etd",                  "Date shipment"),
    ("eta",                  "Date accostage"),
    ("status",               "Statut Expédition"),
    ("document_type",        "Type document"),
    ("statut_container",     "Statut Container"),
    ("size",                 "Container size"),
    ("seal_number",          "N° Seal"),
    ("date_livraison",       "Date livraison"),
    ("site_livraison",       "Site livraison"),
    ("livre_camion",         "Livré par (Camion)"),
    ("livre_chauffeur",      "Livré par (Chauffeur)"),
    ("date_depotement",      "Date dépotement"),
    ("date_debut_surestarie","Date début Surestarie"),
    ("date_restitution_estimative","Date restitution estimative"),
    ("nbr_jours_surestarie_estimes","Nbr jours surestarie estimés"),
    ("nbr_jours_perdu_douane","Nbr jours perdu en douane"),
    ("date_restitution",     "Date réstitution"),
    ("restitue_camion",      "Réstitué par (Camion)"),
    ("restitue_chauffeur",   "Réstitué par (Chauffeur)"),
    ("centre_restitution",   "Centre de réstitution"),
    ("montant_facture_check","Montant facturé (check)"),
    ("nbr_jour_surestarie_facture","Nbr jour surestarie Facturé"),
    ("montant_facture_da",   "Montant facturé (DA)"),
    ("taux_de_change",       "Taux de change"),
    ("n_facture_cm",         "N° Facture compagnie maritime"),
    ("commentaire",          "Commentaire"),
    ("date_declaration_douane","Date declaration douane"),
    ("date_liberation_douane","Date liberation douane"),
    ("source_file",          "Source"),
    ("created_at",           "Créé le"),
    ("modified_at",          "Modifié le"),
]


def _export_select_clause(picked_aliases: set[str]) -> tuple[str, list[tuple[str, str]]]:
    """Build the SELECT clause + return (sql, column_list_in_picked_order)."""
    chosen = [(a, lbl) for (a, lbl) in EXPORT_COLUMNS if a in picked_aliases]
    if not chosen:
        chosen = list(EXPORT_COLUMNS)  # fallback — all columns

    # Map alias → table prefix (shipments fields vs container fields)
    SHIPMENT_FIELDS = {"tan","item_description","compagnie_maritime","port","transitaire",
                       "vessel","etd","eta","status","document_type","source_file"}

    parts = []
    for alias, label in chosen:
        prefix = "s" if alias in SHIPMENT_FIELDS else "c"
        parts.append(f'{prefix}.{alias} AS "{label}"')
    return ",\n            ".join(parts), chosen


def _export_query(picked_aliases: set[str], filters: dict):
    """Run the export query. Returns (column_labels, rows)."""
    select_sql, chosen = _export_select_clause(picked_aliases)
    where_clauses, params = [], []
    if filters.get("status"):
        where_clauses.append("c.statut_container = ?")
        params.append(filters["status"])
    if filters.get("carrier"):
        where_clauses.append("s.compagnie_maritime = ?")
        params.append(filters["carrier"])
    if filters.get("tan"):
        where_clauses.append("s.tan LIKE ?")
        params.append(f"%{filters['tan']}%")
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    conn = get_connection(LOGISTICS_DB)
    try:
        rows = conn.execute(
            f"""SELECT {select_sql}
                FROM containers c JOIN shipments s ON s.id = c.shipment_id
                {where_sql}
                ORDER BY c.id DESC""",
            params,
        ).fetchall()
        labels = [lbl for (_, lbl) in chosen]
        return labels, rows
    finally:
        conn.close()


@app.route("/logistics/export", methods=["GET"])
def ui_logistics_export():
    return render_template(
        "logistics/export.html",
        mode="logistics",
        columns=EXPORT_COLUMNS,
    )


@app.route("/logistics/export.csv")
def ui_logistics_export_csv():
    if not os.path.exists(LOGISTICS_DB):
        abort(404, "Logistics DB not found")
    picked = {c.strip() for c in request.args.get("cols", "").split(",") if c.strip()}
    filters = {k: request.args.get(k, "").strip() or None for k in ("status","carrier","tan")}
    labels, rows = _export_query(picked, filters)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(labels)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return Response(
        "﻿" + buf.getvalue(),  # BOM so Excel opens UTF-8 cleanly
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="logistics_export.csv"'},
    )


@app.route("/logistics/export.xlsx")
def ui_logistics_export_xlsx():
    if not os.path.exists(LOGISTICS_DB):
        abort(404, "Logistics DB not found")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        abort(500, "openpyxl not installed")

    picked = {c.strip() for c in request.args.get("cols", "").split(",") if c.strip()}
    filters = {k: request.args.get(k, "").strip() or None for k in ("status","carrier","tan")}
    labels, rows = _export_query(picked, filters)

    wb = Workbook()
    ws = wb.active
    ws.title = "Containers"
    ws.append(labels)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="6366F1")
    for r in rows:
        ws.append(["" if v is None else v for v in r])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col_idx, label in enumerate(labels, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(12, min(40, len(label) + 4))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="logistics_export.xlsx"'},
    )


@app.route("/logistics/edit/<int:container_id>", methods=["POST"])
def ui_logistics_edit_post(container_id: int):
    if not os.path.exists(LOGISTICS_DB):
        abort(404)

    # Coerce + collect fields that came back in the form
    updates: dict = {}
    for name, kind in EDITABLE_FIELDS.items():
        if name not in request.form:
            continue
        raw = request.form.get(name, "").strip()
        if raw == "":
            updates[name] = None
        elif kind == "number":
            try:
                updates[name] = float(raw)
            except ValueError:
                updates[name] = None
        else:
            updates[name] = raw

    if not updates:
        return render_template(
            "logistics/_edit_result.html",
            ok=False, msg="No fields to update", container_id=container_id,
        )

    conn = get_connection(LOGISTICS_DB)
    try:
        cols = ", ".join(f"{k} = ?" for k in updates.keys())
        params = list(updates.values()) + [container_id]
        conn.execute(
            f"UPDATE containers SET {cols}, modified_at = datetime('now') WHERE id = ?",
            params,
        )
        conn.commit()
        return render_template(
            "logistics/_edit_result.html",
            ok=True,
            msg=f"Updated {len(updates)} field(s)",
            container_id=container_id,
        )
    except Exception as e:
        return render_template(
            "logistics/_edit_result.html",
            ok=False, msg=f"DB error: {e}", container_id=container_id,
        )
    finally:
        conn.close()


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("BRUNS_API_PORT", 7845))
    print(f"\n{'='*60}")
    print(f"  BRUNs Document Intelligence")
    print(f"  Running at: http://localhost:{port}")
    print(f"  UI:         http://localhost:{port}/")
    print(f"  Power BI:   http://localhost:{port}/api/logistics/shipments_full")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
