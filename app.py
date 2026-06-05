# app.py
"""
SNI Extractor — Streamlit App
Mengubah PDF standar SNI menjadi structured JSON dengan embedding_text.
"""

import io
import json
import os
import re
import time
import zipfile
from pathlib import Path

import streamlit as st
import engine

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SNI Extractor",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# CSS  (dark theme, same palette as original)
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.stApp { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%); min-height: 100vh; }
.stApp p, .stApp span, .stApp div, .stApp li, .stApp label,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp td, .stApp th {
    color: #f1f5f9 !important; -webkit-text-fill-color: #f1f5f9 !important; opacity:1 !important;
}
.stApp strong, .stApp b { color:#ffffff !important; -webkit-text-fill-color:#ffffff !important; }
.stApp code { color:#fbbf24 !important; -webkit-text-fill-color:#fbbf24 !important;
              background:rgba(30,41,59,0.8) !important; padding:2px 6px !important; border-radius:4px !important; }
.stMarkdown, [data-testid="stMarkdownContainer"], .stVerticalBlock, .stElementContainer,
.streamlit-expanderContent { background-color:transparent !important; background:transparent !important; }

header[data-testid="stHeader"] { visibility:hidden !important; height:0 !important; }
#MainMenu, footer, .stDeployButton { visibility:hidden; display:none; }

section[data-testid="stSidebar"] { background:#0c1222 !important; border-right:1px solid rgba(99,102,241,0.2) !important; }
section[data-testid="stSidebar"] label { color:#e2e8f0 !important; -webkit-text-fill-color:#e2e8f0 !important; }

.metric-card { background:linear-gradient(135deg,rgba(30,41,59,0.9),rgba(15,23,42,0.9));
               border:1px solid rgba(99,102,241,0.3); border-radius:16px; padding:1.25rem 1.5rem;
               text-align:center; position:relative; overflow:hidden; }
.metric-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px;
                        background:linear-gradient(90deg,#6366f1,#06b6d4,#10b981); }
.metric-value { font-size:2.2rem; font-weight:800;
                background:linear-gradient(135deg,#6366f1,#06b6d4);
                -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.metric-label { font-size:0.82rem; color:#cbd5e1 !important; -webkit-text-fill-color:#cbd5e1 !important;
                margin-top:4px; font-weight:500; }

.page-header { background:linear-gradient(135deg,rgba(99,102,241,0.12),rgba(6,182,212,0.08));
               border:1px solid rgba(99,102,241,0.25); border-radius:20px; padding:2rem 2.5rem;
               margin-bottom:2rem; }
.page-title { font-size:2rem; font-weight:800; margin:0;
              background:linear-gradient(135deg,#f1f5f9,#6366f1);
              -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.page-subtitle { color:#cbd5e1 !important; -webkit-text-fill-color:#cbd5e1 !important; font-size:0.95rem; margin-top:0.4rem; }
.section-header { font-size:1.05rem; font-weight:700; color:#ffffff !important;
                  -webkit-text-fill-color:#ffffff !important; display:flex; align-items:center;
                  gap:0.5rem; margin-bottom:1rem; padding-bottom:0.5rem;
                  border-bottom:1px solid rgba(99,102,241,0.2); }
.gradient-divider { height:1px; background:linear-gradient(90deg,transparent,rgba(99,102,241,0.4),transparent); margin:1.5rem 0; }

.file-item { background:#0a0f1c !important; border:1px solid rgba(99,102,241,0.45) !important;
             border-radius:12px; padding:1rem 1.2rem; margin-bottom:0.6rem;
             display:flex; align-items:center; gap:0.75rem; }
.file-name { font-weight:700 !important; color:#ffffff !important; -webkit-text-fill-color:#ffffff !important;
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.92rem; }
.file-size { font-size:0.82rem !important; color:#c7d2fe !important; -webkit-text-fill-color:#c7d2fe !important; }
.file-badge { padding:5px 14px !important; border-radius:8px; font-size:0.78rem !important;
              font-weight:900 !important; text-transform:uppercase; letter-spacing:0.08em;
              min-width:52px; text-align:center; display:inline-block; line-height:1.4; }
.badge-pdf { background:#991b1b !important; color:#fef2f2 !important; -webkit-text-fill-color:#fef2f2 !important;
             border:2px solid #f87171 !important; }
.badge-docx,.badge-doc { background:#1e3a5f !important; color:#eff6ff !important;
                         -webkit-text-fill-color:#eff6ff !important; border:2px solid #60a5fa !important; }
.badge-xlsx,.badge-xls,.badge-ods,.badge-csv { background:#14532d !important; color:#dcfce7 !important;
                         -webkit-text-fill-color:#dcfce7 !important; border:2px solid #4ade80 !important; }
.badge-txt,.badge-md { background:#374151 !important; color:#f9fafb !important;
                       -webkit-text-fill-color:#f9fafb !important; border:2px solid #9ca3af !important; }

/* SNI record card */
.sni-card { background:rgba(15,23,42,0.85); border:1px solid rgba(99,102,241,0.35);
            border-radius:14px; padding:1.2rem 1.4rem; margin-bottom:1rem; }
.sni-field-label { font-size:0.78rem; color:#a5b4fc !important; -webkit-text-fill-color:#a5b4fc !important;
                   font-weight:700; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:2px; }
.sni-field-value { font-size:0.92rem; color:#f1f5f9 !important; -webkit-text-fill-color:#f1f5f9 !important;
                   margin-bottom:0.75rem; line-height:1.55; }
.sni-number-badge { display:inline-block; background:rgba(99,102,241,0.25);
                    border:1px solid rgba(99,102,241,0.5); border-radius:8px;
                    padding:3px 12px; font-weight:800; font-size:1rem;
                    color:#c7d2fe !important; -webkit-text-fill-color:#c7d2fe !important; }
.embedding-box { background:#0f172a; border:1px solid rgba(16,185,129,0.35); border-radius:10px;
                 padding:0.85rem 1rem; font-family:monospace; font-size:0.82rem; line-height:1.7;
                 white-space:pre-wrap; color:#6ee7b7 !important; -webkit-text-fill-color:#6ee7b7 !important; }
.status-success { background:rgba(16,185,129,0.2); color:#6ee7b7 !important; -webkit-text-fill-color:#6ee7b7 !important;
                  border:1px solid rgba(16,185,129,0.4); border-radius:8px; padding:2px 10px;
                  font-size:0.78rem; font-weight:600; }
.status-error { background:rgba(239,68,68,0.2); color:#fca5a5 !important; -webkit-text-fill-color:#fca5a5 !important;
                border:1px solid rgba(239,68,68,0.4); border-radius:8px; padding:2px 10px;
                font-size:0.78rem; font-weight:600; }
.info-box { background:#162032 !important; border:1px solid rgba(99,102,241,0.4) !important;
            border-radius:12px; padding:1rem 1.25rem; font-size:0.88rem; line-height:1.6; }
.info-box, .info-box p, .info-box span, .info-box div { color:#e0e7ff !important; -webkit-text-fill-color:#e0e7ff !important; background:transparent !important; }
.info-box strong { color:#ffffff !important; -webkit-text-fill-color:#ffffff !important; }

div.stButton > button { border-radius:10px !important; font-weight:600 !important;
                        color:#ffffff !important; -webkit-text-fill-color:#ffffff !important; }
div.stButton > button[kind="primary"] { background:linear-gradient(135deg,#6366f1,#4f46e5) !important;
                                        border:none !important; box-shadow:0 4px 20px rgba(99,102,241,0.4) !important; }
.big-process-btn > div > button { background:linear-gradient(135deg,#10b981,#059669) !important;
                                  color:#ffffff !important; -webkit-text-fill-color:#ffffff !important;
                                  font-size:1.1rem !important; border-radius:12px !important; border:none !important;
                                  box-shadow:0 6px 30px rgba(16,185,129,0.45) !important; width:100% !important; }

[data-testid="stFileUploader"] { border:2px dashed rgba(99,102,241,0.45) !important; border-radius:16px !important;
                                  background:rgba(30,41,59,0.45) !important; padding:0.5rem !important; }
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] { background:#f1f5f9 !important;
  border:1px solid #cbd5e1 !important; border-radius:8px !important; padding:8px 12px !important; }
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] p,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small {
  color:#0f172a !important; -webkit-text-fill-color:#0f172a !important; }

.stTabs [data-baseweb="tab-list"] { background:rgba(15,23,42,0.6) !important; border-radius:12px !important;
                                     padding:4px !important; border:1px solid rgba(99,102,241,0.2) !important; }
.stTabs [data-baseweb="tab"] { border-radius:8px !important; font-weight:600 !important;
                                color:#cbd5e1 !important; -webkit-text-fill-color:#cbd5e1 !important; }
.stTabs [aria-selected="true"] { background:rgba(99,102,241,0.25) !important;
                                  color:#ffffff !important; -webkit-text-fill-color:#ffffff !important; }
.stProgress > div > div > div > div { background:linear-gradient(90deg,#6366f1,#06b6d4,#10b981) !important; }
.stCodeBlock pre, .stCodeBlock code { background:#0f172a !important; color:#e2e8f0 !important;
                                       -webkit-text-fill-color:#e2e8f0 !important; }
.sidebar-logo-wrapper { background:linear-gradient(135deg,#1e293b,#0f172a) !important;
                        border:2px solid rgba(99,102,241,0.4) !important; border-radius:20px !important;
                        padding:1.2rem 1rem !important; margin-bottom:0.5rem !important;
                        text-align:center !important; width:100% !important; }
.sidebar-title { font-size:1.25rem !important; font-weight:800 !important; color:#ffffff !important;
                 -webkit-text-fill-color:#ffffff !important; margin-top:0.4rem !important; }
.sidebar-version { font-size:0.78rem !important; color:#94a3b8 !important; -webkit-text-fill-color:#94a3b8 !important; }
.session-id-box { background:rgba(99,102,241,0.15) !important; border:1px solid rgba(99,102,241,0.4) !important;
                  border-radius:10px !important; padding:0.75rem !important; margin-bottom:1rem !important; }
.session-id-text { font-family:monospace !important; font-size:0.75rem !important; color:#ffffff !important;
                   -webkit-text-fill-color:#ffffff !important; word-break:break-all !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "session_id":      engine.generate_session_id(),
        "uploaded_files":  [],
        "processed_result": None,
        "paraphrased_result": None,
        "save_result":     None,
        "merger_files":    [],
        "merge_result":    None,
        "uploader_key":    0,
        "merger_uploader_key": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ──────────────────────────────────────────────────────────────────────────────
# API KEY CHECK  — tampilkan peringatan jelas jika key tidak ada
# ──────────────────────────────────────────────────────────────────────────────

def _check_api_key() -> bool:
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key and key.strip():
            return True
    except Exception:
        pass
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return bool(key and key.strip())

_api_key_ok = _check_api_key()
if not _api_key_ok:
    st.error(
        "**❌ ANTHROPIC_API_KEY tidak ditemukan!**\n\n"
        "Tambahkan API key Anthropic agar ekstraksi SNI bisa berjalan:\n\n"
        "**Streamlit Cloud:** Buka *App Settings → Secrets*, tambahkan:\n"
        "```\nANTHROPIC_API_KEY = \"sk-ant-...\"\n```\n"
        "**Lokal:** Buat file `.streamlit/secrets.toml` dengan isi yang sama, "
        "atau set environment variable `ANTHROPIC_API_KEY`."
    )

# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""<div style="text-align:center;padding:0.5rem 0 1.5rem;">
      <div class="sidebar-logo-wrapper">
        <div style="font-size:3rem;">📋</div>
        <div class="sidebar-title">SNI Extractor</div>
        <div class="sidebar-version">v3.0 · Claude Powered</div>
      </div></div>""", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**🔑 Active Session**")
    st.markdown(f'<div class="session-id-box"><div class="session-id-text">{st.session_state.session_id}</div></div>',
                unsafe_allow_html=True)

    if st.button("🔄 New Session", use_container_width=True, key="btn_new_session"):
        st.session_state.session_id       = engine.generate_session_id()
        st.session_state.uploaded_files   = []
        st.session_state.processed_result = None
        st.session_state.paraphrased_result = None
        st.session_state.save_result      = None
        st.session_state.uploader_key    += 1
        st.rerun()

    st.markdown("---")
    st.markdown("**ℹ️ Output Fields**")
    st.markdown("""<div class="info-box">
      Setiap dokumen SNI menghasilkan:<br>
      <strong>sni_number</strong> · <strong>title</strong> · <strong>keywords</strong><br>
      <strong>toc</strong> · <strong>summary</strong> · <strong>embedding_text</strong><br><br>
      <strong>Format:</strong> PDF · DOCX · TXT · MD<br>
      XLSX · XLS · ODS · CSV · JPG · PNG<br>
      <em>PDF scan → OCR otomatis</em>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    sessions   = engine.list_sessions()
    total_size = sum(s["file_size"] for s in sessions)
    st.markdown(f'<div style="font-size:0.82rem;color:#fff !important;text-align:center;">'
                f'💾 {len(sessions)} sessions · {engine.format_size(total_size)} used</div>',
                unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""<div class="page-header">
  <h1 class="page-title">📋 SNI Extractor</h1>
  <p class="page-subtitle">Ubah PDF standar SNI menjadi structured JSON dengan embedding_text siap pakai.</p>
</div>""", unsafe_allow_html=True)

tab_process, tab_merge, tab_sessions = st.tabs(
    ["📄 Ekstrak SNI", "🔀 Merge JSON", "📂 Session Manager"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SNI EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════

with tab_process:
    _cur_result     = st.session_state.processed_result
    uploaded_count  = len(st.session_state.uploaded_files)
    records_count   = _cur_result["total_chunks"] if _cur_result else 0
    processed_count = _cur_result["stats"]["processed_files"] if _cur_result else 0

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in [
        (c1, uploaded_count, "Files Uploaded"),
        (c2, processed_count, "Docs Processed"),
        (c3, records_count, "SNI Records"),
        (c4, _cur_result["stats"]["failed_files"] if _cur_result else 0, "Failed"),
    ]:
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div>'
                        f'<div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    col_upload, col_list = st.columns([1, 1], gap="large")
    process_clicked = False

    with col_upload:
        st.markdown('<div class="section-header">📤 Upload Dokumen SNI</div>', unsafe_allow_html=True)
        st.markdown("""<div class="info-box">Format didukung: <strong>PDF, DOCX, TXT, XLSX, XLS, ODS, CSV, Gambar (JPG/PNG)</strong>
          · Claude akan mengekstrak field SNI secara otomatis. PDF scan akan di-OCR otomatis.</div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        new_files = st.file_uploader(
            "Upload file",
            type=["pdf", "docx", "doc", "txt", "md", "xlsx", "xls", "ods", "csv",
                  "jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key=f"main_uploader_{st.session_state.uploader_key}",
        )

        if new_files:
            engine.init_session(st.session_state.session_id)
            added          = 0
            existing_names = {f["original_name"] for f in st.session_state.uploaded_files}
            for uf in new_files:
                if uf.name not in existing_names:
                    info = engine.save_uploaded_file(st.session_state.session_id, uf)
                    st.session_state.uploaded_files.append(info)
                    added += 1
            if added:
                st.success(f"✅ {added} file ditambahkan!")
                st.rerun()

        if st.session_state.uploaded_files:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="big-process-btn">', unsafe_allow_html=True)
            process_clicked = st.button("⚡ Ekstrak SNI", use_container_width=True,
                                        type="primary", key="btn_process")
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Reset", use_container_width=True, key="btn_reset"):
                st.session_state.uploaded_files   = []
                st.session_state.processed_result = None
                st.session_state.paraphrased_result = None
                st.session_state.uploader_key    += 1
                st.rerun()

        _prog_header = st.empty()
        _prog_bar    = st.empty()
        _prog_detail = st.empty()
        _prog_timing = st.empty()

    with col_list:
        st.markdown('<div class="section-header">📋 File Queue</div>', unsafe_allow_html=True)
        _queue_area = st.empty()
        if not st.session_state.uploaded_files:
            _queue_area.markdown("""<div style="text-align:center;padding:3rem 1rem;">
              <div style="font-size:3rem;margin-bottom:1rem;">📂</div>
              <div style="font-weight:600;color:#ffffff !important;">Belum ada file</div>
            </div>""", unsafe_allow_html=True)
        elif _cur_result:
            _queue_area.markdown("""<div style="text-align:center;padding:3rem 1rem;">
              <div style="font-size:3rem;margin-bottom:1rem;">✅</div>
              <div style="font-weight:600;color:#6ee7b7 !important;">Selesai</div>
            </div>""", unsafe_allow_html=True)
        else:
            html = ""
            for fi in st.session_state.uploaded_files:
                ext = fi["ext"].lstrip(".")
                html += (f'<div class="file-item">'
                         f'<span class="file-badge badge-{ext}">{ext.upper()}</span>'
                         f'<div style="flex:1;min-width:0;">'
                         f'<div class="file-name">{fi["original_name"]}</div>'
                         f'<div class="file-size">{fi["size_fmt"]}</div></div></div>')
            _queue_area.markdown(html, unsafe_allow_html=True)

    # ── Processing ──────────────────────────────────────────────────────────
    if process_clicked:
        _t0 = [time.time()]

        def _cb(stage, cur, tot, fname=""):
            elapsed   = time.time() - _t0[0]
            frac      = cur / max(tot, 1)
            bar_val   = max(0.01, frac)
            pct_int   = int(bar_val * 100)
            fname_s   = (fname[:38] + "…") if len(fname) > 40 else fname
            _queue_area.markdown(
                f'<div style="text-align:center;padding:2rem 1rem;">'
                f'<div style="font-size:2rem;">⚙️</div>'
                f'<div style="color:#a5b4fc !important;font-weight:600;">Mengekstrak SNI…</div>'
                f'<div style="font-size:4rem;font-weight:800;background:linear-gradient(135deg,#6366f1,#06b6d4);'
                f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{pct_int}%</div>'
                f'</div>', unsafe_allow_html=True)
            _prog_header.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);'
                f'border-radius:8px;padding:0.55rem 0.9rem;margin-bottom:4px;">'
                f'<span style="color:#e2e8f0;">📂 Claude API — <strong>{cur}</strong> / <strong>{tot}</strong> selesai</span>'
                f'<span style="color:#6ee7b7;font-weight:700;">{pct_int}%</span>'
                f'</div>', unsafe_allow_html=True)
            _prog_bar.progress(bar_val)
            _prog_detail.markdown(
                f'<div style="font-size:0.82rem;color:#94a3b8;">🔄 {fname_s}</div>',
                unsafe_allow_html=True)
            if cur > 0 and elapsed > 0:
                rate = cur / elapsed
                eta  = max(0, (tot - cur) / rate) if rate > 0 else 0
                _prog_timing.markdown(
                    f'<div style="font-size:0.78rem;color:#64748b;">'
                    f'⏱ {elapsed:.1f}s | ETA ~{eta:.0f}s</div>', unsafe_allow_html=True)

        try:
            rd = engine.process_and_paraphrase(
                st.session_state.uploaded_files, {}, progress_callback=_cb)
            st.session_state.processed_result  = rd
            st.session_state.paraphrased_result = rd
            elapsed = time.time() - _t0[0]
            _prog_bar.progress(1.0)
            _prog_header.markdown(
                f'<div style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);'
                f'border-radius:8px;padding:0.55rem 0.9rem;">'
                f'<span style="color:#6ee7b7;">✅ Selesai dalam {elapsed:.1f}s — '
                f'<strong>{rd["total_chunks"]}</strong> record SNI</span></div>',
                unsafe_allow_html=True)
            _prog_detail.empty(); _prog_timing.empty()
            _queue_area.markdown("""<div style="text-align:center;padding:3rem 1rem;">
              <div style="font-size:3rem;">✅</div>
              <div style="font-weight:600;color:#6ee7b7 !important;">Selesai</div>
            </div>""", unsafe_allow_html=True)
        except Exception as ex:
            _prog_header.empty(); _prog_bar.empty(); _prog_detail.empty(); _prog_timing.empty()
            st.error(f"❌ Gagal: {ex}")
        st.rerun()

    # ── Results ─────────────────────────────────────────────────────────────
    # Gunakan session_state langsung agar selalu fresh setelah rerun
    _res = st.session_state.processed_result
    if _res is not None:
        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-header">📊 Hasil Ekstraksi SNI</div>', unsafe_allow_html=True)

        records = _res.get("data", [])

        # Selalu tampilkan download meski records kosong

        # Download buttons (JSON + JSONL ZIP)
        dc1, dc2, dc3 = st.columns([2, 1, 1])
        with dc1:
            ok  = _res.get("stats", {}).get("processed_files", len(records))
            fail = _res.get("stats", {}).get("failed_files", 0)
            st.markdown(
                f'<div class="info-box">'
                f'✅ <strong>{ok}</strong> berhasil · '
                f'❌ <strong>{fail}</strong> gagal</div>',
                unsafe_allow_html=True)

        # Show error details if any failures
        errors = _res.get("stats", {}).get("errors", [])
        if errors:
            with st.expander(f"⚠️ Detail {len(errors)} file gagal", expanded=True):
                for err in errors:
                    st.markdown(
                        f'<div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.4);'
                        f'border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:0.5rem;">'
                        f'<span style="color:#f87171;font-weight:700;">❌ {err["file"]}</span><br>'
                        f'<span style="color:#fca5a5;font-size:0.85rem;">{err["error"]}</span></div>',
                        unsafe_allow_html=True
                    )
        with dc2:
            json_bytes = json.dumps(_res, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("⬇️ Download JSON", data=json_bytes,
                               file_name=f"sni_{st.session_state.session_id[:12]}.json",
                               mime="application/json", use_container_width=True,
                               type="primary", key="dl_json")
        with dc3:
            # Build ZIP containing one .jsonl per processed record
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for rec in records:
                    src = rec.get("source_file", "unknown")
                    safe = re.sub(r"[^a-zA-Z0-9._\-]", "_", Path(src).stem)
                    fname = f"{safe}.jsonl"
                    zf.writestr(fname, json.dumps(rec, ensure_ascii=False) + "\n")
                # Also include a combined JSONL
                combined = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
                zf.writestr("_all_combined.jsonl", combined)
            zip_buf.seek(0)
            st.download_button(
                f"⬇️ Download {len(records)} JSONL (ZIP)",
                data=zip_buf.getvalue(),
                file_name=f"sni_{st.session_state.session_id[:12]}_jsonl.zip",
                mime="application/zip", use_container_width=True,
                key="dl_jsonl"
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Record cards
        for i, rec in enumerate(records):
            sni_num  = rec.get("sni_number", "-")
            title    = rec.get("title", "-")
            keywords = rec.get("keywords", [])
            toc      = rec.get("toc", [])
            summary  = rec.get("summary", "-")
            emb      = rec.get("embedding_text", "")
            src      = rec.get("source_file", "")

            with st.expander(f"📄 [{sni_num}] {title or src}", expanded=(i == 0)):
                st.markdown(
                    f'<div class="sni-card">'

                    # SNI Number
                    f'<div class="sni-field-label">SNI Number</div>'
                    f'<div class="sni-field-value"><span class="sni-number-badge">{sni_num}</span></div>'

                    # Title
                    f'<div class="sni-field-label">Judul</div>'
                    f'<div class="sni-field-value">{title}</div>'

                    # Keywords
                    f'<div class="sni-field-label">Keywords</div>'
                    f'<div class="sni-field-value">{", ".join(keywords) if keywords else "-"}</div>'

                    # TOC
                    f'<div class="sni-field-label">Daftar Isi</div>'
                    f'<div class="sni-field-value">{" | ".join(toc) if toc else "-"}</div>'

                    # Summary
                    f'<div class="sni-field-label">Ringkasan</div>'
                    f'<div class="sni-field-value">{summary}</div>'

                    # Embedding text
                    f'<div class="sni-field-label">embedding_text</div>'
                    f'<div class="embedding-box">{emb}</div>'

                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Raw JSON
                st.code(json.dumps(rec, ensure_ascii=False, indent=2), language="json")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — JSON MERGER
# ══════════════════════════════════════════════════════════════════════════════

with tab_merge:
    st.markdown("""<div class="page-header" style="margin-bottom:1.5rem;">
      <h2 style="font-size:1.4rem;font-weight:700;color:#fbbf24 !important;
                 -webkit-text-fill-color:#fbbf24 !important;margin:0;">🔀 JSON / JSONL Merger</h2>
      <p style="color:#cbd5e1 !important;-webkit-text-fill-color:#cbd5e1 !important;
                font-size:0.88rem;margin-top:4px;">Gabungkan beberapa file JSON hasil ekstraksi menjadi satu dataset.</p>
    </div>""", unsafe_allow_html=True)

    col_mu, col_mr = st.columns([1, 1], gap="large")

    with col_mu:
        st.markdown('<div class="section-header">📤 Upload JSON Files</div>', unsafe_allow_html=True)
        merge_strategy = st.selectbox(
            "Merge Strategy",
            options=["auto", "data", "array", "object"],
            format_func=lambda x: {"auto": "🔍 Auto", "data": "🎯 SNI/DocAI",
                                   "array": "📋 Array", "object": "🗂️ Object"}[x],
            key="sb_merge_strategy",
        )
        json_uploads = st.file_uploader(
            "Upload JSON", type=["json", "jsonl"], accept_multiple_files=True,
            key=f"json_uploader_{st.session_state.get('merger_uploader_key', 0)}")

        if json_uploads:
            added = 0
            existing = {f["name"] for f in st.session_state.merger_files}
            for uf in json_uploads:
                if uf.name not in existing:
                    try:
                        raw = uf.read().decode("utf-8")
                        # Support JSONL
                        if uf.name.endswith(".jsonl"):
                            content = [json.loads(ln) for ln in raw.splitlines() if ln.strip()]
                        else:
                            content = json.loads(raw)
                        st.session_state.merger_files.append({"name": uf.name, "content": content})
                        added += 1
                    except Exception as e:
                        st.error(f"❌ {uf.name}: {e}")
            if added:
                st.success(f"✅ {added} file dimuat!")
                st.rerun()

        if st.session_state.merger_files:
            st.markdown("<br>", unsafe_allow_html=True)
            for mf in st.session_state.merger_files:
                c = mf["content"]
                detail = (f"{len(c['data'])} records (SNI)" if isinstance(c, dict) and isinstance(c.get("data"), list)
                          else f"{len(c)} items" if isinstance(c, list)
                          else f"{len(c)} keys")
                st.markdown(f'<div class="file-item">'
                            f'<span class="file-badge badge-json">JSON</span>'
                            f'<div style="flex:1;min-width:0;">'
                            f'<div class="file-name">{mf["name"]}</div>'
                            f'<div class="file-size">{detail}</div></div></div>',
                            unsafe_allow_html=True)

            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button(f"🔀 Merge {len(st.session_state.merger_files)} Files",
                             use_container_width=True, type="primary", key="btn_merge"):
                    with st.spinner("Merging…"):
                        st.session_state.merge_result = engine.merge_json_files(
                            st.session_state.merger_files, merge_strategy)
                    st.success("✅ Done!"); st.rerun()
            with bc2:
                if st.button("🔄 Reset", use_container_width=True, key="btn_reset_merge"):
                    st.session_state.merger_files  = []
                    st.session_state.merge_result  = None
                    st.session_state.merger_uploader_key = st.session_state.get("merger_uploader_key", 0) + 1
                    st.rerun()
        else:
            st.markdown("""<div style="text-align:center;padding:3rem 1rem;">
              <div style="font-size:3rem;">🔀</div>
              <div style="font-weight:600;color:#ffffff !important;">Upload JSON untuk di-merge</div>
            </div>""", unsafe_allow_html=True)

    with col_mr:
        st.markdown('<div class="section-header">📊 Hasil Merge</div>', unsafe_allow_html=True)
        if st.session_state.merge_result:
            mr   = st.session_state.merge_result
            mg   = mr["merged"]
            ms   = mr["stats"]
            mode = mr["merge_mode"]
            ti   = mg.get("total", len(mg)) if isinstance(mg, dict) else len(mg)
            st.markdown(f'<div style="display:flex;gap:1rem;margin-bottom:1rem;">'
                        f'<div style="background:#0c1222;border:1px solid rgba(99,102,241,0.4);'
                        f'border-radius:10px;padding:0.6rem 1rem;font-size:0.85rem;color:#f1f5f9 !important;">'
                        f'🎯 <strong>{mode.upper()}</strong></div>'
                        f'<div style="background:#0c1222;border:1px solid rgba(99,102,241,0.4);'
                        f'border-radius:10px;padding:0.6rem 1rem;font-size:0.85rem;color:#f1f5f9 !important;">'
                        f'📦 <strong>{ti:,} records</strong></div></div>', unsafe_allow_html=True)
            preview = mg[:3] if isinstance(mg, list) else {k: v for i, (k, v) in enumerate(mg.items()) if i < 3}
            st.code(json.dumps(preview, ensure_ascii=False, indent=2)[:1500], language="json")
            jb = json.dumps(mg, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("⬇️ Download Merged JSON", data=jb,
                               file_name=f"sni_merged_{int(time.time())}.json",
                               mime="application/json", use_container_width=True,
                               type="primary", key="dl_merged")
        else:
            st.markdown("""<div style="text-align:center;padding:4rem 1rem;">
              <div style="font-size:3rem;">📊</div>
              <div style="font-weight:600;color:#ffffff !important;">Hasil muncul di sini</div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SESSION MANAGER
# ══════════════════════════════════════════════════════════════════════════════

with tab_sessions:
    st.markdown("""<div class="page-header" style="margin-bottom:1.5rem;">
      <h2 style="font-size:1.4rem;font-weight:700;color:#22d3ee !important;
                 -webkit-text-fill-color:#22d3ee !important;margin:0;">📂 Session Manager</h2>
    </div>""", unsafe_allow_html=True)

    if st.button("🔄 Refresh", use_container_width=True, key="btn_refresh"):
        st.rerun()

    sessions = engine.list_sessions()
    if not sessions:
        st.markdown("""<div style="text-align:center;padding:4rem;">
          <div style="font-size:3rem;">📭</div>
          <div style="font-weight:600;color:#ffffff !important;">Tidak ada session</div>
        </div>""", unsafe_allow_html=True)
    else:
        ts = sum(s["file_size"] for s in sessions)
        c1, c2, c3 = st.columns(3)
        for col, val, lbl in [
            (c1, len(sessions), "Sessions"),
            (c2, engine.format_size(ts), "Storage"),
            (c3, sum(s["file_count"] for s in sessions), "Files"),
        ]:
            with col:
                st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div>'
                            f'<div class="metric-label">{lbl}</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        with st.expander("🧹 Hapus Semua Session"):
            oc = len([s for s in sessions if s["id"] != st.session_state.session_id])
            if st.button(f"🧹 Hapus {oc} session lama", use_container_width=True,
                         type="primary", key="btn_cleanup"):
                r = engine.delete_all_sessions(st.session_state.session_id)
                if r["deleted"] > 0:
                    st.success(f"✅ Deleted {r['deleted']}, freed {r['freed_fmt']}")
                    time.sleep(1.2); st.rerun()
                else:
                    st.warning("⚠️ Tidak ada yang dihapus.")

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        for s in sessions:
            ia = s["id"] == st.session_state.session_id
            with st.expander(f"{'📍' if ia else '📁'} {s['id']} · {s['file_size_fmt']} · {s['modified_at']}"):
                ci, ca = st.columns([3, 1])
                with ci:
                    st.markdown(f'<div style="font-size:0.88rem;line-height:1.8;">'
                                f'Modified: {s["modified_at"]} · Files: {s["file_count"]}</div>',
                                unsafe_allow_html=True)
                with ca:
                    op = Path(engine.UPLOADS_DIR) / s["id"] / "processed" / "output.json"
                    if op.exists():
                        st.download_button("⬇️ JSON", data=op.read_bytes(),
                                           file_name=f"sni_{s['id'][:12]}.json",
                                           mime="application/json",
                                           key=f"dl_{s['id']}", use_container_width=True)
                    if not ia:
                        if st.button("🔄 Switch", key=f"sw_{s['id']}", use_container_width=True):
                            st.session_state.session_id       = s["id"]
                            st.session_state.uploaded_files   = []
                            st.session_state.processed_result = None
                            st.session_state.uploader_key    += 1
                            st.rerun()
                        if st.button("🗑️ Delete", key=f"del_{s['id']}", use_container_width=True):
                            engine.delete_session(s["id"])
                            st.success("✅ Deleted"); st.rerun()
                    else:
                        st.markdown('<div class="status-success" style="text-align:center;">Current</div>',
                                    unsafe_allow_html=True)
