"""
engine.py — Local SNI extraction engine (NO API, NO network)
PDF/Word → regex heuristic → JSONL record

Extraction strategy (all done in-process, no LLM):
  1. Extract raw text from PDF (PyMuPDF) or DOCX (python-docx)
  2. Parse SNI ID + judul from cover page patterns
  3. Identify ruang lingkup, persyaratan, metode_uji sections by header keywords
  4. Extract numeric parameters from requirement tables
  5. Infer kategori from title/scope keywords
  6. Build keyword string from extracted entities
"""

import re
import json
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Optional

log = logging.getLogger("sni_engine")

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_SCOPE_CHARS = 150
MAX_KW_WORDS    = 20

CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["pangan","makanan","minuman","gula","garam","minyak","susu","daging","ikan","beras","tepung","kopi","teh","cokelat","bumbu","saos","kecap","mie","roti","biskuit","snack","keju","mentega","margarin","es krim","sirup","jus","sari buah"], "Pangan"),
    (["kimia","bahan kimia","pestisida","pupuk","cat","pelarut","asam","basa","reagen","deterjen","sabun","kosmetik","parfum","pigmen","adhesif","lem"], "Kimia"),
    (["konstruksi","bangunan","beton","semen","baja","besi","kayu","cat tembok","keramik","genteng","bata","pondasi","aspal","agregat","mortar","panel","plat","pipa konstruksi"], "Konstruksi"),
    (["elektro","listrik","elektronik","kabel","transformator","motor","generator","baterai","saklar","stop kontak","lampu","led","solar","panel surya","inverter","ups","charger"], "Elektro"),
    (["mekanik","mesin","pompa","kompresor","turbin","roda gigi","bearing","piston","silinder","katup","flanges","baut","mur"], "Mekanik"),
    (["tekstil","kain","benang","serat","rajut","tenun","pakaian","garmen","karpet","nonwoven"], "Tekstil"),
    (["pertanian","agro","bibit","benih","pestisida pertanian","pupuk","tanah","irigasi","traktor"], "Pertanian"),
    (["lingkungan","air","udara","limbah","emisi","polutan","baku mutu lingkungan","amdal"], "Lingkungan"),
    (["kesehatan","medis","alat kesehatan","farmasi","obat","sterilisasi","masker","sarung tangan medis","jarum","syringe"], "Kesehatan"),
    (["informatika","teknologi informasi","perangkat lunak","software","hardware","jaringan","keamanan informasi","enkripsi","iso 27"], "Informatika"),
    (["transportasi","kendaraan","otomotif","sepeda motor","ban","helm","sabuk pengaman","kapal","pesawat","kereta"], "Transportasi"),
]

# Parameter detection patterns: (regex, unit_hint)
PARAM_PATTERNS = [
    # explicit table-style: "Timbal (Pb)   maks 0,05 mg/L"
    r'([A-Za-z][A-Za-z0-9\s\(\)\-\.]{2,40}?)\s+(?:maks(?:imum)?|min(?:imum)?|=|≤|≥|<|>)\s*([\d,\.]+)\s*([a-zA-Z/%µμ°][a-zA-Z0-9/%µμ°]*)',
    # numeric value with unit
    r'([A-Za-z][A-Za-z0-9\s\(\)\-\.]{2,30}?)\s*[:=]\s*([\d,\.]+)\s*([a-zA-Z/%µμ°][a-zA-Z0-9/%µμ°]*)',
]

SNI_REF_PATTERN = re.compile(r'SNI\s+(\d{2}-\d{4,5}-\d{4})', re.IGNORECASE)
SNI_ID_COVER    = re.compile(r'(?:^|\s)SNI\s+(\d{2}[\.\-]\d{3,5}[\.\-]\d{4})', re.IGNORECASE | re.MULTILINE)
YEAR_PATTERN    = re.compile(r'\b(19|20)\d{2}\b')


