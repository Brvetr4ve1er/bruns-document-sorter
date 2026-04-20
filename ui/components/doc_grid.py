"""
Document grid component — Phase 3
- Liquid glass cards with AOS stagger
- Real double-click detection
- Keyboard navigation (Arrow keys, Enter, Esc)
- Pagination for large datasets
- Configurable column count (from settings)
"""
import streamlit as st
import pandas as pd
from ui.styles import COLORS, STATUS_STYLE


# ─── JavaScript injected once per page load ────────────────────────────────────
_JS_INTERACTIONS = """
<script>
(function() {
    // Run after Streamlit finishes rendering
    function initCards() {
        const cards = document.querySelectorAll('[data-doc-card]');
        if (!cards.length) return;

        // ── Double-click detection ────────────────────────────────────────────
        cards.forEach(card => {
            let clicks = 0, timer = null;
            card.style.cursor = 'pointer';
            card.tabIndex = 0;  // keyboard focus

            card.addEventListener('click', function(e) {
                clicks++;
                if (clicks === 1) {
                    timer = setTimeout(() => { clicks = 0; }, 350);
                } else if (clicks >= 2) {
                    clearTimeout(timer);
                    clicks = 0;
                    const btn = card.querySelector('[data-view-btn]');
                    if (btn) btn.click();
                }
            });
        });

        // ── Keyboard navigation (arrow keys + Enter + Escape) ─────────────────
        let focusedIdx = -1;
        const cardArr = Array.from(cards);

        function focusCard(idx) {
            if (idx < 0 || idx >= cardArr.length) return;
            focusedIdx = idx;
            cardArr.forEach((c, i) => {
                if (i === idx) {
                    c.style.outline = '2px solid #6366F1';
                    c.style.outlineOffset = '3px';
                    c.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    c.focus();
                } else {
                    c.style.outline = 'none';
                }
            });
        }

        document.addEventListener('keydown', function(e) {
            // Only activate keyboard nav when not typing in an input
            if (document.activeElement.tagName === 'INPUT' ||
                document.activeElement.tagName === 'TEXTAREA' ||
                document.activeElement.tagName === 'SELECT') return;

            switch(e.key) {
                case 'ArrowRight':
                case 'ArrowDown':
                    e.preventDefault();
                    focusCard(focusedIdx + 1);
                    break;
                case 'ArrowLeft':
                case 'ArrowUp':
                    e.preventDefault();
                    focusCard(Math.max(0, focusedIdx - 1));
                    break;
                case 'Enter':
                    if (focusedIdx >= 0) {
                        const btn = cardArr[focusedIdx].querySelector('[data-view-btn]');
                        if (btn) btn.click();
                    }
                    break;
                case 'Escape':
                    // Find and click any close button
                    const closeBtn = document.querySelector('[data-close-viewer]');
                    if (closeBtn) closeBtn.click();
                    focusedIdx = -1;
                    cardArr.forEach(c => { c.style.outline = 'none'; });
                    break;
                case 'Home':
                    e.preventDefault();
                    focusCard(0);
                    break;
                case 'End':
                    e.preventDefault();
                    focusCard(cardArr.length - 1);
                    break;
            }
        });

        // Focus on first card when 'f' is pressed (shortcut)
        document.addEventListener('keydown', function(e) {
            if (e.key === 'f' && !e.ctrlKey && !e.metaKey &&
                document.activeElement.tagName !== 'INPUT' &&
                document.activeElement.tagName !== 'TEXTAREA') {
                focusCard(0);
            }
        });
    }

    // Try immediately, then retry after Streamlit re-renders
    initCards();
    setTimeout(initCards, 500);
    setTimeout(initCards, 1500);

    // Wire data-view-btn attribute on hidden buttons
    function wireViewBtns() {
        document.querySelectorAll('button[data-viewbtn-id]').forEach(btn => {
            btn.setAttribute('data-view-btn', 'true');
        });
    }
    setTimeout(wireViewBtns, 300);
    setTimeout(wireViewBtns, 1000);
})();
</script>
"""


