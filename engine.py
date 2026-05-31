"""
engine.py — SNI Core Extraction Engine (Improved v2)
PDF/Word → accurate heuristic extraction → record matching sni_core.csv schema

Kolom output (sesuai sni_core.csv):
  no_sni        : Nomor SNI lengkap, mis. "SNI ISO/IEC 27007:2017"
  judul         : Judul dokumen SNI dalam bahasa Indonesia
  kategori      : Kategori bidang SNI (dari keyword mapping + ICS code)
  ruang_lingkup : Isi seksi Scope / Ruang Lingkup (teks asli, maks ~600 char)
  persyaratan   : Isi persyaratan/syarat mutu ("-" jika tidak ada)
  metode_uji    : Referensi metode uji ("-" jika tidak ada)
  keywords      : Kata kunci utama dari judul + topik dokumen

Strategi ekstraksi:
  1. Ekstrak teks PDF (PyMuPDF) atau DOCX (python-docx)
  2. Parse no_sni dari halaman cover (baris "SNI ..." awal dokumen)
  3. Judul: baris judul bahasa Indonesia dari cover (bukan bahasa Inggris)
  4. Kategori: ICS code → mapping kategori; fallback keyword matching
  5. Ruang lingkup: ekstrak seksi "Scope" / "Ruang Lingkup" / "1 Scope"
  6. Persyaratan: ekstrak seksi syarat mutu/requirements (untuk SNI produk)
  7. Metode uji: ekstrak referensi metode pengujian (untuk SNI produk)
  8. Keywords: dari judul + topik utama dokumen
"""

import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict

log = logging.getLogger("sni_engine")

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_SCOPE_CHARS = 600   # Ruang lingkup full, bukan potong 150

# ICS code → kategori (prioritas pertama, paling akurat)
ICS_KATEGORI: dict[str, str] = {
    "67": "pangan",
    "71": "kimia",
    "91": "konstruksi",
    "29": "elektro",
    "27": "elektro",
    "23": "mekanik",
    "25": "mekanik",
    "59": "tekstil",
    "65": "pertanian",
    "13": "lingkungan",
    "11": "kesehatan",
    "35": "teknologi informasi",
    "43": "transportasi",
    "45": "transportasi",
    "03": "manajemen",
    "01": "umum",
    "07": "sains",
    "17": "metrologi",
    "19": "pengujian",
    "21": "sistem mekanik",
    "31": "elektronik",
    "33": "telekomunikasi",
    "37": "optik",
    "39": "presisi",
    "41": "tekstil",
    "47": "perkapalan",
    "49": "penerbangan",
    "53": "material handling",
    "55": "kemasan",
    "57": "kertas",
    "61": "industri tekstil",
    "75": "minyak bumi",
    "77": "metalurgi",
    "79": "kayu",
    "81": "keramik",
    "83": "karet",
    "85": "kertas cetak",
    "87": "cat dan pelapis",
    "93": "sipil",
    "95": "pertahanan",
    "97": "rumah tangga",
}

