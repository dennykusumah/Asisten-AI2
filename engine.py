"""
engine.py — Local SNI extraction engine (NO API, NO network)
PDF/Word → regex heuristic → CSV record

Strategi ekstraksi:
  1. Ekstrak teks dari PDF (PyMuPDF, per-blok dengan posisi) atau DOCX (python-docx)
  2. no_sni  : diambil dari teks pojok KANAN ATAS halaman pertama (x > 60% lebar halaman)
  3. judul   : baris terpanjang/title-case di area tengah halaman pertama, setelah header SNI
  4. ruang_lingkup : teks di bawah header "Ruang Lingkup" s.d. section berikutnya
  5. persyaratan   : parameter + nilai + satuan dari tabel syarat mutu
  6. metode_uji    : referensi SNI/ISO dari section metode/cara uji
  7. halaman       : jumlah halaman dokumen
  8. kategori      : infer dari judul + ruang lingkup
  9. keywords      : token penting dari judul + parameter
"""

import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

log = logging.getLogger("sni_engine")

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_SCOPE_CHARS = 300
MAX_KW_WORDS    = 25

CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["pangan","makanan","minuman","gula","garam","minyak","susu","daging","ikan","beras",
       "tepung","kopi","teh","cokelat","bumbu","saos","kecap","mie","roti","biskuit","snack",
       "keju","mentega","margarin","es krim","sirup","jus","sari buah","pati","santan",
       "kacang","tempe","tahu","produk olahan"], "Pangan"),
    (["kimia","bahan kimia","pestisida","pupuk","cat","pelarut","asam","basa","reagen",
       "deterjen","sabun","kosmetik","parfum","pigmen","adhesif","lem","polimer","resin",
       "solvent","surfaktan"], "Kimia"),
    (["konstruksi","bangunan","beton","semen","baja","besi","kayu","cat tembok","keramik",
       "genteng","bata","pondasi","aspal","agregat","mortar","panel","plat","pipa konstruksi",
       "struktur","dinding","lantai","atap"], "Konstruksi"),
    (["elektro","listrik","elektronik","kabel","transformator","motor","generator","baterai",
       "saklar","stop kontak","lampu","led","solar","panel surya","inverter","ups","charger",
       "tegangan","arus listrik","frekuensi","daya listrik"], "Elektro"),
    (["mekanik","mesin","pompa","kompresor","turbin","roda gigi","bearing","piston","silinder",
       "katup","flange","baut","mur","pipa","fitting","valve"], "Mekanik"),
    (["tekstil","kain","benang","serat","rajut","tenun","pakaian","garmen","karpet","nonwoven",
       "kapas","nilon","polyester","wol"], "Tekstil"),
    (["pertanian","agro","bibit","benih","pupuk","tanah","irigasi","traktor","panen",
       "hortikultura","perkebunan","perikanan","budidaya"], "Pertanian"),
    (["lingkungan","air bersih","air minum","air limbah","udara","limbah","emisi","polutan",
       "baku mutu","amdal","pencemaran","ekosistem"], "Lingkungan"),
    (["kesehatan","medis","alat kesehatan","farmasi","obat","sterilisasi","masker",
       "sarung tangan medis","jarum","syringe","diagnostik","laboratorium klinik"], "Kesehatan"),
    (["informatika","teknologi informasi","perangkat lunak","software","hardware","jaringan",
       "keamanan informasi","enkripsi","iso 27","siber","cloud","data center"], "Informatika"),
    (["transportasi","kendaraan","otomotif","sepeda motor","ban","helm","sabuk pengaman",
       "kapal","pesawat","kereta","jalan","jembatan","pelabuhan"], "Transportasi"),
]

# Pola deteksi parameter (regex, untuk persyaratan)
PARAM_PATTERNS = [
    # "Timbal (Pb)  maks 0,05 mg/L" atau dengan ≤ ≥ < >
    r'([A-Za-z\u00C0-\u024F][A-Za-z0-9\s\(\)\-\.\/]{2,45}?)\s+'
    r'(?:maks(?:imum)?|min(?:imum)?|tidak\s+(?:lebih\s+dari|kurang\s+dari)|≤|≥|<|>|=)\s*'
    r'([\d,\.]+(?:\s*[–\-]\s*[\d,\.]+)?)\s*([a-zA-Z/%µμ°][a-zA-Z0-9/%µμ°]*)?',
    # "Kadar air : 14,0 %"
    r'([A-Za-z\u00C0-\u024F][A-Za-z0-9\s\(\)\-\.\/]{2,40}?)\s*[:=]\s*([\d,\.]+)\s*([a-zA-Z/%µμ°][a-zA-Z0-9/%µμ°]*)',
]

