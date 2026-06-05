"""
app.py — Training Dataset Generator (Multi-PDF, up to 200 dokumen)
Upload drag & drop → Engine 1/2/3 → CSV per dokumen
                   → Engine 4    → JSONL per dokumen
"""

import io
import csv
import json
import zipfile
import streamlit as st

from engine import engine1_daftar_isi, engine2_keywords, engine3_ringkasan, engine4_jsonl


# ─────────────────────────────────────────────
# Konfigurasi halaman
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Training Dataset Generator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
body, .stApp { background-color: #0d1117; color: #cdd6f4; }

/* ── Header ── */
.main-header {
    background: linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);
    padding:2rem; border-radius:14px; margin-bottom:1.8rem; text-align:center;
}
.main-header h1 { color:#e94560; margin:0; font-size:2.1rem; letter-spacing:1px; }
.main-header p  { color:#a8b2d8; margin:.5rem 0 0; font-size:.95rem; }

/* ── Upload zone ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #334155 !important;
    border-radius: 12px !important;
    background: #161b27 !important;
    padding: 1.2rem !important;
    transition: border-color .2s;
}
[data-testid="stFileUploader"]:hover { border-color: #e94560 !important; }

/* ── Dokumen card ── */
.doc-card {
    background:#1e1e2e; border:1px solid #2a2a3e;
    border-radius:10px; padding:1rem; margin-bottom:.7rem;
}
.doc-card-header { display:flex; justify-content:space-between; align-items:center; }
.doc-name  { color:#cdd6f4; font-weight:600; font-size:.95rem; }
.doc-size  { color:#585b70; font-size:.8rem; }
.badge {
    display:inline-block; padding:.15rem .55rem; border-radius:20px;
    font-size:.72rem; font-weight:700; margin-right:.3rem;
}
.badge-ok    { background:#1e3a2f; color:#a6e3a1; }
.badge-error { background:#3a1e1e; color:#f38ba8; }
.badge-wait  { background:#2a2a3e; color:#cba6f7; }
.badge-run   { background:#2a3040; color:#89b4fa; }

/* ── Progress bar label ── */
.prog-label { color:#7f849c; font-size:.78rem; margin:.3rem 0 .1rem; }

/* ── Engine card sidebar ── */
.engine-card {
    background:#1e1e2e; border:1px solid #2a2a3e;
    border-radius:10px; padding:1rem; margin-bottom:.8rem;
}
.engine-card h4 { color:#cdd6f4; margin:0 0 .35rem; font-size:.9rem; }
.engine-card p  { color:#7f849c; font-size:.78rem; margin:0; line-height:1.5; }

/* ── Buttons ── */
.stButton>button {
    background:linear-gradient(135deg,#e94560,#c62a47) !important;
    color:#fff !important; border:none !important;
    border-radius:8px !important; font-weight:600 !important;
}
.stButton>button:hover {
    background:linear-gradient(135deg,#c62a47,#a01f39) !important;
}

/* ── Download button ── */
[data-testid="stDownloadButton"]>button {
    background:linear-gradient(135deg,#1c6b38,#14522b) !important;
    color:#a6e3a1 !important; border:none !important;
    border-radius:8px !important; font-weight:600 !important;
    width:100%;
}
[data-testid="stDownloadButton"]>button:hover {
    background:linear-gradient(135deg,#14522b,#0e3d20) !important;
}

/* ── Tab ── */
.stTabs [data-baseweb="tab"]  { color:#7f849c; }
.stTabs [aria-selected="true"]{ color:#e94560 !important; border-bottom:2px solid #e94560 !important; }

/* ── Status messages ── */
.st-success-msg { color:#a6e3a1; font-size:.85rem; }
.st-error-msg   { color:#f38ba8; font-size:.85rem; }

/* ── Preview box ── */
.preview-box {
    background:#161b27; border:1px solid #2a2a3e; border-radius:8px;
    padding:1rem; font-size:.85rem; line-height:1.7;
    max-height:280px; overflow-y:auto; color:#cdd6f4;
}

/* ── Counter chip ── */
.counter-chip {
    background:#16213e; border:1px solid #0f3460; border-radius:20px;
    padding:.3rem .9rem; color:#89b4fa; font-size:.85rem; display:inline-block;
    margin:.5rem .3rem 1rem;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Session-state init
# ─────────────────────────────────────────────
if "docs" not in st.session_state:
    # docs: dict[filename] = {
    #   "bytes": bytes, "size": int,
    #   "e1": str|None, "e2": str|None, "e3": str|None, "e4": str|None,
    #   "status": {"e1":..,"e2":..,"e3":..,"e4":..}  ("wait"|"ok"|"error"|"running")
    # }
    st.session_state.docs = {}


# ─────────────────────────────────────────────
# Helpers — build CSV / JSONL bytes
# ─────────────────────────────────────────────
def build_csv(daftar_isi: str, keywords: str, ringkasan: str, filename: str) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow(["Daftar Isi", "Keywords", "Ringkasan"])
    writer.writerow([daftar_isi or "", keywords or "", ringkasan or ""])
    return buf.getvalue().encode("utf-8-sig")   # utf-8-sig agar Excel buka tanpa garbled


def build_zip_csv(docs: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, d in docs.items():
            if d["e1"] or d["e2"] or d["e3"]:
                csv_bytes = build_csv(d["e1"] or "", d["e2"] or "", d["e3"] or "", fname)
                base = fname.replace(".pdf", "")
                zf.writestr(f"{base}_training_data.csv", csv_bytes)
    buf.seek(0)
    return buf.getvalue()


def build_zip_jsonl(docs: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, d in docs.items():
            if d["e4"]:
                base = fname.replace(".pdf", "")
                zf.writestr(f"{base}_training_data.jsonl", d["e4"].encode("utf-8"))
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🤖 Training Dataset Generator</h1>
    <p>Upload hingga 200 PDF · Engine 1-3 → CSV · Engine 4 → JSONL · Download semua sekaligus</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Engine")
    for icon, title, desc in [
        ("🔍","Engine 1 — Daftar Isi",
         "Ekstrak daftar isi, bersihkan titik-titik & nomor halaman, pisahkan dengan (;)"),
        ("🏷️","Engine 2 — Keywords",
         "Hasilkan kata kunci penting dari isi dokumen dalam Bahasa Indonesia"),
        ("📝","Engine 3 — Ringkasan",
         "Ringkas dokumen (B. Indonesia). Dwibahasa → hanya bagian Indonesia"),
        ("🔄","Engine 4 — JSONL",
         "OCR-aware, paraphrase isi, konversi ke format JSONL training dataset"),
    ]:
        st.markdown(f"""
        <div class="engine-card">
            <h4>{icon} {title}</h4><p>{desc}</p>
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📊 Statistik")
    n_total  = len(st.session_state.docs)
    n_csv_ok = sum(1 for d in st.session_state.docs.values() if d["e1"] or d["e2"] or d["e3"])
    n_jsl_ok = sum(1 for d in st.session_state.docs.values() if d["e4"])
    st.markdown(f"""
    <div class="counter-chip">📄 {n_total} dokumen</div>
    <div class="counter-chip">📊 {n_csv_ok} CSV siap</div>
    <div class="counter-chip">📋 {n_jsl_ok} JSONL siap</div>
    """, unsafe_allow_html=True)

    if st.button("🗑️ Hapus Semua Dokumen", use_container_width=True):
        st.session_state.docs = {}
        st.rerun()


# ─────────────────────────────────────────────
# UPLOAD AREA  (drag-and-drop, multi-file, max 200)
# ─────────────────────────────────────────────
st.markdown("## 📂 Upload Dokumen PDF")
st.caption("Drag & drop atau klik untuk memilih file · Maksimal 200 PDF sekaligus")

uploaded_files = st.file_uploader(
    label="Drag & drop PDF di sini, atau klik Browse",
    type=["pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if uploaded_files:
    new_count = 0
    skipped   = 0
    for uf in uploaded_files:
        if len(st.session_state.docs) >= 200:
            skipped += 1
            continue
        if uf.name not in st.session_state.docs:
            data = uf.read()
            st.session_state.docs[uf.name] = {
                "bytes": data,
                "size":  len(data),
                "e1": None, "e2": None, "e3": None, "e4": None,
                "status": {"e1":"wait","e2":"wait","e3":"wait","e4":"wait"},
            }
            new_count += 1

    if new_count:
        st.success(f"✅ {new_count} dokumen baru ditambahkan.")
    if skipped:
        st.warning(f"⚠️ {skipped} file dilewati — batas 200 dokumen tercapai.")


# ─────────────────────────────────────────────
# Jika belum ada dokumen
# ─────────────────────────────────────────────
if not st.session_state.docs:
    st.info("⬆️ Upload minimal satu file PDF untuk memulai.")
    st.stop()


# ─────────────────────────────────────────────
# TOMBOL AKSI
# ─────────────────────────────────────────────
st.markdown("---")
c1, c2, c3 = st.columns(3)
run_csv_btn  = c1.button("▶ Engine 1+2+3  →  CSV",   use_container_width=True)
run_jsonl_btn= c2.button("▶ Engine 4  →  JSONL",      use_container_width=True)
run_all_btn  = c3.button("🚀 Semua Engine (CSV+JSONL)",use_container_width=True)


# ─────────────────────────────────────────────
# Helper: proses satu dokumen
# ─────────────────────────────────────────────
def run_engines_csv(fname: str):
    d = st.session_state.docs[fname]
    pdf = d["bytes"]
    for key, fn in [("e1", engine1_daftar_isi),
                    ("e2", engine2_keywords),
                    ("e3", engine3_ringkasan)]:
        d["status"][key] = "running"
        try:
            d[key] = fn(pdf)
            d["status"][key] = "ok"
        except Exception as ex:
            d[key] = f"[ERROR] {ex}"
            d["status"][key] = "error"


def run_engine_jsonl(fname: str):
    d = st.session_state.docs[fname]
    d["status"]["e4"] = "running"
    try:
        d["e4"] = engine4_jsonl(d["bytes"], fname)
        d["status"]["e4"] = "ok"
    except Exception as ex:
        d["e4"] = ""
        d["status"]["e4"] = "error"


# ─────────────────────────────────────────────
# Eksekusi engine dengan progress bar
# ─────────────────────────────────────────────
# PENTING: doc_list diambil di sini agar selalu up-to-date saat tombol ditekan
if run_csv_btn or run_all_btn:
    doc_list = list(st.session_state.docs.keys())
    if doc_list:
        st.markdown("### ⏳ Memproses Engine 1 · 2 · 3")
        prog = st.progress(0, text="Memulai...")
        stat_box = st.empty()
        for i, fname in enumerate(doc_list):
            prog.progress(i / len(doc_list), text=f"[{i+1}/{len(doc_list)}] {fname} — Engine 1,2,3")
            stat_box.info(f"🔄 Memproses: **{fname}**")
            run_engines_csv(fname)
        prog.progress(1.0, text="✅ Engine 1·2·3 selesai untuk semua dokumen!")
        stat_box.success(f"✅ {len(doc_list)} dokumen diproses (CSV).")

if run_jsonl_btn or run_all_btn:
    doc_list = list(st.session_state.docs.keys())
    if doc_list:
        st.markdown("### ⏳ Memproses Engine 4 (JSONL)")
        prog4 = st.progress(0, text="Memulai Engine 4...")
        stat4 = st.empty()
        for i, fname in enumerate(doc_list):
            prog4.progress(i / len(doc_list), text=f"[{i+1}/{len(doc_list)}] {fname} — Engine 4")
            stat4.info(f"🔄 Memproses: **{fname}**")
            run_engine_jsonl(fname)
        prog4.progress(1.0, text="✅ Engine 4 selesai untuk semua dokumen!")
        stat4.success(f"✅ {len(doc_list)} dokumen diproses (JSONL).")


# ─────────────────────────────────────────────
# DAFTAR DOKUMEN + STATUS
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown(f"## 📄 Daftar Dokumen ({len(st.session_state.docs)})")

BADGE = {
    "wait":    ('<span class="badge badge-wait">⏳ Belum</span>', ""),
    "running": ('<span class="badge badge-run">🔄 Proses</span>', ""),
    "ok":      ('<span class="badge badge-ok">✅ OK</span>', ""),
    "error":   ('<span class="badge badge-error">❌ Error</span>', ""),
}

for fname, d in st.session_state.docs.items():
    s = d["status"]
    b_e1 = BADGE[s["e1"]][0]
    b_e2 = BADGE[s["e2"]][0]
    b_e3 = BADGE[s["e3"]][0]
    b_e4 = BADGE[s["e4"]][0]
    size_kb = d["size"] / 1024

    with st.expander(f"📄 {fname}  ({size_kb:.1f} KB)", expanded=False):
        st.markdown(
            f'<div class="doc-card">'
            f'<div class="doc-card-header">'
            f'<span class="doc-name">{fname}</span>'
            f'<span class="doc-size">{size_kb:.1f} KB</span>'
            f'</div>'
            f'<div style="margin-top:.6rem">'
            f'Engine1: {b_e1}&nbsp; Engine2: {b_e2}&nbsp; Engine3: {b_e3}&nbsp; Engine4: {b_e4}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # Preview hasil
        tab_e1, tab_e2, tab_e3, tab_e4 = st.tabs(
            ["📋 Daftar Isi","🏷️ Keywords","📝 Ringkasan","📄 JSONL"]
        )
        with tab_e1:
            if d["e1"]:
                items = [i.strip() for i in d["e1"].split(";") if i.strip()]
                for idx, item in enumerate(items, 1):
                    st.markdown(f"**{idx}.** {item}")
                st.caption(f"Total: {len(items)} item")
            else:
                st.caption("Belum diproses.")
        with tab_e2:
            if d["e2"]:
                kws = [k.strip() for k in d["e2"].split(",") if k.strip()]
                cols = st.columns(3)
                for idx, kw in enumerate(kws):
                    cols[idx % 3].markdown(f"🔹 {kw}")
                st.caption(f"Total: {len(kws)} keyword")
            else:
                st.caption("Belum diproses.")
        with tab_e3:
            if d["e3"]:
                st.markdown(f'<div class="preview-box">{d["e3"]}</div>', unsafe_allow_html=True)
            else:
                st.caption("Belum diproses.")
        with tab_e4:
            if d["e4"]:
                lines = d["e4"].strip().splitlines()
                st.caption(f"Total: {len(lines)} baris JSONL")
                for idx, line in enumerate(lines[:5], 1):
                    try:
                        obj = json.loads(line)
                        with st.expander(f"Baris {idx}: {str(obj.get('prompt',''))[:55]}..."):
                            st.json(obj)
                    except Exception:
                        st.code(line, language="json")
                if len(lines) > 5:
                    st.caption(f"... dan {len(lines)-5} baris lainnya")
            else:
                st.caption("Belum diproses.")

        # Download individual
        dl1, dl2 = st.columns(2)
        with dl1:
            if d["e1"] or d["e2"] or d["e3"]:
                csv_b = build_csv(d["e1"] or "", d["e2"] or "", d["e3"] or "", fname)
                st.download_button(
                    f"⬇️ CSV — {fname.replace('.pdf','')}",
                    data=csv_b,
                    file_name=fname.replace(".pdf","_training_data.csv"),
                    mime="text/csv",
                    use_container_width=True,
                    key=f"csv_{fname}",
                )
        with dl2:
            if d["e4"]:
                st.download_button(
                    f"⬇️ JSONL — {fname.replace('.pdf','')}",
                    data=d["e4"].encode("utf-8"),
                    file_name=fname.replace(".pdf","_training_data.jsonl"),
                    mime="application/json",
                    use_container_width=True,
                    key=f"jsonl_{fname}",
                )


# ─────────────────────────────────────────────
# DOWNLOAD SEMUA (ZIP)
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("## ⬇️ Download Semua Output")

has_csv  = any(d["e1"] or d["e2"] or d["e3"] for d in st.session_state.docs.values())
has_json = any(d["e4"] for d in st.session_state.docs.values())

col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    st.markdown("#### 📊 Semua CSV dalam satu ZIP")
    st.caption(f"1 file CSV per dokumen PDF · {sum(1 for d in st.session_state.docs.values() if d['e1'] or d['e2'] or d['e3'])} CSV siap")
    if has_csv:
        zip_csv = build_zip_csv(st.session_state.docs)
        st.download_button(
            label="⬇️ Download semua CSV (.zip)",
            data=zip_csv,
            file_name="training_data_csv.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_zip_csv",
        )
    else:
        st.info("Jalankan Engine 1+2+3 terlebih dahulu.")

with col_dl2:
    st.markdown("#### 📄 Semua JSONL dalam satu ZIP")
    st.caption(f"1 file JSONL per dokumen PDF · {sum(1 for d in st.session_state.docs.values() if d['e4'])} JSONL siap")
    if has_json:
        zip_jl = build_zip_jsonl(st.session_state.docs)
        st.download_button(
            label="⬇️ Download semua JSONL (.zip)",
            data=zip_jl,
            file_name="training_data_jsonl.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_zip_jsonl",
        )
    else:
        st.info("Jalankan Engine 4 terlebih dahulu.")


# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<center><small>🤖 Training Dataset Generator · Pemrosesan Lokal (tanpa API) · "
    "Upload hingga 200 PDF · Output: CSV + JSONL per dokumen</small></center>",
    unsafe_allow_html=True,
)