# Keyword matching sebagai fallback
CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["pangan", "makanan", "minuman", "gula", "garam", "minyak", "susu",
      "daging", "ikan", "beras", "tepung", "kopi", "teh", "cokelat", "bumbu",
      "saos", "kecap", "mie", "roti", "biskuit", "snack", "keju", "mentega",
      "margarin", "es krim", "sirup", "jus", "sari buah", "halal", "pakan"], "pangan"),
    (["kimia", "bahan kimia", "pestisida", "pupuk", "cat", "pelarut", "asam",
      "basa", "reagen", "deterjen", "sabun", "kosmetik", "parfum", "pigmen",
      "adhesif", "lem", "polimer", "plastik", "resin"], "kimia"),
    (["konstruksi", "bangunan", "beton", "semen", "baja", "besi", "kayu",
      "cat tembok", "keramik", "genteng", "bata", "pondasi", "aspal",
      "agregat", "mortar", "panel", "plat", "pipa konstruksi", "struktur"], "konstruksi"),
    (["elektro", "listrik", "elektronik", "kabel", "transformator", "motor",
      "generator", "baterai", "saklar", "stop kontak", "lampu", "led",
      "solar", "panel surya", "inverter", "ups", "charger", "tegangan"], "elektro"),
    (["mekanik", "mesin", "pompa", "kompresor", "turbin", "roda gigi",
      "bearing", "piston", "silinder", "katup", "flanges", "baut", "mur",
      "valve", "pressure"], "mekanik"),
    (["tekstil", "kain", "benang", "serat", "rajut", "tenun", "pakaian",
      "garmen", "karpet", "nonwoven"], "tekstil"),
    (["pertanian", "agro", "bibit", "benih", "tanah", "irigasi", "traktor",
      "hortikultura", "perkebunan", "kehutanan", "perikanan"], "pertanian"),
    (["lingkungan", "air bersih", "air minum", "air limbah", "udara", "emisi",
      "polutan", "baku mutu lingkungan", "amdal", "limbah", "pencemaran"], "lingkungan"),
    (["kesehatan", "medis", "alat kesehatan", "farmasi", "obat", "sterilisasi",
      "masker", "sarung tangan medis", "jarum", "syringe", "laboratorium klinik",
      "diagnostik"], "kesehatan"),
    (["informatika", "teknologi informasi", "perangkat lunak", "software",
      "hardware", "jaringan", "keamanan informasi", "keamanan siber",
      "enkripsi", "iso 27", "isms", "iec 27", "manajemen keamanan"], "teknologi informasi"),
    (["transportasi", "kendaraan", "otomotif", "sepeda motor", "ban", "helm",
      "sabuk pengaman", "kapal", "pesawat", "kereta", "automotive"], "transportasi"),
    (["manajemen", "sistem manajemen", "audit", "sertifikasi", "akreditasi",
      "mutu", "kualitas", "iso 9", "iso 14", "iso 45", "ohsas"], "manajemen"),
]

# Pattern SNI number
# Contoh: SNI ISO/IEC 27007:2017, SNI 01-3141-1998, SNI 3564:2009
SNI_FULL_PATTERN = re.compile(
    r'SNI\s+(?:ISO(?:/IEC)?(?:\s*/\s*IEC)?\s+[\d]+(?:[:/]\w+)*(?::\d{4})?'
    r'|IEC\s+[\d]+(?:[:/]\w+)*(?::\d{4})?'
    r'|\d{2}[\-\.]\d{3,5}[\-\.]\d{4}'
    r'|\d{4,6}(?:[\-:]\d+)*(?::\d{4})?)',
    re.IGNORECASE
)

# Pattern angka:tahun untuk versi/tahun dokumen
YEAR_PATTERN = re.compile(r':(\d{4})\b')

# Pattern ICS code di cover
ICS_PATTERN = re.compile(r'\bICS\s+(\d{2})\.(\d{3})', re.IGNORECASE)

# Referensi SNI lain dalam teks (untuk metode_uji)
SNI_REF_IN_TEXT = re.compile(
    r'SNI\s+(?:ISO(?:/IEC)?\s+)?(\d[\d\s\-\.:\/A-Z]+(?::\d{4})?)',
    re.IGNORECASE
)

# ─── Data model ───────────────────────────────────────────────────────────────
@dataclass
class SNIRecord:
    no_sni:        str = ""
    judul:         str = ""
    kategori:      str = ""
    ruang_lingkup: str = ""
    persyaratan:   str = "-"
    metode_uji:    str = "-"
    keywords:      str = ""

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ─── Text extraction ──────────────────────────────────────────────────────────
def extract_pdf(path: Path) -> tuple[str, str]:
    """
    Ekstrak teks PDF dengan PyMuPDF.
    Return: (full_text, cover_text)
    cover_text = halaman 1 saja untuk parsing no_sni & judul
    """
    try:
        import fitz
        doc = fitz.open(str(path))
        pages = []
        total = 0
        for i, page in enumerate(doc):
            t = page.get_text("text")
            pages.append(t)
            total += len(t)
            if total > 60_000:
                break
        doc.close()
        cover = pages[0] if pages else ""
        full  = "\n".join(pages)
        return full, cover
    except Exception as e:
        log.debug(f"PyMuPDF failed {path.name}: {e}, trying fallback")
        return _extract_pdf_fallback(path)