# Pola nomor SNI dalam teks biasa
SNI_REF_PATTERN  = re.compile(r'SNI\s+(\d{2}[\-\.\s]\d{3,5}[\-\.\s]\d{4})', re.IGNORECASE)
# Pola nomor SNI di cover (pojok kanan atas): "SNI 3753:2009" atau "SNI 01-3553-2006"
SNI_COVER_FULL   = re.compile(
    r'SNI\s+(\d{2,4}[\.\-:\s]\d{3,5}(?:[\.\-:]\d{4})?)',
    re.IGNORECASE
)
ISO_REF_PATTERN  = re.compile(r'ISO\s+(\d{3,6}(?:[\-:]\d+)?)', re.IGNORECASE)
YEAR_PATTERN     = re.compile(r'\b(19|20)\d{2}\b')


# ─── Data model ───────────────────────────────────────────────────────────────
@dataclass
class SNIRecord:
    no_sni:        str = ""
    judul:         str = ""
    kategori:      str = ""
    ruang_lingkup: str = ""
    persyaratan:   str = "-"
    metode_uji:    str = "-"
    halaman:       int = 0
    keywords:      str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─── PDF Text + Layout Extraction ─────────────────────────────────────────────

def extract_pdf_with_layout(path: Path) -> tuple[list[dict], int]:
    """
    Ekstrak teks PDF per-blok dengan posisi (x0,y0,x1,y1).
    Return: (blocks_list, total_pages)
    blocks_list item: {"page": int, "x0","y0","x1","y1": float, "text": str}
    """
    try:
        import fitz
        doc  = fitz.open(str(path))
        pages = len(doc)
        blocks_all = []
        for page_num, page in enumerate(doc):
            if page_num >= 80:   # batas max
                break
            pw = page.rect.width
            ph = page.rect.height
            raw = page.get_text("blocks")  # (x0,y0,x1,y1,text,block_no,block_type)
            for b in raw:
                if b[6] != 0:   # skip image blocks
                    continue
                text = b[4].strip()
                if not text:
                    continue
                blocks_all.append({
                    "page": page_num,
                    "x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3],
                    "text": text,
                    "pw": pw, "ph": ph,
                })
        doc.close()
        return blocks_all, pages
    except Exception as e:
        log.warning(f"PyMuPDF layout failed {path.name}: {e}")
        return [], 0


def extract_pdf_plain(path: Path) -> tuple[str, int]:
    """Fallback: plain text extraction."""
    try:
        import fitz
        doc   = fitz.open(str(path))
        pages = len(doc)
        parts = []
        total = 0
        for page in doc:
            t = page.get_text("text")
            parts.append(t)
            total += len(t)
            if total > 60_000:
                break
        doc.close()
        return "\n".join(parts), pages
    except Exception:
        pass
    # fallback ke pypdf
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        pages = len(r.pages)
        parts = []
        for page in r.pages[:60]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts), pages
    except Exception as e:
        log.warning(f"PDF fallback failed {path.name}: {e}")
        return "", 0


def extract_docx(path: Path) -> tuple[str, int]:
    """Ekstrak teks dari DOCX, return (full_text, page_count_estimate)."""
    try:
        from docx import Document
        doc   = Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_cells:
                    parts.append(" | ".join(row_cells))
        full = "\n".join(parts)
        # Estimasi halaman dari jumlah kata (~300 kata/hal)
        words = len(full.split())
        pages = max(1, round(words / 300))
        return full, pages
    except Exception as e:
        log.warning(f"DOCX failed {path.name}: {e}")
        return "", 0


# ─── Heuristic Parsers ────────────────────────────────────────────────────────

