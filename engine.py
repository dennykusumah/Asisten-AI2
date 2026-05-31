"""
engine.py — Core processing engine for SNI document extraction
Handles PDF/Word parsing + Gemini API extraction + JSONL output
"""

import os
import re
import json
import time
import logging
import hashlib
from pathlib import Path
from typing import Generator, Optional
from dataclasses import dataclass, asdict

import google.generativeai as genai
from pypdf import PdfReader
from docx import Document as DocxDocument

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sni_engine")

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_TEXT_CHARS = 12_000      # chars sent to Gemini per file (keep costs low)
MAX_SCOPE_CHARS = 150
MAX_KW_WORDS = 20
GEMINI_MODEL = "gemini-1.5-flash"
RETRY_LIMIT = 3
RETRY_DELAY = 5              # seconds between retries

CATEGORY_MAP = {
    "pangan": "Pangan", "makanan": "Pangan", "minuman": "Pangan",
    "kimia": "Kimia", "bahan kimia": "Kimia",
    "konstruksi": "Konstruksi", "bangunan": "Konstruksi", "beton": "Konstruksi", "semen": "Konstruksi",
    "elektro": "Elektro", "listrik": "Elektro", "elektronik": "Elektro",
    "mekanik": "Mekanik", "mesin": "Mekanik",
    "tekstil": "Tekstil", "kain": "Tekstil", "benang": "Tekstil",
    "pertanian": "Pertanian", "agro": "Pertanian",
    "lingkungan": "Lingkungan", "air": "Lingkungan",
    "kesehatan": "Kesehatan", "medis": "Kesehatan",
    "informatika": "Informatika", "teknologi informasi": "Informatika",
    "transportasi": "Transportasi", "kendaraan": "Transportasi",
}

GEMINI_PROMPT = """Kamu adalah ekstraksi SNI (Standar Nasional Indonesia) yang sangat presisi.
Baca dokumen SNI di bawah ini dan ekstrak informasi PERSIS sesuai format JSON berikut.
Aturan KETAT:
1. persyaratan: "Parameter = Nilai Satuan harus/sebaiknya". Pisah dengan " | ". Ambil SEMUA angka+satuan. Jika kosong: "-"
2. metode_uji: "Parameter = Kode_SNI Nama_metode kondisi_singkat". Pisah " | ". Jika kosong: "-"
3. keywords: Maks 20 kata. Wajib ada: nama parameter, angka kunci, satuan, kode SNI lain. Pisah spasi.
4. ruang_lingkup: 1-2 kalimat, maks 150 karakter.
5. kategori: Satu kata saja dari: Pangan, Kimia, Konstruksi, Elektro, Mekanik, Tekstil, Pertanian, Lingkungan, Kesehatan, Informatika, Transportasi, Lainnya

Kembalikan HANYA JSON valid, tanpa markdown, tanpa komentar, tanpa teks lain.

Format output:
{
  "sni_id": "<nomor SNI tanpa prefix 'SNI', contoh: 01-3701-1995>",
  "no_sni": "<prefix SNI + nomor, contoh: SNI 01-3701-1995>",
  "judul": "<judul resmi SNI>",
  "kategori": "<satu kata kategori>",
  "ruang_lingkup": "<1-2 kalimat maks 150 char>",
  "persyaratan": "<param=nilai satuan harus | param2=nilai2 satuan2 sebaiknya | ...>",
  "metode_uji": "<param=kode_sni nama_metode kondisi | ...>",
  "keywords": "<kata1 kata2 ... maks20>"
}

Dokumen SNI:
{text}
"""


# ── Data model ────────────────────────────────────────────────────────────────
@dataclass
class SNIRecord:
    sni_id: str = ""
    no_sni: str = ""
    judul: str = ""
    kategori: str = ""
    ruang_lingkup: str = ""
    persyaratan: str = "-"
    metode_uji: str = "-"
    keywords: str = ""

    def to_jsonl_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ── Text extraction ───────────────────────────────────────────────────────────