def _extract_pdf_fallback(path: Path) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        pages = []
        for page in r.pages[:60]:
            pages.append(page.extract_text() or "")
        cover = pages[0] if pages else ""
        return "\n".join(pages), cover
    except Exception as e:
        log.warning(f"PDF fallback failed {path.name}: {e}")
        return "", ""


def extract_docx(path: Path) -> tuple[str, str]:
    try:
        from docx import Document
        doc = Document(str(path))
        parts = []
        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_cells:
                    parts.append(" | ".join(row_cells))
        full  = "\n".join(parts)
        cover = "\n".join(parts[:40])  # ~40 paragraf pertama sebagai cover
        return full, cover
    except Exception as e:
        log.warning(f"DOCX failed {path.name}: {e}")
        return "", ""


def extract_text(path: Path) -> tuple[str, str]:
    """Return (full_text, cover_text)"""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext in (".docx", ".doc"):
        return extract_docx(path)
    return "", ""


# ─── Parser: no_sni ───────────────────────────────────────────────────────────
def parse_no_sni(cover: str, full: str, filename: str) -> str:
    """
    Ekstrak nomor SNI lengkap dari cover halaman.
    
    Pola yang dicari (prioritas):
      1. "SNI ISO/IEC XXXXX:YYYY" - standar internasional diadopsi
      2. "SNI ISO XXXXX:YYYY"
      3. "SNI XXXX:YYYY" atau "SNI XX-XXXX-YYYY"
    
    Juga tangkap tahun penetapan BSN dari "(Ditetapkan oleh BSN tahun YYYY)"
    untuk memastikan formatnya benar.
    """
    # Cari di 15 baris pertama cover (biasanya ada di halaman 1)
    cover_lines = [l.strip() for l in cover.splitlines() if l.strip()]
    
    # Scan baris-baris cover untuk menemukan nomor SNI
    for line in cover_lines[:30]:
        # Skip baris ICS
        if line.startswith("ICS"):
            continue
        # Cari pola "SNI ..." di baris
        m = SNI_FULL_PATTERN.match(line)
        if m:
            no = m.group(0).strip()
            # Normalisasi spasi
            no = re.sub(r'\s+', ' ', no)
            return no
        # Cari pola di dalam baris (misal ada teks lain di depan)
        m = SNI_FULL_PATTERN.search(line)
        if m and len(line) < 60:  # Baris pendek = kemungkinan baris nomor SNI
            no = m.group(0).strip()
            no = re.sub(r'\s+', ' ', no)
            return no

    # Fallback: cari di 200 karakter pertama full text
    head = full[:500]
    m = SNI_FULL_PATTERN.search(head)
    if m:
        no = m.group(0).strip()
        return re.sub(r'\s+', ' ', no)

    # Fallback: dari filename
    # Mis: SNI_ISO-IEC_27007_2017.pdf → SNI ISO/IEC 27007:2017
    fname = Path(filename).stem
    fname_clean = fname.replace('_', ' ').replace('-', ' ')
    # Cari pola XX-XXXX-YYYY di filename
    m2 = re.search(r'(\d{2})\s+(\d{3,5})\s+(\d{4})', fname_clean)
    if m2:
        return f"SNI {m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    # Cari ISO IEC di filename
    m3 = re.search(r'(ISO[\s\-/]*(?:IEC[\s\-/]*)?\s*\d+[\s\-:]*\d{0,4})', fname_clean, re.IGNORECASE)
    if m3:
        iso_part = re.sub(r'\s+', ' ', m3.group(1).strip())
        return f"SNI {iso_part}"

    return ""


