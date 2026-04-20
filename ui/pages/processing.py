"""
Processing Page — Phase 3
Drag-and-drop PDF upload, batch processing with live progress,
per-file result table, and error log.
"""
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

import streamlit as st
import pandas as pd

from ui.styles import COLORS


def render_processing_page():
    """Full processing dashboard page."""

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div data-aos="fade-up" style="margin-bottom: 8px;">
        <p style="color:#8C95B3; margin:0; font-size:0.95rem;">
        Upload PDF logistics documents (Booking Confirmations, Departure Notices, Bills of Lading).
        The AI will extract and store all data automatically.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Status indicator: Ollama reachability ─────────────────────────────────
    _render_ollama_status()

    st.markdown("---")

    # ── Upload zone ───────────────────────────────────────────────────────────
    st.markdown("#### 📂 Upload PDF Files")
    uploaded_files = st.file_uploader(
        "Drag & drop PDF files here or click to browse",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploader",
        help="Supports Booking Confirmations, Departure Notices, and Bills of Lading"
    )

    if not uploaded_files:
        _render_upload_placeholder()
        return

    # ── File list preview ─────────────────────────────────────────────────────
    st.markdown(f"#### 📋 {len(uploaded_files)} file(s) queued")
    preview_data = []
    for f in uploaded_files:
        size_kb = len(f.getvalue()) / 1024
        preview_data.append({
            "File": f.name,
            "Size": f"{size_kb:.1f} KB",
            "Status": "⏳ Pending"
        })
    st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)

    # ── Process button ────────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 4])
    with col1:
        process_btn = st.button(
            "🚀 Process All",
            type="primary",
            use_container_width=True,
            key="process_btn"
        )
    with col2:
        st.caption("Processing uses your local Ollama model — no data leaves your machine.")

    if not process_btn:
        return

    # ── Run processing ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ⚙️ Processing Results")

    results = []
    progress_bar = st.progress(0, text="Starting...")
    status_container = st.empty()

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from agents.parser_agent import ParserAgent
        agent = ParserAgent()
    except Exception as e:
        st.error(f"❌ Could not load parser agent: {e}")
        st.code(traceback.format_exc())
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, uploaded_file in enumerate(uploaded_files):
            pct = int((idx / len(uploaded_files)) * 100)
            progress_bar.progress(pct, text=f"Processing {uploaded_file.name}...")
            status_container.info(f"📄 Processing: **{uploaded_file.name}**")

            # Save to temp file
            tmp_path = os.path.join(tmpdir, uploaded_file.name)
            with open(tmp_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            t_start = time.time()
            try:
                result = agent.process_file(tmp_path)
                elapsed = time.time() - t_start

                if result and result.get("success"):
                    action = result.get("action", "PROCESSED")
                    containers = result.get("containers", 0)
                    tan = result.get("tan", "—")
                    results.append({
                        "File": uploaded_file.name,
                        "Status": "✅ Success",
                        "Action": action,
                        "TAN": tan,
                        "Containers": containers,
                        "Time (s)": f"{elapsed:.1f}",
                        "Error": ""
                    })
                else:
                    err = result.get("error", "Unknown error") if result else "No result returned"
                    results.append({
                        "File": uploaded_file.name,
                        "Status": "⚠️ Partial",
                        "Action": "—",
                        "TAN": "—",
                        "Containers": 0,
                        "Time (s)": f"{elapsed:.1f}",
                        "Error": str(err)[:80]
                    })

            except Exception as e:
                elapsed = time.time() - t_start
                results.append({
                    "File": uploaded_file.name,
                    "Status": "❌ Failed",
                    "Action": "—",
                    "TAN": "—",
                    "Containers": 0,
                    "Time (s)": f"{elapsed:.1f}",
                    "Error": str(e)[:80]
                })

    progress_bar.progress(100, text="Done!")
    status_container.success("✅ Batch processing complete!")

    # ── Results table ─────────────────────────────────────────────────────────
    results_df = pd.DataFrame(results)
    st.dataframe(results_df, use_container_width=True, hide_index=True)

    # ── Summary metrics ────────────────────────────────────────────────────────
    success_count = sum(1 for r in results if "✅" in r["Status"])
    fail_count = sum(1 for r in results if "❌" in r["Status"])
    partial_count = sum(1 for r in results if "⚠️" in r["Status"])
    total_containers = sum(r["Containers"] for r in results if isinstance(r["Containers"], int))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Succeeded", success_count)
    c2.metric("⚠️ Partial", partial_count)
    c3.metric("❌ Failed", fail_count)
    c4.metric("📦 Containers stored", total_containers)

    if fail_count > 0 or partial_count > 0:
        with st.expander("🔍 Error Details"):
            for r in results:
                if r["Error"]:
                    st.markdown(f"**{r['File']}** — {r['Error']}")

    st.info("🔄 Go to the **Dashboard** to view the newly imported documents.")


def _render_ollama_status():
    """Check and display Ollama connection status."""
    try:
        import requests
        import config
        resp = requests.get(config.OLLAMA_URL.replace("/api/generate", ""), timeout=3)
        if resp.status_code == 200:
            st.markdown("""
            <div style="display:inline-flex; align-items:center; gap:8px;
                        background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3);
                        border-radius:8px; padding:8px 16px; margin-bottom:12px;">
                <span style="color:#10B981; font-size:1.1rem;">●</span>
                <span style="color:#E6E9F2; font-size:0.9rem;">Ollama is running and ready</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            _ollama_warning()
    except Exception:
        _ollama_warning()


def _ollama_warning():
    st.markdown("""
    <div style="display:inline-flex; align-items:center; gap:8px;
                background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3);
                border-radius:8px; padding:8px 16px; margin-bottom:12px;">
        <span style="color:#F59E0B; font-size:1.1rem;">⚠</span>
        <span style="color:#E6E9F2; font-size:0.9rem;">Ollama not detected — processing will fail. Start Ollama first.</span>
    </div>
    """, unsafe_allow_html=True)


def _render_upload_placeholder():
    st.markdown("""
    <div style="
        border: 2px dashed rgba(99,102,241,0.3);
        border-radius: 16px;
        padding: 48px;
        text-align: center;
        color: #8C95B3;
        margin: 24px 0;
    ">
        <div style="font-size: 3rem; margin-bottom: 12px;">📄</div>
        <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; color: #E6E9F2;">
            Drop PDF files here
        </div>
        <div style="font-size: 0.9rem;">
            Supported: Booking Confirmations · Departure Notices · Bills of Lading
        </div>
        <div style="font-size: 0.85rem; margin-top: 12px; color: #6366F1;">
            All processing is local — your data never leaves this machine
        </div>
    </div>
    """, unsafe_allow_html=True)
