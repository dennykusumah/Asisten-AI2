# engine.py
"""
DocAI Trainer - Engine
Core processing logic: file extraction, chunking, merging, session management.
Improvements:
  - Support PDF, DOC, DOCX, JPG, PNG, JPEG, WEBP, GIF images (OCR)
  - Up to 200 files, 200 MB per file
  - Parallel processing with ThreadPoolExecutor
  - Auto-paraphrase on process click (without API)
  - Default paraphrase language = auto-detect
"""

import os
import json
import uuid
import shutil
import time
import re
import random
import urllib.request
import urllib.error
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
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE_MB = 200
MAX_FILES = 200

# Indonesian synonyms for paraphrasing
INDONESIAN_SYNONYMS = {
    "menggunakan": ["memakai", "mengaplikasikan", "menerapkan"],
    "membuat": ["menyusun", "merancang", "menghasilkan"],
    "mendapatkan": ["memperoleh", "meraih", "menerima"],
    "melakukan": ["menjalankan", "mengerjakan", "mengaplikasikan"],
    "mempunyai": ["memiliki", "memperoleh", "mengandung"],
    "menunjukkan": ["menampilkan", "memperlihatkan", "mengindikasikan"],
    "menghasilkan": ["memproduksi", "menciptakan", "menyediakan"],
    "mengurangi": ["meminimalkan", "menurunkan", "memperkecil"],
    "meningkatkan": ["menambah", "memperbesar", "mengembangkan"],
    "mengembangkan": ["memajukan", "memperluas", "meningkatkan"],
    "penting": ["signifikan", "krusial", "esensial"],
    "baik": ["bagus", "berkualitas", "memadai"],
    "besar": ["luas", "signifikan", "substansial"],
    "kecil": ["minimal", "sedikit", "terbatas"],
    "cepat": ["sigap", "efisien", "responsif"],
    "mudah": ["sederhana", "praktis", "tidak rumit"],
    "sulit": ["kompleks", "menantang", "rumit"],
    "juga": ["pun", "lagipula", "selain itu"],
    "karena": ["sebab", "akibat", "lantaran"],
    "tetapi": ["namun", "akan tetapi", "meskipun demikian"],
    "dengan": ["melalui", "lewat", "menggunakan"],
    "untuk": ["bagi", "kepada", "demi"],
    "dari": ["asal", "berasal", "pangkal"],
    "dalam": ["di", "pada", "ke dalam"],
    "atau": ["maupun", "ataupun", "bahkan"],
    "dan": ["serta", "dan juga", "lagi pula"],
}

ENGLISH_SYNONYMS = {
    "use": ["utilize", "employ", "apply"],
    "make": ["create", "construct", "build"],
    "get": ["obtain", "acquire", "receive"],
    "do": ["perform", "execute", "conduct"],
    "have": ["possess", "contain", "hold"],
    "show": ["display", "demonstrate", "indicate"],
    "produce": ["generate", "create", "yield"],
    "reduce": ["minimize", "decrease", "lessen"],
    "increase": ["enhance", "boost", "improve"],
    "develop": ["advance", "expand", "grow"],
    "important": ["significant", "crucial", "essential"],
    "good": ["excellent", "quality", "adequate"],
    "big": ["large", "substantial", "significant"],
    "small": ["minimal", "limited", "minor"],
    "fast": ["quick", "rapid", "efficient"],
    "easy": ["simple", "straightforward", "uncomplicated"],
    "difficult": ["complex", "challenging", "hard"],
    "also": ["additionally", "furthermore", "moreover"],
    "because": ["since", "as", "due to"],
    "but": ["however", "nevertheless", "yet"],
    "with": ["using", "through", "by means of"],
    "for": ["to", "in order to", "intended for"],
    "from": ["originating", "derived", "starting"],
    "in": ["within", "inside", "during"],
    "or": ["alternatively", "otherwise", "or else"],
    "and": ["as well as", "along with", "plus"],
}

# ──────────────────────────────────────────────────────────────────────────────
# UTILITY
# ──────────────────────────────────────────────────────────────────────────────

def format_size(byte_count: int) -> str:
    if byte_count == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    val = float(byte_count)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
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
    ensure_dir(d / "chunks")
    return {"session_id": session_id, "path": str(d)}


