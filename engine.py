# engine.py
"""
SNI Extractor Engine
Memproses PDF standar SNI menjadi structured JSON dengan field:
  sni_number, title, keywords, toc, summary, embedding_text
"""

import os
import json
import uuid
import shutil
import time
import re
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
IMAGE_EXTENSIONS   = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE_MB   = 200
MAX_FILES          = 200

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
# TEXT EXTRACTION
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_from_file(file_path: str, file_ext: str) -> str:
    p   = Path(file_path)
    ext = file_ext.lower()

    if ext in (".txt", ".md"):
        for enc in ("utf-8", "latin-1", "cp1252"):
            try: return p.read_text(enc)
            except UnicodeDecodeError: continue
        return p.read_bytes().decode("utf-8", errors="replace")

    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(p))
            pages  = [page.extract_text() for page in reader.pages if page.extract_text()]
            text   = "\n\n".join(pages)
            if len(text.strip()) >= 50:
                return text
        except ImportError:
            pass
        return _extract_pdf_fallback(p)

    elif ext == ".docx":
        try:
            import docx as python_docx
            doc   = python_docx.Document(str(p))
            parts = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(parts)
        except ImportError:
            return _extract_docx_fallback(p)

    elif ext == ".doc":
        return _extract_doc_legacy(p)

    elif ext in IMAGE_EXTENSIONS:
        return _extract_image_text(p)

    return ""


def _extract_pdf_fallback(p: Path) -> str:
    try:
        import subprocess
        r = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except Exception:
        pass
    return f"[Cannot extract PDF: {p.name}]"


def _extract_docx_fallback(p: Path) -> str:
    try:
        import zipfile, xml.etree.ElementTree as ET
        texts = []
        with zipfile.ZipFile(str(p)) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                ns   = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for t in tree.findall(".//w:t", ns):
                    if t.text: texts.append(t.text)
        return " ".join(texts)
    except Exception:
        return f"[Cannot extract DOCX: {p.name}]"


def _extract_doc_legacy(p: Path) -> str:
    try:
        import subprocess
        r = subprocess.run(["antiword", str(p)], capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except Exception:
        pass
    try:
        raw   = p.read_bytes()
        texts = re.findall(rb"[\x20-\x7e]{4,}", raw)
        return " ".join(t.decode("ascii", errors="replace") for t in texts)
    except Exception:
        return f"[Cannot extract DOC: {p.name}]"


def _extract_image_text(p: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(str(p))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        try:   return pytesseract.image_to_string(img, lang="ind+eng").strip()
        except: return pytesseract.image_to_string(img).strip()
    except Exception as e:
        return f"[Image OCR failed: {p.name} — {e}]"


# ──────────────────────────────────────────────────────────────────────────────
# SNI FIELD NORMALISER  (Python-side fallback / post-processing)
# ──────────────────────────────────────────────────────────────────────────────

_SNI_ID_RE = re.compile(
    r"\bSNI(?:\s+(?:ISO|IEC|ASTM|EN|BS))?[\s\-]+\d[\w.\-:/]*(?:[\-:]\d[\w.\-:/]*)?\b",
    re.IGNORECASE,
)

def _normalise_sni_fields(raw: dict, source_text: str) -> dict:
    """
    Fallback normaliser: fix / fill missing fields after Claude extraction.
    """
    # sni_number — scan raw text for SNI id pattern
    if not raw.get("sni_number"):
        m = _SNI_ID_RE.search(source_text)
        raw["sni_number"] = m.group(0).strip() if m else ""

    # Normalise: uppercase, remove extra spaces
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
# CLAUDE EXTRACTION — 1 API call per document
# ──────────────────────────────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """\
Kamu adalah asisten ekstraksi dokumen standar SNI (Standar Nasional Indonesia).
Tugasmu: baca teks PDF SNI dan kembalikan JSON VALID SAJA — tidak ada teks lain di luar JSON.

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
"""

def _extract_sni_fields_via_claude(text: str) -> dict:
    """Call Claude to extract structured SNI fields from raw PDF text."""
    try:
        import anthropic as _anthropic
    except ImportError:
        raise RuntimeError("Package anthropic tidak ditemukan. Tambahkan anthropic ke requirements.txt.")
    client = _anthropic.Anthropic()

    # Truncate to ~80k chars to stay within context
    truncated = text[:80_000] if len(text) > 80_000 else text

    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=_EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": f"Teks SNI:\n\n{truncated}"}],
    )

    raw_text = msg.content[0].text.strip()

    # Strip markdown fences if present
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Best-effort: extract JSON object from response
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
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
    try:
        raw_text = extract_text_from_file(info["path"], info["ext"])
        if not raw_text.strip():
            return {"status": "empty", "file": info["original_name"], "record": None}

        # Claude extraction
        fields = _extract_sni_fields_via_claude(raw_text)

        # Python-side normalisation / fallback
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
            "source_file":    info["original_name"],
            "processed_at":   datetime.now(timezone.utc).isoformat(),
        }
        return {"status": "success", "file": info["original_name"], "record": record}

    except Exception as e:
        return {"status": "error", "file": info["original_name"], "error": str(e), "record": None}


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PROCESS FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def process_documents(
    file_infos: list,
    settings: dict,
    max_workers: int = 4,          # lower: each call hits Claude API
    progress_callback=None,
) -> dict:
    """
    Process a list of SNI PDF files → list of structured SNI records.
    Returns result dict compatible with app.py expectations.
    """
    total     = len(file_infos)
    results   = [None] * total
    completed = [0]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_process_single_sni_file, (info, settings)): i
            for i, info in enumerate(file_infos)
        }
        for future in as_completed(future_to_idx):
            idx              = future_to_idx[future]
            results[idx]     = future.result()
            completed[0]    += 1
            if progress_callback:
                progress_callback("extract", completed[0], total, file_infos[idx]["original_name"])

    records        = []
    file_results   = []
    processed_ok   = 0
    failed         = 0

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
        "total_chunks":    processed_ok,   # 1 record = 1 "chunk" in UI terms
        "total_chars":     sum(len(r.get("embedding_text", "")) for r in records),
    }

    return {
        "version":      "2.0",
        "type":         "sni_extraction",
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "settings":     settings,
        "stats":        stats,
        "file_results": file_results,
        "total":        len(records),
        "total_chunks": len(records),
        "data":         records,
    }


# ──────────────────────────────────────────────────────────────────────────────
# process_and_paraphrase — kept for app.py compatibility
# For SNI mode paraphrase is skipped; just returns process result
# ──────────────────────────────────────────────────────────────────────────────

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

    # Also write as JSONL (1 record per line)
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
            "version": "2.0", "type": "sni_extraction", "merged": True,
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
