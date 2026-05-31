"""
app.py — SNI Core Generator · Streamlit UI
Upload PDF/Word → Gemini Flash → sni_core.jsonl
Run: streamlit run app.py
"""

import io
import os
import re
import json
import time
import tempfile
import logging
from pathlib import Path
from dataclasses import asdict

import streamlit as st

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SNI Core Generator",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@400;600;700;800&display=swap');

:root {
    --bg:       #080d14;
    --surf:     #0e1621;
    --surf2:    #141f30;
    --surf3:    #1a2840;
    --border:   #1e3050;
    --border2:  #243860;
    --acc:      #3b82f6;
    --acc2:     #10b981;
    --warn:     #f59e0b;
    --err:      #ef4444;
    --txt:      #c5d8f0;
    --txt2:     #4e6f96;
    --mono:     'JetBrains Mono', monospace;
    --head:     'Syne', sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: var(--mono) !important;
    background: var(--bg) !important;
    color: var(--txt) !important;
}
.stApp { background: var(--bg) !important; }
.stApp > header { display: none; }
[data-testid="stSidebar"] { display: none; }

/* ── App shell ── */
.shell {
    max-width: 1280px;
    margin: 0 auto;
    padding: 28px 24px;
}

/* ── Top nav bar ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 28px;
}
.topbar-brand {
    display: flex; align-items: center; gap: 12px;
}
.topbar-icon {
    width: 36px; height: 36px;
    background: var(--acc);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
}
.topbar-title {
    font-family: var(--head);
    font-size: 18px;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.3px;
}
.topbar-sub {
    font-size: 10px;
    color: var(--txt2);
    letter-spacing: 2px;
    text-transform: uppercase;
}
.topbar-badge {
    background: rgba(59,130,246,0.15);
    border: 1px solid rgba(59,130,246,0.4);
    color: var(--acc);
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 20px;
}

/* ── Metric cards ── */
.metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 28px;
}
.mcard {
    background: var(--surf);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 20px;
    position: relative;
    overflow: hidden;
}
.mcard::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: var(--acc);
}
.mcard.g::after { background: var(--acc2); }
.mcard.w::after { background: var(--warn); }
.mcard.r::after { background: var(--err); }
.mcard-num {
    font-family: var(--head);
    font-size: 32px;
    font-weight: 800;
    color: #fff;
    line-height: 1;
    margin-bottom: 6px;
}
.mcard-label {
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--txt2);
}

/* ── Two-col layout ── */
.twocol {
    display: grid;
    grid-template-columns: 1fr 420px;
    gap: 20px;
    align-items: start;
}

/* ── Panel ── */
.panel {
    background: var(--surf);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
}
.panel-title {
    font-family: var(--head);
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 0.3px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.panel-title .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--acc);
}

/* ── Upload zone ── */
.upload-hint {
    background: var(--surf2);
    border: 1px dashed var(--border2);
    border-radius: 8px;
    padding: 14px 16px;
    font-size: 11px;
    color: var(--txt2);
    margin-bottom: 16px;
    line-height: 1.6;
}
.upload-hint strong { color: var(--txt); }

/* ── File queue ── */
.file-queue { margin-top: 4px; }
.fq-item {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--surf2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 12px;
}
.fq-badge {
    background: var(--err);
    color: #fff;
    font-size: 9px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    letter-spacing: 1px;
    flex-shrink: 0;
}
.fq-badge.doc { background: #2563eb; }
.fq-name { color: var(--txt); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fq-size { color: var(--txt2); font-size: 10px; flex-shrink: 0; }
.fq-status { font-size: 10px; flex-shrink: 0; }
.fq-status.ok    { color: var(--acc2); }
.fq-status.err   { color: var(--err); }
.fq-status.proc  { color: var(--warn); }
.fq-status.wait  { color: var(--txt2); }

/* ── Progress bar ── */
.prog-wrap {
    background: var(--surf3);
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
    margin: 12px 0 6px;
}
.prog-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--acc), var(--acc2));
    border-radius: 4px;
    transition: width 0.4s ease;
}
.prog-label {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--txt2);
    margin-bottom: 16px;
}

