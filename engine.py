"""
engine.py — 4 engine pemrosesan PDF tanpa API key, tanpa sumy indonesian
Menggunakan: PyMuPDF, pytesseract, NLTK (english tokenizer), regex
"""

import re
import io
import json
import collections

import fitz          # PyMuPDF
import pytesseract
from PIL import Image

import nltk
from nltk.tokenize import sent_tokenize

for pkg in [("tokenizers/punkt_tab/english", "punkt_tab"),
            ("corpora/stopwords",             "stopwords")]:
    try:
        nltk.data.find(pkg[0])
    except LookupError:
        nltk.download(pkg[1], quiet=True)

try:
    from nltk.corpus import stopwords as _sw
    _EN = set(_sw.words("english"))
except Exception:
    _EN = set()

# Stopwords Indonesia — hardcoded, tidak perlu corpus download
_ID = {
    "yang","dan","di","ke","dari","dengan","untuk","pada","adalah","ini",
    "itu","atau","juga","dalam","tidak","akan","telah","oleh","sebagai",
    "dapat","serta","lebih","maka","tersebut","sesuai","harus","bahwa",
    "tentang","secara","antara","yaitu","namun","apabila","setiap","agar",
    "seperti","jika","bagi","dilakukan","dilaksanakan","berdasarkan",
    "menggunakan","terhadap","maupun","perlu","ada","sudah","belum",
    "sangat","hal","cara","dimana","sedangkan","adapun","selain","sehingga",
    "kemudian","berikut","meliputi","terdiri","melakukan","setelah","sebelum",
    "antara","sampai","sejak","hingga","melalui","selama","termasuk",
    "sebuah","suatu","semua","beberapa","setiap","tiap","banyak","sedikit",
    "lain","lainnya","tersebut","demikian","bahkan","namun","tetapi","namun",
    "meski","walaupun","karena","sehingga","agar","supaya","ketika","saat",
}
STOPWORDS = _ID | _EN


# ─────────────────────────────────────────────
# Utilitas PDF
# ─────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        text = page.get_text("text").strip()
        if text:
            pages.append(text)
        else:
            try:
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr = pytesseract.image_to_string(img, lang="ind+eng")
                if ocr.strip():
                    pages.append(ocr.strip())
            except Exception:
                pass
    doc.close()
    return "\n\n".join(pages)


def _word_freq(text: str) -> collections.Counter:
    words = re.findall(r'\b[a-zA-Z\u00C0-\u024F]{3,}\b', text.lower())
    return collections.Counter(w for w in words if w not in STOPWORDS)


def _score_sentences(sents: list, freq: collections.Counter) -> list:
    """Kembalikan list (score, sent) diurutkan desc."""
    scored = []
    for s in sents:
        ws = re.findall(r'\b[a-zA-Z\u00C0-\u024F]{3,}\b', s.lower())
        score = sum(freq.get(w, 0) for w in ws if w not in STOPWORDS)
        # Normalisasi panjang
        score = score / max(len(ws), 1)
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


# ─────────────────────────────────────────────
# ENGINE 1 — Daftar Isi
# ─────────────────────────────────────────────

def engine1_daftar_isi(pdf_bytes: bytes) -> str:
    text = extract_text_from_pdf(pdf_bytes)
    lines = text.splitlines()

    dots_re    = re.compile(r'\.{3,}')
    pageno_re  = re.compile(r'\s+\d{1,4}\s*$')
    toc_hdr    = re.compile(r'daftar\s+isi|table\s+of\s+contents', re.I)
    heading_re = re.compile(
        r'^(\d+[\.\d]*\s|BAB\s+[IVXLC0-9]+|Pasal\s+\d+|[A-Z]{2,}\s)',
        re.I
    )

    items = []
    in_toc = False
    consecutive_non_toc = 0

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if toc_hdr.search(s):
            in_toc = True
            consecutive_non_toc = 0
            continue

        has_dots = dots_re.search(s)
        looks_heading = heading_re.match(s) and len(s) < 160

        if in_toc:
            if has_dots or looks_heading:
                consecutive_non_toc = 0
                cleaned = dots_re.sub('', s)
                cleaned = pageno_re.sub('', cleaned).strip()
                if 3 < len(cleaned) < 160:
                    items.append(cleaned)
            else:
                consecutive_non_toc += 1
                # Keluar jika 3 baris berturut bukan TOC
                if consecutive_non_toc >= 3:
                    in_toc = False
        elif has_dots:
            cleaned = dots_re.sub('', s)
            cleaned = pageno_re.sub('', cleaned).strip()
            if 3 < len(cleaned) < 160:
                items.append(cleaned)

    # Fallback: ambil baris heading pendek
    if len(items) < 3:
        items = []
        for line in lines:
            s = line.strip()
            if heading_re.match(s) and 5 < len(s) < 140:
                cleaned = dots_re.sub('', s)
                cleaned = pageno_re.sub('', cleaned).strip()
                if cleaned:
                    items.append(cleaned)

    # Deduplikasi
    seen, unique = set(), []
    for it in items:
        k = re.sub(r'\s+', ' ', it.lower())
        if k not in seen:
            seen.add(k)
            unique.append(it)

    return "; ".join(unique) if unique else "TIDAK ADA DAFTAR ISI"