def list_sessions() -> list:
    sessions = []
    if not UPLOADS_DIR.exists():
        return sessions
    for entry in UPLOADS_DIR.iterdir():
        if not entry.is_dir():
            continue
        stat = entry.stat()
        size = _calc_dir_size(entry)
        file_count = sum(1 for f in entry.rglob("*") if f.is_file())
        meta_path = entry / "metadata.json"
        metadata = None
        if meta_path.exists():
            try:
                metadata = json.loads(meta_path.read_text("utf-8"))
            except Exception:
                pass
        sessions.append({
            "id": entry.name,
            "created_at": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M"),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "modified_ts": stat.st_mtime,
            "file_size": size,
            "file_size_fmt": format_size(size),
            "file_count": file_count,
            "metadata": metadata,
        })
    sessions.sort(key=lambda x: x["modified_ts"], reverse=True)
    return sessions


def get_session_detail(session_id: str) -> Optional[dict]:
    session_path = get_session_dir(session_id)
    if not session_path.exists():
        return None
    structure = {}
    for subdir in ["original", "processed", "chunks"]:
        sub = session_path / subdir
        if sub.exists():
            structure[subdir] = [
                {
                    "name": f.name,
                    "size": f.stat().st_size,
                    "size_fmt": format_size(f.stat().st_size),
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
                for f in sub.iterdir()
                if f.is_file()
            ]
    meta_path = session_path / "metadata.json"
    metadata = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else None
    return {"session_id": session_id, "metadata": metadata, "structure": structure}


def delete_session(session_id: str) -> dict:
    session_path = get_session_dir(session_id)
    if not session_path.exists():
        return {"success": False, "error": "Session not found"}
    size = _calc_dir_size(session_path)
    shutil.rmtree(session_path)
    return {"success": True, "freed_bytes": size, "freed_fmt": format_size(size)}


def cleanup_old_sessions(max_age_hours: int = 24, exclude_id: str = "") -> dict:
    max_age_ms = max_age_hours * 3600 * 1000
    now = time.time() * 1000
    deleted, freed = 0, 0
    if not UPLOADS_DIR.exists():
        return {"deleted": 0, "freed_bytes": 0, "freed_fmt": "0 B"}
    for entry in UPLOADS_DIR.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == exclude_id:
            continue
        age_ms = now - entry.stat().st_mtime * 1000
        if age_ms > max_age_ms:
            size = _calc_dir_size(entry)
            shutil.rmtree(entry)
            freed += size
            deleted += 1
    return {"deleted": deleted, "freed_bytes": freed, "freed_fmt": format_size(freed)}


# ══════════════════════════════════════════════════════════════════════════════
# Hapus SEMUA session (kecuali session aktif)
# ══════════════════════════════════════════════════════════════════════════════

def delete_all_sessions(exclude_id: str = "") -> dict:
    """
    Delete ALL sessions from disk, except the one matching exclude_id.
    Returns count of deleted sessions and total freed bytes.
    """
    deleted, freed = 0, 0
    if not UPLOADS_DIR.exists():
        return {"deleted": 0, "freed_bytes": 0, "freed_fmt": "0 B"}
    for entry in list(UPLOADS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name == exclude_id:
            continue
        size = _calc_dir_size(entry)
        shutil.rmtree(entry)
        freed += size
        deleted += 1
    return {"deleted": deleted, "freed_bytes": freed, "freed_fmt": format_size(freed)}


def _calc_dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


# ──────────────────────────────────────────────────────────────────────────────
# FILE SAVING
# ──────────────────────────────────────────────────────────────────────────────

def save_uploaded_file(session_id: str, uploaded_file) -> dict:
    """Save a Streamlit UploadedFile to disk. Returns file info dict."""
    session_dir = get_session_dir(session_id)
    original_dir = ensure_dir(session_dir / "original")

    safe_name = re.sub(r"[^a-zA-Z0-9._\-]", "_", uploaded_file.name)
    unique_name = f"{int(time.time() * 1000)}_{safe_name}"
    dest = original_dir / unique_name

    content = uploaded_file.read()
    dest.write_bytes(content)

    return {
        "original_name": uploaded_file.name,
        "saved_name": unique_name,
        "path": str(dest),
        "size": len(content),
        "size_fmt": format_size(len(content)),
        "ext": Path(uploaded_file.name).suffix.lower(),
        "session_id": session_id,
    }


# ──────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION  (PDF, DOC, DOCX, TXT, MD, Images)
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_from_file(file_path: str, file_ext: str) -> str:
    """Extract raw text from PDF / DOC / DOCX / TXT / MD / image files."""
    p = Path(file_path)
    ext = file_ext.lower()

    # ── Plain text ──
    if ext in (".txt", ".md"):
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return p.read_text(enc)
            except UnicodeDecodeError:
                continue
        return p.read_bytes().decode("utf-8", errors="replace")

    # ── PDF ──
    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(p))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            extracted = "\n\n".join(pages)
            if len(extracted.strip()) >= 50:
                return extracted
        except ImportError:
            pass
        return _extract_pdf_fallback(p)

    # ── DOCX ──
    elif ext == ".docx":
        try:
            import docx as python_docx
            doc = python_docx.Document(str(p))
            parts = [para.text for para in doc.paragraphs if para.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            parts.append(cell.text.strip())
            return "\n\n".join(parts)
        except ImportError:
            return _extract_docx_fallback(p)

    # ── DOC (legacy) ──
    elif ext == ".doc":
        return _extract_doc_legacy(p)

    # ── Excel XLSX ──
    elif ext == ".xlsx":
        return _extract_excel_text(p, engine="openpyxl")

    # ── Excel XLS (legacy) ──
    elif ext == ".xls":
        return _extract_excel_text(p, engine="xlrd")

    # ── Images (OCR) ──
    elif ext in IMAGE_EXTENSIONS:
        return _extract_image_text(p)

    return ""


def _extract_pdf_fallback(p: Path) -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["pdftotext", str(p), "-"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except Exception:
        pass
    return f"[Cannot extract PDF: {p.name}. Install pypdf or pdftotext]"


def _extract_docx_fallback(p: Path) -> str:
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        texts = []
        with zipfile.ZipFile(str(p)) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for t in tree.findall(".//w:t", ns):
                    if t.text:
                        texts.append(t.text)
        return " ".join(texts)
    except Exception:
        return f"[Cannot extract DOCX: {p.name}. Install python-docx]"


def _extract_doc_legacy(p: Path) -> str:
    """Extract text from legacy .doc files."""
    try:
        import subprocess
        result = subprocess.run(
            ["antiword", str(p)],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except Exception:
        pass

    try:
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "txt:Text", "--outdir", tmpdir, str(p)],
                capture_output=True, timeout=120
            )
            txt_file = Path(tmpdir) / (p.stem + ".txt")
            if txt_file.exists():
                return txt_file.read_text("utf-8", errors="replace")
    except Exception:
        pass

    try:
        raw = p.read_bytes()
        texts = re.findall(rb"[\x20-\x7e]{4,}", raw)
        return " ".join(t.decode("ascii", errors="replace") for t in texts)
    except Exception:
        return f"[Cannot extract DOC: {p.name}. Install antiword or LibreOffice]"


def _extract_excel_text(p: Path, engine: str = "openpyxl") -> str:
    """Extract text from Excel files (.xlsx with openpyxl, .xls with xlrd)."""
    try:
        import pandas as pd
        xl = pd.ExcelFile(str(p), engine=engine)
        parts = []
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            if df.empty:
                continue
            parts.append(f"=== Sheet: {sheet_name} ===")
            # Header row
            parts.append("\t".join(str(c) for c in df.columns))
            # Data rows
            for _, row in df.iterrows():
                row_text = "\t".join("" if (str(v) == "nan") else str(v) for v in row)
                if row_text.strip():
                    parts.append(row_text)
        return "\n".join(parts) if parts else f"[Empty Excel file: {p.name}]"
    except ImportError as e:
        missing = "openpyxl" if engine == "openpyxl" else "xlrd"
        return f"[Cannot extract Excel: install {missing}. Error: {e}]"
    except Exception as e:
        return f"[Cannot extract Excel: {p.name}. Error: {e}]"


def _extract_image_text(p: Path) -> str:
    """Extract text from image using pytesseract OCR."""
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
        return text.strip()
    except Exception as e:
        return f"[Image: {p.name} — Install pytesseract + Tesseract OCR for text extraction. Error: {e}]"


# ──────────────────────────────────────────────────────────────────────────────
# CHUNKING
# ──────────────────────────────────────────────────────────────────────────────

def clean_text(text: str, remove_extra_spaces: bool = True, remove_special: bool = False) -> str:
    if remove_extra_spaces:
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
    if remove_special:
        text = re.sub(r"[^\w\s.,!?;:()\-\'\"\n]", "", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    method: str = "tokens",
) -> list:
    text = text.strip()
    if not text:
        return []

    if method == "paragraphs":
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks, current = [], ""
        for para in paras:
            if len((current + " " + para).split()) <= chunk_size:
                current = (current + " " + para).strip()
            else:
                if current:
                    chunks.append(current)
                current = para
        if current:
            chunks.append(current)
        return chunks

    elif method == "sentences":
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks, current_words = [], []
        for sent in sentences:
            words = sent.split()
            if len(current_words) + len(words) <= chunk_size:
                current_words.extend(words)
            else:
                if current_words:
                    chunks.append(" ".join(current_words))
                current_words = current_words[-overlap:] + words if overlap else words
        if current_words:
            chunks.append(" ".join(current_words))
        return chunks

    else:  # tokens (word-based)
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            end = min(i + chunk_size, len(words))
            chunks.append(" ".join(words[i:end]))
            i += chunk_size - overlap
            if i < 0:
                i = chunk_size
        return chunks


def _process_single_file(args) -> dict:
    """Process a single file — used by parallel executor."""
    info, settings = args
    chunk_size = int(settings.get("chunk_size", 512))
    overlap = int(settings.get("overlap", 50))
    method = settings.get("chunk_method", "tokens")
    remove_spaces = settings.get("remove_extra_spaces", True)
    remove_special = settings.get("remove_special_chars", False)
    source_tag = settings.get("source_tag", "")
    output_format = settings.get("output_format", "training")

    try:
        raw = extract_text_from_file(info["path"], info["ext"])
        if not raw.strip():
            return {
                "file_result": {**info, "status": "empty", "chunks": 0},
                "items": [],
                "chars": 0,
            }

        cleaned = clean_text(raw, remove_spaces, remove_special)
        chunks = chunk_text(cleaned, chunk_size, overlap, method)
        items = []

        for idx, chunk in enumerate(chunks):
            if output_format == "qa":
                item = {"instruction": "", "input": chunk, "output": ""}
            elif output_format == "messages":
                item = {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": chunk},
                        {"role": "assistant", "content": ""},
                    ]
                }
            else:
                item = {
                    "id": f"{info['session_id']}_tmp_{idx:04d}",
                    "text": chunk,
                    "source": source_tag or info["original_name"],
                    "chunk_index": idx + 1,
                    "total_chunks_in_doc": len(chunks),
                }
            items.append(item)

        return {
            "file_result": {**info, "status": "success", "chunks": len(chunks)},
            "items": items,
            "chars": len(cleaned),
        }

    except Exception as e:
        return {
            "file_result": {**info, "status": "error", "error": str(e), "chunks": 0},
            "items": [],
            "chars": 0,
        }


def process_documents(
    file_infos: list,
    settings: dict,
    max_workers: int = 12,
    progress_callback=None,
) -> dict:
    """Process a list of saved file infos into training data using parallel workers."""
    all_results = [None] * len(file_infos)
    total = len(file_infos)
    completed_count = [0]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_process_single_file, (info, settings)): i
            for i, info in enumerate(file_infos)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            all_results[idx] = future.result()
            completed_count[0] += 1
            if progress_callback:
                progress_callback("extract", completed_count[0], total, file_infos[idx]["original_name"])

    all_items = []
    file_results = []
    stats = {
        "total_files": len(file_infos),
        "processed_files": 0,
        "failed_files": 0,
        "total_chunks": 0,
        "total_chars": 0,
    }

    for res in all_results:
        if res is None:
            continue
        file_results.append(res["file_result"])
        all_items.extend(res["items"])
        if res["file_result"]["status"] == "success":
            stats["processed_files"] += 1
            stats["total_chunks"] += res["file_result"]["chunks"]
            stats["total_chars"] += res["chars"]
        else:
            stats["failed_files"] += 1

    session_id = file_infos[0]["session_id"] if file_infos else "sess"
    for i, item in enumerate(all_items):
        if isinstance(item, dict) and "id" in item:
            item["id"] = f"{session_id}_{i + 1:04d}"

    return {
        "version": "1.0",
        "type": "training",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
        "stats": stats,
        "file_results": file_results,
        "total": len(all_items),
        "total_chunks": len(all_items),
        "data": all_items,
    }


