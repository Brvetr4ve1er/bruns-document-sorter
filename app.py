import os
import sys
import json
import sqlite3
import shutil
import tempfile
from datetime import datetime, date

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

import settings_store
from db.database import init_db, export_to_csv, update_container
from utils.xlsx_export import export_xlsx
from ui.styles import (
    inject_global_css, hero, status_badge, quick_stats_row,
    empty_state, section_header, COLORS,
)

# ─── page config MUST be first ───────────────────────────────────────────────
st.set_page_config(
    page_title="BRUNs Logistics Agent",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()

if "settings" not in st.session_state:
    st.session_state.settings = settings_store.load()
settings_store.apply_to_config(st.session_state.settings)
init_db()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_db_conn() -> sqlite3.Connection:
    import config
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_containers_view() -> pd.DataFrame:
    conn = get_db_conn()
    df = pd.read_sql_query("""
        SELECT
            c.id                 AS container_id,
            s.id                 AS shipment_id,
            c.container_number   AS "N° Container",
            s.tan                AS "N° TAN",
            s.item_description   AS "Item",
            s.compagnie_maritime AS "Compagnie maritime",
            s.port               AS "Port",
            s.transitaire        AS "Transitaire",
            s.etd                AS "Date shipment",
            s.eta                AS "Date accostage",
            c.statut_container   AS "Statut Container",
            c.size               AS "Container size",
            c.seal_number        AS "N° Seal",
            c.date_livraison     AS "Date livraison",
            c.site_livraison     AS "Site livraison",
            c.date_depotement    AS "Date dépotement",
            c.date_restitution   AS "Date restitution",
            c.restitue_chauffeur AS "Chauffeur restitution",
            c.livre_chauffeur    AS "Chauffeur livraison",
            c.commentaire        AS "Commentaire",
            s.source_file        AS "Source",
            c.created_at         AS "Créé le"
        FROM containers c
        JOIN shipments s ON s.id = c.shipment_id
        ORDER BY c.id DESC
    """, conn)
    conn.close()
    return df


def fetch_stats() -> dict:
    conn = get_db_conn()
    total_s = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
    total_c = conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0]
    booked = conn.execute("SELECT COUNT(*) FROM shipments WHERE status='BOOKED'").fetchone()[0]
    in_transit = conn.execute("SELECT COUNT(*) FROM shipments WHERE status='IN_TRANSIT'").fetchone()[0]
    by_carrier = conn.execute(
        "SELECT compagnie_maritime, COUNT(*) c FROM shipments WHERE compagnie_maritime IS NOT NULL GROUP BY compagnie_maritime ORDER BY c DESC"
    ).fetchall()
    conn.close()
    return {
        "shipments": total_s, "containers": total_c,
        "booked": booked, "in_transit": in_transit,
        "by_carrier": [(r[0], r[1]) for r in by_carrier],
    }


def get_log_files() -> list[str]:
    logs_dir = st.session_state.settings["logs_dir"]
    if not os.path.isdir(logs_dir):
        return []
    return sorted([f for f in os.listdir(logs_dir) if f.endswith(".json")], reverse=True)


def process_pdf_file(pdf_path: str, original_name: str = None) -> dict:
    from parsers.pdf_extractor import extract_text
    from agents.parser_agent import parse_document
    from utils.validator import parse_and_validate
    from utils.logger import log_result
    from db.database import upsert_shipment

    filename = original_name or os.path.basename(pdf_path)
    try:
        text = extract_text(pdf_path)
    except Exception as e:
        log_result(filename, None, False, "SKIP", str(e))
        return {"file": filename, "status": "EXTRACTION_FAILED", "error": str(e)}
    if not text.strip():
        log_result(filename, None, False, "SKIP", "empty text")
        return {"file": filename, "status": "EMPTY_PDF", "error": "No text"}
    raw, llm_error = parse_document(text)
    if llm_error:
        log_result(filename, None, False, "SKIP", llm_error)
        return {"file": filename, "status": "LLM_FAILED", "error": llm_error}
    model, raw_dict, val_error = parse_and_validate(raw)
    if val_error or model is None:
        log_result(filename, raw_dict, False, "SKIP", val_error)
        return {"file": filename, "status": "VALIDATION_FAILED", "error": val_error, "raw": raw_dict}
    try:
        action, sid = upsert_shipment(model, source_file=filename)
    except Exception as e:
        log_result(filename, raw_dict, True, "ERROR", str(e))
        return {"file": filename, "status": "DB_ERROR", "error": str(e)}
    log_result(filename, raw_dict, True, action)
    return {"file": filename, "status": "OK", "db_action": action,
            "shipment_id": sid, "data": raw_dict,
            "container_count": len(model.containers)}