# ─────────────────────────────────────────────
# ENGINE 2 — Keywords
# ─────────────────────────────────────────────

def engine2_keywords(pdf_bytes: bytes) -> str:
    text = extract_text_from_pdf(pdf_bytes)
    freq = _word_freq(text)

    # Bigram
    tokens = [w for w in re.findall(r'\b[a-zA-Z\u00C0-\u024F]{3,}\b', text.lower())
              if w not in STOPWORDS]
    bigram_freq = collections.Counter(
        f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens)-1)
    )

    kws = []
    seen_words = set()

    for phrase, cnt in bigram_freq.most_common(12):
        if cnt < 2:
            break
        kws.append(phrase.title())
        for w in phrase.split():
            seen_words.add(w)

    for word, _ in freq.most_common(25):
        if word not in seen_words and len(kws) < 20:
            kws.append(word.title())

    return ", ".join(kws) if kws else "Tidak ada kata kunci"


# ─────────────────────────────────────────────
# ENGINE 3 — Ringkasan  (pure Python, no sumy)
# ─────────────────────────────────────────────

def engine3_ringkasan(pdf_bytes: bytes) -> str:
    text = extract_text_from_pdf(pdf_bytes)
    if not text.strip():
        return "Dokumen tidak dapat dibaca atau kosong."

    # Filter paragraf berbahasa Indonesia
    id_marker = re.compile(
        r'\b(adalah|merupakan|dalam|untuk|dengan|bahwa|tersebut|'
        r'dilakukan|berdasarkan|sesuai|pasal|bab|ketentuan|standar|'
        r'persyaratan|pengujian|prosedur|metode|dilaksanakan)\b', re.I
    )
    paras = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    id_paras = [p for p in paras if id_marker.search(p)]
    use_text = "\n\n".join(id_paras) if len(id_paras) >= 3 else text
    use_text = use_text[:14000]

    # Tokenisasi kalimat pakai english tokenizer (cukup untuk kalimat-kalimat Indonesia)
    try:
        sents = sent_tokenize(use_text)
    except Exception:
        sents = re.split(r'(?<=[.!?])\s+', use_text)

    if not sents:
        return use_text[:600]

    freq = _word_freq(use_text)
    scored = _score_sentences(sents, freq)

    # Ambil 8 kalimat terbaik, kembalikan dalam urutan asli
    top = set(s for _, s in scored[:8])
    ordered = [s for s in sents if s in top]

    result = " ".join(ordered)
    return result.strip() if result.strip() else use_text[:600]


# ─────────────────────────────────────────────
# ENGINE 4 — JSONL
# ─────────────────────────────────────────────

def _doc_type(text: str, fname: str) -> str:
    fl = fname.lower(); tl = text[:3000].lower()
    if re.search(r'\bsni\b', fl) or 'standar nasional indonesia' in tl:
        return "Standar Nasional Indonesia (SNI)"
    if re.search(r'\biso\b', fl):
        return "Standar Internasional ISO"
    if re.search(r'peraturan\s+(menteri|pemerintah|presiden)', tl):
        return "Peraturan/Regulasi Pemerintah"
    if re.search(r'(panduan|pedoman|manual)', tl):
        return "Panduan / Manual"
    if re.search(r'(laporan|report)', tl):
        return "Laporan"
    return "Dokumen Teknis"


