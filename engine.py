# engine.py
"""
SNI Extractor Engine
Memproses PDF/DOCX/TXT/Excel standar SNI menjadi structured JSON dengan field:
  sni_number, title, keywords, toc, summary, embedding_text
"""

import os
import io
import json
import uuid
import shutil
import time
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".md",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".xlsx", ".xls", ".ods", ".csv",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".ods", ".csv"}
MAX_FILE_SIZE_MB  = 200
MAX_FILES         = 200

# ──────────────────────────────────────────────────────────────────────────────
# UTILITY
# ──────────────────────────────────────────────────────────────────────────────

def format_size(byte_count: int) -> str:
    if byte_count == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i, val = 0, float(byte_count)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024; i += 1
    return f"{val:.2f} {units[i]}"


def generate_session_id() -> str:
    return f"sess_{int(time.time() * 1000)}_{uuid.uuid4().hex[:9]}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ──────────────────────────────────────────────────────────────────────────────
# SESSION MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────

def get_session_dir(session_id: str) -> Path:
    return UPLOADS_DIR / session_id


def init_session(session_id: str) -> dict:
    d = get_session_dir(session_id)
    ensure_dir(d / "original")
    ensure_dir(d / "processed")
    return {"session_id": session_id, "path": str(d)}


def list_sessions() -> list:
    sessions = []
    if not UPLOADS_DIR.exists():
        return sessions
    for entry in UPLOADS_DIR.iterdir():
        if not entry.is_dir():
            continue
        stat   = entry.stat()
        size   = _calc_dir_size(entry)
        fcount = sum(1 for f in entry.rglob("*") if f.is_file())
        sessions.append({
            "id":           entry.name,
            "created_at":  datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M"),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "modified_ts": stat.st_mtime,
            "file_size":   size,
            "file_size_fmt": format_size(size),
            "file_count":  fcount,
        })
    sessions.sort(key=lambda x: x["modified_ts"], reverse=True)
    return sessions


def get_session_detail(session_id: str) -> Optional[dict]:
    session_path = get_session_dir(session_id)
    if not session_path.exists():
        return None
    structure = {}
    for subdir in ["original", "processed"]:
        sub = session_path / subdir
        if sub.exists():
            structure[subdir] = [
                {"name": f.name, "size_fmt": format_size(f.stat().st_size)}
                for f in sub.iterdir() if f.is_file()
            ]
    return {"session_id": session_id, "structure": structure}


def delete_session(session_id: str) -> dict:
    p = get_session_dir(session_id)
    if not p.exists():
        return {"success": False, "error": "Session not found"}
    size = _calc_dir_size(p)
    shutil.rmtree(p)
    return {"success": True, "freed_bytes": size, "freed_fmt": format_size(size)}


def delete_all_sessions(exclude_id: str = "") -> dict:
    deleted, freed = 0, 0
    if not UPLOADS_DIR.exists():
        return {"deleted": 0, "freed_bytes": 0, "freed_fmt": "0 B"}
    for entry in list(UPLOADS_DIR.iterdir()):
        if not entry.is_dir() or entry.name == exclude_id:
            continue
        size = _calc_dir_size(entry)
        shutil.rmtree(entry)
        freed += size; deleted += 1
    return {"deleted": deleted, "freed_bytes": freed, "freed_fmt": format_size(freed)}


def _calc_dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


# ──────────────────────────────────────────────────────────────────────────────
# FILE SAVING
# ──────────────────────────────────────────────────────────────────────────────

def save_uploaded_file(session_id: str, uploaded_file) -> dict:
    session_dir  = get_session_dir(session_id)
    original_dir = ensure_dir(session_dir / "original")
    safe_name    = re.sub(r"[^a-zA-Z0-9._\-]", "_", uploaded_file.name)
    unique_name  = f"{int(time.time() * 1000)}_{safe_name}"
    dest         = original_dir / unique_name
    content      = uploaded_file.read()
    dest.write_bytes(content)
    return {
        "original_name": uploaded_file.name,
        "saved_name":    unique_name,
        "path":          str(dest),
        "size":          len(content),
        "size_fmt":      format_size(len(content)),
        "ext":           Path(uploaded_file.name).suffix.lower(),
        "session_id":    session_id,
    }