# ─── Parser: judul ────────────────────────────────────────────────────────────
def _join_wrapped_lines(lines: list[str]) -> list[str]:
    """Gabungkan baris lanjutan (PDF sering wrap judul panjang ke baris berikutnya).
    
    Aturan penggabungan:
    - Baris dimulai huruf kecil → lanjutan dari baris sebelumnya
    - Baris sebelumnya pendek (<65 char) dan tidak diakhiri tanda baca → lanjutan
    - TIDAK gabungkan jika: baris dimulai "(", angka, atau huruf kapital semua
    """
    result = []
    for line in lines:
        if not line:
            result.append("")
            continue
        if result and result[-1]:
            prev = result[-1]
            # Jangan gabungkan jika baris baru dimulai dengan karakter khusus
            starts_paren   = line[0] == "("
            starts_digit   = line[0].isdigit()
            starts_special = line[0] in "©@#"
            starts_lower   = line[0].islower()
            prev_short     = len(prev) < 65 and prev[-1] not in ".!?:;"
            # Hanya gabungkan jika dimulai huruf kecil ATAU baris sblm pendek
            # dan tidak ada kondisi pengecualian
            if (starts_lower or prev_short) and not (starts_paren or starts_digit or starts_special):
                result[-1] = prev + " " + line
                continue
        result.append(line)
    return result


def parse_judul(cover: str, full: str, filename: str) -> str:
    """
    Ekstrak judul dokumen SNI (bahasa Indonesia).
    Menggabungkan baris lanjutan akibat PDF line-wrap.
    """
    raw_lines = [l.strip() for l in cover.splitlines() if l.strip()]
    cover_lines = _join_wrapped_lines(raw_lines)
    
    # Temukan posisi nomor SNI di cover_lines
    sni_line_idx = -1
    for i, line in enumerate(cover_lines[:20]):
        if SNI_FULL_PATTERN.match(line) or (
            re.search(r'^SNI\s+', line, re.IGNORECASE) and len(line) < 60
        ):
            sni_line_idx = i
            break

    # Kumpulkan kandidat judul:
    # - Baris setelah nomor SNI
    # - Baris yang bukan nomor/copyright/ICS
    # - Bukan dalam bahasa Inggris murni (jika ada bahasa Indonesia)
    candidates = []
    
    # Baris setelah nomor SNI hingga batas cover
    search_start = max(0, sni_line_idx + 1) if sni_line_idx >= 0 else 0
    
    for line in cover_lines[search_start:search_start + 15]:
        # Skip baris tidak relevan
        if not line or len(line) < 8:
            continue
        if line.startswith("ICS"):
            continue
        if re.match(r'^©', line):
            continue
        if re.match(r'^\(', line) and 'IDT' in line:
            continue  # Skip "(ISO/IEC ..., IDT, Eng)"
        if re.match(r'^Badan Standardisasi', line, re.IGNORECASE):
            continue
        if re.match(r'^Standar Nasional', line, re.IGNORECASE):
            continue
        if re.match(r'^\(Ditetapkan', line, re.IGNORECASE):
            continue
        if re.match(r'^\(ISO', line, re.IGNORECASE):
            continue  # Skip "(ISO/IEC ..., IDT, Eng)"
        if re.match(r'^\(IEC', line, re.IGNORECASE):
            continue
        # Skip jika ini nomor SNI itu sendiri
        if SNI_FULL_PATTERN.match(line):
            continue
        # Harus ada huruf, bukan hanya angka
        if not re.search(r'[a-zA-Z]{3,}', line):
            continue
        # Panjang wajar untuk judul
        if 8 <= len(line) <= 200:
            candidates.append(line)

    if not candidates:
        # Fallback: semua baris non-trivial di cover
        for line in cover_lines[:25]:
            if (8 <= len(line) <= 200 and
                re.search(r'[a-zA-Z]{3,}', line) and
                not line.startswith("ICS") and
                not line.startswith("©") and
                not SNI_FULL_PATTERN.match(line)):
                candidates.append(line)

    if not candidates:
        # Fallback akhir: dari filename
        return Path(filename).stem.replace('_', ' ').replace('-', ' ').title()

    # Pilih judul terbaik:
    # Prioritaskan bahasa Indonesia (ada kata khas Indonesia)
    id_keywords = re.compile(
        r'\b(dan|atau|untuk|dari|dengan|yang|dalam|tentang|teknik|pedoman|'
        r'persyaratan|spesifikasi|metode|cara|sistem|manajemen|pengujian|'
        r'informasi|keamanan|teknologi|standar|nasional|prinsip|panduan)\b',
        re.IGNORECASE
    )
    
    # Gabungkan baris yang bisa jadi judul multi-baris (jika pendek-pendek)
    # Mis: "Teknologi informasi - Teknik keamanan - Pedoman\naudit sistem..."
    judul_lines = []
    for c in candidates[:6]:
        if id_keywords.search(c):
            judul_lines.append(c)
        elif not judul_lines and re.search(r'[A-Z]', c):
            # Ambil juga jika belum ada kandidat bahasa Indonesia
            judul_lines.append(c)

    if not judul_lines:
        judul_lines = candidates[:2]

    # Gabungkan baris-baris yang merupakan sambungan judul
    # Deteksi baris lanjutan: baris yang tidak dimulai huruf kapital besar
    # dan tidak ada tanda pemisah topik di baris sebelumnya
    result = []
    for i, line in enumerate(judul_lines[:4]):
        if i == 0:
            result.append(line)
        else:
            # Gabungkan jika baris sebelumnya terlihat belum selesai
            # (tidak diakhiri tanda baca, atau dimulai huruf kecil)
            prev = result[-1] if result else ""
            starts_lower = line and line[0].islower()
            prev_incomplete = prev and not prev.endswith(('.', '!', '?', '"'))
            if starts_lower or prev_incomplete:
                result[-1] = result[-1].rstrip() + " " + line
            else:
                result.append(line)
            # Hentikan jika sudah cukup panjang
            if len(" ".join(result)) > 50:
                break

    judul = " ".join(result).strip()
    # Bersihkan prefix "(Ditetapkan...)" atau "(ISO/IEC...)" yang terbawa
    judul = re.sub(r'^\([^)]{0,60}\)\s*', '', judul).strip()
    # Bersihkan suffix "(ISO/IEC...)"
    judul = re.sub(r'\s*\(ISO[^)]*\)\s*$', '', judul, flags=re.IGNORECASE).strip()
    judul = re.sub(r'\s+', ' ', judul)

    return judul if judul else candidates[0]