# ──────────────────────────────────────────────────────────────────────────────
# PARAPHRASE ENGINE (WITHOUT API)
# ──────────────────────────────────────────────────────────────────────────────

# Words that must NEVER be replaced during paraphrasing (normative/modal terms)
PROTECTED_WORDS = {
    # English normative
    "shall", "should", "must", "may", "can", "will", "would",
    # Indonesian normative
    "harus", "sebaiknya", "wajib", "boleh", "dapat", "tidak boleh",
    "dilarang", "dipersyaratkan", "direkomendasikan", "diperbolehkan",
}


def _replace_synonyms(text: str, synonyms_dict: dict, replace_prob: float = 0.7) -> str:
    """Replace words with their synonyms based on probability, preserving protected words."""
    words = text.split()
    for i, word in enumerate(words):
        clean_word = re.sub(r'[^\w]', '', word.lower())
        # Skip protected normative/modal words — never replace them
        if clean_word in PROTECTED_WORDS:
            continue
        if clean_word in synonyms_dict and random.random() < replace_prob:
            synonyms = synonyms_dict[clean_word]
            synonym = random.choice(synonyms)
            punctuation = re.findall(r'[^\w]', word)
            if punctuation:
                words[i] = synonym + punctuation[-1] if punctuation[-1] else synonym
            else:
                words[i] = synonym
    return " ".join(words)