/* ── Log terminal ── */
.terminal {
    background: #040810;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    height: 240px;
    overflow-y: auto;
    font-size: 11px;
    line-height: 1.8;
}
.t-ok   { color: var(--acc2); }
.t-err  { color: var(--err); }
.t-skip { color: var(--txt2); }
.t-info { color: var(--acc); }
.t-warn { color: var(--warn); }

/* ── Config panel ── */
.cfg-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 14px;
}
.cfg-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--txt2);
}

/* ── Streamlit widget overrides ── */
.stTextInput input, .stNumberInput input, .stPasswordInput input {
    background: var(--surf3) !important;
    border: 1px solid var(--border2) !important;
    color: var(--txt) !important;
    font-family: var(--mono) !important;
    font-size: 12px !important;
    border-radius: 6px !important;
    padding: 8px 12px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--acc) !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}

/* Buttons */
div[data-testid="stButton"] > button {
    width: 100% !important;
    font-family: var(--mono) !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 1px !important;
    border-radius: 8px !important;
    padding: 12px 20px !important;
    transition: all 0.2s !important;
    border: none !important;
}
div[data-testid="stButton"]:nth-of-type(1) > button {
    background: linear-gradient(135deg, var(--acc), #6366f1) !important;
    color: #fff !important;
}
div[data-testid="stButton"]:nth-of-type(1) > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(59,130,246,0.4) !important;
}
div[data-testid="stButton"]:nth-of-type(1) > button:disabled {
    background: var(--surf3) !important;
    color: var(--txt2) !important;
    transform: none !important;
    box-shadow: none !important;
}

div[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, var(--acc2), #059669) !important;
    color: #fff !important;
    width: 100% !important;
    font-family: var(--mono) !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 1px !important;
    border-radius: 8px !important;
    padding: 12px 20px !important;
    border: none !important;
    transition: all 0.2s !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(16,185,129,0.4) !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: var(--surf2) !important;
    border: 1px dashed var(--border2) !important;
    border-radius: 8px !important;
    padding: 8px !important;
}
[data-testid="stFileUploader"] * { color: var(--txt2) !important; font-family: var(--mono) !important; }
[data-testid="stFileUploaderDropzone"] { padding: 20px !important; }

/* Label */
.stTextInput label, .stNumberInput label, .stPasswordInput label, 
.stFileUploader label, .stSlider label {
    font-size: 10px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    color: var(--txt2) !important;
    font-family: var(--mono) !important;
}

/* Success/error boxes */
.stSuccess { background: rgba(16,185,129,0.1) !important; border-left: 3px solid var(--acc2) !important; }
.stError   { background: rgba(239,68,68,0.1) !important; border-left: 3px solid var(--err) !important; }
.stWarning { background: rgba(245,158,11,0.1) !important; border-left: 3px solid var(--warn) !important; }

/* JSON preview */
.stJson { background: var(--surf2) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }

div[data-testid="stVerticalBlock"] { gap: 0.4rem; }
div[data-testid="stHorizontalBlock"] { gap: 12px; }

/* Record preview */
.rec-preview {
    background: var(--surf2);
    border: 1px solid var(--border2);
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 4px;
}
.rec-num { color: var(--acc); font-size: 11px; font-weight: 700; letter-spacing: 1px; }
.rec-title { color: #fff; font-family: var(--head); font-size: 15px; font-weight: 700; margin: 4px 0 10px; }
.rec-cat {
    display: inline-block;
    border: 1px solid var(--acc2);
    color: var(--acc2);
    font-size: 9px;
    padding: 2px 8px;
    border-radius: 3px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 10px;
}
.rec-field-label { font-size: 9px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--txt2); margin-top: 8px; margin-bottom: 2px; }
.rec-field-val { font-size: 11px; color: var(--txt); line-height: 1.5; }