# ─── Parser: kategori ─────────────────────────────────────────────────────────
def parse_kategori(cover: str, full: str) -> str:
    """
    Kategori dari ICS code (paling akurat) lalu fallback keyword.
    ICS code contoh: "ICS 35.030" → prefix "35" → Informatika
    """
    # Cari ICS code di cover
    m = ICS_PATTERN.search(cover)
    if m:
        ics_prefix = m.group(1)
        if ics_prefix in ICS_KATEGORI:
            return ICS_KATEGORI[ics_prefix]

    # Fallback: keyword matching di 3000 char pertama
    text_low = (cover + "\n" + full[:2000]).lower()
    for keywords, cat in CATEGORY_RULES:
        for kw in keywords:
            if kw in text_low:
                return cat

    return "umum"


# ─── Utility: find section ────────────────────────────────────────────────────
def _find_section_text(text: str, start_patterns: list[str],
                       end_patterns: list[str], max_chars: int = 2000) -> str:
    """
    Cari teks antara header section dan header section berikutnya.
    start_patterns: list regex pattern untuk header mulai
    end_patterns: list regex pattern untuk header akhir
    """
    text_lines = text.splitlines()
    start_idx = -1
    
    for pat in start_patterns:
        for i, line in enumerate(text_lines):
            if re.search(pat, line, re.IGNORECASE):
                start_idx = i + 1
                break
        if start_idx >= 0:
            break

    if start_idx < 0:
        return ""

    # Cari akhir section
    end_idx = len(text_lines)
    for pat in end_patterns:
        for i, line in enumerate(text_lines[start_idx:], start=start_idx):
            if re.search(pat, line, re.IGNORECASE):
                end_idx = i
                break
        if end_idx < len(text_lines):
            break

    section_lines = text_lines[start_idx:end_idx]
    section_text = "\n".join(section_lines).strip()
    return section_text[:max_chars]