def _rephrase_sentence_structure(text: str) -> str:
    """Slightly modify sentence structure without changing meaning."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    rephrased = []

    for sentence in sentences:
        if len(sentence.split()) < 5:
            rephrased.append(sentence)
            continue

        # Don't restructure sentences containing normative/modal words
        sentence_lower = sentence.lower()
        has_protected = any(pw in sentence_lower.split() or
                            f" {pw} " in f" {sentence_lower} "
                            for pw in PROTECTED_WORDS)
        if has_protected:
            rephrased.append(sentence)
            continue

        if ',' in sentence:
            parts = sentence.split(',', 1)
            if len(parts) == 2 and random.random() < 0.3:
                sentence = f"{parts[1].strip()} {parts[0].strip()}"
                sentence = sentence[0].upper() + sentence[1:]

        rephrased.append(sentence)

    return " ".join(rephrased)


def _add_transitional_phrases(text: str) -> str:
    """Add or modify transitional phrases."""
    indonesian_transitions = [
        "Selain itu, ", "Sebagai tambahan, ", "Di sisi lain, ",
        "Dalam konteks ini, ", "Sehubungan dengan itu, ", "Pada dasarnya, "
    ]
    english_transitions = [
        "Additionally, ", "Furthermore, ", "On the other hand, ",
        "In this context, ", "Related to this, ", "Essentially, "
    ]

    if len(text.split()) < 30:
        return text

    if random.random() < 0.2:
        if any(word in text.lower() for word in ["dan", "yang", "dengan", "untuk", "dari"]):
            transition = random.choice(indonesian_transitions)
        else:
            transition = random.choice(english_transitions)
        text = transition + text

    return text


def paraphrase_text(text: str, language: str = "auto") -> str:
    """
    Paraphrase text without using an API.
    Default language is 'auto' for auto-detection.
    """
    if not text.strip():
        return text

    if language == "id":
        synonyms = INDONESIAN_SYNONYMS
    elif language == "en":
        synonyms = ENGLISH_SYNONYMS
    else:
        # Auto-detect language (simple heuristic)
        if any(word in text.lower() for word in ["dan", "yang", "dengan", "untuk", "dari"]):
            synonyms = INDONESIAN_SYNONYMS
        else:
            synonyms = ENGLISH_SYNONYMS

    paraphrased = _replace_synonyms(text, synonyms)
    paraphrased = _rephrase_sentence_structure(paraphrased)
    paraphrased = _add_transitional_phrases(paraphrased)

    return paraphrased


def _paraphrase_item_task(args) -> tuple:
    """Returns (index, paraphrased_item)."""
    import copy
    idx, item, language = args
    item = copy.deepcopy(item)
    try:
        if "text" in item:
            item["text"] = paraphrase_text(item["text"], language)
        elif "input" in item:
            item["input"] = paraphrase_text(item["input"], language)
        elif "messages" in item:
            for msg in item["messages"]:
                if msg.get("role") == "user" and msg.get("content"):
                    msg["content"] = paraphrase_text(msg["content"], language)
    except Exception:
        pass
    return idx, item


def paraphrase_dataset(
    result: dict,
    language: str = "auto",
    progress_callback=None,
    max_workers: int = 10,
) -> dict:
    """
    Paraphrase every text field in result['data'] using parallel processing.
    Default language is 'auto' for auto-detection.
    """
    import copy
    new_result = copy.deepcopy(result)
    items = new_result.get("data", [])
    total = len(items)
    paraphrased_items = [None] * total

    completed_count = [0]
    tasks = [(i, item, language) for i, item in enumerate(items)]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_paraphrase_item_task, task): task[0] for task in tasks}
        for future in as_completed(futures):
            idx, para_item = future.result()
            paraphrased_items[idx] = para_item
            completed_count[0] += 1
            if progress_callback:
                progress_callback(completed_count[0], total)

    if progress_callback:
        progress_callback(total, total)

    new_result["data"] = paraphrased_items
    new_result["paraphrased"] = True
    new_result["paraphrase_language"] = language
    new_result["paraphrased_at"] = datetime.now(timezone.utc).isoformat()
    return new_result


def process_and_paraphrase(
    file_infos: list,
    settings: dict,
    language: str = "auto",
    progress_callback=None,
) -> dict:
    """
    One-shot: extract text from files, chunk, then immediately paraphrase.
    Default language is 'auto' for auto-detection.
    progress_callback(stage: str, current: int, total: int)
    """
    if progress_callback:
        progress_callback("extract", 0, len(file_infos), "")

    def _extract_cb(stage, cur, tot, fname=""):
        if progress_callback:
            progress_callback(stage, cur, tot, fname)

    result = process_documents(file_infos, settings, max_workers=12, progress_callback=_extract_cb)

    if progress_callback:
        progress_callback("extract", len(file_infos), len(file_infos), "")

    def _para_cb(current, total):
        if progress_callback:
            progress_callback("paraphrase", current, total, "")

    para_result = paraphrase_dataset(result, language, _para_cb, max_workers=10)
    return para_result


# ──────────────────────────────────────────────────────────────────────────────
# SAVE PROCESSED DATA
# ──────────────────────────────────────────────────────────────────────────────

def save_processed_data(session_id: str, data: dict, settings: dict) -> dict:
    session_dir = get_session_dir(session_id)
    processed_dir = ensure_dir(session_dir / "processed")
    chunks_dir = ensure_dir(session_dir / "chunks")

    output_path = processed_dir / "output.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

    chunk_count = 0
    if isinstance(data.get("data"), list):
        def _write_chunk(args):
            i, item = args
            (chunks_dir / f"chunk_{i + 1:03d}.json").write_text(
                json.dumps(item, ensure_ascii=False, indent=2), "utf-8"
            )
            return i

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(_write_chunk, enumerate(data["data"])))
            chunk_count = len(results)

    metadata = {
        "session_id": session_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
        "stats": {
            "total_chunks": chunk_count,
            "output_file": str(output_path),
            "chunks_directory": str(chunks_dir),
        },
    }
    (session_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), "utf-8"
    )

    return {
        "success": True,
        "processed_path": str(output_path),
        "chunks_saved": chunk_count,
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
    stats = {
        "files_count": len(file_contents),
        "merge_mode": merge_mode,
        "item_counts": [],
    }

    if merge_mode == "data":
        all_items = []
        for f in file_contents:
            items = f["content"].get("data", [])
            all_items.extend(items)
            stats["item_counts"].append({"file": f["name"], "items": len(items)})
        merged = {
            "version": "1.0",
            "type": "training",
            "merged": True,
            "merged_at": datetime.now(timezone.utc).isoformat(),
            "source_files": [f["name"] for f in file_contents],
            "total": len(all_items),
            "total_chunks": len(all_items),
            "data": all_items,
        }

    elif merge_mode == "array":
        all_items = []
        for f in file_contents:
            c = f["content"]
            if isinstance(c, list):
                arr = c
            elif isinstance(c, dict) and isinstance(c.get("data"), list):
                arr = c["data"]
            elif isinstance(c, dict):
                arr = [c]
            else:
                arr = []
            all_items.extend(arr)
            stats["item_counts"].append({"file": f["name"], "items": len(arr)})
        merged = all_items

    else:
        merged = {
            "_merged": True,
            "_merged_at": datetime.now(timezone.utc).isoformat(),
            "_source_files": [f["name"] for f in file_contents],
        }
        for f in file_contents:
            src = f["content"] if isinstance(f["content"], dict) else {"_array_data": f["content"]}
            merged.update(src)
            stats["item_counts"].append({"file": f["name"], "keys": len(src)})

    return {"merged": merged, "merge_mode": merge_mode, "stats": stats}


# ══════════════════════════════════════════════════════════════════════════════
# SNI CORE EXTRACTOR  — output: sni_core.jsonl
# ══════════════════════════════════════════════════════════════════════════════

import urllib.request
import urllib.error
import base64

_SNI_SYSTEM_PROMPT = """\
Kamu adalah ekstraksi data SNI (Standar Nasional Indonesia) yang sangat presisi.
Tugasmu: baca teks/gambar dokumen SNI dan kembalikan HANYA satu JSON object (tanpa markdown, tanpa penjelasan).

