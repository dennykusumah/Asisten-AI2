"""
app.py — Streamlit UI for SNI Core JSONL Generator
Run: streamlit run app.py
"""

import os
import time
import threading
import queue
from pathlib import Path
import json

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SNI Core Generator",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

:root {
    --bg: #0a0e14;
    --surface: #141a24;
    --surface2: #1c2535;
    --border: #243044;
    --accent: #4d9eff;
    --accent2: #00e5a0;
    --warn: #ffb347;
    --error: #ff5f6d;
    --text: #c8d6e8;
    --text-dim: #5c7a9e;
    --mono: 'IBM Plex Mono', monospace;
    --sans: 'IBM Plex Sans', sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--sans);
    background-color: var(--bg) !important;
    color: var(--text) !important;
}

.stApp { background-color: var(--bg) !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* Header */
.sni-header {
    display: flex; align-items: center; gap: 16px;
    padding: 24px 0 8px;
    border-bottom: 2px solid var(--accent);
    margin-bottom: 28px;
}
.sni-header .badge {
    background: var(--accent);
    color: #000;
    font-family: var(--mono);
    font-weight: 600;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 2px;
    letter-spacing: 1.5px;
}
.sni-header h1 {
    font-family: var(--mono);
    font-size: 22px;
    font-weight: 600;
    color: #fff;
    margin: 0;
    letter-spacing: -0.5px;
}
.sni-header p { color: var(--text-dim); font-size: 13px; margin: 0; }

/* Metric cards */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px 20px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
}
.metric-card.green::before { background: var(--accent2); }
.metric-card.warn::before { background: var(--warn); }
.metric-card.red::before { background: var(--error); }
.metric-card .label {
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 1.5px;
    color: var(--text-dim);
    text-transform: uppercase;
    margin-bottom: 6px;
}
.metric-card .value {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 600;
    color: #fff;
    line-height: 1;
}
.metric-card .sub { font-size: 11px; color: var(--text-dim); margin-top: 4px; }

/* Log terminal */
.log-terminal {
    background: #060a10;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    height: 280px;
    overflow-y: auto;
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.7;
}
.log-ok    { color: var(--accent2); }
.log-skip  { color: var(--text-dim); }
.log-error { color: var(--error); }
.log-info  { color: var(--accent); }

/* Progress bar */
.progress-wrap {
    background: var(--surface2);
    border-radius: 3px;
    height: 6px;
    margin: 12px 0;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent) 0%, var(--accent2) 100%);
    border-radius: 3px;
    transition: width 0.3s ease;
}

/* Inputs */
.stTextInput input, .stNumberInput input {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    border-radius: 4px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}

/* Buttons */
.stButton button {
    background: var(--accent) !important;
    color: #000 !important;
    font-family: var(--mono) !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 4px !important;
    letter-spacing: 0.5px !important;
    transition: all 0.2s !important;
}
.stButton button:hover {
    background: var(--accent2) !important;
    transform: translateY(-1px);
}
.stButton button:disabled {
    background: var(--surface2) !important;
    color: var(--text-dim) !important;
}