# ─── Parser: ruang_lingkup ────────────────────────────────────────────────────
def parse_ruang_lingkup(full: str) -> str:
    """
    Ekstrak isi Scope / Ruang Lingkup.
    
    Untuk SNI adopsi internasional (bahasa Inggris): ambil teks aslinya.
    Untuk SNI lokal (bahasa Indonesia): ambil teks bahasa Indonesia.
    
    Cari seksi:
    - "1 Scope" / "1. Scope" / "Scope"
    - "Ruang lingkup" / "1 Ruang lingkup"
    """
    SCOPE_START = [
        r'^\s*1[\.\s]+\s*Scope\s*$',
        r'^\s*1[\.\s]+\s*Ruang\s+lingkup\s*$',
        r'^\s*Scope\s*$',
        r'^\s*Ruang\s+lingkup\s*$',
        r'^\s*1\s+Scope',
        r'^\s*1\s+Ruang',
    ]
    SCOPE_END = [
        r'^\s*2[\.\s]',
        r'^\s*Normative',
        r'^\s*Acuan\s+normatif',
        r'^\s*Terms\s+and\s+definitions',
        r'^\s*Istilah\s+dan\s+definisi',
    ]

    section = _find_section_text(full, SCOPE_START, SCOPE_END, max_chars=MAX_SCOPE_CHARS)
    
    if not section:
        return ""
    
    # Bersihkan: hapus header halaman, copyright, baris kosong berlebih
    lines = []
    for line in section.splitlines():
        line = line.strip()
        if not line:
            if lines and lines[-1]:  # Satu baris kosong saja
                lines.append("")
            continue
        # Skip header halaman (mis: "SNI ISO/IEC 27007:2017")
        if SNI_FULL_PATTERN.match(line):
            continue
        # Skip "© BSN XXXX"
        if re.match(r'^©', line):
            continue
        # Skip baris nomor halaman "1 dari 43"
        if re.match(r'^\d+\s+dari\s+\d+$', line, re.IGNORECASE):
            continue
        lines.append(line)
    
    # Gabungkan dan bersihkan spasi berlebih
    result = re.sub(r'\n{3,}', '\n\n', "\n".join(lines)).strip()
    return result[:MAX_SCOPE_CHARS]


# ─── Parser: persyaratan ──────────────────────────────────────────────────────
def parse_persyaratan(full: str) -> str:
    """
    Ekstrak persyaratan mutu / syarat teknis.
    
    Relevan untuk SNI produk (pangan, kimia, dll).
    Untuk SNI sistem manajemen / panduan, biasanya kosong ("-").
    
    Cari seksi:
    - "Syarat mutu" / "Persyaratan mutu" / "Persyaratan teknis"
    - "Requirements" / "Karakteristik"
    
    Kembalikan teks persyaratan (bukan hanya parameter),
    atau "-" jika tidak ada.
    """
    SYARAT_START = [
        r'^\s*\d+[\.\s]+\s*Syarat\s+mutu',
        r'^\s*\d+[\.\s]+\s*Persyaratan\s+mutu',
        r'^\s*\d+[\.\s]+\s*Persyaratan\s+teknis',
        r'^\s*\d+[\.\s]+\s*Ketentuan\s+mutu',
        r'^\s*\d+[\.\s]+\s*Karakteristik',
        r'^\s*\d+[\.\s]+\s*Spesifikasi\s+teknis',
        r'^\s*\d+[\.\s]+\s*Requirements',
        r'^\s*Syarat\s+mutu',
        r'^\s*Persyaratan\s+mutu',
    ]
    SYARAT_END = [
        r'^\s*\d+[\.\s]+\s*Metode\s+uji',
        r'^\s*\d+[\.\s]+\s*Cara\s+uji',
        r'^\s*\d+[\.\s]+\s*Pengujian',
        r'^\s*\d+[\.\s]+\s*Pengambilan\s+contoh',
        r'^\s*\d+[\.\s]+\s*Pengemasan',
        r'^\s*\d+[\.\s]+\s*Penandaan',
        r'^\s*\d+[\.\s]+\s*Marking',
        r'^\s*\d+[\.\s]+\s*Sampling',
    ]

    section = _find_section_text(full, SYARAT_START, SYARAT_END, max_chars=800)

    if not section or len(section.strip()) < 10:
        return "-"

    # Bersihkan teks
    lines = []
    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        if SNI_FULL_PATTERN.match(line):
            continue
        if re.match(r'^©', line):
            continue
        if re.match(r'^\d+\s+dari\s+\d+$', line, re.IGNORECASE):
            continue
        lines.append(line)

    result = " ".join(lines).strip()
    result = re.sub(r'\s+', ' ', result)
    return result[:600] if result else "-"


