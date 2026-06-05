"""
engine.py — 4 engine pemrosesan dokumen PDF tanpa API key
Menggunakan: PyMuPDF, pdfplumber, pytesseract, NLTK, sumy
"""

import re
import io
import json
import math
import string
import collections

import fitz          # PyMuPDF
import pytesseract
from PIL import Image

# NLTK
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize

# Sumy untuk extractive summarization
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

# Pastikan NLTK data tersedia
for pkg in ["punkt", "stopwords", "punkt_tab"]:
    try:
        nltk.data.find(f"tokenizers/{pkg}" if "punkt" in pkg else f"corpora/{pkg}")
    except LookupError:
        nltk.download(pkg, quiet=True)

STOPWORDS_ID = set([
    "yang", "dan", "di", "ke", "dari", "dengan", "untuk", "pada", "adalah",
    "ini", "itu", "atau", "juga", "dalam", "tidak", "akan", "telah", "oleh",
    "sebagai", "dapat", "serta", "lebih", "maka", "tersebut", "sesuai",
    "harus", "bahwa", "tentang", "secara", "antara", "yaitu", "namun",
    "apabila", "setiap", "agar", "seperti", "jika", "tersebut", "bagi",
    "dilakukan", "dilaksanakan", "berdasarkan", "menggunakan", "terhadap",
    "maupun", "perlu", "ada", "sudah", "belum", "sangat", "hal", "cara",
    "dimana", "sedangkan", "adapun", "selain", "sehingga", "kemudian",
    "berikut", "meliputi", "terdiri", "melakukan", "setelah", "sebelum",
])

try:
    STOPWORDS_ID.update(stopwords.words("indonesian"))
except Exception:
    pass

try:
    STOPWORDS_EN = set(stopwords.words("english"))
except Exception:
    STOPWORDS_EN = set()

ALL_STOPWORDS = STOPWORDS_ID | STOPWORDS_EN


# ─────────────────────────────────────────────
# Utilitas PDF
# ─────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Ekstrak teks dari PDF. Halaman kosong → OCR via PyMuPDF + pytesseract."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []

    for page in doc:
        text = page.get_text("text").strip()
        if text:
            pages_text.append(text)
        else:
            try:
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr = pytesseract.image_to_string(img, lang="ind+eng")
                if ocr.strip():
                    pages_text.append(ocr.strip())
            except Exception:
                pass

    doc.close()
    return "\n\n".join(pages_text)