/* Preview table */
.preview-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-size: 12px;
}
.preview-row .sni-num {
    font-family: var(--mono);
    color: var(--accent);
    font-weight: 600;
    font-size: 11px;
}
.preview-row .sni-title { color: #fff; font-weight: 600; font-size: 14px; }
.preview-row .sni-cat {
    display: inline-block;
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 1px 8px;
    border-radius: 2px;
    font-size: 10px;
    font-family: var(--mono);
    color: var(--accent2);
    letter-spacing: 1px;
}
.preview-row .field-label {
    color: var(--text-dim);
    font-family: var(--mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 8px;
    margin-bottom: 2px;
}
.preview-row .field-val { color: var(--text); font-size: 12px; }

/* Section headers */
.section-title {
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin-bottom: 16px;
}

/* Status pill */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}
.status-pill.idle { background: var(--surface2); color: var(--text-dim); border: 1px solid var(--border); }
.status-pill.running { background: rgba(77,158,255,0.15); color: var(--accent); border: 1px solid var(--accent); }
.status-pill.done { background: rgba(0,229,160,0.15); color: var(--accent2); border: 1px solid var(--accent2); }
.status-pill.error { background: rgba(255,95,109,0.15); color: var(--error); border: 1px solid var(--error); }

div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "running": False,
        "done": False,
        "stats": {"total": 0, "ok": 0, "skip": 0, "error": 0},
        "log_lines": [],
        "last_record": None,
        "start_time": None,
        "eta": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sni-header">
  <div>
    <span class="badge">BSN · TOOL</span>
    <h1>SNI Core Generator</h1>
    <p>Ekstrak ribuan PDF/Word SNI → sni_core.jsonl via Gemini Flash</p>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar config ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-title">⚙ Konfigurasi</div>', unsafe_allow_html=True)

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="AIza...",
        help="Dapatkan di https://aistudio.google.com/apikey"
    )

    input_folder = st.text_input(
        "Folder Input (PDF/Word)",
        placeholder="/path/to/sni_files",
        help="Folder yang berisi file PDF dan DOCX SNI"
    )

    output_file = st.text_input(
        "Output File",
        value="sni_core.jsonl",
        help="Path file output JSONL"
    )

    rpm = st.number_input(
        "Request Per Menit (RPM)",
        min_value=1, max_value=60, value=15,
        help="Gemini Flash free tier: 15 RPM. Paid tier bisa lebih."
    )

    st.markdown("---")
    st.markdown('<div class="section-title">ℹ Info</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:11px; color: var(--text-dim); font-family: var(--mono); line-height:1.8">
    • Model: gemini-1.5-flash<br>
    • Max chars/file: 12.000<br>
    • Output: 1 baris JSONL/SNI<br>
    • Resume otomatis via checkpoint<br>
    • Rate limit aman via sleep
    </div>
    """, unsafe_allow_html=True)


# ── Metrics row ───────────────────────────────────────────────────────────────
s = st.session_state.stats
total_done = s["ok"] + s["skip"] + s["error"]
pct = (total_done / s["total"] * 100) if s["total"] > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="metric-card">
      <div class="label">Total File</div>
      <div class="value">{s['total']:,}</div>
      <div class="sub">PDF + DOCX ditemukan</div>
    </div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card green">
      <div class="label">Berhasil</div>
      <div class="value">{s['ok']:,}</div>
      <div class="sub">record di JSONL</div>
    </div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-card warn">
      <div class="label">Dilewati</div>
      <div class="value">{s['skip']:,}</div>
      <div class="sub">sudah diproses</div>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="metric-card red">
      <div class="label">Error</div>
      <div class="value">{s['error']:,}</div>
      <div class="sub">gagal ekstraksi</div>
    </div>""", unsafe_allow_html=True)

# Progress bar
st.markdown(f"""
<div class="progress-wrap">
  <div class="progress-fill" style="width:{pct:.1f}%"></div>
</div>
<div style="font-family:var(--mono);font-size:11px;color:var(--text-dim);text-align:right">
  {pct:.1f}% selesai — {total_done:,} / {s['total']:,} file
</div>
""", unsafe_allow_html=True)


# ── Status + Control ──────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
ctrl_col, status_col = st.columns([1, 3])

with ctrl_col:
    btn_disabled = st.session_state.running or not api_key or not input_folder
    start_btn = st.button("▶ Mulai Proses", disabled=btn_disabled, use_container_width=True)

    if st.session_state.running:
        if st.button("⏹ Stop", use_container_width=True):
            st.session_state.running = False

with status_col:
    if st.session_state.running:
        elapsed = time.time() - (st.session_state.start_time or time.time())
        m, sec = divmod(int(elapsed), 60)
        st.markdown(f'<span class="status-pill running">● BERJALAN — {m:02d}:{sec:02d}</span>', unsafe_allow_html=True)
    elif st.session_state.done:
        st.markdown('<span class="status-pill done">✓ SELESAI</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill idle">○ IDLE</span>', unsafe_allow_html=True)


# ── Log terminal ──────────────────────────────────────────────────────────────
st.markdown('<br><div class="section-title">📟 Log Real-time</div>', unsafe_allow_html=True)
log_placeholder = st.empty()

def render_log():
    lines = st.session_state.log_lines[-80:]  # last 80 lines
    html = '<div class="log-terminal">'
    for line in lines:
        cls = "log-ok" if "✓" in line else "log-error" if "✗" in line else "log-skip" if "→" in line else "log-info"
        html += f'<div class="{cls}">{line}</div>'
    html += "</div>"
    log_placeholder.markdown(html, unsafe_allow_html=True)

render_log()