# ─── Parser: metode_uji ───────────────────────────────────────────────────────
def parse_metode_uji(full: str) -> str:
    """
    Ekstrak referensi metode uji.
    
    Untuk SNI produk: cari seksi "Metode uji" / "Cara uji"
    dan referensi SNI yang dikutip di sana.
    
    Untuk SNI sistem manajemen / panduan: biasanya "-".
    """
    METODE_START = [
        r'^\s*\d+[\.\s]+\s*Metode\s+uji',
        r'^\s*\d+[\.\s]+\s*Cara\s+uji',
        r'^\s*\d+[\.\s]+\s*Metoda\s+uji',
        r'^\s*\d+[\.\s]+\s*Pengujian',
        r'^\s*\d+[\.\s]+\s*Test\s+methods',
        r'^\s*Metode\s+uji',
        r'^\s*Cara\s+uji',
    ]
    METODE_END = [
        r'^\s*\d+[\.\s]+\s*Pengambilan\s+contoh',
        r'^\s*\d+[\.\s]+\s*Pengemasan',
        r'^\s*\d+[\.\s]+\s*Penandaan',
        r'^\s*\d+[\.\s]+\s*Sampling',
        r'^\s*\d+[\.\s]+\s*Marking',
        r'^\s*Lampiran',
        r'^\s*Annex',
        r'^\s*Bibliography',
        r'^\s*Bibliografi',
    ]

    section = _find_section_text(full, METODE_START, METODE_END, max_chars=800)

    if not section or len(section.strip()) < 10:
        return "-"

    # Bersihkan teks
    lines = []
    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        if SNI_FULL_PATTERN.match(line):
            continue
        if re.match(r'^©', line):
            continue
        if re.match(r'^\d+\s+dari\s+\d+$', line, re.IGNORECASE):
            continue
        lines.append(line)

    result = " ".join(lines).strip()
    result = re.sub(r'\s+', ' ', result)
    return result[:500] if result else "-"