# ─── Data model ───────────────────────────────────────────────────────────────
@dataclass
class SNIRecord:
    sni_id:       str = ""
    no_sni:       str = ""
    judul:        str = ""
    kategori:     str = ""
    ruang_lingkup: str = ""
    persyaratan:  str = "-"
    metode_uji:   str = "-"
    keywords:     str = ""

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ─── Text extraction ──────────────────────────────────────────────────────────
def extract_pdf(path: Path) -> str:
    """Fast PDF text extraction via PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        parts = []
        total = 0
        for page in doc:
            t = page.get_text("text")
            parts.append(t)
            total += len(t)
            if total > 40_000:   # read max ~40k chars = ~300 pages worth
                break
        doc.close()
        return "\n".join(parts)
    except Exception as e:
        log.debug(f"PyMuPDF failed {path.name}: {e}, falling back to pypdf")
        return _extract_pdf_fallback(path)


def _extract_pdf_fallback(path: Path) -> str:
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        parts = []
        for page in r.pages[:60]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception as e:
        log.warning(f"PDF fallback failed {path.name}: {e}")
        return ""


def extract_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_cells:
                    parts.append(" | ".join(row_cells))
        return "\n".join(parts)
    except Exception as e:
        log.warning(f"DOCX failed {path.name}: {e}")
        return ""


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext in (".docx", ".doc"):
        return extract_docx(path)
    return ""


# ─── Heuristic parsers ────────────────────────────────────────────────────────

def parse_sni_id(text: str, filename: str) -> tuple[str, str]:
    """Extract SNI number from text or filename."""
    # Try cover-page pattern first (usually first 500 chars)
    head = text[:800]
    m = SNI_ID_COVER.search(head)
    if m:
        raw = re.sub(r'[\.\s]+', '-', m.group(1))
        return raw, f"SNI {raw}"
    # Try whole text
    m = SNI_ID_COVER.search(text)
    if m:
        raw = re.sub(r'[\.\s]+', '-', m.group(1))
        return raw, f"SNI {raw}"
    # Fallback: filename
    m2 = re.search(r'(\d{2}[\-\.]\d{3,5}[\-\.]\d{4})', filename)
    if m2:
        raw = re.sub(r'\.', '-', m2.group(1))
        return raw, f"SNI {raw}"
    return "", ""


def parse_judul(text: str, filename: str) -> str:
    """Extract title: usually the longest ALL-CAPS or Title Case line near the top."""
    lines = [l.strip() for l in text[:2000].splitlines() if l.strip()]
    # Filter out lines that look like SNI number lines
    candidates = []
    for ln in lines:
        # Skip short, numeric-heavy, or SNI-number lines
        if len(ln) < 8 or len(ln) > 120:
            continue
        if re.match(r'^SNI\s+\d', ln, re.IGNORECASE):
            continue
        if re.match(r'^\d', ln):
            continue
        # Prefer lines that are title-case or all-caps words
        word_count = len(ln.split())
        if 2 <= word_count <= 12:
            candidates.append(ln)
    if candidates:
        # Pick the longest candidate (usually the title)
        return max(candidates, key=len)
    # Last resort: stem of filename
    return Path(filename).stem.replace('_', ' ').replace('-', ' ').title()


def parse_kategori(text: str) -> str:
    text_low = text[:3000].lower()
    for keywords, cat in CATEGORY_RULES:
        for kw in keywords:
            if kw in text_low:
                return cat
    return "Lainnya"


def _find_section(text: str, headers: list[str], next_headers: list[str]) -> str:
    """Extract text between a section header and the next section."""
    text_low = text.lower()
    start = -1
    for h in headers:
        idx = text_low.find(h.lower())
        if idx != -1:
            # move past the header line
            start = text.find('\n', idx)
            if start == -1:
                start = idx + len(h)
            else:
                start += 1
            break
    if start == -1:
        return ""

    end = len(text)
    for nh in next_headers:
        idx = text_low.find(nh.lower(), start)
        if idx != -1 and idx < end:
            end = idx

    return text[start:end].strip()


def parse_ruang_lingkup(text: str) -> str:
    SCOPE_HEADERS = ["ruang lingkup", "1. ruang lingkup", "1 ruang lingkup", "scope", "lingkup"]
    NEXT = ["acuan normatif", "istilah", "definisi", "persyaratan", "2.", "ketentuan"]
    section = _find_section(text, SCOPE_HEADERS, NEXT)
    if not section:
        return ""
    # Take first 1-2 sentences
    sentences = re.split(r'(?<=[.!?])\s+', section)
    result = ""
    for s in sentences:
        s = s.strip()
        if len(s) < 10:
            continue
        result += (" " if result else "") + s
        if len(result) >= 80:
            break
    return result[:MAX_SCOPE_CHARS]


def parse_persyaratan(text: str) -> str:
    """Extract requirement parameters with values/units from text."""
    SYARAT_HEADERS = [
        "syarat mutu", "persyaratan mutu", "persyaratan teknis", "ketentuan mutu",
        "karakteristik", "spesifikasi", "requirements", "persyaratan",
    ]
    NEXT = ["metode uji", "cara uji", "pengujian", "pengambilan contoh", "sampel"]
    section = _find_section(text, SYARAT_HEADERS, NEXT)
    if not section:
        section = text  # fallback: scan entire text

    entries = []
    seen = set()

    for pattern in PARAM_PATTERNS:
        for m in re.finditer(pattern, section, re.IGNORECASE):
            param  = m.group(1).strip().rstrip(':=')
            value  = m.group(2).strip()
            unit   = m.group(3).strip() if m.lastindex >= 3 else ""

            # Filter noise
            param_clean = param.strip()
            if len(param_clean) < 3 or len(param_clean) > 50:
                continue
            if re.match(r'^[\d\s]+$', param_clean):
                continue

            key = f"{param_clean.lower()}={value}"
            if key in seen:
                continue
            seen.add(key)

            # Determine harus/sebaiknya
            ctx = section[max(0, m.start()-60):m.start()+60].lower()
            qualifier = "harus" if any(w in ctx for w in ["maks","min","harus","wajib","tidak boleh","≤","≥","<",">"]) else "sebaiknya"

            unit_str = f" {unit}" if unit else ""
            entries.append(f"{param_clean} = {value}{unit_str} {qualifier}")

        if entries:
            break  # first pattern that yields results is enough

    if not entries:
        return "-"

    # Deduplicate and limit
    return " | ".join(entries[:15])


def parse_metode_uji(text: str) -> str:
    """Extract test method references (SNI codes + method names)."""
    METODE_HEADERS = ["metode uji", "cara uji", "pengujian", "prosedur uji", "metoda uji"]
    NEXT = ["pengambilan contoh", "pengemasan", "penandaan", "syarat lulus"]
    section = _find_section(text, METODE_HEADERS, NEXT)
    if not section:
        section = text

    entries = []
    seen_codes = set()

    for m in SNI_REF_PATTERN.finditer(section):
        code = m.group(1)
        if code in seen_codes:
            continue
        seen_codes.add(code)

        # Try to find what parameter this SNI is used for (look back ~80 chars)
        start = max(0, m.start() - 100)
        ctx_before = section[start:m.start()]
        # Get last meaningful phrase before the SNI code
        param_match = re.search(r'([A-Za-z][A-Za-z0-9\s\(\)]{3,35})\s*$', ctx_before)
        param_name = param_match.group(1).strip() if param_match else "Parameter"

        # Look for method name after code
        ctx_after = section[m.end():m.end()+80]
        method_match = re.search(r'[:\-–]\s*([A-Za-z][^\n]{4,50})', ctx_after)
        method_name = method_match.group(1).strip() if method_match else ""

        entry = f"{param_name} = SNI {code}"
        if method_name:
            entry += f" {method_name[:40]}"
        entries.append(entry)

    if not entries:
        return "-"
    return " | ".join(entries[:10])


def build_keywords(record: SNIRecord, text: str) -> str:
    """Build keyword string: param names + numbers + units + SNI refs."""
    words = []

    # Add key terms from judul
    stop = {"standar","nasional","indonesia","dan","atau","untuk","dari","dengan","yang","dalam","sni","iso","iec"}
    for w in record.judul.split():
        if w.lower() not in stop and len(w) > 2:
            words.append(w)

    # Add all numbers+units from persyaratan
    for m in re.finditer(r'[\d,\.]+\s*[a-zA-Z/%µ°]+', record.persyaratan):
        words.append(m.group().strip())

    # Add SNI reference codes found in text
    for m in SNI_REF_PATTERN.finditer(text[:5000]):
        ref = f"SNI-{m.group(1)}"
        if ref not in words:
            words.append(ref)

    # Deduplicate preserving order
    seen = set()
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
    Process a single file (given as bytes) → return dict ready for JSONL.
    Designed to be called in a ProcessPoolExecutor worker.
    """
    import tempfile, os
    # Write to temp file for library access
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        text = extract_text(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not text.strip():
        return {"_error": f"empty text: {filename}", "sni_id": "", "no_sni": "",
                "judul": Path(filename).stem, "kategori": "Lainnya",
                "ruang_lingkup": "", "persyaratan": "-", "metode_uji": "-", "keywords": ""}

    rec = SNIRecord()
    rec.sni_id, rec.no_sni = parse_sni_id(text, filename)
    rec.judul        = parse_judul(text, filename)
    rec.kategori     = parse_kategori(text)
    rec.ruang_lingkup = parse_ruang_lingkup(text)
    rec.persyaratan  = parse_persyaratan(text)
    rec.metode_uji   = parse_metode_uji(text)
    rec.keywords     = build_keywords(rec, text)

    d = asdict(rec)
    d["_source"] = filename
    return d