def parse_no_sni_from_blocks(blocks: list[dict]) -> str:
    """
    Ekstrak nomor SNI dari pojok KANAN ATAS halaman pertama.
    Kriteria: halaman 0, x0 > 55% lebar halaman, y0 < 25% tinggi halaman,
    mengandung pola SNI number.
    """
    cover_blocks = [b for b in blocks if b["page"] == 0]
    if not cover_blocks:
        return ""

    # Ambil lebar & tinggi halaman pertama
    pw = cover_blocks[0]["pw"]
    ph = cover_blocks[0]["ph"]

    # Cari blok di kuadran kanan atas
    right_top = [
        b for b in cover_blocks
        if b["x0"] > pw * 0.45 and b["y1"] < ph * 0.30
    ]
    # Urutkan: paling atas dulu
    right_top.sort(key=lambda b: b["y0"])

    for b in right_top:
        text = b["text"].replace("\n", " ").strip()
        m = SNI_COVER_FULL.search(text)
        if m:
            raw = m.group(0).strip()
            # Normalisasi: ganti spasi/titik dengan strip, pastikan format SNI XX-XXXX-XXXX
            raw = re.sub(r'\s+', ' ', raw)
            return raw

    # Jika tidak ditemukan di kanan atas, coba seluruh halaman pertama (fallback)
    for b in cover_blocks:
        text = b["text"].replace("\n", " ").strip()
        # Prioritaskan baris yang HANYA berisi nomor SNI (pendek)
        if re.match(r'^SNI\s+[\d]', text, re.IGNORECASE) and len(text) < 60:
            m = SNI_COVER_FULL.search(text)
            if m:
                return m.group(0).strip()
    return ""


def parse_no_sni_from_text(text: str, filename: str) -> str:
    """Fallback: cari nomor SNI dari teks biasa (DOCX atau PDF tanpa layout)."""
    head = text[:1500]
    # Pola lengkap "SNI 3553:2006" atau "SNI 01-3553-2006"
    m = SNI_COVER_FULL.search(head)
    if m:
        return re.sub(r'\s+', ' ', m.group(0).strip())
    # Seluruh teks
    m = SNI_COVER_FULL.search(text)
    if m:
        return re.sub(r'\s+', ' ', m.group(0).strip())
    # Fallback dari nama file
    m2 = re.search(r'(\d{2}[\-\.]\d{3,5}[\-\.]\d{4})', filename)
    if m2:
        return f"SNI {m2.group(1)}"
    return ""


def parse_judul(blocks: list[dict], text: str, filename: str) -> str:
    """
    Ekstrak judul dokumen SNI.
    Pada PDF berformat standar BSN, judul biasanya:
      - Di area TENGAH halaman pertama (20%–75% tinggi)
      - Huruf besar semua atau Title Case
      - Bukan nomor SNI, bukan "Standar Nasional Indonesia"
      - Lebih dari 3 kata
    """
    SKIP_PATTERNS = [
        r'^SNI\b', r'^Standar\s+Nasional', r'^Badan\s+Standar',
        r'^ICS\b', r'^Ditetapkan', r'^Hak\s+cipta', r'^©',
        r'^\d+[\.\)]\s', r'^BSN\b',
    ]

    if blocks:
        cover = [b for b in blocks if b["page"] == 0]
        if cover:
            pw = cover[0]["pw"]
            ph = cover[0]["ph"]
            # Zona tengah halaman cover
            mid_blocks = [
                b for b in cover
                if ph * 0.18 < b["y0"] < ph * 0.80
                and b["x0"] < pw * 0.85   # bukan pojok kanan (area nomor SNI)
            ]
            # Filter blok yang tidak masuk pola skip
            candidates = []
            for b in mid_blocks:
                lines = [l.strip() for l in b["text"].splitlines() if l.strip()]
                for ln in lines:
                    if len(ln) < 8 or len(ln) > 150:
                        continue
                    skip = any(re.match(p, ln, re.IGNORECASE) for p in SKIP_PATTERNS)
                    if skip:
                        continue
                    wc = len(ln.split())
                    if wc < 3:
                        continue
                    # Nilai skor: panjang teks + bonus judul besar
                    score = len(ln)
                    if ln.isupper():
                        score += 30
                    elif ln.istitle():
                        score += 15
                    candidates.append((score, ln))

            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]

    # Fallback: dari teks biasa
    lines = [l.strip() for l in text[:3000].splitlines() if l.strip()]
    candidates = []
    for ln in lines:
        if len(ln) < 8 or len(ln) > 150:
            continue
        skip = any(re.match(p, ln, re.IGNORECASE) for p in SKIP_PATTERNS)
        if skip:
            continue
        wc = len(ln.split())
        if 3 <= wc <= 20:
            score = len(ln) + (20 if ln.isupper() else 10 if ln.istitle() else 0)
            candidates.append((score, ln))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    return Path(filename).stem.replace('_', ' ').replace('-', ' ').title()


def parse_kategori(text: str) -> str:
    text_low = text[:5000].lower()
    for keywords, cat in CATEGORY_RULES:
        for kw in keywords:
            if kw in text_low:
                return cat
    return "Lainnya"