# ─── Parser: keywords ─────────────────────────────────────────────────────────
def parse_keywords(judul: str, kategori: str, ruang_lingkup: str,
                   no_sni: str) -> str:
    """
    Bangun string keywords yang ringkas dan akurat dari judul dokumen SNI.
    
    Strategi: ambil frasa inti dari tiap segmen judul (setelah " - "),
    hilangkan kata generik di awal, ambil yang paling spesifik.
    
    Format target: "audit, sistem manajemen keamanan informasi"
    """
    GENERIC_PREFIX = re.compile(
        r'^(?:pedoman|panduan|teknik|teknologi|cara|metode|spesifikasi|'
        r'persyaratan|prinsip|sistem|pengantar|petunjuk|petunjuk teknis|'
        r'informasi tentang|guidelines for|guidance on|requirements for|'
        r'code of practice for)\s+',
        re.IGNORECASE
    )
    STOP_WORDS = {
        "standar", "nasional", "indonesia", "dan", "atau", "untuk", "dari",
        "dengan", "yang", "dalam", "sni", "iso", "iec", "bsn", "ini",
        "adalah", "pada", "juga", "oleh", "ke", "di", "the", "of", "and",
        "or", "for", "in", "a", "an", "to", "with", "its", "this",
        "document", "guidance", "general", "technical", "part",
        "ditetapkan", "tahun", "bagian", "edisi", "revisi", "adopsi",
    }

    kws: list[str] = []
    seen: set[str] = set()

    def add(w: str) -> None:
        w = re.sub(r'\s+', ' ', w.strip().lower())
        if w and w not in seen and len(w) > 2 and w not in STOP_WORDS:
            seen.add(w)
            kws.append(w)

    # Pecah judul per " - "
    parts = re.split(r'\s*[-–—]\s*', judul)

    for part in parts:
        part = part.strip()
        if len(part) < 4:
            continue
        # Hapus prefix generik untuk dapatkan inti
        core = GENERIC_PREFIX.sub('', part).strip()
        if core and core.lower() not in STOP_WORDS and len(core) > 3:
            add(core)

    # Jika keywords terlalu banyak, pertahankan hanya yang paling spesifik:
    # yaitu yang TIDAK generik (tidak diawali kata seperti "teknologi", "teknik", dll)
    GENERIC_STANDALONE = re.compile(
        r'^(teknologi informasi|teknik keamanan|teknik|teknologi|informasi|'
        r'keamanan|manajemen|sistem)$',
        re.IGNORECASE
    )
    # Filter: buang yang terlalu generik jika sudah ada yang lebih spesifik
    specific = [k for k in kws if not GENERIC_STANDALONE.match(k)]
    generic  = [k for k in kws if GENERIC_STANDALONE.match(k)]

    # Dari frasa panjang yang spesifik, juga ekstrak kata kunci pertama
    # Mis: "audit sistem manajemen keamanan informasi" → tambahkan "audit" saja
    extra: list[str] = []
    for phrase in specific:
        first_word = phrase.split()[0]
        if (first_word not in seen and len(first_word) > 3
                and not GENERIC_STANDALONE.match(first_word)):
            extra.append(first_word)

    # Susun: kata tunggal dulu (lebih ringkas), lalu frasa spesifik
    # Hapus frasa yang hanya menambahkan kata di depan frasa lain (duplikat)
    ordered: list[str] = []
    for w in extra:
        if w not in ordered:
            ordered.append(w)
    for k in specific:
        # Jangan tambahkan frasa yang diawali kata yang sudah ada di ordered
        first = k.split()[0]
        if first in ordered:
            # Simpan sisa frasa setelah kata pertama sebagai keyword baru
            rest = " ".join(k.split()[1:]).strip()
            if rest and rest not in ordered and len(rest) > 4:
                ordered.append(rest)
        else:
            if k not in ordered:
                ordered.append(k)

    # Prioritaskan yang spesifik, maksimal 3 keywords
    final = ordered[:3]
    # Tambah generic hanya jika kurang dari 2 keyword
    if len(final) < 2:
        final += [g for g in generic if g not in final][:2 - len(final)]

    return ", ".join(final)


# ─── Main extraction entry point ──────────────────────────────────────────────
def process_file(file_bytes: bytes, filename: str) -> dict:
    """
    Proses satu file (bytes) → kembalikan dict siap JSONL.
    
    Output keys: no_sni, judul, kategori, ruang_lingkup,
                 persyaratan, metode_uji, keywords
    
    Didesain untuk dipanggil dari ThreadPoolExecutor.
    """
    import tempfile
    import os

    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        full_text, cover_text = extract_text(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not full_text.strip():
        return {
            "_error": f"Teks kosong: {filename}",
            "no_sni": Path(filename).stem,
            "judul": Path(filename).stem.replace('_', ' ').replace('-', ' ').title(),
            "kategori": "Umum",
            "ruang_lingkup": "",
            "persyaratan": "-",
            "metode_uji": "-",
            "keywords": "",
        }

    rec = SNIRecord()
    rec.no_sni        = parse_no_sni(cover_text, full_text, filename)
    rec.judul         = parse_judul(cover_text, full_text, filename)
    rec.kategori      = parse_kategori(cover_text, full_text)
    rec.ruang_lingkup = parse_ruang_lingkup(full_text)
    rec.persyaratan   = parse_persyaratan(full_text)
    rec.metode_uji    = parse_metode_uji(full_text)
    rec.keywords      = parse_keywords(
        rec.judul, rec.kategori, rec.ruang_lingkup, rec.no_sni
    )

    d = asdict(rec)
    d["_source"] = filename
    return d