Format wajib (semua field harus ada, string kosong jika tidak tersedia):
{
  "sni_id": "<nomor tanpa 'SNI', misal '01-3701-1995' atau '22739_2024'>",
  "no_sni": "<nomor lengkap, misal 'SNI 01-3701-1995' atau 'SNI ISO 22739:2024'>",
  "judul": "<judul bahasa Indonesia, tanpa tanda baca trailing>",
  "tahun": <integer tahun, misal 2024>,
  "kategori": "<ICS atau bidang, misal 'Pangan', 'Teknologi Informasi', 'Konstruksi'>",
  "ruang_lingkup": "<ringkasan 1-2 kalimat max 150 karakter>",
  "persyaratan": "<Parameter = Nilai Satuan harus/sebaiknya | Parameter2 = Nilai2 Satuan2 harus | ...> atau '-' jika tidak ada",
  "metode_uji": "<Parameter = Kode/Nama metode kondisi | ...> atau '-' jika tidak ada",
  "keywords": "<max 20 kata, wajib: parameter, angka, satuan, kode SNI; buang kata umum>",
  "halaman": <integer jumlah halaman, 0 jika tidak diketahui>
}

Aturan ketat:
- persyaratan: ambil SEMUA parameter yang punya angka + satuan + kata maks/min/harus/sebaiknya. Format "Parameter = Nilai Satuan harus/sebaiknya". Pisah " | ".
- metode_uji: format "Parameter = Kode SNI Nama metode kondisi". Pisah " | ". Tulis '-' jika tidak ada metode uji eksplisit.
- keywords: max 20 kata. Wajib ada angka, satuan, kode SNI terkait. Buang: batas mutu persyaratan standar nasional indonesia SNI.
- ruang_lingkup: potong di 150 karakter, kalimat utuh.
- Jangan tambah field lain. Jangan wrap dalam array. Output HANYA JSON object murni.
"""

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_SNI_MODEL = "claude-sonnet-4-20250514"


def _call_claude_for_sni(text: str = "", image_b64: str = "", media_type: str = "image/png") -> dict:
    """
    Call Claude API to extract SNI fields.
    Sends either text or image (base64) or both.
    Returns parsed dict or raises on error.
    """
    content = []
    if image_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": image_b64},
        })
    if text.strip():
        content.append({"type": "text", "text": f"Dokumen SNI:\n\n{text[:15000]}"})
    if not content:
        raise ValueError("No content to send to Claude API")

    payload = json.dumps({
        "model": _SNI_MODEL,
        "max_tokens": 1000,
        "system": _SNI_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": content}],
    }).encode("utf-8")

    req = urllib.request.Request(
        _ANTHROPIC_API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    raw = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            raw += block["text"]

    # Strip markdown code fences if Claude wrapped it anyway
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw.strip())


def _file_to_b64(path: Path) -> tuple[str, str]:
    """Return (base64_data, media_type) for image files."""
    ext = path.suffix.lower()
    mt_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".webp": "image/webp", ".gif": "image/gif"}
    media_type = mt_map.get(ext, "image/png")
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


def extract_sni_from_file(file_info: dict) -> dict:
    """
    Extract SNI fields from a single file.
    Returns the sni_core dict or a dict with '_error' key.
    """
    p = Path(file_info["path"])
    ext = file_info["ext"].lower()

    try:
        if ext in IMAGE_EXTENSIONS:
            b64, mt = _file_to_b64(p)
            result = _call_claude_for_sni(image_b64=b64, media_type=mt)
        elif ext == ".pdf":
            # Try text extraction first; fall back to first-page image via pdf2image
            text = extract_text_from_file(file_info["path"], ext)
            if len(text.strip()) >= 100:
                result = _call_claude_for_sni(text=text)
            else:
                # pdf2image fallback: send first page as image
                try:
                    from pdf2image import convert_from_path
                    pages = convert_from_path(str(p), first_page=1, last_page=1, dpi=150)
                    if pages:
                        import io
                        buf = io.BytesIO()
                        pages[0].save(buf, format="PNG")
                        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                        result = _call_claude_for_sni(image_b64=b64, media_type="image/png")
                    else:
                        result = _call_claude_for_sni(text=text)
                except ImportError:
                    result = _call_claude_for_sni(text=text)
        else:
            text = extract_text_from_file(file_info["path"], ext)
            result = _call_claude_for_sni(text=text)

        # Normalise required keys
        defaults = {
            "sni_id": "", "no_sni": "", "judul": "", "tahun": 0,
            "kategori": "", "ruang_lingkup": "", "persyaratan": "-",
            "metode_uji": "-", "keywords": "", "halaman": 0,
        }
        for k, v in defaults.items():
            if k not in result:
                result[k] = v

        result["_source_file"] = file_info["original_name"]
        return result

    except Exception as e:
        return {
            "_error": str(e),
            "_source_file": file_info["original_name"],
            "sni_id": "", "no_sni": "", "judul": "",
            "tahun": 0, "kategori": "", "ruang_lingkup": "",
            "persyaratan": "-", "metode_uji": "-",
            "keywords": "", "halaman": 0,
        }


def process_sni_documents(
    file_infos: list,
    max_workers: int = 4,
    progress_callback=None,
) -> dict:
    """
    Process a list of SNI documents in parallel.
    Returns dict with 'records' (list of sni_core dicts), 'stats'.
    """
    total = len(file_infos)
    results = [None] * total
    completed = [0]

    def _task(args):
        idx, info = args
        return idx, extract_sni_from_file(info)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_task, (i, info)): i for i, info in enumerate(file_infos)}
        for future in as_completed(futures):
            idx, res = future.result()
            results[idx] = res
            completed[0] += 1
            if progress_callback:
                progress_callback(completed[0], total, res.get("_source_file", ""))

    records = [r for r in results if r is not None]
    ok = [r for r in records if "_error" not in r or not r.get("_error")]
    err = [r for r in records if r.get("_error")]

    return {
        "records": records,
        "stats": {
            "total": total,
            "success": len(ok),
            "error": len(err),
            "errors": [{"file": r["_source_file"], "error": r["_error"]} for r in err],
        },
    }


def build_sni_jsonl(records: list) -> str:
    """
    Convert list of sni_core dicts to JSONL string.
    Each line = 1 JSON object. No array, no trailing comma.
    Strips internal '_source_file' key from output.
    """
    _CORE_KEYS = ["sni_id", "no_sni", "judul", "tahun", "kategori",
                  "ruang_lingkup", "persyaratan", "metode_uji", "keywords", "halaman"]
    lines = []
    for rec in records:
        obj = {k: rec.get(k, "" if k not in ("tahun", "halaman") else 0) for k in _CORE_KEYS}
        lines.append(json.dumps(obj, ensure_ascii=False))
    return "\n".join(lines)