def _find_section(text: str, headers: list[str], next_headers: list[str],
                  max_chars: int = 4000) -> str:
    """Ekstrak teks antara header section dan section berikutnya."""
    text_low = text.lower()
    start    = -1

    for h in headers:
        # Coba cocokkan sebagai baris tersendiri
        pattern = re.compile(
            r'(?:^|\n)\s*' + re.escape(h.lower()) + r'\s*\n',
            re.IGNORECASE
        )
        m = pattern.search(text_low)
        if m:
            start = m.end()
            break
        # Fallback: substring biasa
        idx = text_low.find(h.lower())
        if idx != -1:
            nl = text.find('\n', idx)
            start = nl + 1 if nl != -1 else idx + len(h)
            break

    if start == -1:
        return ""

    end = min(len(text), start + max_chars)
    for nh in next_headers:
        pattern = re.compile(r'(?:^|\n)\s*' + re.escape(nh.lower()), re.IGNORECASE)
        m = pattern.search(text_low[start:start + max_chars])
        if m:
            candidate = start + m.start()
            if candidate < end:
                end = candidate

    return text[start:end].strip()


def parse_ruang_lingkup(text: str) -> str:
    SCOPE_HEADERS = [
        "1 ruang lingkup", "1. ruang lingkup", "ruang lingkup",
        "1  ruang lingkup", "scope", "1 scope",
    ]
    NEXT = [
        "2 acuan normatif", "2. acuan normatif", "acuan normatif",
        "2 istilah", "istilah dan definisi", "istilah",
        "2 ketentuan", "persyaratan", "syarat mutu",
        "2.", "3.",
    ]
    section = _find_section(text, SCOPE_HEADERS, NEXT, max_chars=1500)
    if not section:
        return ""

    # Bersihkan artefak: header pasal, nomor baris pendek
    lines = []
    for ln in section.splitlines():
        ln = ln.strip()
        if not ln or re.match(r'^\d{1,2}$', ln):
            continue
        lines.append(ln)

    merged = " ".join(lines)
    # Ambil hingga MAX_SCOPE_CHARS, potong di akhir kalimat
    if len(merged) > MAX_SCOPE_CHARS:
        cut = merged[:MAX_SCOPE_CHARS]
        last_dot = cut.rfind('.')
        if last_dot > MAX_SCOPE_CHARS // 2:
            cut = cut[:last_dot + 1]
        merged = cut
    return merged.strip()


def parse_persyaratan(text: str) -> str:
    """Ekstrak parameter mutu + nilai + satuan."""
    SYARAT_HEADERS = [
        "syarat mutu", "persyaratan mutu", "persyaratan teknis",
        "ketentuan mutu", "karakteristik mutu", "spesifikasi teknis",
        "karakteristik", "persyaratan", "requirements",
        "4 persyaratan", "5 persyaratan",
        "4. persyaratan", "5. persyaratan",
    ]
    NEXT = [
        "metode uji", "cara uji", "pengujian", "metoda uji",
        "pengambilan contoh", "pengambilan sampel",
        "penandaan", "pengemasan",
    ]
    section = _find_section(text, SYARAT_HEADERS, NEXT, max_chars=6000)
    if not section:
        section = text  # fallback: scan seluruh teks

    entries = []
    seen    = set()

    for pattern in PARAM_PATTERNS:
        for m in re.finditer(pattern, section, re.IGNORECASE):
            param  = m.group(1).strip().rstrip(':=').strip()
            value  = m.group(2).strip()
            unit   = (m.group(3) or "").strip()

            if len(param) < 3 or len(param) > 60:
                continue
            if re.match(r'^[\d\s]+$', param):
                continue
            # Buang baris kosong/header
            if re.match(r'^(?:no|nama|parameter|uji|syarat|nilai|satuan)\s*$', param, re.IGNORECASE):
                continue

            key = f"{param.lower()}={value}"
            if key in seen:
                continue
            seen.add(key)

            ctx = section[max(0, m.start() - 80):m.start() + 80].lower()
            qual = "maks" if any(w in ctx for w in ["maks", "maksimum", "tidak lebih", "≤", "<"]) else \
                   "min"  if any(w in ctx for w in ["min", "minimum", "tidak kurang", "≥", ">"]) else ""

            unit_str = f" {unit}" if unit else ""
            qual_str = f" ({qual})" if qual else ""
            entries.append(f"{param} = {value}{unit_str}{qual_str}")

        if entries:
            break

    if not entries:
        return "-"

    return " | ".join(entries[:20])


