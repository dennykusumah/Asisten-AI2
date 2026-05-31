"""
app.py — SNI Core Generator · Streamlit UI (Local Processing, No API)
Upload PDF/Word → local regex/heuristic extraction → sni_core.jsonl
Run: streamlit run app.py
"""

import io
import os
import re
import json
import time
import tempfile
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@600;700;800&display=swap');

:root {
    --bg:      #07090f;
    --s1:      #0c1220;
    --s2:      #101929;
    --s3:      #172135;
    --border:  #1c2e48;
    --b2:      #243a5e;
    --acc:     #3b82f6;
    --acc2:    #10b981;
    --warn:    #f59e0b;
    --err:     #ef4444;
    --txt:     #c0d4ec;
    --txt2:    #4a6890;
    --mono:    'JetBrains Mono', monospace;
    --head:    'Syne', sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body,[class*="css"]{font-family:var(--mono)!important;background:var(--bg)!important;color:var(--txt)!important;}
.stApp{background:var(--bg)!important;}
.stApp>header,[data-testid="stSidebar"]{display:none!important;}
section[data-testid="stMain"] > div{padding-top:0!important;}

/* ── Top bar ── */
.topbar{
    display:flex;align-items:center;justify-content:space-between;
    padding:20px 28px 18px;
    border-bottom:1px solid var(--border);
    background:var(--s1);
    margin-bottom:0;
}
.brand{display:flex;align-items:center;gap:14px;}
.brand-icon{
    width:40px;height:40px;border-radius:10px;
    background:linear-gradient(135deg,var(--acc),#6366f1);
    display:flex;align-items:center;justify-content:center;
    font-size:20px;flex-shrink:0;
}
.brand-name{font-family:var(--head);font-size:17px;font-weight:800;color:#fff;letter-spacing:-0.3px;}
.brand-sub{font-size:9px;color:var(--txt2);letter-spacing:2px;text-transform:uppercase;margin-top:1px;}
.pill{
    background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);
    color:var(--acc2);font-size:9px;letter-spacing:2px;text-transform:uppercase;
    padding:4px 12px;border-radius:20px;
}

/* ── Metrics bar ── */
.metrics{
    display:grid;grid-template-columns:repeat(4,1fr);gap:0;
    border-bottom:1px solid var(--border);
    background:var(--s1);
}
.mc{
    padding:16px 24px;border-right:1px solid var(--border);
    position:relative;overflow:hidden;
}
.mc:last-child{border-right:none;}
.mc::after{
    content:'';position:absolute;bottom:0;left:0;right:0;height:2px;
    background:var(--acc);
}
.mc.g::after{background:var(--acc2);}
.mc.w::after{background:var(--warn);}
.mc.r::after{background:var(--err);}
.mc-num{font-family:var(--head);font-size:28px;font-weight:800;color:#fff;line-height:1;}
.mc-lbl{font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--txt2);margin-top:5px;}

/* ── Main layout ── */
.main-wrap{display:grid;grid-template-columns:1fr 400px;gap:0;min-height:calc(100vh - 120px);}
.left-panel{padding:24px;border-right:1px solid var(--border);}
.right-panel{padding:24px;background:var(--s1);}

/* ── Section head ── */
.sec-head{
    font-family:var(--head);font-size:11px;font-weight:700;
    letter-spacing:2px;text-transform:uppercase;color:var(--txt2);
    margin-bottom:14px;display:flex;align-items:center;gap:8px;
}
.sec-head::before{content:'';width:3px;height:12px;background:var(--acc);border-radius:2px;}

/* ── Upload area ── */
.upload-hint{
    background:var(--s2);border:1px dashed var(--b2);border-radius:8px;
    padding:12px 16px;font-size:11px;color:var(--txt2);margin-bottom:14px;line-height:1.7;
}
.upload-hint b{color:var(--txt);}

/* ── Streamlit widget overrides ── */
[data-testid="stFileUploader"]{
    background:var(--s2)!important;border:1px dashed var(--b2)!important;
    border-radius:8px!important;
}
[data-testid="stFileUploaderDropzone"]{padding:24px!important;text-align:center!important;}
[data-testid="stFileUploader"] *{color:var(--txt2)!important;font-family:var(--mono)!important;font-size:12px!important;}
[data-testid="stFileUploaderDropzone"] svg{display:none!important;}

.stTextInput input,.stNumberInput input,.stPasswordInput input{
    background:var(--s3)!important;border:1px solid var(--border)!important;
    color:var(--txt)!important;font-family:var(--mono)!important;font-size:12px!important;
    border-radius:6px!important;padding:9px 12px!important;
}
.stTextInput input:focus{border-color:var(--acc)!important;box-shadow:0 0 0 2px rgba(59,130,246,0.15)!important;}
label{font-size:9px!important;letter-spacing:2px!important;text-transform:uppercase!important;color:var(--txt2)!important;font-family:var(--mono)!important;}

/* ── Buttons ── */
div[data-testid="stButton"] > button{
    font-family:var(--mono)!important;font-size:12px!important;font-weight:700!important;
    letter-spacing:1px!important;border-radius:8px!important;padding:11px 20px!important;
    transition:all 0.2s!important;border:none!important;width:100%!important;
}
div[data-testid="stButton"]:first-of-type > button{
    background:linear-gradient(135deg,var(--acc),#6366f1)!important;color:#fff!important;
}
div[data-testid="stButton"]:first-of-type > button:hover{
    transform:translateY(-2px);box-shadow:0 8px 24px rgba(59,130,246,0.4)!important;
}
div[data-testid="stButton"]:first-of-type > button:disabled{
    background:var(--s3)!important;color:var(--txt2)!important;transform:none!important;box-shadow:none!important;
}
div[data-testid="stDownloadButton"] > button{
    background:linear-gradient(135deg,var(--acc2),#059669)!important;color:#fff!important;
    font-family:var(--mono)!important;font-weight:700!important;font-size:12px!important;
    letter-spacing:1px!important;border-radius:8px!important;padding:11px 20px!important;
    border:none!important;width:100%!important;transition:all 0.2s!important;
}
div[data-testid="stDownloadButton"] > button:hover{
    transform:translateY(-2px);box-shadow:0 8px 24px rgba(16,185,129,0.4)!important;
}

/* ── Progress ── */
.prog-outer{background:var(--s3);border-radius:4px;height:5px;overflow:hidden;margin:10px 0 5px;}
.prog-inner{height:100%;background:linear-gradient(90deg,var(--acc),var(--acc2));border-radius:4px;transition:width 0.3s ease;}
.prog-meta{display:flex;justify-content:space-between;font-size:10px;color:var(--txt2);}

/* ── Terminal ── */
.terminal{
    background:#030609;border:1px solid var(--border);border-radius:8px;
    padding:14px 16px;height:220px;overflow-y:auto;
    font-size:11px;line-height:1.9;
}
.t-ok{color:var(--acc2);}
.t-err{color:var(--err);}
.t-warn{color:var(--warn);}
.t-info{color:var(--acc);}
.t-dim{color:var(--txt2);}

/* ── File queue ── */
.fq-item{
    display:flex;align-items:center;gap:10px;
    background:var(--s2);border:1px solid var(--border);border-radius:7px;
    padding:9px 13px;margin-bottom:7px;font-size:11px;
    transition:border-color 0.2s;
}
.fq-item.proc{border-color:var(--warn);}
.fq-item.ok{border-color:rgba(16,185,129,0.4);}
.fq-item.err{border-color:rgba(239,68,68,0.4);}
.fq-badge{
    font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;
    letter-spacing:1px;flex-shrink:0;color:#fff;
}
.fq-badge.pdf{background:#dc2626;}
.fq-badge.doc{background:#2563eb;}
.fq-name{color:var(--txt);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.fq-size{color:var(--txt2);font-size:10px;flex-shrink:0;}
.fq-stat{font-size:10px;flex-shrink:0;}
.fq-stat.wait{color:var(--txt2);}
.fq-stat.proc{color:var(--warn);}
.fq-stat.ok{color:var(--acc2);}
.fq-stat.err{color:var(--err);}

/* ── Record preview ── */
.rec-box{
    background:var(--s2);border:1px solid var(--b2);border-radius:8px;
    padding:14px 16px;margin-top:4px;
}
.rec-num{color:var(--acc);font-size:10px;font-weight:700;letter-spacing:1px;}
.rec-title{color:#fff;font-family:var(--head);font-size:14px;font-weight:700;margin:4px 0 8px;}
.rec-cat{
    display:inline-block;border:1px solid var(--acc2);color:var(--acc2);
    font-size:8px;padding:2px 7px;border-radius:3px;letter-spacing:1.5px;
    text-transform:uppercase;margin-bottom:10px;
}
.fl{font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:var(--txt2);margin-top:9px;margin-bottom:2px;}
.fv{font-size:11px;color:var(--txt);line-height:1.55;}
.fv.kw{color:var(--acc);}

div[data-testid="stVerticalBlock"]{gap:0.35rem;}
div[data-testid="stHorizontalBlock"]{gap:10px;}

/* ── Speed indicator ── */
.speed-bar{
    display:flex;gap:6px;align-items:center;
    font-size:10px;color:var(--txt2);margin-top:6px;
}
.speed-dot{width:6px;height:6px;border-radius:50%;background:var(--acc2);animation:pulse 1.2s infinite;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.3;}}
</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────────────────
def _init():
    defs = {
        "running":     False,
        "done":        False,
        "jsonl_bytes": None,
        "stats":       {"total": 0, "ok": 0, "error": 0},
        "logs":        [],
        "last_rec":    None,
        "fstatus":     {},   # fname -> "wait"|"proc"|"ok"|"err"
        "speed":       0.0,  # files/sec
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
S = st.session_state

# ─── Top bar ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
  <div class="brand">
    <div class="brand-icon">📋</div>
    <div>
      <div class="brand-name">SNI Core Generator</div>
      <div class="brand-sub">Local Processing · No API · PDF &amp; Word → JSONL</div>
    </div>
  </div>
  <span class="pill">⚡ 100% Lokal</span>
</div>
""", unsafe_allow_html=True)

# ─── Metrics ──────────────────────────────────────────────────────────────────
ms = S["stats"]
total_up = len(S["fstatus"])
done_up  = sum(1 for v in S["fstatus"].values() if v in ("ok","err"))
speed    = S.get("speed", 0.0)
speed_str = f"{speed:.1f} file/s" if speed > 0 else "—"

st.markdown(f"""
<div class="metrics">
  <div class="mc"><div class="mc-num">{total_up}</div><div class="mc-lbl">Files Uploaded</div></div>
  <div class="mc g"><div class="mc-num">{ms['ok']}</div><div class="mc-lbl">Berhasil</div></div>
  <div class="mc r"><div class="mc-num">{ms['error']}</div><div class="mc-lbl">Error</div></div>
  <div class="mc w"><div class="mc-num">{speed_str}</div><div class="mc-lbl">Kecepatan</div></div>
</div>
""", unsafe_allow_html=True)

# ─── Two-col layout via st.columns ────────────────────────────────────────────
left, right = st.columns([5, 3], gap="small")

# ═══════════════════════════════════════
# LEFT PANEL
# ═══════════════════════════════════════
with left:
    st.markdown('<div style="padding:20px 4px 0">', unsafe_allow_html=True)

    # Upload
    st.markdown('<div class="sec-head">Upload Dokumen SNI</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="upload-hint">
      Format: <b>PDF, DOC, DOCX</b> · Bisa upload banyak sekaligus · Proses paralel, tidak butuh internet<br>
      Ekstraksi dilakukan 100% di lokal menggunakan PyMuPDF + python-docx + regex heuristik
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Pilih file PDF atau Word",
        type=["pdf","docx","doc"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="uploader",
    )

    # Track new uploads
    if uploaded:
        for f in uploaded:
            if f.name not in S["fstatus"]:
                S["fstatus"][f.name] = "wait"

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Workers slider
    workers = st.select_slider(
        "Worker Paralel",
        options=[1,2,4,6,8,10,12,16],
        value=4,
        help="Jumlah file diproses bersamaan. Naikkan untuk CPU multi-core.",
    )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # Action buttons
    c1, c2 = st.columns([3,1])
    with c1:
        can_start = bool(uploaded and not S["running"])
        start_btn = st.button(
            "⚡  Proses Sekarang" if not S["running"] else "⏳  Memproses...",
            disabled=not can_start,
            use_container_width=True,
        )
    with c2:
        reset_btn = st.button("↺ Reset", disabled=S["running"], use_container_width=True)

    if reset_btn:
        for key in ["running","done","jsonl_bytes","last_rec"]:
            S[key] = False if key == "running" else None
        S["stats"]  = {"total":0,"ok":0,"error":0}
        S["logs"]   = []
        S["fstatus"] = {}
        S["speed"]  = 0.0
        st.rerun()

    # Progress bar
    pct = (done_up / total_up * 100) if total_up > 0 else 0
    st.markdown(f"""
    <div class="prog-outer"><div class="prog-inner" style="width:{pct:.1f}%"></div></div>
    <div class="prog-meta"><span>{done_up} / {total_up} file</span><span>{pct:.1f}%</span></div>
    """, unsafe_allow_html=True)

    if S["running"]:
        st.markdown(f"""
        <div class="speed-bar">
          <div class="speed-dot"></div>
          Memproses... {speed_str}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Download button (shows when done)
    if S["jsonl_bytes"]:
        n_rec = S["stats"]["ok"]
        size_kb = len(S["jsonl_bytes"]) // 1024
        st.download_button(
            label=f"⬇  Download sni_core.jsonl  ({n_rec} record · {size_kb} KB)",
            data=S["jsonl_bytes"],
            file_name="sni_core.jsonl",
            mime="application/jsonlines",
            use_container_width=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Terminal log
    st.markdown('<div class="sec-head">Log</div>', unsafe_allow_html=True)
    log_lines = S["logs"][-60:]
    rows = ""
    for ln in log_lines:
        cls = "t-ok" if "✓" in ln else "t-err" if "✗" in ln else "t-warn" if "WARN" in ln else "t-info" if "INFO" in ln else "t-dim"
        escaped = ln.replace("<","&lt;").replace(">","&gt;")
        rows += f'<div class="{cls}">{escaped}</div>'
    st.markdown(f'<div class="terminal">{rows}</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════
# RIGHT PANEL
# ═══════════════════════════════════════
with right:
    st.markdown('<div style="padding:20px 4px 0">', unsafe_allow_html=True)

    # File Queue
    st.markdown('<div class="sec-head">File Queue</div>', unsafe_allow_html=True)

    if not S["fstatus"]:
        st.markdown('<div style="color:var(--txt2);font-size:12px;padding:12px 0">Belum ada file...</div>', unsafe_allow_html=True)
    else:
        q_html = ""
        file_list = list(S["fstatus"].items())
        for fname, fstat in file_list[:25]:
            ext = fname.rsplit(".",1)[-1].upper()
            badge_cls = "pdf" if ext == "PDF" else "doc"
            size_str = ""
            if uploaded:
                for uf in uploaded:
                    if uf.name == fname:
                        kb = len(uf.getvalue()) / 1024
                        size_str = f"{kb:.0f}KB" if kb < 1024 else f"{kb/1024:.1f}MB"
                        break
            stat_map = {"wait":("○","wait"),"proc":("◉","proc"),"ok":("✓","ok"),"err":("✗","err")}
            slabel, scls = stat_map.get(fstat, ("?","wait"))
            item_cls = fstat if fstat in ("proc","ok","err") else ""
            q_html += f"""
            <div class="fq-item {item_cls}">
              <span class="fq-badge {badge_cls}">{ext}</span>
              <span class="fq-name" title="{fname}">{fname}</span>
              <span class="fq-size">{size_str}</span>
              <span class="fq-stat {scls}">{slabel}</span>
            </div>"""
        if len(S["fstatus"]) > 25:
            extra = len(S["fstatus"]) - 25
            q_html += f'<div style="color:var(--txt2);font-size:10px;text-align:center;padding:6px">+{extra} file lainnya</div>'
        st.markdown(q_html, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Last record preview
    st.markdown('<div class="sec-head">Record Terakhir</div>', unsafe_allow_html=True)
    rec = S["last_rec"]
    if rec is None:
        st.markdown('<div style="color:var(--txt2);font-size:12px;padding:8px 0">Belum ada record...</div>', unsafe_allow_html=True)
    else:
        syarat = rec.get("persyaratan","-") or "-"
        metode = rec.get("metode_uji","-") or "-"
        st.markdown(f"""
        <div class="rec-box">
          <div class="rec-num">{rec.get('no_sni','')}</div>
          <div class="rec-title">{rec.get('judul','')[:70]}</div>
          <div class="rec-cat">{rec.get('kategori','')}</div>
          <div class="fl">Ruang Lingkup</div>
          <div class="fv">{rec.get('ruang_lingkup','')[:150]}</div>
          <div class="fl">Persyaratan</div>
          <div class="fv">{syarat[:200]}</div>
          <div class="fl">Metode Uji</div>
          <div class="fv">{metode[:160]}</div>
          <div class="fl">Keywords</div>
          <div class="fv kw">{rec.get('keywords','')}</div>
        </div>
        """, unsafe_allow_html=True)

    # JSONL preview (last 2 records)
    if S["jsonl_bytes"]:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="sec-head">Preview Output</div>', unsafe_allow_html=True)
        lines = S["jsonl_bytes"].decode("utf-8").strip().split("\n")
        st.markdown(f'<div style="font-size:10px;color:var(--txt2);margin-bottom:6px">{len(lines)} record total</div>', unsafe_allow_html=True)
        for line in lines[-2:]:
            try:
                obj = json.loads(line)
                obj.pop("_source", None)
                st.json(obj, expanded=False)
            except Exception:
                pass

    st.markdown("</div>", unsafe_allow_html=True)


# ─── Processing Logic (runs in main thread, updates state) ────────────────────
if start_btn and uploaded and not S["running"]:
    from engine import process_file

    S["running"] = True
    S["done"]    = False
    S["jsonl_bytes"] = None
    S["stats"]   = {"total": len(uploaded), "ok": 0, "error": 0}
    S["logs"]    = [
        f"[INFO] {len(uploaded)} file akan diproses · {workers} worker paralel",
        "[INFO] Ekstraksi lokal — PyMuPDF + python-docx + regex heuristik",
    ]

    # Mark all as waiting
    for uf in uploaded:
        S["fstatus"][uf.name] = "wait"

    # Read all file bytes upfront (fast, in-memory)
    file_data = []
    for uf in uploaded:
        file_data.append((uf.name, uf.getvalue()))

    results = []
    t_start = time.time()
    completed = 0

    # Mark first batch as proc
    batch_size = min(workers, len(file_data))
    for name, _ in file_data[:batch_size]:
        S["fstatus"][name] = "proc"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_name = {
            pool.submit(process_file, data, name): name
            for name, data in file_data
        }

        for future in as_completed(future_to_name):
            name = future_to_name[future]
            completed += 1
            elapsed = time.time() - t_start
            S["speed"] = completed / elapsed if elapsed > 0 else 0

            try:
                rec_dict = future.result()
                if rec_dict.get("_error"):
                    S["fstatus"][name] = "err"
                    S["stats"]["error"] += 1
                    S["logs"].append(f"✗ [{completed}/{len(file_data)}] {name} — {rec_dict['_error']}")
                else:
                    rec_dict.pop("_source", None)
                    rec_dict.pop("_error", None)
                    results.append(json.dumps(rec_dict, ensure_ascii=False))
                    S["fstatus"][name] = "ok"
                    S["stats"]["ok"]  += 1
                    S["last_rec"] = rec_dict
                    judul_short = rec_dict.get("judul","")[:45]
                    no_sni = rec_dict.get("no_sni","?")
                    S["logs"].append(f"✓ [{completed}/{len(file_data)}] {name[:30]} → {no_sni} · {judul_short}")
            except Exception as e:
                S["fstatus"][name] = "err"
                S["stats"]["error"] += 1
                S["logs"].append(f"✗ [{completed}/{len(file_data)}] {name} — {str(e)[:60]}")

            # Mark next queued files as proc
            if completed < len(file_data):
                next_idx = completed + batch_size - 1
                if next_idx < len(file_data):
                    next_name = file_data[next_idx][0]
                    if S["fstatus"].get(next_name) == "wait":
                        S["fstatus"][next_name] = "proc"

    # Build JSONL bytes
    elapsed_total = time.time() - t_start
    if results:
        S["jsonl_bytes"] = "\n".join(results).encode("utf-8")

    S["running"] = False
    S["done"]    = True
    S["speed"]   = len(file_data) / elapsed_total if elapsed_total > 0 else 0

    ok  = S["stats"]["ok"]
    err = S["stats"]["error"]
    S["logs"].append(
        f"[INFO] ✅ Selesai dalam {elapsed_total:.1f}s · "
        f"{ok} berhasil · {err} error · "
        f"avg {elapsed_total/len(file_data):.2f}s/file"
    )
    st.rerun()