# ── Last record preview ───────────────────────────────────────────────────────
st.markdown('<br><div class="section-title">🔍 Record Terakhir</div>', unsafe_allow_html=True)
preview_placeholder = st.empty()

def render_preview(rec):
    if rec is None:
        preview_placeholder.markdown(
            '<div style="color:var(--text-dim);font-family:var(--mono);font-size:12px">Belum ada record...</div>',
            unsafe_allow_html=True
        )
        return
    preview_placeholder.markdown(f"""
    <div class="preview-row">
      <span class="sni-num">{rec.no_sni}</span>
      <span class="sni-cat" style="margin-left:8px">{rec.kategori}</span>
      <div class="sni-title" style="margin-top:6px">{rec.judul}</div>
      <div class="field-label">Ruang Lingkup</div>
      <div class="field-val">{rec.ruang_lingkup}</div>
      <div class="field-label">Persyaratan</div>
      <div class="field-val">{rec.persyaratan[:300]}</div>
      <div class="field-label">Metode Uji</div>
      <div class="field-val">{rec.metode_uji[:200]}</div>
      <div class="field-label">Keywords</div>
      <div class="field-val" style="color:var(--accent)">{rec.keywords}</div>
    </div>
    """, unsafe_allow_html=True)

render_preview(st.session_state.last_record)


# ── JSONL preview ─────────────────────────────────────────────────────────────
out_path = Path(output_file) if output_file else Path("sni_core.jsonl")
if out_path.exists() and out_path.stat().st_size > 0:
    st.markdown('<br><div class="section-title">📂 Preview JSONL Output (5 baris terakhir)</div>', unsafe_allow_html=True)
    with out_path.open(encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[-5:]:
        try:
            obj = json.loads(line)
            st.json(obj)
        except Exception:
            st.code(line.strip(), language="json")

    col_dl, _ = st.columns([1, 3])
    with col_dl:
        st.download_button(
            "⬇ Download sni_core.jsonl",
            data=out_path.read_bytes(),
            file_name=out_path.name,
            mime="application/jsonl",
            use_container_width=True,
        )


# ── Processing logic ──────────────────────────────────────────────────────────
if start_btn and not st.session_state.running:
    from engine import process_folder, discover_files, count_jsonl_lines

    in_path = Path(input_folder)
    if not in_path.exists():
        st.error(f"❌ Folder tidak ditemukan: {input_folder}")
        st.stop()

    checkpoint = Path(".sni_checkpoint.txt")
    all_files = discover_files(in_path)

    st.session_state.running = True
    st.session_state.done = False
    st.session_state.start_time = time.time()
    st.session_state.stats = {
        "total": len(all_files), "ok": 0, "skip": 0, "error": 0
    }
    st.session_state.log_lines = [
        f"[INFO] Ditemukan {len(all_files):,} file di {in_path}",
        f"[INFO] Output → {output_file}",
        f"[INFO] RPM limit: {rpm}",
        "[INFO] Memulai proses...",
    ]

    # Run synchronously with st.rerun loop
    gen = process_folder(
        api_key=api_key,
        input_folder=in_path,
        output_file=out_path,
        checkpoint_file=checkpoint,
        rpm_limit=int(rpm),
    )

    for result in gen:
        if not st.session_state.running:
            st.session_state.log_lines.append("[WARN] Proses dihentikan oleh user.")
            break

        fname = result["file"]
        idx = result["index"]
        total = result["total"]
        status = result["status"]

        if status == "ok":
            st.session_state.stats["ok"] += 1
            rec = result["record"]
            st.session_state.last_record = rec
            st.session_state.log_lines.append(
                f"✓ [{idx}/{total}] {fname} → {rec.no_sni} · {rec.judul[:40]}"
            )
        elif status == "skip":
            st.session_state.stats["skip"] += 1
            st.session_state.log_lines.append(
                f"→ [{idx}/{total}] {fname} (skip — sudah ada)"
            )
        else:
            st.session_state.stats["error"] += 1
            st.session_state.log_lines.append(
                f"✗ [{idx}/{total}] {fname} — {result['msg']}"
            )

        # Rerender every 5 files to avoid too many reruns
        if idx % 5 == 0:
            render_log()
            render_preview(st.session_state.last_record)
            st.rerun()

    st.session_state.running = False
    st.session_state.done = True
    st.session_state.log_lines.append(
        f"[DONE] Selesai! {st.session_state.stats['ok']:,} record di {output_file}"
    )
    render_log()
    st.rerun()
