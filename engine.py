"""
engine.py — 4 engine pemrosesan dokumen PDF menggunakan Claude API
"""

import re
import json
import fitz          # PyMuPDF
import pytesseract
from PIL import Image
import io
import anthropic

client = anthropic.Anthropic()
MODEL  = "claude-sonnet-4-20250514"


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
            # Fallback OCR
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr  = pytesseract.image_to_string(img, lang="ind+eng")
            if ocr.strip():
                pages_text.append(ocr.strip())

    doc.close()
    return "\n\n".join(pages_text)


def call_claude(system: str, user_text: str, max_tokens: int = 2048) -> str:
    """Panggil Claude API, kembalikan teks respons."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    return resp.content[0].text.strip()


def _truncate(text: str, limit: int = 9000) -> str:
    return text[:limit]


# ─────────────────────────────────────────────
# ENGINE 1 — Identifikasi Daftar Isi
# ─────────────────────────────────────────────

def engine1_daftar_isi(pdf_bytes: bytes) -> str:
    """
    Identifikasi daftar isi dokumen.
    Hapus titik-titik (......) dan nomor halaman.
    Tiap item dipisahkan dengan titik koma (;).
    """
    text = extract_text_from_pdf(pdf_bytes)

    system = (
        "Kamu adalah asisten yang mengidentifikasi daftar isi dari sebuah dokumen. "
        "Tugasmu: temukan semua item daftar isi, hapus titik-titik (......) dan nomor halaman, "
        "gabungkan dengan pemisah titik koma (;). "
        "Keluarkan HANYA daftar isi yang sudah dibersihkan, tanpa penjelasan tambahan."
    )
    prompt = (
        f"Teks dokumen:\n\n{_truncate(text)}\n\n"
        "Identifikasi daftar isi. Hapus titik-titik dan nomor halaman. "
        "Pisahkan tiap item dengan (;). "
        "Jika tidak ada daftar isi, tulis: TIDAK ADA DAFTAR ISI."
    )
    return call_claude(system, prompt, max_tokens=1500)


# ─────────────────────────────────────────────
# ENGINE 2 — Ekstraksi Keywords
# ─────────────────────────────────────────────

def engine2_keywords(pdf_bytes: bytes) -> str:
    """
    Hasilkan daftar keywords dari isi dokumen dalam Bahasa Indonesia,
    dipisahkan koma.
    """
    text = extract_text_from_pdf(pdf_bytes)

    system = (
        "Kamu adalah asisten ekstraksi kata kunci dari dokumen. "
        "Hasilkan daftar kata kunci penting dalam Bahasa Indonesia. "
        "Keluarkan HANYA daftar kata kunci dipisahkan koma, tanpa penjelasan tambahan."
    )
    prompt = (
        f"Teks dokumen:\n\n{_truncate(text)}\n\n"
        "Buat daftar kata kunci penting dalam Bahasa Indonesia, dipisahkan koma. "
        "Fokus pada: istilah teknis, topik utama, konsep kunci, nama entitas penting."
    )
    return call_claude(system, prompt, max_tokens=800)


# ─────────────────────────────────────────────
# ENGINE 3 — Ringkasan Dokumen
# ─────────────────────────────────────────────

def engine3_ringkasan(pdf_bytes: bytes) -> str:
    """
    Ringkas isi dokumen dalam Bahasa Indonesia.
    Dokumen dwibahasa (Indonesia+Inggris) → hanya bagian Indonesia yang dirangkum.
    """
    text = extract_text_from_pdf(pdf_bytes)

    system = (
        "Kamu adalah asisten peringkas dokumen. "
        "Jika dokumen mengandung dua bahasa (Indonesia dan Inggris), "
        "fokuskan ringkasan HANYA pada bagian berbahasa Indonesia. "
        "Semua output ringkasan harus dalam Bahasa Indonesia. "
        "Keluarkan HANYA ringkasan tanpa penjelasan prosedur."
    )
    prompt = (
        f"Teks dokumen:\n\n{_truncate(text, 10000)}\n\n"
        "Buat ringkasan komprehensif. Jika dokumen dwibahasa, ringkas HANYA bagian Indonesia. "
        "Sertakan: tujuan dokumen, poin-poin utama, dan kesimpulan. "
        "Semua dalam Bahasa Indonesia."
    )
    return call_claude(system, prompt, max_tokens=2000)


# ─────────────────────────────────────────────
# ENGINE 4 — Identifikasi, Paraphrase → JSONL
# ─────────────────────────────────────────────

def engine4_jsonl(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """
    Identifikasi dokumen (dengan OCR fallback), paraphrase isi,
    konversi ke format JSONL training dataset.
    Format per baris: {"prompt": "...", "completion": "..."}
    """
    text = extract_text_from_pdf(pdf_bytes)

    if not text.strip():
        return json.dumps(
            {"prompt": f"Apa isi dari {filename}?",
             "completion": "Dokumen tidak dapat dibaca atau kosong."},
            ensure_ascii=False
        )

    system = (
        "Kamu adalah asisten pembuat training dataset JSONL. "
        "Baca dokumen, identifikasi jenis dan topiknya, "
        "lalu buat pasangan prompt-completion yang merepresentasikan isi dokumen. "
        "Setiap baris berformat tepat: {\"prompt\": \"...\", \"completion\": \"...\"} "
        "Buat minimal 8 pasangan beragam: definisi, penjelasan, contoh, prosedur, "
        "perbandingan, analisis, kesimpulan, konteks. "
        "Keluarkan HANYA baris-baris JSONL valid, tanpa markdown, tanpa penjelasan, "
        "tanpa nomor, tanpa kode blok."
    )
    prompt = (
        f"Nama file: {filename}\n\n"
        f"Isi dokumen:\n\n{_truncate(text, 10000)}\n\n"
        "Buat training dataset JSONL. "
        "Paraphrase secara alami dalam Bahasa Indonesia. "
        "Tiap baris: JSON valid satu baris dengan key 'prompt' dan 'completion'."
    )

    raw = call_claude(system, prompt, max_tokens=3500)

    # Bersihkan & validasi output JSONL
    jsonl_lines = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Hapus prefix angka/simbol
        line = re.sub(r'^[\d]+[.)]\s*', '', line)
        line = re.sub(r'^[-•*]\s*', '', line)
        # Hapus markdown code fence
        if line.startswith("```"):
            continue
        try:
            obj = json.loads(line)
            if "prompt" in obj and "completion" in obj:
                jsonl_lines.append(json.dumps(obj, ensure_ascii=False))
        except json.JSONDecodeError:
            pass

    # Fallback jika parsing gagal
    if not jsonl_lines:
        fallback_sys = (
            "Keluarkan HANYA baris JSON valid. Tidak ada teks lain. "
            "Format: {\"prompt\": \"pertanyaan\", \"completion\": \"jawaban\"}"
        )
        fallback_prompt = (
            "Buat 5 baris JSONL dari teks ini. "
            "Setiap baris harus valid JSON satu baris.\n\n"
            f"{_truncate(text, 3000)}"
        )
        raw2 = call_claude(fallback_sys, fallback_prompt, max_tokens=2000)
        for line in raw2.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("```"):
                continue
            try:
                obj = json.loads(line)
                if "prompt" in obj and "completion" in obj:
                    jsonl_lines.append(json.dumps(obj, ensure_ascii=False))
            except json.JSONDecodeError:
                pass

    return "\n".join(jsonl_lines)