def _clean_text(text: str) -> str:
    """Bersihkan teks dari karakter aneh."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\u0100-\u017F\u1E00-\u1EFF\u00A0-\u00FF'
                  r'\u0020-\u007E\u0080-\u00FF]', ' ', text)
    return text.strip()


# ─────────────────────────────────────────────
# ENGINE 1 — Identifikasi Daftar Isi
# ─────────────────────────────────────────────

def engine1_daftar_isi(pdf_bytes: bytes) -> str:
    """
    Identifikasi daftar isi dokumen secara lokal.
    Cari baris yang mengandung pola daftar isi (heading/nomor bab).
    Hapus titik-titik dan nomor halaman, gabungkan dengan (;).
    """
    text = extract_text_from_pdf(pdf_bytes)
    lines = text.splitlines()

    # Pola khas daftar isi:
    # - Baris dengan banyak titik-titik (......) diikuti angka
    # - Baris dengan nomor bab: "1.", "BAB I", "1.1", "Pasal", dll
    # - Berada dalam blok "DAFTAR ISI" / "TABLE OF CONTENTS"

    toc_items = []
    in_toc_block = False
    dots_pattern   = re.compile(r'\.{3,}')
    page_num_end   = re.compile(r'\s+\d{1,4}\s*$')
    # Pola heading: dimulai dengan angka/huruf romawi/BAB/Pasal
    heading_pattern = re.compile(
        r'^(\s*)(\d+[\.\d]*|BAB\s+[IVXLC]+|Pasal\s+\d+|[A-Z][A-Z\s]{2,})\s+\S',
        re.IGNORECASE
    )
    toc_header = re.compile(r'daftar\s+isi|table\s+of\s+contents|contents', re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Deteksi masuk blok daftar isi
        if toc_header.search(stripped):
            in_toc_block = True
            continue

        # Keluar dari blok jika sudah jauh dari daftar isi
        if in_toc_block and len(toc_items) > 3:
            no_dots = not dots_pattern.search(stripped)
            not_heading = not re.match(r'^(\d+[\.\d]*|BAB|Pasal|[IVXLC]+[\.\s])', stripped, re.IGNORECASE)
            if (len(stripped) > 120 and no_dots) or (no_dots and not_heading and len(stripped) > 60):
                in_toc_block = False
                continue

        if in_toc_block or dots_pattern.search(stripped):
            # Hapus titik-titik
            cleaned = dots_pattern.sub('', stripped)
            # Hapus nomor halaman di akhir
            cleaned = page_num_end.sub('', cleaned)
            cleaned = cleaned.strip()
            if cleaned and len(cleaned) > 3 and len(cleaned) < 200:
                toc_items.append(cleaned)

    # Fallback: cari baris heading jika tidak ada TOC eksplisit
    if len(toc_items) < 3:
        toc_items = []
        for line in lines:
            stripped = line.strip()
            if not stripped or len(stripped) > 150:
                continue
            if heading_pattern.match(stripped):
                # Hapus dots & page num jika ada
                cleaned = dots_pattern.sub('', stripped)
                cleaned = page_num_end.sub('', cleaned).strip()
                if cleaned and len(cleaned) > 3:
                    toc_items.append(cleaned)

    # Deduplikasi dengan mempertahankan urutan
    seen = set()
    unique_items = []
    for item in toc_items:
        key = re.sub(r'\s+', ' ', item.lower())
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    if unique_items:
        return "; ".join(unique_items)
    return "TIDAK ADA DAFTAR ISI"


# ─────────────────────────────────────────────
# ENGINE 2 — Ekstraksi Keywords
# ─────────────────────────────────────────────

def engine2_keywords(pdf_bytes: bytes) -> str:
    """
    Hasilkan daftar keywords dari isi dokumen menggunakan TF-IDF sederhana.
    """
    text = extract_text_from_pdf(pdf_bytes)
    text_clean = _clean_text(text).lower()

    # Tokenisasi kata
    tokens = re.findall(r'\b[a-zA-Z\u00C0-\u024F]{3,}\b', text_clean)
    tokens = [t for t in tokens if t not in ALL_STOPWORDS and len(t) > 2]

    # Hitung frekuensi
    freq = collections.Counter(tokens)

    # Ambil juga bigram (frasa 2 kata)
    bigrams = []
    token_list = [t for t in re.findall(r'\b[a-zA-Z\u00C0-\u024F]{3,}\b', text_clean)
                  if t not in ALL_STOPWORDS]
    for i in range(len(token_list) - 1):
        bigrams.append(f"{token_list[i]} {token_list[i+1]}")
    bigram_freq = collections.Counter(bigrams)

    # Skor gabungan: ambil top unigram + bigram
    top_uni = [w for w, _ in freq.most_common(25)]
    top_bi  = [w for w, c in bigram_freq.most_common(15) if c >= 2]

    # Gabungkan, prioritaskan bigram
    keywords = []
    seen_words = set()
    for phrase in top_bi[:10]:
        keywords.append(phrase)
        for w in phrase.split():
            seen_words.add(w)
    for word in top_uni:
        if word not in seen_words and len(keywords) < 20:
            keywords.append(word)

    if keywords:
        # Kapitalisasi pertama tiap kata
        keywords = [k.title() for k in keywords]
        return ", ".join(keywords)
    return "Tidak ada kata kunci ditemukan"


# ─────────────────────────────────────────────
# ENGINE 3 — Ringkasan Dokumen
# ─────────────────────────────────────────────

def engine3_ringkasan(pdf_bytes: bytes) -> str:
    """
    Ringkas isi dokumen menggunakan LSA extractive summarization (sumy).
    Untuk dokumen dwibahasa, fokus pada kalimat berbahasa Indonesia.
    """
    text = extract_text_from_pdf(pdf_bytes)
    if not text.strip():
        return "Dokumen tidak dapat dibaca atau kosong."

    # Filter kalimat Indonesia (heuristik: banyak kata Indonesia)
    id_markers = re.compile(
        r'\b(adalah|merupakan|dalam|untuk|dengan|bahwa|tersebut|'
        r'dilakukan|berdasarkan|sesuai|pasal|bab|ketentuan|standar|'
        r'persyaratan|pengujian|pengukuran|prosedur|metode)\b',
        re.IGNORECASE
    )

    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    id_paragraphs = []
    for p in paragraphs:
        if id_markers.search(p):
            id_paragraphs.append(p)

    # Jika tidak cukup kalimat Indonesia, gunakan semua
    use_text = "\n\n".join(id_paragraphs) if len(id_paragraphs) >= 3 else text

    # Batasi panjang teks agar sumy tidak terlalu lambat
    use_text = use_text[:15000]

    try:
        parser = PlaintextParser.from_string(use_text, Tokenizer("indonesian"))
        stemmer = Stemmer("indonesian")
        summarizer = LsaSummarizer(stemmer)
        summarizer.stop_words = get_stop_words("indonesian")

        sentences = summarizer(parser.document, 10)
        result = " ".join(str(s) for s in sentences)
        if result.strip():
            return result.strip()
    except Exception:
        pass

    # Fallback: ambil kalimat dengan skor TF sederhana
    all_sents = sent_tokenize(use_text[:8000])
    if not all_sents:
        return use_text[:500]

    # Skor kalimat berdasarkan kandungan kata penting
    words = re.findall(r'\b\w{4,}\b', use_text.lower())
    word_freq = collections.Counter(w for w in words if w not in ALL_STOPWORDS)

    scored = []
    for sent in all_sents:
        score = sum(word_freq.get(w.lower(), 0) for w in re.findall(r'\b\w{4,}\b', sent))
        scored.append((score, sent))

    scored.sort(reverse=True)
    top_sents = [s for _, s in scored[:8]]

    # Kembalikan dalam urutan asli
    ordered = sorted(top_sents, key=lambda s: all_sents.index(s) if s in all_sents else 999)
    return " ".join(ordered)


# ─────────────────────────────────────────────
# ENGINE 4 — Identifikasi, Paraphrase → JSONL
# ─────────────────────────────────────────────

def _identify_doc_type(text: str, filename: str) -> str:
    """Tebak jenis dokumen dari teks & nama file."""
    fname_lower = filename.lower()
    text_lower  = text[:3000].lower()

    if re.search(r'\bsni\b', fname_lower) or re.search(r'standar nasional indonesia', text_lower):
        return "Standar Nasional Indonesia (SNI)"
    if re.search(r'\biso\b', fname_lower):
        return "Standar Internasional ISO"
    if re.search(r'peraturan\s+(menteri|pemerintah|presiden)', text_lower):
        return "Peraturan/Regulasi Pemerintah"
    if re.search(r'\b(manual|panduan|pedoman)\b', text_lower):
        return "Panduan / Manual"
    if re.search(r'\b(laporan|report)\b', text_lower):
        return "Laporan"
    if re.search(r'\b(skripsi|thesis|disertasi)\b', text_lower):
        return "Karya Ilmiah"
    return "Dokumen Teknis"


def _extract_key_sentences(text: str, n: int = 20) -> list:
    """Ekstrak kalimat paling informatif dari teks."""
    sents = sent_tokenize(text[:12000])
    if not sents:
        return [text[:200]]

    words = re.findall(r'\b\w{4,}\b', text.lower())
    word_freq = collections.Counter(w for w in words if w not in ALL_STOPWORDS)

    scored = []
    for s in sents:
        ws = re.findall(r'\b\w{4,}\b', s.lower())
        score = sum(word_freq.get(w, 0) for w in ws if w not in ALL_STOPWORDS)
        scored.append((score, s))

    scored.sort(reverse=True)
    return [s for _, s in scored[:n]]


def _paraphrase_sentence(sent: str) -> str:
    """Paraphrase sederhana: ubah struktur kalimat sedikit."""
    sent = sent.strip()
    # Ganti beberapa frasa umum
    replacements = [
        (r'\badalah\b', 'merupakan'),
        (r'\bmerupakan\b', 'didefinisikan sebagai'),
        (r'\bdilakukan\b', 'dikerjakan'),
        (r'\bdigunakan\b', 'dimanfaatkan'),
        (r'\bberdasarkan\b', 'mengacu pada'),
        (r'\bharus\b', 'wajib'),
        (r'\bperlu\b', 'diperlukan'),
        (r'\bsebaiknya\b', 'disarankan'),
        (r'\bmencakup\b', 'meliputi'),
        (r'\bditetapkan\b', 'ditentukan'),
    ]
    for pat, repl in replacements:
        sent = re.sub(pat, repl, sent, count=1, flags=re.IGNORECASE)
    return sent


def engine4_jsonl(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """
    Konversi dokumen PDF ke format JSONL training dataset secara lokal.
    Hasilkan pasangan prompt-completion dari isi dokumen.
    """
    text = extract_text_from_pdf(pdf_bytes)

    if not text.strip():
        return json.dumps(
            {"prompt": f"Apa isi dari {filename}?",
             "completion": "Dokumen tidak dapat dibaca atau kosong."},
            ensure_ascii=False
        )

    doc_type  = _identify_doc_type(text, filename)
    base_name = re.sub(r'\.pdf$', '', filename, flags=re.IGNORECASE)

    # Ekstrak kalimat kunci
    key_sents = _extract_key_sentences(text, n=30)

    # Keywords untuk konteks
    kw_raw = engine2_keywords(pdf_bytes)
    keywords_list = [k.strip() for k in kw_raw.split(',')[:8]]

    # Ringkasan singkat
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 80]
    intro_para = paragraphs[0][:400] if paragraphs else text[:400]

    jsonl_lines = []

    # ── Pair 1: Definisi/jenis dokumen
    jsonl_lines.append(json.dumps({
        "prompt": f"Apa jenis dokumen {base_name}?",
        "completion": f"Dokumen {base_name} merupakan {doc_type}."
    }, ensure_ascii=False))

    # ── Pair 2: Topik utama
    if keywords_list:
        kw_str = ", ".join(keywords_list[:5])
        jsonl_lines.append(json.dumps({
            "prompt": f"Apa topik utama yang dibahas dalam {base_name}?",
            "completion": f"Topik utama dalam {base_name} meliputi: {kw_str}."
        }, ensure_ascii=False))

    # ── Pair 3: Isi/deskripsi awal
    if intro_para:
        jsonl_lines.append(json.dumps({
            "prompt": f"Jelaskan secara singkat isi dari dokumen {base_name}.",
            "completion": _paraphrase_sentence(intro_para)
        }, ensure_ascii=False))

    # ── Pair 4–8: Dari kalimat kunci (penjelasan & definisi)
    used = set()
    pair_count = 0
    question_templates = [
        "Apa yang dimaksud dengan {kw} dalam {doc}?",
        "Bagaimana {doc} menjelaskan tentang {kw}?",
        "Sebutkan ketentuan terkait {kw} dalam {doc}.",
        "Apa persyaratan {kw} berdasarkan {doc}?",
        "Bagaimana prosedur {kw} menurut {doc}?",
        "Apa tujuan dari {kw} yang disebutkan dalam {doc}?",
        "Jelaskan fungsi {kw} sesuai {doc}.",
    ]

    for i, sent in enumerate(key_sents):
        if pair_count >= 10:
            break
        sent_clean = sent.strip()
        if len(sent_clean) < 40 or sent_clean in used:
            continue
        used.add(sent_clean)

        # Pilih keyword yang relevan untuk kalimat ini
        rel_kw = None
        for kw in keywords_list:
            if kw.lower() in sent_clean.lower():
                rel_kw = kw
                break
        if not rel_kw and keywords_list:
            rel_kw = keywords_list[i % len(keywords_list)]

        tmpl = question_templates[pair_count % len(question_templates)]
        question = tmpl.format(kw=rel_kw or "hal ini", doc=base_name)
        completion = _paraphrase_sentence(sent_clean)

        jsonl_lines.append(json.dumps({
            "prompt": question,
            "completion": completion
        }, ensure_ascii=False))
        pair_count += 1

    # ── Pair akhir: ringkasan
    ringkasan = engine3_ringkasan(pdf_bytes)
    if ringkasan and len(ringkasan) > 50:
        jsonl_lines.append(json.dumps({
            "prompt": f"Berikan ringkasan dokumen {base_name}.",
            "completion": ringkasan[:600]
        }, ensure_ascii=False))

    # ── Pair: kesimpulan/konteks
    if len(paragraphs) > 1:
        last_para = paragraphs[-1][:300]
        jsonl_lines.append(json.dumps({
            "prompt": f"Apa kesimpulan atau ketentuan akhir dalam {base_name}?",
            "completion": _paraphrase_sentence(last_para)
        }, ensure_ascii=False))

    return "\n".join(jsonl_lines)
