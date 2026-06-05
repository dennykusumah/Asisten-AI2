"""
app.py — Streamlit PDF Keyword Extractor
Uses engine.py (no AI/API) for keyword extraction.
"""

import io
import csv
import json
import datetime
import streamlit as st
import pdfplumber

from engine import extract_keywords, document_stats

# ─── Page Config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PDF Keyword Extractor",
    page_icon="🔑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }

    /* Header */
    .main-header {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2rem;
        font-weight: 600;
        color: #58a6ff;
        letter-spacing: -0.5px;
        margin-bottom: 0;
    }
    .main-subheader {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.9rem;
        color: #8b949e;
        margin-top: 4px;
        margin-bottom: 24px;
    }

    /* Stat cards */
    .stat-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px 20px;
        text-align: center;
    }
    .stat-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.6rem;
        font-weight: 600;
        color: #58a6ff;
    }
    .stat-label {
        font-size: 0.75rem;
        color: #8b949e;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }

    /* Keyword tags */
    .kw-tag {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 4px;
        border: 1px solid;
    }
    .kw-high   { background: #1f3a5f; border-color: #58a6ff; color: #a5d3ff; }
    .kw-medium { background: #1f3524; border-color: #3fb950; color: #7ee787; }
    .kw-low    { background: #2d2416; border-color: #d29922; color: #e3b341; }

    /* Table */
    .kw-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.88rem;
    }
    .kw-table th {
        background: #1c2128;
        color: #8b949e;
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 1px;
        padding: 10px 14px;
        text-align: left;
        border-bottom: 1px solid #30363d;
        font-family: 'IBM Plex Mono', monospace;
    }
    .kw-table td {
        padding: 9px 14px;
        border-bottom: 1px solid #21262d;
        color: #e6edf3;
    }
    .kw-table tr:hover td {
        background: #1c2128;
    }
    .kw-table .rank {
        color: #6e7681;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
    }
    .kw-table .score {
        font-family: 'IBM Plex Mono', monospace;
        color: #58a6ff;
        font-size: 0.82rem;
    }
    .method-badge {
        display: inline-block;
        background: #1f2d3d;
        border: 1px solid #264f78;
        border-radius: 4px;
        padding: 2px 7px;
        font-size: 0.7rem;
        color: #79c0ff;
        font-family: 'IBM Plex Mono', monospace;
    }
    .score-bar-bg {
        background: #21262d;
        border-radius: 4px;
        height: 6px;
        width: 100%;
        margin-top: 4px;
    }
    .score-bar-fill {
        background: linear-gradient(90deg, #1f6feb, #58a6ff);
        border-radius: 4px;
        height: 6px;
    }

    /* Buttons */
    .stDownloadButton > button {
        background: #1f6feb !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-weight: 600 !important;
        letter-spacing: 0.3px !important;
        padding: 8px 20px !important;
    }
    .stDownloadButton > button:hover {
        background: #388bfd !important;
    }

    /* Upload area */
    .uploadedFile {
        background: #161b22 !important;
        border: 1px dashed #30363d !important;
        border-radius: 8px !important;
    }

    /* Divider */
    hr { border-color: #30363d; }

    /* Slider */
    .stSlider > div > div { color: #58a6ff; }

    /* Select box */
    .stSelectbox label { color: #8b949e; font-size: 0.82rem; }

    /* Section titles */
    .section-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        border-bottom: 1px solid #21262d;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }

    /* Badge pill */
    .badge {
        display: inline-block;
        background: #0d419d;
        color: #79c0ff;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 12px;
        margin-left: 8px;
    }
    
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #8b949e;
        border: 1px dashed #30363d;
        border-radius: 12px;
        margin-top: 16px;
    }
    .empty-state .icon { font-size: 3rem; }
    .empty-state p { margin-top: 12px; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(uploaded_file) -> str:
    """Extract all text from uploaded PDF using pdfplumber."""
    text_parts = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def score_class(score: float, all_scores: list) -> str:
    if not all_scores:
        return "kw-medium"
    mx = max(all_scores)
    if mx == 0:
        return "kw-medium"
    ratio = score / mx
    if ratio >= 0.6:
        return "kw-high"
    elif ratio >= 0.3:
        return "kw-medium"
    return "kw-low"


def build_csv(keywords: list) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["rank", "keyword", "score", "method"])
    writer.writeheader()
    for i, kw in enumerate(keywords, 1):
        writer.writerow({"rank": i, **kw})
    return buf.getvalue().encode("utf-8")


def build_json(keywords: list, stats: dict, filename: str) -> bytes:
    payload = {
        "source_file": filename,
        "extracted_at": datetime.datetime.now().isoformat(),
        "document_stats": stats,
        "keywords": [{"rank": i + 1, **kw} for i, kw in enumerate(keywords)],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def build_txt(keywords: list) -> bytes:
    lines = ["EXTRACTED KEYWORDS", "=" * 40, ""]
    for i, kw in enumerate(keywords, 1):
        lines.append(f"{i:3}. {kw['keyword']} (score: {kw['score']}) [{kw['method']}]")
    return "\n".join(lines).encode("utf-8")


# ─── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Extraction Settings")
    st.markdown("---")

    method = st.selectbox(
        "Extraction Method",
        options=["ensemble", "tfidf", "rake", "frequency"],
        index=0,
        format_func=lambda x: {
            "ensemble": "🔀 Ensemble (Recommended)",
            "tfidf": "📊 TF-IDF",
            "rake": "🌿 RAKE",
            "frequency": "📈 Frequency + Bigrams",
        }[x],
        help="Choose the algorithm to extract keywords.",
    )

    top_n = st.slider("Max Keywords", min_value=5, max_value=100, value=30, step=5)

    min_score = st.slider(
        "Min Score Threshold", min_value=0.0, max_value=1.0, value=0.0, step=0.05,
        help="Filter out keywords below this normalized score.",
    )

    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown("""
<div style='font-size:0.8rem; color:#8b949e; line-height:1.6'>
<b style='color:#e6edf3'>Methods used:</b><br>
• <b style='color:#58a6ff'>TF-IDF</b> — term importance vs. document frequency<br>
• <b style='color:#3fb950'>RAKE</b> — rapid phrase extraction via stopword splitting<br>
• <b style='color:#d29922'>Frequency</b> — unigram + bigram frequency analysis<br><br>
<b style='color:#e6edf3'>No AI / external API used.</b><br>
All computation is local & offline.
</div>
""", unsafe_allow_html=True)


# ─── Main ────────────────────────────────────────────────────────────────────────

st.markdown('<p class="main-header">🔑 PDF Keyword Extractor</p>', unsafe_allow_html=True)
st.markdown('<p class="main-subheader">Upload a PDF and instantly extract meaningful keywords — no AI, no API, fully offline.</p>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    label="Drag & drop or click to upload a PDF",
    type=["pdf"],
    accept_multiple_files=False,
    label_visibility="visible",
)

if uploaded_file is None:
    st.markdown("""
    <div class="empty-state">
        <div class="icon">📄</div>
        <p>Upload a PDF file to begin extracting keywords.<br>
        Supports any text-based PDF document.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ─── Processing ─────────────────────────────────────────────────────────────────

with st.spinner("📖 Reading PDF..."):
    try:
        raw_text = extract_text_from_pdf(uploaded_file)
    except Exception as e:
        st.error(f"❌ Failed to read PDF: {e}")
        st.stop()

if not raw_text or len(raw_text.strip()) < 100:
    st.warning("⚠️ The PDF appears to have very little extractable text (may be scanned/image-based). Try a text-based PDF.")
    st.stop()

with st.spinner("🔍 Extracting keywords..."):
    keywords = extract_keywords(raw_text, method=method, top_n=top_n, min_score=min_score)
    stats = document_stats(raw_text)

if not keywords:
    st.warning("No keywords found with current settings. Try lowering the minimum score threshold.")
    st.stop()

# ─── Document Stats ──────────────────────────────────────────────────────────────

st.markdown('<p class="section-title">Document Overview</p>', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)
for col, label, value in zip(
    [c1, c2, c3, c4, c5],
    ["Words", "Sentences", "Unique Tokens", "Characters", "Keywords Found"],
    [stats["total_words"], stats["total_sentences"], stats["unique_tokens"],
     stats["total_chars"], len(keywords)],
):
    col.markdown(f"""
    <div class="stat-card">
        <div class="stat-value">{value:,}</div>
        <div class="stat-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Tabs: Visual / Table / Text ────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["☁️ Tag Cloud", "📋 Table View", "📄 Raw Text"])

all_scores = [kw["score"] for kw in keywords]

with tab1:
    st.markdown('<p class="section-title">Keywords — Visual Overview</p>', unsafe_allow_html=True)
    tag_html = ""
    for kw in keywords:
        css_cls = score_class(kw["score"], all_scores)
        tag_html += f'<span class="kw-tag {css_cls}">{kw["keyword"]}</span>'
    st.markdown(f'<div style="line-height:2.4">{tag_html}</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style='margin-top:16px; font-size:0.76rem; color:#6e7681'>
        <span class='kw-tag kw-high' style='font-size:0.7rem'>high</span>
        <span class='kw-tag kw-medium' style='font-size:0.7rem'>medium</span>
        <span class='kw-tag kw-low' style='font-size:0.7rem'>low</span>
        &nbsp; relevance tiers
    </div>
    """, unsafe_allow_html=True)

with tab2:
    st.markdown('<p class="section-title">Keywords — Detailed Table</p>', unsafe_allow_html=True)
    max_score = max(all_scores) if all_scores else 1

    rows_html = ""
    for i, kw in enumerate(keywords, 1):
        pct = int((kw["score"] / max_score) * 100) if max_score else 0
        rows_html += f"""
        <tr>
            <td class="rank">#{i}</td>
            <td><b>{kw['keyword']}</b>
                <div class="score-bar-bg"><div class="score-bar-fill" style="width:{pct}%"></div></div>
            </td>
            <td class="score">{kw['score']}</td>
            <td><span class="method-badge">{kw['method']}</span></td>
        </tr>
        """

    st.markdown(f"""
    <table class="kw-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Keyword</th>
                <th>Score</th>
                <th>Method</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """, unsafe_allow_html=True)

with tab3:
    st.markdown('<p class="section-title">Extracted Raw Text</p>', unsafe_allow_html=True)
    st.text_area(
        label="",
        value=raw_text[:5000] + ("\n\n[... truncated for display ...]" if len(raw_text) > 5000 else ""),
        height=350,
        label_visibility="collapsed",
    )
    st.caption(f"Showing first 5,000 of {len(raw_text):,} characters.")

# ─── Download Section ────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown('<p class="section-title">Download Results</p>', unsafe_allow_html=True)

base_name = uploaded_file.name.replace(".pdf", "")
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

dl_csv, dl_json, dl_txt = st.columns(3)

with dl_csv:
    st.download_button(
        label="⬇️ Download CSV",
        data=build_csv(keywords),
        file_name=f"keywords_{base_name}_{timestamp}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with dl_json:
    st.download_button(
        label="⬇️ Download JSON",
        data=build_json(keywords, stats, uploaded_file.name),
        file_name=f"keywords_{base_name}_{timestamp}.json",
        mime="application/json",
        use_container_width=True,
    )

with dl_txt:
    st.download_button(
        label="⬇️ Download TXT",
        data=build_txt(keywords),
        file_name=f"keywords_{base_name}_{timestamp}.txt",
        mime="text/plain",
        use_container_width=True,
    )

st.caption(f"📄 Source: **{uploaded_file.name}** &nbsp;|&nbsp; Method: **{method}** &nbsp;|&nbsp; {len(keywords)} keywords extracted")