# ──────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION  — multi-layer with detailed error propagation
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_from_file(file_path: str, file_ext: str) -> str:
    """
    Extract text from any supported file type.
    Returns non-empty string on success, raises RuntimeError on total failure.
    """
    p   = Path(file_path)
    ext = file_ext.lower()

    if ext in (".txt", ".md"):
        return _read_text_file(p)

    elif ext == ".pdf":
        return _extract_pdf(p)

    elif ext == ".docx":
        return _extract_docx(p)

    elif ext == ".doc":
        return _extract_doc_legacy(p)

    elif ext in EXCEL_EXTENSIONS:
        return _extract_excel(p, ext)

    elif ext in IMAGE_EXTENSIONS:
        return _extract_image_ocr(p)

    raise RuntimeError(f"Tipe file tidak didukung: {ext}")


# ── Plain text ────────────────────────────────────────────────────────────────

def _read_text_file(p: Path) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            text = p.read_text(enc)
            if text.strip():
                return text
        except UnicodeDecodeError:
            continue
    return p.read_bytes().decode("utf-8", errors="replace")


# ── PDF — 4-layer extraction ──────────────────────────────────────────────────

def _extract_pdf(p: Path) -> str:
    errors = []

    # Layer 1: pypdf (fast, works on digital PDFs)
    try:
        import pypdf
        reader = pypdf.PdfReader(str(p))
        pages  = []
        for page in reader.pages:
            t = page.extract_text()
            if t and t.strip():
                pages.append(t.strip())
        text = "\n\n".join(pages)
        if len(text.strip()) >= 100:
            return text
        errors.append("pypdf: teks < 100 karakter")
    except Exception as e:
        errors.append(f"pypdf: {e}")

    # Layer 2: pdfminer.six (better layout handling)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(str(p))
        if text and len(text.strip()) >= 100:
            return text.strip()
        errors.append("pdfminer: teks < 100 karakter")
    except ImportError:
        errors.append("pdfminer: tidak terinstall")
    except Exception as e:
        errors.append(f"pdfminer: {e}")

    # Layer 3: pdftotext CLI
    try:
        r = subprocess.run(
            ["pdftotext", "-layout", str(p), "-"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0 and r.stdout and len(r.stdout.strip()) >= 100:
            return r.stdout.strip()
        errors.append(f"pdftotext: returncode={r.returncode} atau teks kosong")
    except FileNotFoundError:
        errors.append("pdftotext: binary tidak ditemukan")
    except Exception as e:
        errors.append(f"pdftotext: {e}")

    # Layer 4: OCR via pdf2image + pytesseract (for scanned PDFs)
    try:
        return _extract_pdf_ocr(p)
    except Exception as e:
        errors.append(f"OCR: {e}")

    raise RuntimeError(
        f"Semua metode ekstraksi PDF gagal untuk '{p.name}':\n" +
        "\n".join(f"  • {e}" for e in errors)
    )


def _extract_pdf_ocr(p: Path) -> str:
    """OCR fallback for scanned PDFs using pdf2image + pytesseract."""
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(str(p), dpi=200, first_page=1, last_page=10)
    if not images:
        raise RuntimeError("pdf2image: tidak ada halaman yang dikonversi")

    pages = []
    for img in images:
        # Try Indonesian + English, fallback to English only
        try:
            t = pytesseract.image_to_string(img, lang="ind+eng")
        except Exception:
            t = pytesseract.image_to_string(img)
        if t.strip():
            pages.append(t.strip())

    text = "\n\n".join(pages)
    if len(text.strip()) < 50:
        raise RuntimeError("OCR menghasilkan teks yang sangat pendek")
    return text


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _extract_docx(p: Path) -> str:
    # Primary: python-docx
    try:
        import docx as python_docx
        doc   = python_docx.Document(str(p))
        parts = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        # Also extract tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    parts.append(row_text)
        text = "\n\n".join(parts)
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: raw XML parsing
    try:
        import zipfile, xml.etree.ElementTree as ET
        texts = []
        with zipfile.ZipFile(str(p)) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                ns   = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for t in tree.findall(".//w:t", ns):
                    if t.text:
                        texts.append(t.text)
        text = " ".join(texts)
        if text.strip():
            return text
    except Exception:
        pass

    raise RuntimeError(f"Tidak dapat mengekstrak teks dari DOCX: {p.name}")


# ── Legacy DOC ────────────────────────────────────────────────────────────────

def _extract_doc_legacy(p: Path) -> str:
    try:
        r = subprocess.run(["antiword", str(p)], capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except Exception:
        pass
    # Fallback: extract printable ASCII
    try:
        raw   = p.read_bytes()
        texts = re.findall(rb"[\x20-\x7e]{4,}", raw)
        text  = " ".join(t.decode("ascii", errors="replace") for t in texts)
        if text.strip():
            return text
    except Exception:
        pass
    raise RuntimeError(f"Tidak dapat mengekstrak teks dari DOC: {p.name}")


# ── Excel / CSV ───────────────────────────────────────────────────────────────

def _extract_excel(p: Path, ext: str) -> str:
    """Extract text from Excel/CSV files."""
    import pandas as pd

    try:
        if ext == ".csv":
            df = pd.read_csv(str(p), dtype=str, nrows=500)
        elif ext == ".xls":
            df = pd.read_excel(str(p), dtype=str, engine="xlrd", nrows=500)
        elif ext == ".ods":
            df = pd.read_excel(str(p), dtype=str, engine="odf", nrows=500)
        else:  # .xlsx
            df = pd.read_excel(str(p), dtype=str, engine="openpyxl", nrows=500)

        # Convert to plain text representation
        lines = []
        lines.append(f"[File: {p.name}]")
        lines.append(f"Kolom: {', '.join(str(c) for c in df.columns)}")
        lines.append("")
        for _, row in df.iterrows():
            row_text = " | ".join(str(v) for v in row.values if str(v) not in ("nan", "None", ""))
            if row_text.strip():
                lines.append(row_text)
        text = "\n".join(lines)
        if text.strip():
            return text
    except Exception as e:
        raise RuntimeError(f"Gagal membaca file Excel '{p.name}': {e}")

    raise RuntimeError(f"File Excel kosong atau tidak terbaca: {p.name}")


# ── Image OCR ─────────────────────────────────────────────────────────────────

def _extract_image_ocr(p: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(str(p))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        try:
            text = pytesseract.image_to_string(img, lang="ind+eng")
        except Exception:
            text = pytesseract.image_to_string(img)
        if text.strip():
            return text.strip()
        raise RuntimeError("OCR menghasilkan teks kosong")
    except ImportError as e:
        raise RuntimeError(f"pytesseract/Pillow tidak terinstall: {e}")
    except Exception as e:
        raise RuntimeError(f"OCR gagal untuk '{p.name}': {e}")


# ──────────────────────────────────────────────────────────────────────────────
# SNI FIELD NORMALISER
# ──────────────────────────────────────────────────────────────────────────────

_SNI_ID_RE = re.compile(
    r"\bSNI(?:\s+(?:ISO|IEC|ASTM|EN|BS))?[\s\-]+\d[\w.\-:/]*(?:[\-:]\d[\w.\-:/]*)?\b",
    re.IGNORECASE,
)

def _normalise_sni_fields(raw: dict, source_text: str) -> dict:
    # sni_number
    if not raw.get("sni_number"):
        m = _SNI_ID_RE.search(source_text)
        raw["sni_number"] = m.group(0).strip() if m else ""
    raw["sni_number"] = re.sub(r"\s+", " ", raw.get("sni_number", "").strip()).upper()

    # title
    if not raw.get("title"):
        raw["title"] = ""

    # keywords — ensure list of strings
    kw = raw.get("keywords", [])
    if isinstance(kw, str):
        kw = [k.strip() for k in re.split(r"[,;]", kw) if k.strip()]
    raw["keywords"] = kw if isinstance(kw, list) else []

    # toc — ensure list of strings
    toc = raw.get("toc", [])
    if isinstance(toc, str):
        toc = [t.strip() for t in toc.splitlines() if t.strip()]
    raw["toc"] = toc if isinstance(toc, list) else []

    # summary
    if not raw.get("summary"):
        raw["summary"] = ""

    return raw


# ──────────────────────────────────────────────────────────────────────────────
# CLAUDE EXTRACTION
# ──────────────────────────────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """\
Kamu adalah asisten ekstraksi dokumen standar SNI (Standar Nasional Indonesia).
Tugasmu: baca teks dokumen SNI dan kembalikan JSON VALID SAJA — tidak ada teks lain di luar JSON.

Format JSON yang harus dikembalikan:
{
  "sni_number": "<nomor SNI, contoh: SNI 01-3140-2010 atau SNI 4:2025>",
  "title": "<judul lengkap dokumen standar, bukan nomor SNI>",
  "keywords": ["<keyword1>", "<keyword2>", "..."],
  "toc": ["<bab/seksi 1>", "<bab/seksi 2>", "..."],
  "summary": "<ringkasan isi standar dalam 3-5 kalimat bahasa Indonesia>"
}

Aturan:
- sni_number: ambil nomor SNI yang tertera di cover/header (e.g. "SNI 01-3140-2010")
- title: judul komoditas/subjek standar (bukan "Standar Nasional Indonesia")
- keywords: 5-10 kata kunci teknis relevan dari isi standar
- toc: daftar isi / nama bab utama (tanpa nomor halaman)
- summary: ringkasan singkat ruang lingkup dan persyaratan utama
- Kembalikan HANYA JSON, tidak ada penjelasan, tidak ada markdown.
- Jika dokumen bukan SNI, tetap ekstrak field semampu mungkin dari konten yang ada.
"""

def _get_anthropic_api_key() -> str:
    # 1. Streamlit secrets
    try:
        import streamlit as _st
        key = _st.secrets.get("ANTHROPIC_API_KEY", "")
        if key and key.strip():
            return key.strip()
    except Exception:
        pass
    # 2. Environment variable
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key and key.strip():
        return key.strip()
    raise RuntimeError(
        "ANTHROPIC_API_KEY tidak ditemukan.\n"
        "Tambahkan di Streamlit Cloud > App Settings > Secrets:\n"
        "  ANTHROPIC_API_KEY = \"sk-ant-...\""
    )


def _extract_sni_fields_via_claude(text: str) -> dict:
    """Call Claude to extract structured SNI fields from raw document text."""
    try:
        import anthropic as _anthropic
    except ImportError:
        raise RuntimeError("Package 'anthropic' tidak ditemukan. Tambahkan ke requirements.txt")

    api_key   = _get_anthropic_api_key()
    client    = _anthropic.Anthropic(api_key=api_key)
    truncated = text[:80_000] if len(text) > 80_000 else text

    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=_EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": f"Teks dokumen:\n\n{truncated}"}],
    )

    raw_text = msg.content[0].text.strip()
    # Strip markdown fences
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# BUILD EMBEDDING TEXT
# ──────────────────────────────────────────────────────────────────────────────

def build_embedding_text(sni_number: str, title: str, keywords: list,
                         toc: list, summary: str) -> str:
    return (
        f"Source: {sni_number}\n"
        f"Judul: {title}\n"
        f"Keyword: {', '.join(keywords)}\n"
        f"Daftar Isi: {' | '.join(toc)}\n"
        f"Ringkasan: {summary}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# PROCESS SINGLE FILE  →  1 SNI record
# ──────────────────────────────────────────────────────────────────────────────

def _process_single_sni_file(args) -> dict:
    info, _settings = args
    fname = info["original_name"]
    try:
        raw_text = extract_text_from_file(info["path"], info["ext"])

        if not raw_text or not raw_text.strip():
            return {"status": "error", "file": fname,
                    "error": "Tidak ada teks yang bisa diekstrak dari file ini", "record": None}

        # Claude extraction
        fields = _extract_sni_fields_via_claude(raw_text)

        # Normalise
        fields = _normalise_sni_fields(fields, raw_text)

        sni_number = fields["sni_number"]
        title      = fields["title"]
        keywords   = fields["keywords"]
        toc        = fields["toc"]
        summary    = fields["summary"]

        embedding_text = build_embedding_text(sni_number, title, keywords, toc, summary)

        record = {
            "sni_number":     sni_number,
            "title":          title,
            "keywords":       keywords,
            "toc":            toc,
            "summary":        summary,
            "embedding_text": embedding_text,
            "source_file":    fname,
            "processed_at":   datetime.now(timezone.utc).isoformat(),
        }
        return {"status": "success", "file": fname, "record": record}

    except Exception as e:
        return {"status": "error", "file": fname, "error": str(e), "record": None}


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PROCESS FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def process_documents(
    file_infos: list,
    settings: dict,
    max_workers: int = 8,
    progress_callback=None,
) -> dict:
    total     = len(file_infos)
    results   = [None] * total
    completed = [0]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_process_single_sni_file, (info, settings)): i
            for i, info in enumerate(file_infos)
        }
        for future in as_completed(future_to_idx):
            idx           = future_to_idx[future]
            results[idx]  = future.result()
            completed[0] += 1
            if progress_callback:
                progress_callback("extract", completed[0], total, file_infos[idx]["original_name"])

    records      = []
    file_results = []
    processed_ok = 0
    failed       = 0

    for res in results:
        if res is None:
            continue
        file_results.append(res)
        if res["status"] == "success" and res["record"]:
            records.append(res["record"])
            processed_ok += 1
        else:
            failed += 1

    stats = {
        "total_files":     total,
        "processed_files": processed_ok,
        "failed_files":    failed,
        "total_chunks":    processed_ok,
        "total_chars":     sum(len(r.get("embedding_text", "")) for r in records),
        "errors":          [
            {"file": r["file"], "error": r.get("error", "")}
            for r in file_results if r["status"] != "success"
        ],
    }

    return {
        "version":      "3.0",
        "type":         "sni_extraction",
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "settings":     settings,
        "stats":        stats,
        "file_results": file_results,
        "total":        len(records),
        "total_chunks": len(records),
        "data":         records,
    }


def process_and_paraphrase(
    file_infos: list,
    settings: dict,
    language: str = "auto",
    progress_callback=None,
) -> dict:
    result = process_documents(file_infos, settings, max_workers=8,
                               progress_callback=progress_callback)
    result["paraphrased"] = False
    return result


# ──────────────────────────────────────────────────────────────────────────────
# SAVE
# ──────────────────────────────────────────────────────────────────────────────

def save_processed_data(session_id: str, data: dict, settings: dict) -> dict:
    session_dir   = get_session_dir(session_id)
    processed_dir = ensure_dir(session_dir / "processed")
    output_path   = processed_dir / "output.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

    jsonl_path = processed_dir / "output.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for record in data.get("data", []):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "success":        True,
        "processed_path": str(output_path),
        "jsonl_path":     str(jsonl_path),
        "chunks_saved":   len(data.get("data", [])),
    }


# ──────────────────────────────────────────────────────────────────────────────
# JSON MERGER
# ──────────────────────────────────────────────────────────────────────────────

def detect_merge_strategy(parsed_files: list, strategy: str = "auto") -> str:
    if strategy != "auto":
        return strategy
    if all(isinstance(f["content"], dict) and isinstance(f["content"].get("data"), list)
           for f in parsed_files):
        return "data"
    if all(isinstance(f["content"], list) for f in parsed_files):
        return "array"
    return "object"


def merge_json_files(file_contents: list, strategy: str = "auto") -> dict:
    merge_mode = detect_merge_strategy(file_contents, strategy)
    stats      = {"files_count": len(file_contents), "merge_mode": merge_mode, "item_counts": []}

    if merge_mode == "data":
        all_items = []
        for f in file_contents:
            items = f["content"].get("data", [])
            all_items.extend(items)
            stats["item_counts"].append({"file": f["name"], "items": len(items)})
        merged = {
            "version": "3.0", "type": "sni_extraction", "merged": True,
            "merged_at": datetime.now(timezone.utc).isoformat(),
            "source_files": [f["name"] for f in file_contents],
            "total": len(all_items), "total_chunks": len(all_items), "data": all_items,
        }
    elif merge_mode == "array":
        all_items = []
        for f in file_contents:
            c   = f["content"]
            arr = c if isinstance(c, list) else c.get("data", [c]) if isinstance(c, dict) else []
            all_items.extend(arr)
            stats["item_counts"].append({"file": f["name"], "items": len(arr)})
        merged = all_items
    else:
        merged = {"_merged": True, "_merged_at": datetime.now(timezone.utc).isoformat(),
                  "_source_files": [f["name"] for f in file_contents]}
        for f in file_contents:
            src = f["content"] if isinstance(f["content"], dict) else {"_data": f["content"]}
            merged.update(src)
            stats["item_counts"].append({"file": f["name"], "keys": len(src)})

    return {"merged": merged, "merge_mode": merge_mode, "stats": stats}