def _paraphrase(s: str) -> str:
    """Variasi kalimat sederhana."""
    s = s.strip()
    subs = [
        (r'\badalah\b',       'merupakan'),
        (r'\bmerupakan\b',    'didefinisikan sebagai'),
        (r'\bdilakukan\b',    'dikerjakan'),
        (r'\bdigunakan\b',    'dimanfaatkan'),
        (r'\bberdasarkan\b',  'mengacu pada'),
        (r'\bharus\b',        'wajib'),
        (r'\bperlu\b',        'diperlukan'),
        (r'\bmencakup\b',     'meliputi'),
        (r'\bditetapkan\b',   'ditentukan'),
    ]
    for pat, rep in subs:
        s = re.sub(pat, rep, s, count=1, flags=re.I)
    return s


def engine4_jsonl(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    text = extract_text_from_pdf(pdf_bytes)
    if not text.strip():
        return json.dumps({"prompt": f"Apa isi dari {filename}?",
                           "completion": "Dokumen tidak dapat dibaca."}, ensure_ascii=False)

    base     = re.sub(r'\.pdf$', '', filename, flags=re.I)
    doc_type = _doc_type(text, filename)
    freq     = _word_freq(text)

    # Kalimat kunci
    try:
        sents = sent_tokenize(text[:12000])
    except Exception:
        sents = re.split(r'(?<=[.!?])\s+', text[:12000])

    scored = _score_sentences(sents, freq)
    key_sents = [s for _, s in scored[:25] if len(s) > 40]

    kw_str  = engine2_keywords(pdf_bytes)
    kw_list = [k.strip() for k in kw_str.split(',')[:8]]

    paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 80]
    intro = paras[0][:400]  if paras     else text[:400]
    outro = paras[-1][:300] if len(paras)>1 else ""

    lines = []

    # Pair 1: jenis dokumen
    lines.append(json.dumps({
        "prompt": f"Apa jenis dokumen {base}?",
        "completion": f"Dokumen {base} merupakan {doc_type}."
    }, ensure_ascii=False))

    # Pair 2: topik utama
    if kw_list:
        lines.append(json.dumps({
            "prompt": f"Apa topik utama yang dibahas dalam {base}?",
            "completion": f"Topik utama dalam {base} meliputi: {', '.join(kw_list[:5])}."
        }, ensure_ascii=False))

    # Pair 3: deskripsi awal
    if intro:
        lines.append(json.dumps({
            "prompt": f"Jelaskan secara singkat isi dari dokumen {base}.",
            "completion": _paraphrase(intro)
        }, ensure_ascii=False))

    # Pair 4–13: dari kalimat kunci
    templates = [
        "Apa yang dimaksud dengan {kw} dalam {doc}?",
        "Bagaimana {doc} menjelaskan tentang {kw}?",
        "Sebutkan ketentuan terkait {kw} dalam {doc}.",
        "Apa persyaratan {kw} berdasarkan {doc}?",
        "Bagaimana prosedur {kw} menurut {doc}?",
        "Apa tujuan dari {kw} yang disebutkan dalam {doc}?",
        "Jelaskan fungsi {kw} sesuai {doc}.",
        "Apa yang diatur tentang {kw} di dalam {doc}?",
        "Bagaimana standar {kw} dijelaskan dalam {doc}?",
        "Sebutkan informasi penting tentang {kw} dalam {doc}.",
    ]
    used = set()
    for i, sent in enumerate(key_sents):
        if len(lines) >= 13:
            break
        if sent in used:
            continue
        used.add(sent)
        kw = next((k for k in kw_list if k.lower() in sent.lower()), None)
        if not kw and kw_list:
            kw = kw_list[i % len(kw_list)]
        tmpl = templates[i % len(templates)]
        lines.append(json.dumps({
            "prompt": tmpl.format(kw=kw or "hal ini", doc=base),
            "completion": _paraphrase(sent)
        }, ensure_ascii=False))

    # Pair: ringkasan
    ring = engine3_ringkasan(pdf_bytes)
    if ring and len(ring) > 50:
        lines.append(json.dumps({
            "prompt": f"Berikan ringkasan dokumen {base}.",
            "completion": ring[:600]
        }, ensure_ascii=False))

    # Pair: kesimpulan
    if outro:
        lines.append(json.dumps({
            "prompt": f"Apa kesimpulan atau ketentuan akhir dalam {base}?",
            "completion": _paraphrase(outro)
        }, ensure_ascii=False))

    return "\n".join(lines)