def parse_date_input(s):
    if not s:
        return None
    if isinstance(s, date):
        return s
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def date_to_str(d):
    if d is None:
        return None
    if isinstance(d, (datetime, date)):
        return d.strftime("%Y-%m-%d")
    return str(d)


def render_badges_df(df: pd.DataFrame, status_col: str = "Statut Container") -> pd.DataFrame:
    """Return a copy of df where the status column is rendered as badge HTML."""
    if status_col not in df.columns:
        return df
    out = df.copy()
    out[status_col] = out[status_col].apply(lambda v: status_badge(v) if v else "")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

PAGES = [
    ("📊", "Overview",       "Dashboard"),
    ("📥", "Process PDFs",   "Ingest"),
    ("📋", "Containers",     "Tracking"),
    ("🚚", "Shipments",      "Tracking"),
    ("✏️", "Edit Container", "Operations"),
    ("📤", "Export",         "Data"),
    ("📄", "Logs",           "Data"),
    ("⚙️", "Settings",       "Config"),
]

with st.sidebar:
    st.markdown(f"""
    <div style="padding: 8px 4px 20px 4px;">
      <div style="display:flex; align-items:center; gap:10px;">
        <div style="font-size: 2rem; filter: drop-shadow(0 0 12px {COLORS["primary"]}88);">🚢</div>
        <div>
          <div style="font-weight:800; font-size:1.15rem; letter-spacing:-0.02em;
                      background: linear-gradient(135deg, #fff, #A5B4FC);
                      -webkit-background-clip: text; -webkit-text-fill-color: transparent;">BRUNs Logistics</div>
          <div style="font-size:0.72rem; color:{COLORS["text_muted"]}; text-transform:uppercase; letter-spacing:0.1em;">Local AI Agent</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigate",
        [f"{i} {n}" for i, n, _ in PAGES],
        label_visibility="collapsed",
    )
    page_name = page.split(" ", 1)[1] if page else "Overview"

    st.markdown("---")
    try:
        stats = fetch_stats()
        c1, c2 = st.columns(2)
        c1.metric("📦 Shipments", stats["shipments"])
        c2.metric("🗃️ Containers", stats["containers"])
        c1.metric("🟢 Booked", stats["booked"])
        c2.metric("🚢 Transit", stats["in_transit"])
    except Exception:
        st.info("DB warming up…")

    st.markdown("---")
    s = st.session_state.settings
    st.markdown(f"""
    <div style="font-size:0.75rem; color:{COLORS["text_muted"]}; line-height:1.6;">
      <div>🤖 Model: <code>{s["ollama_model"]}</code></div>
      <div>🔌 Ollama: <code>{s["ollama_url"].split("/api")[0]}</code></div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if page_name == "Overview":
    hero(
        "Welcome back",
        "Your local AI agent parsed every PDF — no cloud, no paid APIs, no drama.",
        "🚢",
    )

    try:
        stats = fetch_stats()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Shipments", stats["shipments"])
        c2.metric("Total Containers", stats["containers"])
        c3.metric("🟢 Booked", stats["booked"])
        c4.metric("🚢 In Transit", stats["in_transit"])
    except Exception as e:
        st.error(f"Stats error: {e}")

    st.markdown("")
    df = fetch_containers_view()

    if df.empty:
        empty_state("📭", "No containers yet",
                    "Head over to Process PDFs to import your first document.")
    else:
        col1, col2 = st.columns([2, 1])

        with col1:
            section_header("Recent Containers", "🕑", "Most recent 10 imports")
            preview = df.head(10)[["N° Container", "N° TAN", "Compagnie maritime",
                                    "Date shipment", "Date accostage",
                                    "Statut Container", "Container size"]].copy()
            # Render with HTML badges for status
            html = render_badges_df(preview).to_html(escape=False, index=False,
                                                      classes="stylish-table")
            st.markdown(f"""
            <style>
              .stylish-table {{
                width: 100%; border-collapse: collapse;
                font-size: 0.85rem; border-radius: 12px; overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,.20);
                border: 1px solid {COLORS["border"]};
              }}
              .stylish-table th {{
                background: {COLORS["bg_3"]}; color: {COLORS["text"]};
                text-transform: uppercase; font-size: 0.72rem;
                letter-spacing: 0.04em; padding: 10px 12px; text-align: left;
              }}
              .stylish-table td {{ padding: 10px 12px; border-top: 1px solid {COLORS["border"]}44; }}
              .stylish-table tbody tr {{ transition: background .15s ease; }}
              .stylish-table tbody tr:hover {{ background: rgba(99,102,241,.08); }}
            </style>
            {html}
            """, unsafe_allow_html=True)

        with col2:
            section_header("By Carrier", "⚓", "Shipment distribution")
            if stats["by_carrier"]:
                bc_df = pd.DataFrame(stats["by_carrier"], columns=["Carrier", "Shipments"])
                st.bar_chart(bc_df.set_index("Carrier"), color=COLORS["primary"])
            else:
                st.caption("— no carrier data yet")

            section_header("Container Sizes", "📏")
            size_df = df["Container size"].value_counts().reset_index()
            size_df.columns = ["Size", "Count"]
            st.bar_chart(size_df.set_index("Size"), color=COLORS["accent"])


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PROCESS PDFs
# ══════════════════════════════════════════════════════════════════════════════

elif page_name == "Process PDFs":
    hero(
        "Import documents",
        "Drop PDFs — the local LLM extracts TAN, carrier, containers, dates automatically.",
        "📥",
    )

    tab1, tab2 = st.tabs(["📁  Upload Files", "📂  Batch from Directory"])

    with tab1:
        uploaded = st.file_uploader(
            "Drop one or more PDFs here",
            type=["pdf"], accept_multiple_files=True,
        )
        save_to_input = st.checkbox(
            "💾 Keep copies in input directory", value=True,
            help="So they're available for future batch runs.",
        )

        if uploaded and st.button("🚀 Process files", type="primary", use_container_width=True):
            results = []
            progress = st.progress(0)
            status_box = st.empty()

            for i, uf in enumerate(uploaded):
                status_box.markdown(
                    f'<div class="glass-card">⏳ <strong>{uf.name}</strong> — {i+1}/{len(uploaded)}</div>',
                    unsafe_allow_html=True,
                )
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(uf.read())
                    tmp_path = tmp.name
                if save_to_input:
                    dest = os.path.join(st.session_state.settings["input_dir"], uf.name)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy(tmp_path, dest)
                r = process_pdf_file(tmp_path, original_name=uf.name)
                results.append(r)
                try: os.unlink(tmp_path)
                except Exception: pass
                progress.progress((i + 1) / len(uploaded))

            status_box.empty()
            progress.empty()

            ok = sum(1 for r in results if r["status"] == "OK")
            total_c = sum(r.get("container_count", 0) for r in results if r["status"] == "OK")

            if ok == len(results):
                st.balloons()
                st.success(f"🎉  All {len(results)} file(s) processed — **{total_c} containers** imported!")
            else:
                st.warning(f"✅ {ok}/{len(results)} succeeded — {total_c} containers. See details below.")

            for r in results:
                icon = "✅" if r["status"] == "OK" else "❌"
                cc = f" · {r.get('container_count', 0)} containers" if r["status"] == "OK" else ""
                with st.expander(f"{icon}  {r['file']}  —  {r['status']}{cc}"):
                    if r["status"] == "OK":
                        st.caption(f"Shipment #{r['shipment_id']}  ·  action: **{r['db_action']}**")
                        st.json(r.get("data", {}))
                    else:
                        st.error(r.get("error", "Unknown"))
                        if r.get("raw"):
                            st.json(r["raw"])

    with tab2:
        input_dir = st.session_state.settings["input_dir"]
        st.markdown(f"""
        <div class="glass-card">
          <div style="font-size:0.85rem; color:{COLORS["text_muted"]};">Scanning directory:</div>
          <code style="color:{COLORS["accent"]};">{input_dir}</code>
        </div>
        """, unsafe_allow_html=True)

        pdf_files = []
        if os.path.isdir(input_dir):
            pdf_files = sorted(f for f in os.listdir(input_dir) if f.lower().endswith(".pdf"))

        if pdf_files:
            st.markdown(f"**{len(pdf_files)} file(s) ready:**")
            cols = st.columns(3)
            for i, f in enumerate(pdf_files):
                cols[i % 3].markdown(f"<div class='glass-card' style='padding:10px;'>📄 {f}</div>",
                                      unsafe_allow_html=True)
        else:
            empty_state("📂", "No PDFs found", f"Drop some into {input_dir}")

        if st.button("▶ Run Batch", type="primary", disabled=not pdf_files, use_container_width=True):
            results = []
            progress = st.progress(0)
            status_box = st.empty()
            for i, f in enumerate(pdf_files):
                status_box.markdown(
                    f'<div class="glass-card">⏳ <strong>{f}</strong> — {i+1}/{len(pdf_files)}</div>',
                    unsafe_allow_html=True,
                )
                r = process_pdf_file(os.path.join(input_dir, f))
                results.append(r)
                progress.progress((i + 1) / len(pdf_files))
            status_box.empty()
            progress.empty()

            ok = sum(1 for r in results if r["status"] == "OK")
            total_c = sum(r.get("container_count", 0) for r in results if r["status"] == "OK")
            if ok == len(results):
                st.balloons()
            st.success(f"✨ {ok}/{len(results)} processed — {total_c} containers")

            for r in results:
                icon = "✅" if r["status"] == "OK" else "❌"
                with st.expander(f"{icon}  {r['file']}  —  {r['status']}"):
                    if r["status"] == "OK":
                        st.json(r.get("data", {}))
                    else:
                        st.error(r.get("error", "?"))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CONTAINERS
# ══════════════════════════════════════════════════════════════════════════════

elif page_name == "Containers":
    hero("All containers", "Filter, search, and drill down to every detail.", "📋")

    df = fetch_containers_view()
    if df.empty:
        empty_state("📦", "No containers yet", "Process some PDFs first.")
        st.stop()

    stats = fetch_stats()
    quick_stats_row(stats)

    with st.expander("🔍  Filters", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        carriers = sorted([c for c in df["Compagnie maritime"].dropna().unique()])
        f_car = c1.multiselect("Carrier", carriers, default=carriers)
        sizes = sorted([s for s in df["Container size"].dropna().unique()])
        f_size = c2.multiselect("Size", sizes, default=sizes)
        statuts = sorted([s for s in df["Statut Container"].dropna().unique()])
        f_stat = c3.multiselect("Statut", statuts, default=statuts)
        f_text = c4.text_input("🔎 Search", placeholder="TAN, container, item…")

    filt = df.copy()
    if f_car:
        filt = filt[filt["Compagnie maritime"].isin(f_car) | filt["Compagnie maritime"].isna()]
    if f_size:
        filt = filt[filt["Container size"].isin(f_size) | filt["Container size"].isna()]
    if f_stat:
        filt = filt[filt["Statut Container"].isin(f_stat) | filt["Statut Container"].isna()]
    if f_text:
        p = f_text.lower()
        filt = filt[
            filt["N° Container"].fillna("").str.lower().str.contains(p) |
            filt["N° TAN"].fillna("").str.lower().str.contains(p) |
            filt["Item"].fillna("").str.lower().str.contains(p)
        ]

    st.markdown(
        f'<div style="color:{COLORS["text_muted"]}; font-size:0.9rem; margin:6px 0 10px;">'
        f'Showing <strong style="color:{COLORS["text"]};">{len(filt)}</strong> of '
        f'<strong>{len(df)}</strong> containers</div>',
        unsafe_allow_html=True,
    )

    st.dataframe(
        filt.drop(columns=["container_id", "shipment_id"]),
        use_container_width=True, hide_index=True, height=580,
        column_config={
            "Date shipment":   st.column_config.DateColumn("ETD"),
            "Date accostage":  st.column_config.DateColumn("ETA"),
            "Date livraison":  st.column_config.DateColumn(),
            "Date dépotement": st.column_config.DateColumn(),
            "Date restitution": st.column_config.DateColumn(),
            "Créé le":         st.column_config.DatetimeColumn(),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SHIPMENTS
# ══════════════════════════════════════════════════════════════════════════════

elif page_name == "Shipments":
    hero("Shipments", "Every booking, every voyage — grouped by TAN.", "🚚")

    conn = get_db_conn()
    df = pd.read_sql_query("""
        SELECT s.id, s.tan, s.vessel, s.compagnie_maritime AS carrier,
               s.transitaire, s.item_description AS item,
               s.etd, s.eta, s.status, s.document_type, s.source_file,
               (SELECT COUNT(*) FROM containers c WHERE c.shipment_id = s.id) AS containers
        FROM shipments s ORDER BY s.id DESC
    """, conn)
    conn.close()

    if df.empty:
        empty_state("🚚", "No shipments yet", "Import some PDFs to get started.")
        st.stop()

    with st.expander("🔍 Filters", expanded=True):
        c1, c2 = st.columns(2)
        carriers = sorted([c for c in df["carrier"].dropna().unique()])
        f_car = c1.multiselect("Carrier", carriers, default=carriers)
        f_status = c2.multiselect("Status", sorted(df["status"].unique()), default=sorted(df["status"].unique()))
        f_txt = st.text_input("🔎 Search", placeholder="TAN, vessel, item…")

    filt = df.copy()
    if f_car:
        filt = filt[filt["carrier"].isin(f_car) | filt["carrier"].isna()]
    if f_status:
        filt = filt[filt["status"].isin(f_status)]
    if f_txt:
        p = f_txt.lower()
        filt = filt[
            filt["tan"].fillna("").str.lower().str.contains(p) |
            filt["vessel"].fillna("").str.lower().str.contains(p) |
            filt["item"].fillna("").str.lower().str.contains(p)
        ]

    st.caption(f"Showing **{len(filt)}** of **{len(df)}** shipments")
    st.dataframe(filt, use_container_width=True, hide_index=True, height=500)

    st.markdown("---")
    section_header("Delete Shipment", "🗑", "Containers cascade-delete")
    ids = filt["id"].tolist()
    if ids:
        c1, c2 = st.columns([1, 3])
        del_id = c1.selectbox("Shipment ID", ids)
        if c2.button("⚠️ Delete cascade", type="secondary"):
            conn = get_db_conn()
            with conn:
                conn.execute("DELETE FROM shipments WHERE id=?", (int(del_id),))
            conn.close()
            st.toast(f"Shipment #{del_id} deleted", icon="🗑")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: EDIT CONTAINER
# ══════════════════════════════════════════════════════════════════════════════

elif page_name == "Edit Container":
    hero("Edit container", "Fill in ops fields — delivery, demurrage, drivers, douane.", "✏️")

    df = fetch_containers_view()
    if df.empty:
        empty_state("✏️", "Nothing to edit", "Import some containers first.")
        st.stop()

    labels = [f"#{r.container_id}  ·  {r['N° Container']}  ·  {r['N° TAN'] or '—'}"
              for r in df.itertuples()]
    idx = st.selectbox("Pick a container", range(len(labels)), format_func=lambda i: labels[i])
    row = df.iloc[idx]
    cid = int(row["container_id"])

    conn = get_db_conn()
    c_row = conn.execute("SELECT * FROM containers WHERE id = ?", (cid,)).fetchone()
    conn.close()
    c = dict(c_row)

    # Header card
    st.markdown(f"""
    <div class="hero-banner" style="padding:18px 22px; margin-top: -6px;">
      <div style="display:flex; gap:20px; align-items:center; flex-wrap:wrap;">
        <div style="font-size:2.2rem;">📦</div>
        <div>
          <div style="font-size:1.2rem; font-weight:700;">{c['container_number']}</div>
          <div style="color:{COLORS["text_muted"]}; font-size:0.85rem;">
            Shipment #{c['shipment_id']}  ·  {row["N° TAN"] or "no TAN"}  ·  {row["Compagnie maritime"] or "—"}
          </div>
        </div>
        <div style="margin-left:auto;">{status_badge(c.get("statut_container") or "En transit")}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("edit_container"):
        tab_a, tab_b, tab_c, tab_d = st.tabs(
            ["📦  Status & Delivery", "🚛  Transport", "💶  Demurrage & Billing", "🛃  Douane"]
        )

        with tab_a:
            colA, colB, colC = st.columns(3)
            statuts = ["Réservé", "En transit", "Arrivé", "Livré", "Dépoté", "Restitué"]
            statut = colA.selectbox("Statut Container", statuts,
                                    index=statuts.index(c.get("statut_container") or "En transit"))
            sizes_list = ["40 feet", "20 feet", "40 feet refrigerated", "20 feet refrigerated"]
            size = colB.selectbox("Container size", sizes_list,
                                  index=sizes_list.index(c.get("size") or "40 feet"))
            site_list = ["", "Rouiba", "Boudouaou", "Other"]
            site = colC.selectbox("Site livraison", site_list,
                                  index=site_list.index(c.get("site_livraison") or ""))

            colD, colE, colF = st.columns(3)
            date_liv = colD.date_input("Date livraison", value=parse_date_input(c.get("date_livraison")))
            date_dep = colE.date_input("Date dépotement", value=parse_date_input(c.get("date_depotement")))
            date_rest = colF.date_input("Date réstitution", value=parse_date_input(c.get("date_restitution")))

        with tab_b:
            colG, colH = st.columns(2)
            livre_cam = colG.text_input("🚛 Livré par (Camion)", value=c.get("livre_camion") or "")
            livre_ch = colG.text_input("👤 Livré par (Chauffeur)", value=c.get("livre_chauffeur") or "")
            rest_cam = colH.text_input("🚛 Réstitué par (Camion)", value=c.get("restitue_camion") or "")
            rest_ch = colH.text_input("👤 Réstitué par (Chauffeur)", value=c.get("restitue_chauffeur") or "")
            centre = st.text_input("🏢 Centre de réstitution", value=c.get("centre_restitution") or "")

        with tab_c:
            colI, colJ, colK = st.columns(3)
            date_debut_sur = colI.date_input("Date début Surestarie", value=parse_date_input(c.get("date_debut_surestarie")))
            date_rest_est = colJ.date_input("Date restitution estimative", value=parse_date_input(c.get("date_restitution_estimative")))
            taux = colK.number_input("Taux de change", value=float(c.get("taux_de_change") or 0), step=0.01)

            colL, colM, colN = st.columns(3)
            jours_est = colL.number_input("Jours surestarie estimés", value=int(c.get("nbr_jours_surestarie_estimes") or 0), step=1)
            jours_douane = colM.number_input("Jours perdu en douane", value=int(c.get("nbr_jours_perdu_douane") or 0), step=1)
            jours_facture = colN.number_input("Jours surestarie facturés", value=int(c.get("nbr_jour_surestarie_facture") or 0), step=1)

            colO, colP, colQ = st.columns(3)
            facture_check = colO.selectbox("Montant facturé (check)", ["No", "Yes"],
                                           index=0 if (c.get("montant_facture_check") or "No") == "No" else 1)
            montant = colP.number_input("Montant facturé (DA)", value=float(c.get("montant_facture_da") or 0), step=1.0)
            n_facture = colQ.text_input("N° Facture compagnie", value=c.get("n_facture_cm") or "")

        with tab_d:
            colR, colS = st.columns(2)
            date_decl = colR.date_input("Date déclaration douane", value=parse_date_input(c.get("date_declaration_douane")))
            date_lib = colS.date_input("Date libération douane", value=parse_date_input(c.get("date_liberation_douane")))
            comment = st.text_area("💬 Commentaire", value=c.get("commentaire") or "", height=100)

        st.markdown("")
        submitted = st.form_submit_button("💾 Save changes", type="primary", use_container_width=True)

    if submitted:
        update_container(cid, {
            "statut_container": statut,
            "size": size,
            "site_livraison": site or None,
            "date_livraison": date_to_str(date_liv),
            "date_depotement": date_to_str(date_dep),
            "date_restitution": date_to_str(date_rest),
            "livre_camion": livre_cam or None,
            "livre_chauffeur": livre_ch or None,
            "restitue_camion": rest_cam or None,
            "restitue_chauffeur": rest_ch or None,
            "centre_restitution": centre or None,
            "date_debut_surestarie": date_to_str(date_debut_sur),
            "date_restitution_estimative": date_to_str(date_rest_est),
            "taux_de_change": taux,
            "nbr_jours_surestarie_estimes": jours_est,
            "nbr_jours_perdu_douane": jours_douane,
            "nbr_jour_surestarie_facture": jours_facture,
            "montant_facture_check": facture_check,
            "montant_facture_da": montant,
            "n_facture_cm": n_facture or None,
            "date_declaration_douane": date_to_str(date_decl),
            "date_liberation_douane": date_to_str(date_lib),
            "commentaire": comment or None,
        })
        st.toast("Saved ✨", icon="✅")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: EXPORT
# ══════════════════════════════════════════════════════════════════════════════

elif page_name == "Export":
    hero("Export data", "Download your containers in the exact target format — 49 columns, ready for Excel.", "📤")

    import config
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding:24px;">
          <div style="font-size:3rem;">📗</div>
          <h3 style="margin:8px 0 4px;">XLSX (target format)</h3>
          <p style="color:#8C95B3; margin:0 0 16px; font-size:0.85rem;">Matches <strong>Containers actifs</strong> — 49 columns.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔧 Generate XLSX", type="primary", use_container_width=True, key="gen_xlsx"):
            path = config.DB_PATH.replace(".db", f"_containers_actifs_{ts}.xlsx")
            export_xlsx(path)
            st.session_state["_xlsx_path"] = path
            st.toast("XLSX ready — download button below", icon="📗")
        if st.session_state.get("_xlsx_path") and os.path.exists(st.session_state["_xlsx_path"]):
            with open(st.session_state["_xlsx_path"], "rb") as f:
                st.download_button(
                    "⬇  Download XLSX", data=f,
                    file_name=os.path.basename(st.session_state["_xlsx_path"]),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    with col2:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding:24px;">
          <div style="font-size:3rem;">📄</div>
          <h3 style="margin:8px 0 4px;">CSV (flat dump)</h3>
          <p style="color:#8C95B3; margin:0 0 16px; font-size:0.85rem;">Quick analysis in any tool.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔧 Generate CSV", use_container_width=True, key="gen_csv"):
            path = config.DB_PATH.replace(".db", f"_export_{ts}.csv")
            export_to_csv(path)
            st.session_state["_csv_path"] = path
            st.toast("CSV ready", icon="📄")
        if st.session_state.get("_csv_path") and os.path.exists(st.session_state["_csv_path"]):
            with open(st.session_state["_csv_path"], "rb") as f:
                st.download_button(
                    "⬇  Download CSV", data=f,
                    file_name=os.path.basename(st.session_state["_csv_path"]),
                    mime="text/csv", use_container_width=True,
                )

    st.markdown("---")
    section_header("Preview", "👀", "First 20 rows of current dataset")
    df = fetch_containers_view()
    if not df.empty:
        st.dataframe(df.head(20), use_container_width=True, hide_index=True, height=420)
    else:
        empty_state("📭", "No data", "Import PDFs first.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: LOGS
# ══════════════════════════════════════════════════════════════════════════════

elif page_name == "Logs":
    hero("Processing logs", "Every PDF has a trail — browse, filter, inspect.", "📄")

    logs_dir = st.session_state.settings["logs_dir"]
    files = get_log_files()
    if not files:
        empty_state("📭", f"No logs in", logs_dir)
        st.stop()

    data = []
    for fn in files:
        try:
            with open(os.path.join(logs_dir, fn), "r", encoding="utf-8") as f:
                rec = json.load(f)
            data.append({
                "file": rec.get("filename", fn),
                "timestamp": rec.get("timestamp", ""),
                "ok": "✅" if rec.get("validation_ok") else "❌",
                "action": rec.get("db_action", "—"),
                "error": rec.get("error") or "—",
                "_fn": fn,
            })
        except Exception:
            data.append({"file": fn, "timestamp": "", "ok": "?", "action": "?", "error": "unreadable", "_fn": fn})

    df = pd.DataFrame(data)
    success_count = (df["ok"] == "✅").sum()
    error_count = (df["ok"] == "❌").sum()

    c1, c2, c3 = st.columns([1, 1, 2])
    c1.metric("✅ Success", int(success_count))
    c2.metric("❌ Errors", int(error_count))
    if c3.button("🗑 Clear all logs", use_container_width=False):
        for f in files:
            os.remove(os.path.join(logs_dir, f))
        st.toast("Logs cleared", icon="🧹")
        st.rerun()

    flt = st.radio("Filter", ["All", "Success only", "Errors only"], horizontal=True)
    disp = df.copy()
    if flt == "Success only":
        disp = disp[disp["ok"] == "✅"]
    elif flt == "Errors only":
        disp = disp[disp["ok"] == "❌"]
    st.dataframe(disp.drop(columns=["_fn"]), use_container_width=True, hide_index=True, height=360)

    st.markdown("---")
    section_header("Inspect entry", "🔎")
    sel = st.selectbox("Log file", files)
    if sel:
        with open(os.path.join(logs_dir, sel), "r", encoding="utf-8") as f:
            st.json(json.load(f))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

elif page_name == "Settings":
    hero("Settings", "All knobs in one place — runs fully local.", "⚙️")

    s = st.session_state.settings

    with st.form("settings_form"):
        section_header("Ollama / LLM", "🤖")
        c1, c2 = st.columns(2)
        url = c1.text_input("Ollama URL", value=s["ollama_url"])
        model = c2.text_input("Model", value=s["ollama_model"],
                              help="llama3, mistral, phi3, gemma2, qwen2.5, etc.")
        timeout = st.slider("Timeout (seconds)", 30, 600, int(s["ollama_timeout"]), step=10)
        chars = st.slider("Max chars sent to LLM", 1000, 30000, int(s["text_char_limit"]), step=500)

        section_header("Paths", "📁")
        in_dir = st.text_input("Input directory", value=s["input_dir"])
        log_dir = st.text_input("Logs directory", value=s["logs_dir"])
        db = st.text_input("Database path", value=s["db_path"])

        st.markdown("")
        submitted = st.form_submit_button("💾 Save settings", type="primary", use_container_width=True)

    if submitted:
        new = {
            "ollama_url": url.strip(), "ollama_model": model.strip(),
            "ollama_timeout": timeout, "text_char_limit": chars,
            "input_dir": in_dir.strip(), "logs_dir": log_dir.strip(), "db_path": db.strip(),
        }
        settings_store.save(new)
        settings_store.apply_to_config(new)
        st.session_state.settings = new
        st.toast("Settings saved", icon="✨")
        st.rerun()

    st.markdown("---")
    section_header("Connection test", "🔌")
    if st.button("Test Ollama", use_container_width=False):
        import requests
        try:
            r = requests.get(s["ollama_url"].replace("/api/generate", "/api/tags"), timeout=5)
            if r.status_code == 200:
                tags = r.json().get("models", [])
                names = ", ".join(m.get('name', '?') for m in tags)
                st.success(f"✅ Ollama is up — {len(tags)} model(s): {names}")
            else:
                st.warning(f"⚠️ HTTP {r.status_code}")
        except Exception as e:
            st.error(f"❌ {e}\n\nStart it with: `ollama serve`")

    st.markdown("---")
    section_header("Database", "🗄️")
    c1, c2 = st.columns(2)
    if c1.button("🔧 Re-init tables", use_container_width=True):
        init_db()
        st.toast("Tables ensured", icon="🔧")
    if c2.button("⚠️ Wipe all data", type="secondary", use_container_width=True):
        conn = get_db_conn()
        with conn:
            conn.execute("DELETE FROM containers")
            conn.execute("DELETE FROM shipments")
        conn.close()
        st.toast("All data wiped", icon="🧹")
        st.rerun()

    st.markdown("---")
    with st.expander("🔬 Current settings dump"):
        st.json(s)