def extract_text_pdf(path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    """Extract raw text from PDF, truncated to max_chars."""
    try:
        reader = PdfReader(str(path))
        parts = []
        total = 0
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
            total += len(t)
            if total >= max_chars:
                break
        return "\n".join(parts)[:max_chars]
    except Exception as e:
        log.warning(f"PDF read error {path.name}: {e}")
        return ""


def extract_text_docx(path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    """Extract raw text from DOCX."""
    try:
        doc = DocxDocument(str(path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        # Also grab table cells
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    parts.append(cell.text.strip())
        return "\n".join(parts)[:max_chars]
    except Exception as e:
        log.warning(f"DOCX read error {path.name}: {e}")
        return ""


def extract_text(path: Path) -> str:
    """Route to correct extractor by extension."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_text_pdf(path)
    elif ext in (".docx", ".doc"):
        return extract_text_docx(path)
    return ""


# ── Gemini call ───────────────────────────────────────────────────────────────
def call_gemini(model, text: str) -> Optional[dict]:
    """Send text to Gemini, return parsed dict or None."""
    prompt = GEMINI_PROMPT.replace("{text}", text)
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            # Strip accidental markdown fences
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning(f"JSON parse fail attempt {attempt}: {e}")
        except Exception as e:
            log.warning(f"Gemini error attempt {attempt}: {e}")
            time.sleep(RETRY_DELAY * attempt)
    return None


# ── Post-process & validate ───────────────────────────────────────────────────
def guess_category_from_text(text: str) -> str:
    text_low = text.lower()
    for kw, cat in CATEGORY_MAP.items():
        if kw in text_low:
            return cat
    return "Lainnya"


def guess_sni_id_from_filename(filename: str) -> tuple[str, str]:
    """Try to parse SNI number from filename like 'SNI_01-3701-1995.pdf'"""
    m = re.search(r"(\d{2}-\d{4}-\d{4})", filename)
    if m:
        sni_id = m.group(1)
        return sni_id, f"SNI {sni_id}"
    return "", ""


def post_process(raw: dict, path: Path, source_text: str) -> SNIRecord:
    """Clean and validate extracted fields."""
    rec = SNIRecord()

    # sni_id / no_sni
    rec.sni_id = str(raw.get("sni_id", "")).strip()
    rec.no_sni = str(raw.get("no_sni", "")).strip()
    if not rec.sni_id:
        rec.sni_id, rec.no_sni = guess_sni_id_from_filename(path.name)

    # judul
    rec.judul = str(raw.get("judul", path.stem)).strip()

    # kategori
    cat = str(raw.get("kategori", "")).strip()
    # Validate against known categories
    valid_cats = set(CATEGORY_MAP.values()) | {"Lainnya"}
    rec.kategori = cat if cat in valid_cats else guess_category_from_text(source_text)

    # ruang_lingkup — enforce max length
    scope = str(raw.get("ruang_lingkup", "")).strip()
    rec.ruang_lingkup = scope[:MAX_SCOPE_CHARS]

    # persyaratan & metode_uji — keep as-is, fallback to "-"
    rec.persyaratan = str(raw.get("persyaratan", "-")).strip() or "-"
    rec.metode_uji = str(raw.get("metode_uji", "-")).strip() or "-"

    # keywords — enforce max 20 words
    kw = str(raw.get("keywords", "")).strip()
    words = kw.split()[:MAX_KW_WORDS]
    rec.keywords = " ".join(words)

    return rec


# ── File discovery ─────────────────────────────────────────────────────────────
def discover_files(folder: Path) -> list[Path]:
    """Return all PDF/DOCX files in folder (recursive)."""
    exts = {".pdf", ".docx", ".doc"}
    files = [p for p in folder.rglob("*") if p.suffix.lower() in exts and p.is_file()]
    files.sort()
    return files


# ── Checkpoint helpers ────────────────────────────────────────────────────────
def file_hash(path: Path) -> str:
    return hashlib.md5(path.name.encode()).hexdigest()


def load_done_set(checkpoint_file: Path) -> set[str]:
    done = set()
    if checkpoint_file.exists():
        for line in checkpoint_file.read_text().splitlines():
            done.add(line.strip())
    return done


def mark_done(checkpoint_file: Path, h: str):
    with checkpoint_file.open("a") as f:
        f.write(h + "\n")


# ── Main processing pipeline ──────────────────────────────────────────────────
def process_folder(
    api_key: str,
    input_folder: Path,
    output_file: Path,
    checkpoint_file: Path,
    rpm_limit: int = 15,
    progress_callback=None,
) -> Generator[dict, None, None]:
    """
    Generator that processes files one-by-one and yields status dicts:
      {"file": str, "status": "ok"|"skip"|"error", "record": SNIRecord|None, "msg": str}
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    files = discover_files(input_folder)
    total = len(files)
    done_set = load_done_set(checkpoint_file)

    # Open output in append mode so we can resume
    out_f = output_file.open("a", encoding="utf-8")

    # Rate limiting: track request timestamps
    req_times: list[float] = []
    min_interval = 60.0 / rpm_limit  # seconds per request

    try:
        for idx, path in enumerate(files, 1):
            h = file_hash(path)
            status_base = {"file": path.name, "index": idx, "total": total}

            if h in done_set:
                yield {**status_base, "status": "skip", "record": None, "msg": "already processed"}
                continue

            # Rate limiting
            now = time.time()
            req_times = [t for t in req_times if now - t < 60]
            if len(req_times) >= rpm_limit:
                wait = 60 - (now - req_times[0]) + 0.5
                log.info(f"Rate limit: sleeping {wait:.1f}s")
                time.sleep(wait)

            # Extract text
            text = extract_text(path)
            if not text.strip():
                yield {**status_base, "status": "error", "record": None, "msg": "empty text extracted"}
                mark_done(checkpoint_file, h)
                continue

            # Call Gemini
            req_times.append(time.time())
            raw = call_gemini(model, text)

            if raw is None:
                yield {**status_base, "status": "error", "record": None, "msg": "Gemini returned no valid JSON"}
                continue

            # Post-process
            rec = post_process(raw, path, text)
            line = rec.to_jsonl_line()
            out_f.write(line + "\n")
            out_f.flush()
            mark_done(checkpoint_file, h)

            yield {**status_base, "status": "ok", "record": rec, "msg": ""}

    finally:
        out_f.close()


# ── Stats helper ──────────────────────────────────────────────────────────────
def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)
