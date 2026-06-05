"""
engine.py — Empat engine pemrosesan dokumen PDF menggunakan Claude API
"""

import re
import json
import base64
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"


# ─────────────────────────────────────────────
# Utilitas: ekstrak teks dari PDF (text + OCR)
# ─────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Ekstrak teks dari PDF. Jika scanned, gunakan OCR via PyMuPDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = []

    for page in doc:
        text = page.get_text("text").strip()
        if text:
            full_text.append(text)
        else:
            # Fallback ke OCR
            pix = page.get_pixmap(dpi=200)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            ocr_text = pytesseract.image_to_string(img, lang="ind+eng")
            if ocr_text.strip():
                full_text.append(ocr_text.strip())

    doc.close()
    return "\n\n".join(full_text)


def pdf_to_base64_pages(pdf_bytes: bytes, max_pages: int = 10) -> list[dict]:
    """Konversi halaman PDF ke base64 image untuk vision API."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    total = min(len(doc), max_pages)

    for i in range(total):
        page = doc[i]
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        b64 = base64.standard_b64encode(img_data).decode("utf-8")
        pages.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})

    doc.close()
    return pages


def call_claude(system_prompt: str, user_content, max_tokens: int = 2048) -> str:
    """Helper untuk memanggil Claude API."""
    if isinstance(user_content, str):
        user_content = [{"type": "text", "text": user_content}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}]
    )
    return response.content[0].text.strip()


# ─────────────────────────────────────────────
# ENGINE 1 — Identifikasi Daftar Isi
# ─────────────────────────────────────────────

def engine1_daftar_isi(pdf_bytes: bytes) -> str:
    """
    Mengidentifikasi daftar isi dokumen PDF.
    Menghilangkan titik-titik (......) dan nomor halaman.
    Tiap pasal dipisahkan dengan tanda titik koma (;).
    Hasil disimpan di cache (dikembalikan sebagai string).
    """
    text = extract_text_from_pdf(pdf_bytes)

    system = (
        "Kamu adalah asisten yang mengidentifikasi daftar isi dari sebuah dokumen. "
        "Tugasmu: temukan semua item daftar isi, hilangkan titik-titik (......) dan nomor halaman, "
        "lalu gabungkan seluruh item dengan pemisah titik koma (;). "
        "Keluarkan HANYA daftar isi yang sudah dibersihkan tanpa penjelasan tambahan."
    )

    prompt = (
        f"Berikut adalah teks dokumen:\n\n{text[:8000]}\n\n"
        "Identifikasi daftar isi dari teks di atas. "
        "Hilangkan semua titik-titik (......) dan nomor halaman. "
        "Pisahkan tiap pasal/item dengan tanda titik koma (;). "
        "Jika tidak ada daftar isi, tulis: TIDAK ADA DAFTAR ISI."
    )

    result = call_claude(system, prompt, max_tokens=1500)
    return result


# ─────────────────────────────────────────────
# ENGINE 2 — Ekstraksi Keywords
# ─────────────────────────────────────────────

def engine2_keywords(pdf_bytes: bytes) -> str:
    """
    Menghasilkan keywords dari isi dokumen dalam Bahasa Indonesia.
    Hasil disimpan di cache sebagai string dipisah koma.
    """
    text = extract_text_from_pdf(pdf_bytes)

    system = (
        "Kamu adalah asisten ekstraksi kata kunci dari dokumen. "
        "Tugasmu: baca isi dokumen dan hasilkan daftar kata kunci (keywords) penting "
        "dalam Bahasa Indonesia. "
        "Keluarkan HANYA daftar kata kunci dipisahkan koma, tanpa penjelasan tambahan."
    )

    prompt = (
        f"Teks dokumen:\n\n{text[:8000]}\n\n"
        "Buat daftar kata kunci penting dari dokumen ini dalam Bahasa Indonesia. "
        "Keluarkan kata kunci dipisahkan dengan koma. "
        "Fokus pada istilah teknis, topik utama, konsep kunci, dan nama entitas penting."
    )

    result = call_claude(system, prompt, max_tokens=800)
    return result


# ─────────────────────────────────────────────
# ENGINE 3 — Ringkasan Dokumen
# ─────────────────────────────────────────────

def engine3_ringkasan(pdf_bytes: bytes) -> str:
    """
    Meringkas isi dokumen dalam Bahasa Indonesia.
    Jika dokumen dua bahasa (Indonesia & Inggris), hanya bagian Indonesia yang dirangkum.
    Hasil disimpan di cache.
    """
    text = extract_text_from_pdf(pdf_bytes)

    system = (
        "Kamu adalah asisten peringkas dokumen berbahasa Indonesia. "
        "Jika dokumen mengandung dua bahasa (Indonesia dan Inggris), "
        "fokuskan ringkasan HANYA pada bagian berbahasa Indonesia. "
        "Semua output ringkasan harus dalam Bahasa Indonesia. "
        "Keluarkan HANYA ringkasan tanpa penjelasan prosedur."
    )

    prompt = (
        f"Teks dokumen:\n\n{text[:10000]}\n\n"
        "Buat ringkasan komprehensif dari dokumen ini. "
        "Jika dokumen dua bahasa (Indonesia dan Inggris), ringkas HANYA bagian berbahasa Indonesia. "
        "Semua ringkasan harus dalam Bahasa Indonesia. "
        "Sertakan: tujuan dokumen, poin-poin utama, dan kesimpulan."
    )

    result = call_claude(system, prompt, max_tokens=2000)
    return result


# ─────────────────────────────────────────────
# ENGINE 4 — Identifikasi, Paraphrase & JSONL
# ─────────────────────────────────────────────

def engine4_jsonl(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """
    Mengidentifikasi dokumen (dengan OCR jika perlu), mem-paraphrase isi,
    dan mengubahnya ke format JSONL untuk training dataset.
    Format: {"prompt": <pertanyaan/instruksi>, "completion": <jawaban/isi>}
    """
    text = extract_text_from_pdf(pdf_bytes)

    # Deteksi dokumen kosong / scanned murni
    if not text.strip():
        return json.dumps({"error": "Tidak dapat mengekstrak teks dari dokumen."}, ensure_ascii=False)

    system = (
        "Kamu adalah asisten yang membuat training dataset dalam format JSONL. "
        "Tugasmu: baca dokumen, identifikasi jenis dan topik dokumen, "
        "lalu buat pasangan prompt-completion yang merepresentasikan isi dokumen "
        "dalam format JSONL (satu JSON per baris). "
        "Setiap baris harus berformat: {\"prompt\": \"...\", \"completion\": \"...\"} "
        "Buat minimal 5 pasangan yang beragam (definisi, penjelasan, contoh, prosedur, kesimpulan). "
        "Keluarkan HANYA baris-baris JSONL tanpa penjelasan tambahan, tanpa markdown, tanpa kode blok."
    )

    prompt = (
        f"Nama file: {filename}\n\n"
        f"Isi dokumen:\n\n{text[:10000]}\n\n"
        "Buat training dataset JSONL dari dokumen ini. "
        "Paraphrase konten secara alami. "
        "Tiap baris harus berupa JSON valid dengan key 'prompt' dan 'completion'. "
        "Gunakan Bahasa Indonesia untuk prompt dan completion. "
        "Pastikan setiap baris adalah JSON lengkap yang valid."
    )

    result = call_claude(system, prompt, max_tokens=3000)

    # Validasi & bersihkan output JSONL
    jsonl_lines = []
    for line in result.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Hapus prefix nomor seperti "1." atau "- "
        line = re.sub(r'^[\d]+\.\s*', '', line)
        line = re.sub(r'^[-•]\s*', '', line)
        try:
            obj = json.loads(line)
            if "prompt" in obj and "completion" in obj:
                jsonl_lines.append(json.dumps(obj, ensure_ascii=False))
        except json.JSONDecodeError:
            pass  # Skip baris yang tidak valid

    if not jsonl_lines:
        # Fallback: minta ulang dalam format yang lebih ketat
        fallback_prompt = (
            f"Buat 5 baris JSONL dari teks berikut. "
            f"SETIAP baris harus berformat tepat: {{\"prompt\": \"pertanyaan\", \"completion\": \"jawaban\"}}\n\n"
            f"Teks: {text[:3000]}"
        )
        fallback = call_claude(system, fallback_prompt, max_tokens=2000)
        for line in fallback.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if "prompt" in obj and "completion" in obj:
                    jsonl_lines.append(json.dumps(obj, ensure_ascii=False))
            except json.JSONDecodeError:
                pass

    return "\n".join(jsonl_lines)