def render_document_grid(df: pd.DataFrame, columns: int = 3):
    """
    Render interactive document grid with AOS animations, keyboard nav, and pagination.
    """
    if df.empty:
        st.info("📭 No documents match your filters. Try adjusting the search or filters above.")
        return

    # Load settings for cards_per_page and grid_columns override
    try:
        import json, os
        from pathlib import Path
        settings_path = Path(__file__).parent.parent.parent / "data" / "ui_settings.json"
        if settings_path.exists():
            with open(settings_path) as f:
                ui_settings = json.load(f)
            columns = ui_settings.get("grid_columns", columns)
            cards_per_page = ui_settings.get("cards_per_page", 50)
        else:
            cards_per_page = 50
    except Exception:
        cards_per_page = 50

    # ── Pagination ─────────────────────────────────────────────────────────────
    total = len(df)
    total_pages = max(1, (total + cards_per_page - 1) // cards_per_page)

    if "grid_page" not in st.session_state:
        st.session_state.grid_page = 0

    # Reset page if filters changed
    if st.session_state.grid_page >= total_pages:
        st.session_state.grid_page = 0

    page = st.session_state.grid_page
    page_df = df.iloc[page * cards_per_page : (page + 1) * cards_per_page]

    # Header row
    hcol1, hcol2 = st.columns([3, 2])
    with hcol1:
        st.markdown(
            f"<div style='color:#8C95B3; font-size:0.875rem; padding:4px 0;'>"
            f"Showing <b style='color:#E6E9F2'>{len(page_df)}</b> of "
            f"<b style='color:#E6E9F2'>{total:,}</b> containers"
            f"{'  —  Page ' + str(page+1) + ' / ' + str(total_pages) if total_pages > 1 else ''}"
            f"  <span style='color:#6366F1; font-size:0.8rem;'>Press F to focus cards, ← → to navigate, Enter to open</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with hcol2:
        if total_pages > 1:
            pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
            with pcol1:
                if st.button("◀ Prev", key="grid_prev", disabled=page == 0):
                    st.session_state.grid_page -= 1
                    st.rerun()
            with pcol2:
                st.markdown(
                    f"<div style='text-align:center; color:#8C95B3; font-size:0.85rem; padding-top:8px;'>"
                    f"Page {page+1} / {total_pages}</div>",
                    unsafe_allow_html=True
                )
            with pcol3:
                if st.button("Next ▶", key="grid_next", disabled=page >= total_pages - 1):
                    st.session_state.grid_page += 1
                    st.rerun()

    # Inject JS once per render
    st.markdown(_JS_INTERACTIONS, unsafe_allow_html=True)

    # ── Card grid ──────────────────────────────────────────────────────────────
    cols = st.columns(columns)
    for idx, (_, row) in enumerate(page_df.iterrows()):
        global_idx = page * cards_per_page + idx
        with cols[idx % columns]:
            _render_card(row, global_idx)


def _render_card(row: pd.Series, card_id: int):
    """Render a single glass document card."""
    container  = str(row.get("N° Container", "—"))
    tan        = str(row.get("N° TAN", "—"))
    item       = str(row.get("Item", "—"))
    item_short = (item[:38] + "…") if len(item) > 38 else item
    status     = str(row.get("Statut Container", "UNKNOWN"))
    carrier    = str(row.get("Compagnie maritime", "—"))
    size       = str(row.get("Container size", "—"))
    port       = str(row.get("Port", "—"))
    eta        = str(row.get("Date accostage", "—"))
    etd        = str(row.get("Date shipment", "—"))

    status_info = STATUS_STYLE.get(
        status,
        ("rgba(99,102,241,0.1)", "rgba(99,102,241,0.5)", "📦")
    )
    status_bg, status_color, status_emoji = status_info

    # AOS delay capped so large lists don't have massive delays
    aos_delay = min(card_id * 40, 500)

    st.markdown(f"""
    <div data-doc-card="{card_id}"
         data-aos="fade-up"
         data-aos-delay="{aos_delay}"
         data-aos-duration="550"
         style="
            background: linear-gradient(135deg, rgba(20,26,46,0.65), rgba(27,35,65,0.45));
            backdrop-filter: blur(12px) saturate(180%);
            -webkit-backdrop-filter: blur(12px) saturate(180%);
            border: 1px solid rgba(99,102,241,.22);
            border-radius: 16px;
            padding: 18px;
            cursor: pointer;
            transition: transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1),
                        box-shadow 0.28s ease,
                        border-color 0.2s ease;
            margin-bottom: 14px;
            position: relative;
            overflow: hidden;
         "
         onmouseover="
            this.style.transform='translateY(-5px) scale(1.01)';
            this.style.boxShadow='0 16px 40px rgba(99,102,241,0.28), 0 0 0 1px rgba(99,102,241,0.3)';
            this.style.borderColor='rgba(99,102,241,.45)';
         "
         onmouseout="
            this.style.transform='none';
            this.style.boxShadow='none';
            this.style.borderColor='rgba(99,102,241,.22)';
         ">

        <!-- accent bar top -->
        <div style="position:absolute; top:0; left:0; right:0; height:2px;
                    background:linear-gradient(90deg,#6366F1,#8B5CF6,transparent);
                    border-radius:16px 16px 0 0;"></div>

        <!-- header row: container number + status badge -->
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:14px;">
            <div>
                <div style="font-size:0.72rem; color:#8C95B3; font-weight:500;
                            text-transform:uppercase; letter-spacing:0.06em; margin-bottom:2px;">
                    Container
                </div>
                <h4 style="margin:0; font-weight:800; font-size:1.05rem;
                           color:#E6E9F2; letter-spacing:-0.01em;">
                    {container}
                </h4>
            </div>
            <span style="
                background:{status_bg};
                color:{status_color};
                padding:4px 10px;
                border-radius:20px;
                font-size:0.72rem;
                font-weight:700;
                white-space:nowrap;
                display:inline-flex;
                align-items:center;
                gap:4px;
                border:1px solid {status_color}33;
            ">{status_emoji} {status}</span>
        </div>

        <!-- info rows -->
        <div style="color:#8C95B3; font-size:0.82rem; line-height:1.65;">
            <div style="display:flex; gap:6px; align-items:baseline;">
                <span style="color:#6366F1; font-weight:600; min-width:34px;">TAN</span>
                <span style="color:#C4CAE0;">{tan}</span>
            </div>
            <div style="display:flex; gap:6px; align-items:baseline; margin-top:5px;">
                <span style="color:#6366F1; font-weight:600; min-width:34px;">Item</span>
                <span style="color:#C4CAE0;" title="{item}">{item_short}</span>
            </div>
            <div style="display:flex; gap:6px; align-items:baseline; margin-top:5px;">
                <span style="color:#6366F1; font-weight:600; min-width:34px;">Line</span>
                <span style="color:#C4CAE0;">{carrier}</span>
            </div>
        </div>

        <!-- footer row: size, port, dates -->
        <div style="
            display:flex; justify-content:space-between; align-items:center;
            margin-top:14px; padding-top:12px;
            border-top:1px solid rgba(99,102,241,0.12);
            font-size:0.76rem; color:#6B7399;
        ">
            <span>📏 {size}</span>
            <span>⚓ {port}</span>
            <span>🛫 {etd}</span>
            <span>🛬 {eta}</span>
        </div>

        <!-- double-click hint (hidden, appears on hover via opacity) -->
        <div style="
            position:absolute; bottom:8px; right:12px;
            font-size:0.65rem; color:#6366F1; opacity:0.5;
            pointer-events:none;
        ">dbl-click to open</div>
    </div>
    """, unsafe_allow_html=True)

    # Hidden trigger button — the JS finds this via data-view-btn
    btn_clicked = st.button(
        "👁️ View",
        key=f"view_{card_id}",
        help="Double-click the card or press Enter when focused",
        label_visibility="collapsed"
    )
    if btn_clicked:
        st.session_state.selected_doc = row.to_dict()
        st.session_state.show_viewer = True
        st.rerun()

    # Tag the button with the correct attribute so JS can find it
    st.markdown(f"""
    <script>
    (function(){{
        var btns = document.querySelectorAll('button');
        btns.forEach(function(b){{
            if(b.innerText.trim()==='👁️ View' || b.getAttribute('kind')==='secondary'){{
                // heuristic: tag the most recently added button with card id
            }}
        }});
        // more reliable: tag via key
        var allBtns = document.querySelectorAll('[data-testid="baseButton-secondary"]');
        // Just wire all [data-doc-card] buttons as view buttons
        var cards = document.querySelectorAll('[data-doc-card]');
        cards.forEach(function(card){{
            var sib = card.nextElementSibling;
            if(sib && sib.tagName==='DIV'){{
                var btn = sib.querySelector('button');
                if(btn) btn.setAttribute('data-view-btn','true');
            }}
        }});
    }})();
    </script>
    """, unsafe_allow_html=True)


def render_document_viewer():
    """
    Render the document detail modal when show_viewer is True.
    Must be called after render_document_grid().
    """
    if not st.session_state.get("show_viewer") or st.session_state.selected_doc is None:
        return

    doc = st.session_state.selected_doc

    # Modal styling
    st.markdown("""
    <style>
    @keyframes scaleIn {
        from { opacity: 0; transform: scale(0.94) translateY(10px); }
        to   { opacity: 1; transform: scale(1)    translateY(0);     }
    }
    .viewer-modal-wrap { animation: scaleIn 0.28s cubic-bezier(0.34, 1.56, 0.64, 1); }
    </style>
    """, unsafe_allow_html=True)

    status = str(doc.get("Statut Container", "UNKNOWN"))
    status_info = STATUS_STYLE.get(status, ("rgba(99,102,241,0.1)", "rgba(99,102,241,0.5)", "📦"))
    status_bg, status_color, status_emoji = status_info

    st.markdown(f"""
    <div class="viewer-modal-wrap" style="
        background: linear-gradient(135deg, rgba(11,16,32,0.94), rgba(20,26,46,0.9));
        backdrop-filter: blur(24px) saturate(190%);
        -webkit-backdrop-filter: blur(24px) saturate(190%);
        border: 1px solid rgba(99,102,241,.3);
        border-radius: 24px;
        padding: 32px 32px 24px;
        margin-top: 24px;
        box-shadow: 0 24px 80px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.08);
        position: relative;
    ">
        <div style="position:absolute; top:0; left:0; right:0; height:3px;
                    background:linear-gradient(90deg,#6366F1,#8B5CF6,#06B6D4);
                    border-radius:24px 24px 0 0;"></div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <div>
                <h2 style="margin:0; color:#E6E9F2; font-size:1.45rem; font-weight:800; letter-spacing:-0.02em;">
                    📄 {doc.get('N° Container','—')}
                </h2>
                <div style="margin-top:4px;">
                    <span style="background:{status_bg}; color:{status_color};
                                 padding:3px 12px; border-radius:20px; font-size:0.78rem; font-weight:700;
                                 border:1px solid {status_color}33;">
                        {status_emoji} {status}
                    </span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Close button row (Streamlit button so it triggers rerun)
    close_col, _ = st.columns([1, 11])
    with close_col:
        if st.button("✕ Close", key="close_viewer", help="Esc also closes (Escape key)", type="secondary"):
            st.session_state.show_viewer = False
            st.session_state.selected_doc = None
            st.rerun()

    # Mark close button for keyboard Esc handler
    st.markdown("""
    <script>
    setTimeout(function(){
        var btns = document.querySelectorAll('button');
        btns.forEach(function(b){
            if(b.innerText.includes('✕') || b.innerText.includes('Close')){
                b.setAttribute('data-close-viewer','true');
            }
        });
    }, 200);
    </script>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Main detail grid ──────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📦 Container & Shipment")
        _info_row("Container #", doc.get("N° Container"))
        _info_row("Size",        doc.get("Container size"))
        _info_row("Seal #",      doc.get("N° Seal"))
        _info_row("TAN",         doc.get("N° TAN"))
        _info_row("Status",      doc.get("Statut Container"))

    with col2:
        st.markdown("#### 🚢 Logistics")
        _info_row("Carrier",     doc.get("Compagnie maritime"))
        _info_row("Transitaire", doc.get("Transitaire"))
        _info_row("Port",        doc.get("Port"))
        _info_row("ETD",         doc.get("Date shipment"))
        _info_row("ETA",         doc.get("Date accostage"))

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 📍 Delivery")
        _info_row("Date",    doc.get("Date livraison"))
        _info_row("Site",    doc.get("Site livraison"))
        _info_row("Driver",  doc.get("Chauffeur livraison"))

    with col2:
        st.markdown("#### 📭 Dépotement & Restitution")
        _info_row("Dépotement",  doc.get("Date dépotement"))
        _info_row("Restitution", doc.get("Date restitution"))
        _info_row("Driver",      doc.get("Chauffeur restitution"))

    with col3:
        st.markdown("#### 📝 Reference")
        item = str(doc.get("Item", "—"))
        st.markdown(f"**Item:** {item}")
        _info_row("Source", doc.get("Source"))
        _info_row("Created", doc.get("Créé le"))

    # Notes
    comment = doc.get("Commentaire") or ""
    if str(comment).strip() and str(comment).strip() not in ("—", "None", "nan"):
        st.divider()
        st.markdown("#### 📌 Notes / Commentaire")
        st.info(comment)

    # ── Action buttons ────────────────────────────────────────────────────────
    st.divider()
    bcol1, bcol2, bcol3, bcol4 = st.columns(4)

    with bcol1:
        # Export this single container to CSV
        single_row_df = pd.DataFrame([doc])
        csv_single = single_row_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📄 Export to CSV",
            data=csv_single.encode("utf-8-sig"),
            file_name=f"{doc.get('N° Container', 'container')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with bcol2:
        # Copy summary to clipboard via JS
        summary = (
            f"Container: {doc.get('N° Container','—')}\n"
            f"TAN: {doc.get('N° TAN','—')}\n"
            f"Status: {doc.get('Statut Container','—')}\n"
            f"Carrier: {doc.get('Compagnie maritime','—')}\n"
            f"ETD: {doc.get('Date shipment','—')} | ETA: {doc.get('Date accostage','—')}"
        )
        st.button(
            "📋 Copy summary",
            key="copy_summary",
            use_container_width=True,
            on_click=_copy_to_clipboard_js,
            args=(summary,)
        )

    with bcol3:
        source = str(doc.get("Source") or "")
        if source.strip() and source.strip() not in ("—", "None", "nan"):
            st.markdown(f"🔗 **Source:** `{source}`")
        else:
            st.markdown("🔗 *No source file*")

    with bcol4:
        if st.button("❌ Close viewer", key="close_viewer_bottom", use_container_width=True):
            st.session_state.show_viewer = False
            st.session_state.selected_doc = None
            st.rerun()


def _info_row(label: str, value):
    """Render a styled label: value row."""
    val = str(value) if value is not None else "—"
    if val in ("None", "nan", ""):
        val = "—"
    st.markdown(
        f"<div style='margin-bottom:6px;'>"
        f"<span style='color:#8C95B3; font-size:0.82rem; font-weight:600; "
        f"text-transform:uppercase; letter-spacing:0.04em;'>{label}</span><br>"
        f"<span style='color:#E6E9F2; font-size:0.9rem;'>{val}</span>"
        f"</div>",
        unsafe_allow_html=True
    )


def _copy_to_clipboard_js(text: str):
    """Inject a JS snippet to copy text to clipboard."""
    safe = text.replace("`", "'").replace("\n", "\\n")
    st.markdown(f"""
    <script>
    navigator.clipboard.writeText(`{safe}`).then(function(){{
        console.log('Copied to clipboard');
    }}).catch(function(err){{
        console.error('Could not copy text:', err);
    }});
    </script>
    """, unsafe_allow_html=True)
    st.success("✅ Summary copied to clipboard!")


def render_bulk_actions_bar(total_docs: int):
    """Render bulk action buttons below the grid."""
    st.markdown(
        f"<div style='color:#8C95B3; font-size:0.82rem; margin-bottom:8px;'>"
        f"💡 Bulk actions apply to all <b>{total_docs:,}</b> filtered documents</div>",
        unsafe_allow_html=True
    )
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📊 Export Filtered → CSV", use_container_width=True):
            st.session_state["bulk_export_trigger"] = "csv"

    with col2:
        if st.button("📈 Export Filtered → Excel", use_container_width=True):
            st.session_state["bulk_export_trigger"] = "xlsx"

    with col3:
        if st.button("📝 Update status (coming soon)", use_container_width=True, disabled=True):
            pass

    with col4:
        st.metric("Filtered", f"{total_docs:,}")
