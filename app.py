# app.py
"""
DocAI Trainer - Streamlit App
Modern, elegant dashboard for processing documents into AI training data.
"""

import json
import time
from pathlib import Path

import streamlit as st

import engine

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Generator Dataset",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   GLOBAL TEKS — SOLID & TERLIHAT
   ══════════════════════════════════════════════════════════════════════════ */
.stApp p, .stApp span, .stApp div, .stApp li, .stApp a, .stApp label,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp td, .stApp th, .stApp strong, .stApp em, .stApp b, .stApp i,
.stApp small, .stApp pre, .stApp blockquote {
    color: #f1f5f9 !important;
    -webkit-text-fill-color: #f1f5f9 !important;
    opacity: 1 !important;
}
.stApp strong, .stApp b { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.stApp em, .stApp i { color: #cbd5e1 !important; -webkit-text-fill-color: #cbd5e1 !important; }
.stApp small { color: #94a3b8 !important; -webkit-text-fill-color: #94a3b8 !important; }
.stApp code {
    color: #fbbf24 !important; -webkit-text-fill-color: #fbbf24 !important;
    background-color: rgba(30,41,59,0.8) !important; padding: 2px 6px !important; border-radius: 4px !important;
}

/* ★★★ HAPUS BACKGROUND PUTIH STREAMLIT ★★★ */
.stMarkdown, .stMarkdown > div, .stMarkdown > div > div, .stMarkdown > div > div > div,
.streamlit-expanderContent, .streamlit-expanderContent > div, .streamlit-expanderContent > div > div,
[data-testid="stExpander"], [data-testid="stExpander"] > div, [data-testid="stExpander"] > div > div,
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] > div,
[data-testid="stMarkdownContainer"] > div > div,
.stVerticalBlock, .stVerticalBlock > div,
.stElementContainer, .stElementContainer > div {
    background-color: transparent !important; background: transparent !important;
}
[data-testid="stMarkdownContainer"] div, [data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] em, [data-testid="stMarkdownContainer"] code,
[data-testid="stMarkdownContainer"] small {
    background-color: transparent !important; color: #f1f5f9 !important; -webkit-text-fill-color: #f1f5f9 !important;
}
[data-testid="stMarkdownContainer"] strong { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }

::selection { background-color: rgba(99,102,241,0.5) !important; color: #fff !important; }
::-moz-selection { background-color: rgba(99,102,241,0.5) !important; color: #fff !important; }

/* ══════════════════════════════════════════════════════════════════════════
   HEADER & BACKGROUND
   ══════════════════════════════════════════════════════════════════════════ */
header[data-testid="stHeader"] { visibility: hidden !important; height: 0 !important; min-height: 0 !important; padding: 0 !important; margin: 0 !important; overflow: hidden !important; border: none !important; background: transparent !important; }
#MainMenu, footer { visibility: hidden; }
.stDeployButton { display: none; }
.stApp { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%); min-height: 100vh; padding-top: 0 !important; }

/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR
   ══════════════════════════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] { background: #0c1222 !important; border-right: 1px solid rgba(99,102,241,0.2) !important; }
section[data-testid="stSidebar"], section[data-testid="stSidebar"] * { opacity: 1 !important; }
section[data-testid="stSidebar"] .block-container { padding-top: 0.5rem !important; }
section[data-testid="stSidebar"] label { color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important; }

/* ══════════════════════════════════════════════════════════════════════════════════════════
   ★★★ FORM INPUTS — BACKGROUND TERANG, TEKS HITAM SOLID, TIDAK BOLD ★★★
   ★★★ Override GLOBAL .stApp * yang memaksa warna terang                         ★★★
   ══════════════════════════════════════════════════════════════════════════════════════════ */

/* Outer container */
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stNumberInput"] > div > div,
div[data-testid="stTextInput"] > div > div {
    background-color: #1e293b !important;
    border: 1px solid rgba(99,102,241,0.55) !important;
    color: #f1f5f9 !important;
    -webkit-text-fill-color: #f1f5f9 !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
}

/* ★★★ SELECTBOX: Selected value text — TERANG di background GELAP ★★★ */
div[data-testid="stSelectbox"] [role="combobox"],
div[data-testid="stSelectbox"] [role="combobox"] > div,
div[data-testid="stSelectbox"] [role="combobox"] > div > div,
div[data-testid="stSelectbox"] [role="combobox"] span,
div[data-testid="stSelectbox"] [role="combobox"] p {
    color: #f1f5f9 !important;
    -webkit-text-fill-color: #f1f5f9 !important;
    font-weight: 500 !important;
    background-color: transparent !important;
    opacity: 1 !important;
}

/* The input inside selectbox */
div[data-testid="stSelectbox"] input {
    color: #f1f5f9 !important;
    -webkit-text-fill-color: #f1f5f9 !important;
    font-weight: 500 !important;
    caret-color: #f1f5f9 !important;
    background-color: transparent !important;
    opacity: 1 !important;
}

/* ★★★ CRITICAL: Override SVG arrow icon in selectbox — light on dark bg ★★★ */
div[data-testid="stSelectbox"] svg { fill: #f1f5f9 !important; }
div[data-testid="stSelectbox"] svg path { fill: #f1f5f9 !important; }

/* Number input */
div[data-testid="stNumberInput"] input {
    background-color: #1e293b !important; color: #f1f5f9 !important;
    -webkit-text-fill-color: #f1f5f9 !important; font-weight: 400 !important; caret-color: #f1f5f9 !important;
}
/* Text input */
div[data-testid="stTextInput"] input {
    background-color: #1e293b !important; color: #f1f5f9 !important;
    -webkit-text-fill-color: #f1f5f9 !important; font-weight: 400 !important; caret-color: #f1f5f9 !important;
}

/* ★★★ DROPDOWN POPUP — BACKGROUND PUTIH, TEKS HITAM ★★★ */
[data-baseweb="popover"] { background-color: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 12px !important; box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important; }
[data-baseweb="popover"] ul, [data-baseweb="popover"] [role="listbox"] { background-color: #ffffff !important; border-radius: 12px !important; }
[data-baseweb="popover"] ul li, [data-baseweb="popover"] [role="option"] {
    color: #0f172a !important; -webkit-text-fill-color: #0f172a !important;
    font-weight: 400 !important; background-color: transparent !important; padding: 8px 14px !important;
}
[data-baseweb="popover"] ul li:hover, [data-baseweb="popover"] [role="option"]:hover {
    background-color: #e0e7ff !important; color: #1e1b4b !important; -webkit-text-fill-color: #1e1b4b !important;
}
[data-baseweb="popover"] ul li[aria-selected="true"], [data-baseweb="popover"] [role="option"][aria-selected="true"] {
    background-color: #c7d2fe !important; color: #1e1b4b !important; -webkit-text-fill-color: #1e1b4b !important;
}
[data-baseweb="popover"] ul li span, [data-baseweb="popover"] ul li div, [data-baseweb="popover"] ul li p,
[data-baseweb="popover"] [role="option"] > div, [data-baseweb="popover"] [role="option"] span, [data-baseweb="popover"] [role="option"] p {
    color: #0f172a !important; -webkit-text-fill-color: #0f172a !important;
    font-weight: 400 !important; background-color: transparent !important;
}
[data-baseweb="popover"] ul li:hover span, [data-baseweb="popover"] ul li:hover div, [data-baseweb="popover"] ul li:hover p,
[data-baseweb="popover"] [role="option"]:hover > div, [data-baseweb="popover"] [role="option"]:hover span, [data-baseweb="popover"] [role="option"]:hover p {
    color: #1e1b4b !important; -webkit-text-fill-color: #1e1b4b !important;
}

/* Number +/- buttons */
div[data-testid="stNumberInput"] button { background-color: #e2e8f0 !important; color: #0f172a !important; border: 1px solid #cbd5e1 !important; border-radius: 6px !important; }
div[data-testid="stNumberInput"] button:hover { background-color: #cbd5e1 !important; }
div[data-testid="stNumberInput"] button svg { fill: #0f172a !important; }

/* Labels stay light */
div[data-testid="stSelectbox"] label, div[data-testid="stNumberInput"] label,
div[data-testid="stTextInput"] label, div[data-testid="stCheckbox"] label {
    color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   CARDS & LAYOUT
   ══════════════════════════════════════════════════════════════════════════ */
.metric-card { background: linear-gradient(135deg, rgba(30,41,59,0.9), rgba(15,23,42,0.9)); border: 1px solid rgba(99,102,241,0.3); border-radius: 16px; padding: 1.25rem 1.5rem; text-align: center; position: relative; overflow: hidden; }
.metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #6366f1, #06b6d4, #10b981); }
.metric-value { font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.metric-label { font-size: 0.82rem; color: #cbd5e1 !important; -webkit-text-fill-color: #cbd5e1 !important; margin-top: 4px; font-weight: 500; }

.page-header { background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(6,182,212,0.08)); border: 1px solid rgba(99,102,241,0.25); border-radius: 20px; padding: 2rem 2.5rem; margin-bottom: 2rem; position: relative; overflow: hidden; }
.page-header::after { content: ''; position: absolute; top: -50%; right: -10%; width: 300px; height: 300px; background: radial-gradient(circle, rgba(99,102,241,0.15), transparent 70%); border-radius: 50%; }
.page-title { font-size: 2rem; font-weight: 800; margin: 0; background: linear-gradient(135deg, #f1f5f9, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.page-subtitle { color: #cbd5e1 !important; -webkit-text-fill-color: #cbd5e1 !important; font-size: 0.95rem; margin-top: 0.4rem; }
.section-header { font-size: 1.05rem; font-weight: 700; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid rgba(99,102,241,0.2); }

/* ══════════════════════════════════════════════════════════════════════════
   FILE ITEMS — BACKGROUND GELAP, TEKS PUTIH CERAH
   ══════════════════════════════════════════════════════════════════════════ */
.file-item {
    background: #0a0f1c !important; border: 1px solid rgba(99,102,241,0.45) !important;
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
    display: flex; align-items: center; gap: 0.75rem;
}
.file-item:hover { border-color: rgba(99,102,241,0.75) !important; background: #0e1628 !important; }
.file-item, .file-item *, .file-item span, .file-item div, .file-item p, .file-item strong {
    color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1 !important;
}
.file-name { font-weight: 700 !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.92rem; }
.file-size { font-size: 0.82rem !important; color: #c7d2fe !important; -webkit-text-fill-color: #c7d2fe !important; font-weight: 500 !important; }

/* ══════════════════════════════════════════════════════════════════════════
   FILE BADGES
   ══════════════════════════════════════════════════════════════════════════ */
.file-badge { padding: 5px 14px !important; border-radius: 8px; font-size: 0.78rem !important; font-weight: 900 !important; text-transform: uppercase; letter-spacing: 0.08em; min-width: 52px; text-align: center; display: inline-block; line-height: 1.4; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.badge-pdf { background: #991b1b !important; color: #fef2f2 !important; -webkit-text-fill-color: #fef2f2 !important; border: 2px solid #f87171 !important; }
.badge-docx { background: #1e3a5f !important; color: #eff6ff !important; -webkit-text-fill-color: #eff6ff !important; border: 2px solid #60a5fa !important; }
.badge-doc { background: #1e3a5f !important; color: #eff6ff !important; -webkit-text-fill-color: #eff6ff !important; border: 2px solid #93c5fd !important; }
.badge-txt { background: #374151 !important; color: #f9fafb !important; -webkit-text-fill-color: #f9fafb !important; border: 2px solid #9ca3af !important; }
.badge-xlsx { background: #14532d !important; color: #dcfce7 !important; -webkit-text-fill-color: #dcfce7 !important; border: 2px solid #4ade80 !important; }
.badge-xls { background: #166534 !important; color: #dcfce7 !important; -webkit-text-fill-color: #dcfce7 !important; border: 2px solid #86efac !important; }
.badge-md { background: #3b0764 !important; color: #f5f3ff !important; -webkit-text-fill-color: #f5f3ff !important; border: 2px solid #a78bfa !important; }
.badge-json { background: #713f12 !important; color: #fffbeb !important; -webkit-text-fill-color: #fffbeb !important; border: 2px solid #fbbf24 !important; }
.badge-jpg, .badge-jpeg { background: #064e3b !important; color: #ecfdf5 !important; -webkit-text-fill-color: #ecfdf5 !important; border: 2px solid #34d399 !important; }
.badge-png { background: #164e63 !important; color: #ecfeff !important; -webkit-text-fill-color: #ecfeff !important; border: 2px solid #22d3ee !important; }
.badge-webp { background: #134e4a !important; color: #f0fdfa !important; -webkit-text-fill-color: #f0fdfa !important; border: 2px solid #2dd4bf !important; }
.badge-gif { background: #581c87 !important; color: #faf5ff !important; -webkit-text-fill-color: #faf5ff !important; border: 2px solid #c084fc !important; }

.status-success { background: rgba(16,185,129,0.2); color: #6ee7b7 !important; -webkit-text-fill-color: #6ee7b7 !important; border: 1px solid rgba(16,185,129,0.4); border-radius: 8px; padding: 2px 10px; font-size: 0.78rem; font-weight: 600; }
.status-error { background: rgba(239,68,68,0.2); color: #fca5a5 !important; -webkit-text-fill-color: #fca5a5 !important; border: 1px solid rgba(239,68,68,0.4); border-radius: 8px; padding: 2px 10px; font-size: 0.78rem; font-weight: 600; }
.status-pending { background: rgba(245,158,11,0.2); color: #fde68a !important; -webkit-text-fill-color: #fde68a !important; border: 1px solid rgba(245,158,11,0.4); border-radius: 8px; padding: 2px 10px; font-size: 0.78rem; font-weight: 600; }
.status-saved { background: rgba(6,182,212,0.2); color: #67e8f9 !important; -webkit-text-fill-color: #67e8f9 !important; border: 1px solid rgba(6,182,212,0.4); border-radius: 8px; padding: 2px 10px; font-size: 0.78rem; font-weight: 600; }

/* ══════════════════════════════════════════════════════════════════════════
   BUTTONS
   ══════════════════════════════════════════════════════════════════════════ */
div.stButton > button { border-radius: 10px !important; font-weight: 600 !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #6366f1, #4f46e5) !important; border: none !important; box-shadow: 0 4px 20px rgba(99,102,241,0.4) !important; }
div.stButton > button[kind="primary"]:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 30px rgba(99,102,241,0.55) !important; }
div.stButton > button[kind="secondary"] { background: rgba(51,65,85,0.8) !important; border: 1px solid rgba(100,116,139,0.4) !important; color: #f1f5f9 !important; -webkit-text-fill-color: #f1f5f9 !important; }
.big-process-btn > div > button { background: linear-gradient(135deg, #10b981, #059669) !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; font-size: 1.1rem !important; padding: 0.75rem 2rem !important; border-radius: 12px !important; border: none !important; box-shadow: 0 6px 30px rgba(16,185,129,0.45) !important; width: 100% !important; }

/* ══════════════════════════════════════════════════════════════════════════
   INFO BOX & WARN BOX
   ══════════════════════════════════════════════════════════════════════════ */
.info-box { background: #162032 !important; border: 1px solid rgba(99,102,241,0.4) !important; border-radius: 12px; padding: 1rem 1.25rem; font-size: 0.88rem; line-height: 1.6; }
.info-box, .info-box p, .info-box span, .info-box div, .info-box li, .info-box small { color: #e0e7ff !important; -webkit-text-fill-color: #e0e7ff !important; background-color: transparent !important; }
.info-box strong, .info-box b { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.info-box code { color: #fbbf24 !important; -webkit-text-fill-color: #fbbf24 !important; background-color: rgba(30,41,59,0.8) !important; }

.warn-box { background: #1c1507 !important; border: 1px solid rgba(245,158,11,0.5) !important; border-radius: 12px; padding: 1rem 1.25rem; font-size: 0.88rem; line-height: 1.6; }
.warn-box, .warn-box p, .warn-box span, .warn-box div, .warn-box li, .warn-box small { color: #fef3c7 !important; -webkit-text-fill-color: #fef3c7 !important; background-color: transparent !important; }
.warn-box strong, .warn-box b { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.warn-box code { color: #fde68a !important; -webkit-text-fill-color: #fde68a !important; background-color: rgba(30,41,59,0.8) !important; padding: 2px 6px !important; border-radius: 4px !important; }

.gradient-divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(99,102,241,0.4), transparent); margin: 1.5rem 0; }
.stProgress > div > div > div > div { background: linear-gradient(90deg, #6366f1, #06b6d4, #10b981) !important; }

.stTabs [data-baseweb="tab-list"] { background: rgba(15,23,42,0.6) !important; border-radius: 12px !important; padding: 4px !important; border: 1px solid rgba(99,102,241,0.2) !important; }
.stTabs [data-baseweb="tab"] { border-radius: 8px !important; font-weight: 600 !important; color: #cbd5e1 !important; -webkit-text-fill-color: #cbd5e1 !important; }
.stTabs [aria-selected="true"] { background: rgba(99,102,241,0.25) !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }

.streamlit-expanderHeader { background: rgba(30,41,59,0.7) !important; border: 1px solid rgba(99,102,241,0.2) !important; border-radius: 10px !important; font-weight: 600 !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.streamlit-expanderHeader p, .streamlit-expanderHeader span { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.streamlit-expanderContent, .streamlit-expanderContent > div, .streamlit-expanderContent > div > div { background-color: transparent !important; border: none !important; }

/* ══════════════════════════════════════════════════════════════════════════════════════════
   ★★★ FILE UPLOADER — ZONA UPLOAD & DAFTAR FILE TERLIHAT JELAS ★★★
   ★★★ PERHATIAN: Nama file di dalam uploader HARUS terlihat jelas          ★★★
   ══════════════════════════════════════════════════════════════════════════════════════════ */
[data-testid="stFileUploader"] {
    border: 2px dashed rgba(99,102,241,0.45) !important; border-radius: 16px !important;
    background: rgba(30,41,59,0.45) !important; padding: 0.5rem !important;
}
[data-testid="stFileUploader"]:hover, [data-testid="stFileUploader"]:focus-within {
    border-color: rgba(99,102,241,0.9) !important; background: rgba(99,102,241,0.08) !important;
}
[data-testid="stFileUploader"] section { border: none !important; background: transparent !important; padding: 1.5rem 1rem !important; }
[data-testid="stFileUploader"] section, [data-testid="stFileUploader"] section > div { color: #e0e7ff !important; -webkit-text-fill-color: #e0e7ff !important; }
[data-testid="stFileUploaderDropzoneInstructions"] > div,
[data-testid="stFileUploaderDropzoneInstructions"] > div > small,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: #c7d2fe !important; -webkit-text-fill-color: #c7d2fe !important; font-weight: 500 !important; opacity: 1 !important;
}

/* ★★★ NAMA FILE SETELAH UPLOAD — HITAM / GELAP di BACKGROUND TERANG ★★★ */
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
    background: #f1f5f9 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
}
/* ★ Semua teks di dalam file item uploader — HITAM */
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] > div,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] > div > div,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] p,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] strong {
    color: #0f172a !important;
    -webkit-text-fill-color: #0f172a !important;
    font-weight: 400 !important;
    opacity: 1 !important;
}

/* ★ Filename text specifically — SANGAT JELAS */
[data-testid="stFileInfoFileName"],
[data-testid="stFileInfoFileName"] span,
[data-testid="stFileInfoFileName"] div,
[data-testid="stFileInfoFileName"] p {
    color: #0f172a !important;
    -webkit-text-fill-color: #0f172a !important;
    font-weight: 600 !important;
    opacity: 1 !important;
}

/* ★ Browse / Delete button di uploader */
[data-testid="stFileUploader"] button {
    background-color: rgba(99,102,241,0.3) !important;
    color: #ffffff !important; -webkit-text-fill-color: #ffffff !important;
    border: 1px solid rgba(99,102,241,0.5) !important; border-radius: 8px !important;
}

/* ★ Input file path */
[data-testid="stFileUploader"] [data-testid="stFormattedInput"] {
    color: #0f172a !important; -webkit-text-fill-color: #0f172a !important; background-color: #f1f5f9 !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   ALERT / TOAST / DOWNLOAD / EMPTY STATE
   ══════════════════════════════════════════════════════════════════════════ */
.stAlert { border-radius: 12px !important; }
[data-testid="stAlert"] p, [data-testid="stAlert"] span, [data-testid="stAlert"] div { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
a.stDownloadButton > button { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.empty-state-title { font-weight: 600 !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; font-size: 1.1rem !important; margin-bottom: 0.5rem !important; }
.empty-state-desc { color: #cbd5e1 !important; -webkit-text-fill-color: #cbd5e1 !important; font-size: 0.9rem !important; }

/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR HEADER
   ══════════════════════════════════════════════════════════════════════════ */
.sidebar-logo-wrapper { background: linear-gradient(135deg, #1e293b, #0f172a) !important; border: 2px solid rgba(99,102,241,0.4) !important; border-radius: 20px !important; padding: 1.2rem 1rem !important; margin-bottom: 0.5rem !important; display: inline-block !important; text-align: center !important; width: 100% !important; box-sizing: border-box !important; }
.sidebar-logo-icon { font-size: 3rem !important; line-height: 1 !important; margin-bottom: 0.3rem !important; filter: drop-shadow(0 0 8px rgba(99,102,241,0.6)) brightness(1.3) !important; }
.sidebar-title { font-size: 1.25rem !important; font-weight: 800 !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; letter-spacing: 0.02em !important; margin-top: 0.4rem !important; }
.sidebar-version { font-size: 0.78rem !important; color: #94a3b8 !important; -webkit-text-fill-color: #94a3b8 !important; margin-top: 2px !important; }
.session-id-box { background: rgba(99,102,241,0.15) !important; border: 1px solid rgba(99,102,241,0.4) !important; border-radius: 10px !important; padding: 0.75rem !important; margin-bottom: 1rem !important; }
.session-id-text { font-family: monospace !important; font-size: 0.75rem !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; word-break: break-all !important; }

.summary-row { display: flex; justify-content: space-between; padding: 0.45rem 0; border-bottom: 1px solid rgba(71,85,105,0.3); font-size: 0.9rem; }
.summary-label { color: #a5b4fc !important; -webkit-text-fill-color: #a5b4fc !important; font-weight: 500; }
.summary-value { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; font-weight: 700; }
.detail-label { color: #a5b4fc !important; -webkit-text-fill-color: #a5b4fc !important; }
.detail-value { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; font-weight: 600; }
.counter-box { background: #0c1222 !important; border: 1px solid rgba(99,102,241,0.4) !important; border-radius: 10px !important; padding: 0.6rem 1rem !important; font-size: 0.85rem; color: #f1f5f9 !important; -webkit-text-fill-color: #f1f5f9 !important; }
.counter-box strong { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
.stSlider label { color: #f1f5f9 !important; -webkit-text-fill-color: #f1f5f9 !important; }

/* ══════════════════════════════════════════════════════════════════════════
   CODE BLOCK / JSON PREVIEW
   ══════════════════════════════════════════════════════════════════════════ */
.stCodeBlock, .stCodeBlock > div, .stCodeBlock > div > div { background-color: #0f172a !important; border-radius: 12px !important; border: 1px solid rgba(99,102,241,0.3) !important; }
.stCodeBlock pre, .stCodeBlock code, .stCodeBlock pre code { background-color: #0f172a !important; color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important; font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace !important; font-size: 0.85rem !important; line-height: 1.6 !important; }
.stCodeBlock * { color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important; opacity: 1 !important; }
.stCodeBlock .token.keyword, .stCodeBlock code .hljs-keyword, .stCodeBlock code .hljs-literal { color: #c084fc !important; -webkit-text-fill-color: #c084fc !important; }
.stCodeBlock .token.string, .stCodeBlock code .hljs-string { color: #6ee7b7 !important; -webkit-text-fill-color: #6ee7b7 !important; }
.stCodeBlock .token.number, .stCodeBlock code .hljs-number { color: #fbbf24 !important; -webkit-text-fill-color: #fbbf24 !important; }
.stCodeBlock .token.property, .stCodeBlock .token.attr-name, .stCodeBlock code .hljs-attr { color: #93c5fd !important; -webkit-text-fill-color: #93c5fd !important; }
.stCodeBlock .token.punctuation, .stCodeBlock code .hljs-punctuation { color: #94a3b8 !important; -webkit-text-fill-color: #94a3b8 !important; }
.stCodeBlock button[title="Copy"], .stCodeBlock button[aria-label="Copy"] { background-color: rgba(99,102,241,0.3) !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; border: 1px solid rgba(99,102,241,0.4) !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ──────────────────────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "session_id": engine.generate_session_id(),
        "uploaded_files": [], "processed_result": None, "paraphrased_result": None,
        "save_result": None, "merger_files": [], "merge_result": None,
        "active_tab": "process", "paraphrase_running": False,
        "uploader_key": 0, "merger_uploader_key": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""<div style="text-align:center;padding:0.5rem 0 1.5rem;"><div class="sidebar-logo-wrapper"><div class="sidebar-logo-icon">🤖</div><div class="sidebar-title">Generator Dataset</div><div class="sidebar-version">v2.0 · Streamlit Edition</div></div></div>""", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**🔑 Active Session**")
    st.markdown(f'<div class="session-id-box"><div class="session-id-text">{st.session_state.session_id}</div></div>', unsafe_allow_html=True)

    if st.button("🔄 New Session", use_container_width=True, key="btn_new_session"):
        st.session_state.session_id = engine.generate_session_id()
        st.session_state.uploaded_files = []; st.session_state.processed_result = None
        st.session_state.paraphrased_result = None; st.session_state.save_result = None
        st.session_state.uploader_key += 1; st.rerun()

    st.markdown("---")
    st.markdown("**⚙️ Processing Settings**")

    chunk_method = st.selectbox("Chunking Method", options=["tokens", "sentences", "paragraphs"],
        format_func=lambda x: {"tokens": "📦 Tokens", "sentences": "📝 Sentences", "paragraphs": "📄 Paragraphs"}[x], key="sb_chunk_method")
    chunk_size = st.number_input("Chunk Size", min_value=64, max_value=4096, value=512, step=64, key="ni_chunk_size")
    overlap = st.number_input("Overlap", min_value=0, max_value=500, value=20, step=10, key="ni_overlap")
    output_format = st.selectbox("Output Format", options=["training", "qa", "messages"],
        format_func=lambda x: {"training": "🎯 Training", "qa": "❓ Q&A", "messages": "💬 Messages"}[x], key="sb_output_format")
    source_tag = st.text_input("Source Tag", placeholder="e.g. company_docs", value="", key="ti_source_tag")

    st.markdown("**🧹 Cleaning Options**")
    remove_spaces = st.checkbox("Remove Extra Spaces", value=True, key="cb_remove_spaces")
    remove_special = st.checkbox("Remove Special Chars", value=False, key="cb_remove_special")

    st.markdown("**✍️ Paraphrase Settings**")
    auto_paraphrase = st.checkbox("🔄 Auto-Paraphrase", value=True, key="cb_auto_paraphrase")
    para_language_sidebar = st.selectbox("Bahasa Paraphrase", options=["auto", "id", "en"],
        format_func=lambda x: {"auto": "🌐 Auto-detect", "id": "🇮🇩 Indonesia", "en": "🇬🇧 English"}[x], key="sb_para_lang")

    st.markdown("---")
    sessions = engine.list_sessions()
    total_size = sum(s["file_size"] for s in sessions)
    st.markdown(f'<div style="font-size:0.82rem;color:#fff !important;-webkit-text-fill-color:#fff !important;text-align:center;">💾 {len(sessions)} sessions · {engine.format_size(total_size)} used</div>', unsafe_allow_html=True)

settings = {
    "chunk_method": chunk_method, "chunk_size": chunk_size, "overlap": overlap,
    "output_format": output_format, "source_tag": source_tag,
    "remove_extra_spaces": remove_spaces, "remove_special_chars": remove_special,
    "auto_paraphrase": auto_paraphrase, "paraphrase_language": para_language_sidebar,
}

# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""<div class="page-header"><h1 class="page-title">🤖 Generator Dataset</h1><p class="page-subtitle">Mengubah dokumen menjadi data pelatihan AI berkualitas tinggi.</p></div>""", unsafe_allow_html=True)
tab_process, tab_merge, tab_sessions = st.tabs(["📄 Process Documents", "🔀 Merge JSON Files", "📂 Session Manager"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1
# ══════════════════════════════════════════════════════════════════════════════

with tab_process:
    uploaded_count = len(st.session_state.uploaded_files)
    result = st.session_state.processed_result
    chunks_count = result["total_chunks"] if result else 0
    chars_count = result["stats"]["total_chars"] if result else 0
    processed_count = result["stats"]["processed_files"] if result else 0

    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in [(c1, uploaded_count, "Files Uploaded"), (c2, processed_count, "Docs Processed"), (c3, chunks_count, "Total Chunks"), (c4, engine.format_size(chars_count), "Characters")]:
        with col: st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
    col_upload, col_list = st.columns([1, 1], gap="large")
    process_clicked = False

    with col_upload:
        st.markdown('<div class="section-header">📤 Upload Documents</div>', unsafe_allow_html=True)
        st.markdown("""<div class="info-box">Supported: <strong>PDF, DOC, DOCX, TXT, MD, XLS, XLSX, JPG, PNG, JPEG, WEBP, GIF</strong> · Max <strong>200 MB</strong> · <strong>200 files</strong> · OCR supported</div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""<div style="text-align:center;margin-bottom:0.5rem;font-size:0.85rem;color:#c7d2fe !important;font-weight:600;">☁️ Drag & Drop atau klik browse</div>""", unsafe_allow_html=True)

        new_files = st.file_uploader("Upload file", type=["pdf","doc","docx","txt","md","xls","xlsx","jpg","jpeg","png","webp","gif"], accept_multiple_files=True, key=f"main_uploader_{st.session_state.uploader_key}")

        if new_files:
            engine.init_session(st.session_state.session_id); added = 0
            existing_names = {f["original_name"] for f in st.session_state.uploaded_files}
            for uf in new_files:
                if uf.name not in existing_names:
                    info = engine.save_uploaded_file(st.session_state.session_id, uf)
                    st.session_state.uploaded_files.append(info); added += 1
            if added: st.success(f"✅ {added} file(s) added!"); st.rerun()

        if st.session_state.uploaded_files:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="big-process-btn">', unsafe_allow_html=True)
            process_clicked = st.button("⚡ Proses", use_container_width=True, type="primary", key="btn_process")
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Reset", use_container_width=True, key="btn_reset_process"):
                st.session_state.uploaded_files = []; st.session_state.processed_result = None; st.session_state.paraphrased_result = None; st.session_state.save_result = None; st.session_state.uploader_key += 1; st.rerun()

        _prog_header  = st.empty()   # stage label + percentage
        _prog_bar     = st.empty()   # st.progress bar
        _prog_detail  = st.empty()   # current file name
        _prog_timing  = st.empty()   # elapsed / ETA

    with col_list:
        st.markdown('<div class="section-header">📋 File Queue</div>', unsafe_allow_html=True)
        _queue_area = st.empty()
        if not st.session_state.uploaded_files:
            _queue_area.markdown("""<div style="text-align:center;padding:3rem 1rem;"><div style="font-size:3rem;margin-bottom:1rem;">📂</div><div class="empty-state-title">No files uploaded yet</div></div>""", unsafe_allow_html=True)
        elif st.session_state.processed_result:
            _queue_area.markdown("""<div style="text-align:center;padding:3rem 1rem;"><div style="font-size:3rem;margin-bottom:1rem;">✅</div><div class="empty-state-title" style="color:#6ee7b7 !important;">Selesai</div></div>""", unsafe_allow_html=True)
        else:
            queue_html = ""
            for fi in st.session_state.uploaded_files:
                ext = fi["ext"].lstrip(".")
                queue_html += f"""<div class="file-item"><span class="file-badge badge-{ext}">{ext.upper()}</span><div style="flex:1;min-width:0;"><div class="file-name">{fi['original_name']}</div><div class="file-size">{fi['size_fmt']}</div></div></div>"""
            _queue_area.markdown(queue_html, unsafe_allow_html=True)

    if process_clicked:
        # Initial state — queue shows "Sedang diproses" with 0%
        def _render_queue_processing(pct_int=0, stage_label="Ekstrak"):
            _queue_area.markdown(
                f'<div style="text-align:center;padding:2rem 1rem;">'
                f'<div style="font-size:2rem;margin-bottom:0.5rem;">⚙️</div>'
                f'<div class="empty-state-title" style="color:#a5b4fc !important;">Sedang diproses…</div>'
                f'<div style="margin-top:0.75rem;">'
                f'<span style="font-size:4.2rem;font-weight:800;line-height:1;'
                f'background:linear-gradient(135deg,#6366f1,#06b6d4);'
                f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
                f'background-clip:text;">{pct_int}%</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True)

        _render_queue_processing(0, "Ekstrak")

        do_para = settings.get("auto_paraphrase", True)
        para_lang = settings.get("paraphrase_language", "auto")
        _t_start = [time.time()]

        def _cb(stage, cur, tot, fname=""):
            elapsed = time.time() - _t_start[0]

            if stage == "extract":
                # Extract fills 0 → 98 % of the bar
                raw_frac = cur / max(tot, 1)
                bar_val = max(0.01, raw_frac * 0.98)
                pct_int = int(bar_val * 100)
                fname_short = (fname[:38] + "…") if len(fname) > 40 else fname
                # Update queue panel with live %
                _render_queue_processing(pct_int, "Ekstrak")
                _prog_header.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);'
                    f'border-radius:8px;padding:0.55rem 0.9rem;margin-bottom:4px;">'
                    f'<span style="color:#e2e8f0;font-size:0.9rem;">📂 Ekstrak teks &nbsp;—&nbsp; '
                    f'<strong>{cur}</strong> / <strong>{tot}</strong> file selesai</span>'
                    f'<span style="color:#6ee7b7;font-weight:700;font-size:0.92rem;">{pct_int}%</span>'
                    f'</div>', unsafe_allow_html=True)
                _prog_bar.progress(bar_val)
                _prog_detail.markdown(
                    f'<div style="font-size:0.82rem;color:#94a3b8;margin-top:2px;">'
                    f'{"🔄 Sedang memproses: <strong>" + fname_short + "</strong>" if fname_short else "⏳ Memulai ekstraksi…"}'
                    f'</div>', unsafe_allow_html=True)
                if cur > 0 and elapsed > 0:
                    rate = cur / elapsed
                    eta = max(0, (tot - cur) / rate) if rate > 0 else 0
                    _prog_timing.markdown(
                        f'<div style="font-size:0.78rem;color:#64748b;">'
                        f'⏱ Berlalu: <strong>{elapsed:.1f}s</strong> &nbsp;|&nbsp; '
                        f'ETA: <strong>~{eta:.0f}s</strong> &nbsp;|&nbsp; '
                        f'Kecepatan: <strong>{rate:.1f} file/s</strong>'
                        f'</div>', unsafe_allow_html=True)

            elif stage == "paraphrase":
                # Paraphrase fills 98 % → 100 %
                raw_frac = cur / max(tot, 1)
                bar_val = min(0.98 + raw_frac * 0.02, 1.0)
                pct_int = int(bar_val * 100)
                # Update queue panel with live %
                _render_queue_processing(pct_int, "Paraphrase")
                _prog_header.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);'
                    f'border-radius:8px;padding:0.55rem 0.9rem;margin-bottom:4px;">'
                    f'<span style="color:#e2e8f0;font-size:0.9rem;">✍️ Paraphrase &nbsp;—&nbsp; '
                    f'<strong>{cur}</strong> / <strong>{tot}</strong> chunk</span>'
                    f'<span style="color:#fbbf24;font-weight:700;font-size:0.92rem;">{pct_int}%</span>'
                    f'</div>', unsafe_allow_html=True)
                _prog_bar.progress(bar_val)
                _prog_detail.markdown(
                    f'<div style="font-size:0.82rem;color:#94a3b8;margin-top:2px;">'
                    f'🔄 Memparafrase chunk ke-<strong>{cur}</strong> dari <strong>{tot}</strong>'
                    f'</div>', unsafe_allow_html=True)
                if cur > 0 and elapsed > 0:
                    rate = cur / elapsed
                    eta = max(0, (tot - cur) / rate) if rate > 0 else 0
                    _prog_timing.markdown(
                        f'<div style="font-size:0.78rem;color:#64748b;">'
                        f'⏱ Berlalu: <strong>{elapsed:.1f}s</strong> &nbsp;|&nbsp; '
                        f'ETA: <strong>~{eta:.0f}s</strong> &nbsp;|&nbsp; '
                        f'Kecepatan: <strong>{rate:.1f} chunk/s</strong>'
                        f'</div>', unsafe_allow_html=True)

        if do_para:
            try:
                rd = engine.process_and_paraphrase(
                    st.session_state.uploaded_files, settings,
                    language=para_lang, progress_callback=_cb)
                st.session_state.processed_result = rd
                st.session_state.paraphrased_result = rd
                total_elapsed = time.time() - _t_start[0]
                _prog_bar.progress(1.0)
                _prog_header.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);'
                    f'border-radius:8px;padding:0.55rem 0.9rem;margin-bottom:4px;">'
                    f'<span style="color:#6ee7b7;font-size:0.9rem;">✅ Selesai dalam '
                    f'<strong>{total_elapsed:.1f}s</strong> — '
                    f'<strong>{rd["total_chunks"]}</strong> chunk dari '
                    f'<strong>{rd["stats"]["processed_files"]}</strong> file</span>'
                    f'<span style="color:#6ee7b7;font-weight:700;font-size:0.92rem;">100%</span>'
                    f'</div>', unsafe_allow_html=True)
                _prog_detail.empty(); _prog_timing.empty()
                # Update queue to show "Selesai"
                _queue_area.markdown("""<div style="text-align:center;padding:3rem 1rem;"><div style="font-size:3rem;margin-bottom:1rem;">✅</div><div class="empty-state-title" style="color:#6ee7b7 !important;">Selesai</div></div>""", unsafe_allow_html=True)
            except Exception as ex:
                _prog_header.empty(); _prog_bar.empty(); _prog_detail.empty(); _prog_timing.empty()
                st.error(f"❌ Gagal: {ex}")
            st.rerun()
        else:
            def _extract_only_cb(stage, cur, tot, fname=""):
                _cb(stage, cur, tot, fname)
            rd = engine.process_documents(
                st.session_state.uploaded_files, settings,
                max_workers=12, progress_callback=_extract_only_cb)
            st.session_state.processed_result = rd
            total_elapsed = time.time() - _t_start[0]
            _prog_bar.progress(1.0)
            _prog_header.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);'
                f'border-radius:8px;padding:0.55rem 0.9rem;margin-bottom:4px;">'
                f'<span style="color:#6ee7b7;font-size:0.9rem;">✅ Selesai dalam '
                f'<strong>{total_elapsed:.1f}s</strong> — '
                f'<strong>{rd["total_chunks"]}</strong> chunks</span>'
                f'<span style="color:#6ee7b7;font-weight:700;font-size:0.92rem;">100%</span>'
                f'</div>', unsafe_allow_html=True)
            _prog_detail.empty(); _prog_timing.empty()
            _queue_area.markdown("""<div style="text-align:center;padding:3rem 1rem;"><div style="font-size:3rem;margin-bottom:1rem;">✅</div><div class="empty-state-title" style="color:#6ee7b7 !important;">Selesai</div></div>""", unsafe_allow_html=True)
            st.rerun()

    if st.session_state.processed_result:
        res = st.session_state.processed_result
        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-header">📊 Results</div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="info-box" style="margin-bottom:1rem;">✅ <strong>{res['stats']['processed_files']}</strong> file berhasil</div>""", unsafe_allow_html=True)
        if st.session_state.paraphrased_result:
            pr = st.session_state.paraphrased_result
            st.markdown('<div class="section-header" style="color:#6ee7b7 !important;">📋 Hasil Paraphrase</div>', unsafe_allow_html=True)
            cp, cd = st.columns([2, 1], gap="large")
            with cp:
                st.markdown('<div class="section-header">👁️ Preview</div>', unsafe_allow_html=True)
                st.code(json.dumps({"total_chunks": pr["total_chunks"], "paraphrased": True, "sample": pr["data"][:2] if pr["data"] else []}, ensure_ascii=False, indent=2), language="json")
            with cd:
                st.markdown('<div class="section-header">💾 Download</div>', unsafe_allow_html=True)
                pb = json.dumps(pr, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button("⬇️ Download JSON", data=pb, file_name=f"paraphrased_{st.session_state.session_id[:12]}.json", mime="application/json", use_container_width=True, type="primary", key="dl_para")
                st.markdown("""<div class="info-box" style="margin-top:0.75rem;">✅ Dataset siap digunakan.</div>""", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True); st.markdown("**📈 Summary**")
                si = res.get("stats", {})
                for l, v in [("Total Files", si.get("total_files",0)), ("Processed", si.get("processed_files",0)), ("Failed", si.get("failed_files",0)), ("Chunks", si.get("total_chunks",0)), ("Chars", engine.format_size(si.get("total_chars",0)))]:
                    st.markdown(f'<div class="summary-row"><span class="summary-label">{l}</span><span class="summary-value">{v}</span></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — JSON MERGER
# ══════════════════════════════════════════════════════════════════════════════

with tab_merge:
    st.markdown("""<div class="page-header" style="margin-bottom:1.5rem;"><h2 style="font-size:1.4rem;font-weight:700;color:#fbbf24 !important;-webkit-text-fill-color:#fbbf24 !important;margin:0;">🔀 JSON File Merger</h2><p style="color:#cbd5e1 !important;-webkit-text-fill-color:#cbd5e1 !important;font-size:0.88rem;margin-top:4px;">Combine multiple training JSON files into one unified dataset.</p></div>""", unsafe_allow_html=True)

    col_mu, col_mr = st.columns([1, 1], gap="large")

    with col_mu:
        st.markdown('<div class="section-header">📤 Upload JSON Files</div>', unsafe_allow_html=True)
        merge_strategy = st.selectbox("Merge Strategy", options=["auto", "data", "array", "object"],
            format_func=lambda x: {"auto": "🔍 Auto-detect", "data": "🎯 DocAI", "array": "📋 Array", "object": "🗂️ Object"}[x], key="sb_merge_strategy")
        st.markdown("""<div style="text-align:center;margin-bottom:0.5rem;font-size:0.85rem;color:#fcd34d !important;font-weight:600;">☁️ Drag & Drop JSON</div>""", unsafe_allow_html=True)

        json_uploads = st.file_uploader("Upload JSON", type=["json"], accept_multiple_files=True, key=f"json_uploader_{st.session_state.get('merger_uploader_key',0)}")

        if json_uploads:
            added = 0; existing = {f["name"] for f in st.session_state.merger_files}
            for uf in json_uploads:
                if uf.name not in existing:
                    try: st.session_state.merger_files.append({"name": uf.name, "content": json.loads(uf.read().decode("utf-8"))}); added += 1
                    except json.JSONDecodeError as e: st.error(f"❌ Invalid JSON: {uf.name}: {e}")
                    except Exception as e: st.error(f"❌ Error: {uf.name}: {e}")
            if added: st.success(f"✅ {added} JSON loaded!"); st.rerun()

        if st.session_state.merger_files:
            st.markdown("<br>", unsafe_allow_html=True)
            for mf in st.session_state.merger_files:
                c = mf["content"]
                if isinstance(c, dict) and isinstance(c.get("data"), list): detail = f"{len(c['data'])} items (DocAI)"
                elif isinstance(c, list): detail = f"{len(c)} items (array)"
                elif isinstance(c, dict): detail = f"{len(c)} keys"
                else: detail = "?"
                st.markdown(f"""<div class="file-item"><span class="file-badge badge-json">JSON</span><div style="flex:1;min-width:0;"><div class="file-name">{mf['name']}</div><div class="file-size">{detail}</div></div></div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button(f"🔀 Merge {len(st.session_state.merger_files)} Files", use_container_width=True, type="primary", key="btn_merge"):
                    with st.spinner("Merging..."): st.session_state.merge_result = engine.merge_json_files(st.session_state.merger_files, merge_strategy)
                    st.success("✅ Done!"); st.rerun()
            with bc2:
                if st.button("🔄 Reset", use_container_width=True, key="btn_reset_merge"):
                    st.session_state.merger_files = []; st.session_state.merge_result = None
                    st.session_state.merger_uploader_key = st.session_state.get("merger_uploader_key", 0) + 1; st.rerun()
        else:
            st.markdown("""<div style="text-align:center;padding:3rem 1rem;"><div style="font-size:3rem;margin-bottom:1rem;">🔀</div><div class="empty-state-title">Upload JSON to merge</div></div>""", unsafe_allow_html=True)

    with col_mr:
        st.markdown('<div class="section-header">📊 Results</div>', unsafe_allow_html=True)
        if st.session_state.merge_result:
            mr = st.session_state.merge_result; mode = mr["merge_mode"]; ms = mr["stats"]; mg = mr["merged"]
            mc = {"data": "#6ee7b7", "array": "#a5b4fc", "object": "#67e8f9"}.get(mode, "#94a3b8")
            ti = mg.get("total", len(mg)) if isinstance(mg, dict) else len(mg)
            st.markdown(f"""<div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;"><div class="counter-box">🎯 <strong style="color:{mc} !important;">{mode.upper()}</strong></div><div class="counter-box">📦 <strong style="color:#fbbf24 !important;">{ti:,}</strong></div><div class="counter-box">📄 <strong>{ms['files_count']}</strong></div></div>""", unsafe_allow_html=True)
            with st.expander("📋 Breakdown"):
                for ic in ms.get("item_counts", []): st.markdown(f'<div class="summary-row"><span class="summary-label">{ic["file"]}</span><span class="summary-value">{ic.get("items",ic.get("keys","?"))}</span></div>', unsafe_allow_html=True)
            pd = mg[:3] if isinstance(mg, list) else {k:v for i,(k,v) in enumerate(mg.items()) if i<5}
            st.code(json.dumps(pd, ensure_ascii=False, indent=2)[:1200], language="json")
            jb = json.dumps(mg, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("⬇️ Download Merged JSON", data=jb, file_name=f"merged_{int(time.time())}.json", mime="application/json", use_container_width=True, type="primary", key="dl_merged")
        else:
            st.markdown("""<div style="text-align:center;padding:4rem 1rem;"><div style="font-size:3rem;margin-bottom:1rem;">📊</div><div class="empty-state-title">Results appear here</div></div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SESSION MANAGER
# ══════════════════════════════════════════════════════════════════════════════

with tab_sessions:
    st.markdown("""<div class="page-header" style="margin-bottom:1.5rem;"><h2 style="font-size:1.4rem;font-weight:700;color:#22d3ee !important;-webkit-text-fill-color:#22d3ee !important;margin:0;">📂 Session Manager</h2><p style="color:#cbd5e1 !important;-webkit-text-fill-color:#cbd5e1 !important;font-size:0.88rem;margin-top:4px;">View, inspect, and clean up sessions.</p></div>""", unsafe_allow_html=True)

    if st.button("🔄 Refresh", use_container_width=True, key="btn_refresh"): st.rerun()

    sessions = engine.list_sessions()
    if not sessions:
        st.markdown("""<div style="text-align:center;padding:4rem;"><div style="font-size:3rem;">📭</div><div class="empty-state-title">No sessions</div></div>""", unsafe_allow_html=True)
    else:
        ts = sum(s["file_size"] for s in sessions)
        for col, val, label in [(c, v, l) for c, v, l in zip(st.columns(3), [len(sessions), engine.format_size(ts), sum(s["file_count"] for s in sessions)], ["Sessions", "Storage", "Files"])]:
            with col: st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        with st.expander("🧹 Cleanup All"):
            st.markdown(f"""<div class="warn-box">⚠️ Hapus <strong>SEMUA</strong> session kecuali aktif (<code>{st.session_state.session_id[:16]}…</code>)</div>""", unsafe_allow_html=True)
            oc = len([s for s in sessions if s["id"] != st.session_state.session_id])
            os = sum(s["file_size"] for s in sessions if s["id"] != st.session_state.session_id)
            st.markdown(f"""<div class="info-box">📊 Dihapus: <strong>{oc}</strong> · 💾 <strong>{engine.format_size(os)}</strong></div>""", unsafe_allow_html=True)
            if st.button("🧹 Run Cleanup", use_container_width=True, type="primary", key="btn_cleanup"):
                r = engine.delete_all_sessions(st.session_state.session_id)
                if r["deleted"] > 0: st.success(f"✅ Deleted {r['deleted']}, freed {r['freed_fmt']}"); time.sleep(1.5); st.rerun()
                else: st.warning("⚠️ Nothing to clean.")

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
        
        for s in sessions:
            ia = s["id"] == st.session_state.session_id
            ab = '<span class="status-saved">ACTIVE</span>' if ia else ""
            with st.expander(f"{'📍' if ia else '📁'} {s['id']} · {s['file_size_fmt']} · {s['modified_at']}"):
                ci, ca = st.columns([3, 1]); dt = engine.get_session_detail(s["id"])
                with ci:
                    st.markdown(f"""{ab}<div style="margin-top:0.5rem;font-size:0.88rem;line-height:1.8;"><div><span class="detail-label">Created:</span> <span class="detail-value">{s['created_at']}</span></div><div><span class="detail-label">Modified:</span> <span class="detail-value">{s['modified_at']}</span></div><div><span class="detail-label">Files:</span> <span class="detail-value">{s['file_count']}</span></div><div><span class="detail-label">Size:</span> <span class="detail-value">{s['file_size_fmt']}</span></div></div>""", unsafe_allow_html=True)
                with ca:
                    if dt:
                        for pf in dt.get("structure", {}).get("processed", []):
                            if pf["name"] == "output.json":
                                op = Path(engine.UPLOADS_DIR) / s["id"] / "processed" / "output.json"
                                if op.exists(): st.download_button("⬇️", data=op.read_bytes(), file_name=f"output_{s['id'][:12]}.json", mime="application/json", key=f"dl_{s['id']}", use_container_width=True)
                    if not ia:
                        if st.button("🔄 Switch", key=f"sw_{s['id']}", use_container_width=True): st.session_state.session_id = s["id"]; st.session_state.uploaded_files = []; st.session_state.processed_result = None; st.session_state.uploader_key += 1; st.rerun()
                        if st.button("🗑️ Delete", key=f"del_{s['id']}", use_container_width=True): engine.delete_session(s["id"]); st.success("✅ Deleted"); st.rerun()
                    else: st.markdown('<div class="status-saved" style="text-align:center;">Current</div>', unsafe_allow_html=True)