def parse_metode_uji(text: str) -> str:
    """Ekstrak referensi SNI/ISO dari bagian metode uji."""
    METODE_HEADERS = [
        "metode uji", "cara uji", "metoda uji",
        "pengujian", "prosedur uji",
        "metode pengujian",
    ]
    NEXT = [
        "pengambilan contoh", "pengambilan sampel",
        "pengemasan", "penandaan", "syarat lulus uji",
        "lampiran",
    ]
    section = _find_section(text, METODE_HEADERS, NEXT, max_chars=5000)
    if not section:
        section = text

    entries   = []
    seen_refs = set()

    # Kumpulkan semua SNI & ISO refs
    for pattern, prefix in [(SNI_REF_PATTERN, "SNI"), (ISO_REF_PATTERN, "ISO")]:
        for m in pattern.finditer(section):
            code = m.group(1).strip()
            ref  = f"{prefix} {code}"
            if ref in seen_refs:
                continue
            seen_refs.add(ref)

            # Coba tangkap nama parameter sebelum referensi
            ctx_before = section[max(0, m.start() - 120):m.start()]
            pm = re.search(r'([A-Za-z\u00C0-\u024F][A-Za-z0-9\s\(\)]{3,40})\s*$', ctx_before)
            param = pm.group(1).strip() if pm else ""

            # Nama metode setelah kode
            ctx_after = section[m.end():m.end() + 100]
            mm = re.search(r'[:\-–]\s*([A-Za-z][^\n]{4,60})', ctx_after)
            method = mm.group(1).strip()[:50] if mm else ""

            entry = f"{param + ' = ' if param else ''}{ref}"
            if method:
                entry += f" – {method}"
            entries.append(entry)

    if not entries:
        return "-"
    return " | ".join(entries[:15])


def build_keywords(record: SNIRecord, text: str) -> str:
    """Bangun string keywords dari judul, parameter, dan referensi SNI."""
    words = []
    stop  = {
        "standar","nasional","indonesia","dan","atau","untuk","dari","dengan",
        "yang","dalam","sni","iso","iec","the","of","for","and","or","to",
        "ini","adalah","pada","ke","di","se","per","bagi","antara",
    }
    for w in record.judul.split():
        if w.lower() not in stop and len(w) > 2:
            words.append(w)

    # Angka + satuan dari persyaratan
    for m in re.finditer(r'[\d,\.]+\s*[a-zA-Z/%µ°]+', record.persyaratan):
        words.append(m.group().strip())

    # Referensi SNI dalam teks
    for m in SNI_REF_PATTERN.finditer(text[:8000]):
        ref = f"SNI-{m.group(1)}"
        if ref not in words:
            words.append(ref)

    # Deduplikasi
    seen   = set()
    result = []
    for w in words:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            result.append(w)
    return " ".join(result[:MAX_KW_WORDS])


# ─── Main extraction entry point ──────────────────────────────────────────────

def process_file(file_bytes: bytes, filename: str) -> dict:
    """
    Proses satu file (bytes) → return dict siap CSV.
    """
    import tempfile, os
    suffix = Path(filename).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    blocks: list[dict] = []
    text:   str        = ""
    pages:  int        = 0

    try:
        if suffix == ".pdf":
            blocks, pages = extract_pdf_with_layout(tmp_path)
            # Buat plain text dari blocks
            if blocks:
                text = "\n".join(b["text"] for b in sorted(blocks, key=lambda b: (b["page"], b["y0"])))
            if not text.strip():
                text, pages = extract_pdf_plain(tmp_path)
        elif suffix in (".docx", ".doc"):
            text, pages = extract_docx(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not text.strip():
        return {
            "_error": f"teks kosong: {filename}",
            "no_sni": Path(filename).stem, "judul": "", "kategori": "Lainnya",
            "ruang_lingkup": "", "persyaratan": "-", "metode_uji": "-",
            "halaman": 0, "keywords": "",
        }

    rec = SNIRecord()

    # ── no_sni: pojok kanan atas halaman pertama
    if blocks:
        rec.no_sni = parse_no_sni_from_blocks(blocks)
    if not rec.no_sni:
        rec.no_sni = parse_no_sni_from_text(text, filename)

    # ── judul
    rec.judul        = parse_judul(blocks, text, filename)

    # ── kategori
    rec.kategori     = parse_kategori(text)

    # ── ruang lingkup
    rec.ruang_lingkup = parse_ruang_lingkup(text)

    # ── persyaratan
    rec.persyaratan  = parse_persyaratan(text)

    # ── metode uji
    rec.metode_uji   = parse_metode_uji(text)

    # ── halaman
    rec.halaman      = pages

    # ── keywords
    rec.keywords     = build_keywords(rec, text)

    d = rec.to_dict()
    d["_source"] = filename
    return d