</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────────────────
def _init():
    defs = {
        "running":    False,
        "done":       False,
        "jsonl_data": None,   # bytes of final JSONL
        "stats":      {"total": 0, "ok": 0, "error": 0},
        "logs":       [],
        "last_rec":   None,
        "file_statuses": {},  # filename -> "wait"|"proc"|"ok"|"err"
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
s = st.session_state

# ─── Top bar ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
  <div class="topbar-brand">
    <div class="topbar-icon">📋</div>
    <div>
      <div class="topbar-title">SNI Core Generator</div>
      <div class="topbar-sub">Gemini Flash · PDF & Word → JSONL</div>
    </div>
  </div>
  <span class="topbar-badge">gemini-1.5-flash</span>
</div>
""", unsafe_allow_html=True)

# ─── Metric row ───────────────────────────────────────────────────────────────
ms = s["stats"]
total_up  = len(s["file_statuses"])
chars_est = ms["ok"] * 650  # rough estimate

st.markdown(f"""
<div class="metrics">
  <div class="mcard">
    <div class="mcard-num">{total_up}</div>
    <div class="mcard-label">Files Uploaded</div>
  </div>
  <div class="mcard g">
    <div class="mcard-num">{ms['ok']}</div>
    <div class="mcard-label">Docs Processed</div>
  </div>
  <div class="mcard w">
    <div class="mcard-num">{ms['error']}</div>
    <div class="mcard-label">Errors</div>
  </div>
  <div class="mcard">
    <div class="mcard-num">{chars_est:,}</div>
    <div class="mcard-label">Est. Characters</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Layout ───────────────────────────────────────────────────────────────────
left, right = st.columns([3, 2], gap="medium")

# ════════════════════════════════
# LEFT: Upload + Process
# ════════════════════════════════
with left:
    # API Key
    st.markdown('<div class="panel-title"><div class="dot"></div>API Configuration</div>', unsafe_allow_html=True)
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="AIza...",
        help="https://aistudio.google.com/apikey",
        key="api_key_input",
    )
    rpm = st.number_input("Request per Menit (RPM)", min_value=1, max_value=60, value=15, key="rpm_input")

    st.markdown("<br>", unsafe_allow_html=True)

    # Upload panel
    st.markdown('<div class="panel-title"><div class="dot" style="background:var(--acc2)"></div>Upload Dokumen SNI</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="upload-hint">
      Supported: <strong>PDF, DOC, DOCX</strong> · Maks 200 MB per file · Bisa upload banyak sekaligus<br>
      Setiap file akan diekstrak teksnya dan diproses oleh Gemini Flash untuk menghasilkan 1 baris JSONL
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload file PDF atau Word",
        type=["pdf", "docx", "doc"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="file_uploader",
    )

    # Update file status tracker when new files uploaded
    if uploaded:
        for f in uploaded:
            if f.name not in s["file_statuses"]:
                s["file_statuses"][f.name] = "wait"

    st.markdown("<br>", unsafe_allow_html=True)

    # Buttons row
    bcol1, bcol2 = st.columns(2)
    with bcol1:
        can_start = bool(api_key and uploaded and not s["running"])
        start_btn = st.button(
            "⚡  Proses" if not s["running"] else "⏳  Memproses...",
            disabled=not can_start,
            use_container_width=True,
        )
    with bcol2:
        reset_btn = st.button("↺  Reset", disabled=s["running"], use_container_width=True)

    if reset_btn:
        for key in ["running","done","jsonl_data","last_rec","logs"]:
            s[key] = False if key=="running" else None if key in ["jsonl_data","last_rec"] else [] if key=="logs" else False
        s["stats"] = {"total":0,"ok":0,"error":0}
        s["file_statuses"] = {}
        st.rerun()

    # Progress
    total_f = len(s["file_statuses"])
    done_f  = sum(1 for v in s["file_statuses"].values() if v in ("ok","err"))
    pct = (done_f / total_f * 100) if total_f > 0 else 0

    st.markdown(f"""
    <div class="prog-wrap"><div class="prog-fill" style="width:{pct:.1f}%"></div></div>
    <div class="prog-label"><span>{done_f} / {total_f} file selesai</span><span>{pct:.1f}%</span></div>
    """, unsafe_allow_html=True)

    # Log terminal
    st.markdown('<div class="panel-title" style="margin-top:8px"><div class="dot" style="background:var(--warn)"></div>Log</div>', unsafe_allow_html=True)
    log_lines = s["logs"][-60:]
    log_html = '<div class="terminal">'
    for ln in log_lines:
        cls = "t-ok" if "✓" in ln else "t-err" if "✗" in ln else "t-warn" if "WARN" in ln else "t-skip" if "→" in ln else "t-info"
        log_html += f'<div class="{cls}">{ln}</div>'
    log_html += "</div>"
    st.markdown(log_html, unsafe_allow_html=True)

# ════════════════════════════════
# RIGHT: File Queue + Preview + Download
# ════════════════════════════════
with right:
    # File Queue
    st.markdown('<div class="panel-title"><div class="dot" style="background:var(--warn)"></div>File Queue</div>', unsafe_allow_html=True)

    if not s["file_statuses"]:
        st.markdown('<div style="color:var(--txt2);font-size:12px;padding:20px 0">Belum ada file diupload...</div>', unsafe_allow_html=True)
    else:
        queue_html = '<div class="file-queue">'
        for fname, fstatus in list(s["file_statuses"].items())[:20]:
            ext = fname.split(".")[-1].upper()
            badge_cls = "doc" if ext in ("DOCX","DOC") else ""
            size_str = ""
            if uploaded:
                for uf in uploaded:
                    if uf.name == fname:
                        kb = len(uf.getvalue()) / 1024
                        size_str = f"{kb:.1f} KB" if kb < 1024 else f"{kb/1024:.2f} MB"
                        break
            status_map = {
                "wait": ("○ Antri", "wait"),
                "proc": ("◉ Proses", "proc"),
                "ok":   ("✓ Selesai", "ok"),
                "err":  ("✗ Error", "err"),
            }
            slabel, scls = status_map.get(fstatus, ("?","wait"))
            queue_html += f"""
            <div class="fq-item">
              <span class="fq-badge {badge_cls}">{ext}</span>
              <span class="fq-name">{fname}</span>
              <span class="fq-size">{size_str}</span>
              <span class="fq-status {scls}">{slabel}</span>
            </div>"""
        if len(s["file_statuses"]) > 20:
            queue_html += f'<div style="color:var(--txt2);font-size:10px;text-align:center;padding:6px">+{len(s["file_statuses"])-20} file lainnya</div>'
        queue_html += '</div>'
        st.markdown(queue_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Last record preview
    st.markdown('<div class="panel-title"><div class="dot"></div>Record Terakhir</div>', unsafe_allow_html=True)
    rec = s["last_rec"]
    if rec is None:
        st.markdown('<div style="color:var(--txt2);font-size:12px;padding:10px 0">Belum ada record...</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="rec-preview">
          <div class="rec-num">{rec.get('no_sni','')}</div>
          <div class="rec-title">{rec.get('judul','')}</div>
          <div class="rec-cat">{rec.get('kategori','')}</div>
          <div class="rec-field-label">Ruang Lingkup</div>
          <div class="rec-field-val">{rec.get('ruang_lingkup','')}</div>
          <div class="rec-field-label">Persyaratan</div>
          <div class="rec-field-val">{rec.get('persyaratan','')[:250]}</div>
          <div class="rec-field-label">Keywords</div>
          <div class="rec-field-val" style="color:var(--acc)">{rec.get('keywords','')}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Download
    st.markdown('<div class="panel-title"><div class="dot" style="background:var(--acc2)"></div>Download Output</div>', unsafe_allow_html=True)
    if s["jsonl_data"]:
        st.download_button(
            label=f"⬇  Download sni_core.jsonl  ({len(s['jsonl_data']) // 1024} KB)",
            data=s["jsonl_data"],
            file_name="sni_core.jsonl",
            mime="application/jsonlines",
            use_container_width=True,
        )
        # Show last 3 lines as preview
        lines = s["jsonl_data"].decode("utf-8").strip().split("\n")
        st.markdown(f'<div style="font-size:10px;color:var(--txt2);margin:8px 0 4px">{len(lines)} record total · preview 3 terakhir:</div>', unsafe_allow_html=True)
        for line in lines[-3:]:
            try:
                st.json(json.loads(line))
            except Exception:
                pass
    else:
        st.markdown(
            '<div style="color:var(--txt2);font-size:12px;padding:10px 0">Output tersedia setelah proses selesai</div>',
            unsafe_allow_html=True
        )

# ─── Processing Logic ──────────────────────────────────────────────────────────
if start_btn and uploaded and api_key and not s["running"]:
    from engine import (
        extract_text, call_gemini, post_process,
        guess_sni_id_from_filename,
    )
    import google.generativeai as genai

    s["running"] = True
    s["done"] = False
    s["jsonl_data"] = None
    s["stats"] = {"total": len(uploaded), "ok": 0, "error": 0}
    s["logs"] = [
        f"[INFO] {len(uploaded)} file ditemukan, mulai proses...",
        f"[INFO] Model: gemini-1.5-flash | RPM: {rpm}",
    ]

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    jsonl_lines = []
    req_times: list[float] = []
    min_wait = 60.0 / int(rpm)

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, uf in enumerate(uploaded, 1):
            fname = uf.name
            s["file_statuses"][fname] = "proc"
            s["logs"].append(f"[{i}/{len(uploaded)}] 🔄 {fname}")

            # Save to temp
            tmp_path = Path(tmpdir) / fname
            tmp_path.write_bytes(uf.getvalue())

            # Extract text
            text = extract_text(tmp_path)
            if not text.strip():
                s["file_statuses"][fname] = "err"
                s["stats"]["error"] += 1
                s["logs"].append(f"✗ [{i}] {fname} — teks kosong / gagal baca")
                continue

            # Rate limit
            now = time.time()
            req_times = [t for t in req_times if now - t < 60]
            if len(req_times) >= int(rpm):
                wait = 60 - (now - req_times[0]) + 1
                s["logs"].append(f"[WARN] Rate limit — tunggu {wait:.0f}s")
                time.sleep(wait)

            # Call Gemini
            req_times.append(time.time())
            raw = call_gemini(model, text)

            if raw is None:
                s["file_statuses"][fname] = "err"
                s["stats"]["error"] += 1
                s["logs"].append(f"✗ [{i}] {fname} — Gemini gagal/timeout")
                continue

            # Post-process
            rec = post_process(raw, tmp_path, text)
            rec_dict = {
                "sni_id": rec.sni_id, "no_sni": rec.no_sni,
                "judul": rec.judul, "kategori": rec.kategori,
                "ruang_lingkup": rec.ruang_lingkup,
                "persyaratan": rec.persyaratan,
                "metode_uji": rec.metode_uji,
                "keywords": rec.keywords,
            }
            jsonl_lines.append(json.dumps(rec_dict, ensure_ascii=False))
            s["file_statuses"][fname] = "ok"
            s["stats"]["ok"] += 1
            s["last_rec"] = rec_dict
            s["logs"].append(f"✓ [{i}] {fname} → {rec.no_sni} · {rec.judul[:45]}")

    # Build output bytes
    if jsonl_lines:
        s["jsonl_data"] = "\n".join(jsonl_lines).encode("utf-8")
        s["logs"].append(f"[INFO] ✅ Selesai! {s['stats']['ok']} record berhasil · {s['stats']['error']} error")
    else:
        s["logs"].append("[WARN] Tidak ada record berhasil dihasilkan.")

    s["running"] = False
    s["done"] = True
    st.rerun()
