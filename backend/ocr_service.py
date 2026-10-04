# CareVoice OCR & Prescription AI Parsing Service
import os
import json
import base64
import sys
import re
from io import BytesIO
from functools import lru_cache
sys.path.append('..')
import pypdf
from PIL import Image
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
@lru_cache(maxsize=1)
def get_ocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ModuleNotFoundError as exc:
        missing_module = exc.name or "an OCR dependency"
        raise RuntimeError(
            f"RapidOCR dependency '{missing_module}' is unavailable. "
            "Rebuild the deployment from requirements.txt and check its Python version."
        ) from exc
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            f"RapidOCR could not load ({type(exc).__name__}: {exc}). "
            "Check the deployment build logs and Python version."
        ) from exc
    return RapidOCR()


def extract_text_from_pil_image(image):
    vision_text = extract_handwritten_text_with_vision(image)
    if vision_text:
        return vision_text

    import numpy as np

    image_bgr = np.asarray(image.convert("RGB"))[:, :, ::-1].copy()
    result, _ = get_ocr_engine()(image_bgr)
    if not result:
        return ""
    return "\n".join(row[1].strip() for row in result if len(row) > 1 and row[1].strip())

def get_groq_client():
    if GROQ_API_KEY:
        try:
            return Groq(api_key=GROQ_API_KEY)
        except Exception:
            return None
    return None


def extract_handwritten_text_with_vision(image):
    client = get_groq_client()
    if not client:
        return ""

    try:
        api_image = image.convert("RGB").copy()
        api_image.thumbnail((2200, 2200))
        image_buffer = BytesIO()
        api_image.save(image_buffer, format="JPEG", quality=88, optimize=True)
        image_data = base64.b64encode(image_buffer.getvalue()).decode("ascii")
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribe all printed and handwritten text in this prescription, especially every medicine name, strength, dosage, frequency, timing, duration, and directions. Preserve the wording. Do not infer or correct unclear handwriting; write [unclear] when it cannot be read. Return only the transcription, one medicine per line when possible.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                ],
            }],
            temperature=0,
            max_tokens=1200,
        )
        content = response.choices[0].message.content
        return content.strip() if isinstance(content, str) else ""
    except Exception:
        return ""

def extract_text_from_pdf(file_input):
    """
    Extract readable text from a PDF file using pypdf.
    file_input can be a file path string or a file-like object (BytesIO / Streamlit UploadedFile).
    """
    try:
        reader = pypdf.PdfReader(file_input)
        text_pages = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt:
                text_pages.append(f"--- Page {i+1} ---\n" + txt.strip())
        
        full_text = "\n\n".join(text_pages).strip()
        if full_text:
            return full_text
        try:
            import pymupdf
        except ImportError as exc:
            raise RuntimeError("This scanned PDF needs PyMuPDF. Install the project requirements and try again.") from exc

        if isinstance(file_input, (str, os.PathLike)):
            document = pymupdf.open(file_input)
        else:
            file_input.seek(0)
            pdf_bytes = file_input.read()
            file_input.seek(0)
            document = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        with document:
            for page_number, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                page_image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                page_text = extract_text_from_pil_image(page_image)
                if page_text:
                    text_pages.append(f"--- Page {page_number} ---\n{page_text}")

        full_text = "\n\n".join(text_pages).strip()
        if not full_text:
            raise ValueError("No readable text was found in this PDF. Upload a clearer copy or enter medicines manually.")
        return full_text
    except Exception as e:
        if isinstance(e, (RuntimeError, ValueError)):
            raise
        raise ValueError(f"Could not read this PDF: {e}") from e

def extract_text_from_image(file_input):
    """
    Extract readable text from an image file using Pillow / pytesseract or fallback.
    file_input can be a file path string or file object.
    """
    try:
        with Image.open(file_input) as image:
            raw_text = extract_text_from_pil_image(image).strip()
    except Exception as exc:
        if isinstance(exc, (RuntimeError, ValueError)):
            raise
        raise ValueError(f"Could not read this image: {exc}") from exc
    if not raw_text:
        raise ValueError("No readable text was found in this image. Upload a clearer copy or enter medicines manually.")
    return raw_text

def extract_raw_text(file_input, filename):
    """
    Determines file type and extracts raw text string.
    """
    fn_lower = filename.lower()
    if fn_lower.endswith(".pdf"):
        return extract_text_from_pdf(file_input)
    else:
        return extract_text_from_image(file_input)


def _normalize_prescription_text(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _ground_medicines(parsed_medicines, raw_text):
    source = _normalize_prescription_text(raw_text)
    grounded = []

    for medicine in parsed_medicines:
        if not isinstance(medicine, dict):
            continue

        name = str(medicine.get("name", "")).strip()
        normalized_name = _normalize_prescription_text(name)
        if not normalized_name or normalized_name not in source:
            continue

        dosage = str(medicine.get("dosage", "Not specified")).strip()
        if dosage.lower() in {"not found", "please verify", "none", "null", ""}:
            dosage = "Not specified"

        frequency = str(medicine.get("frequency", "Not specified")).strip()
        if not frequency or frequency.lower() in {"not found", "none", "null"}:
            frequency = "Not specified"

        # Generate time slots based on frequency
        freq_lower = frequency.lower()
        if "four" in freq_lower or "4" in freq_lower:
            time_slot = "08:00 AM, 12:00 PM, 05:00 PM, 09:00 PM"
            if frequency == "Not specified": frequency = "Four times daily"
        elif "three" in freq_lower or "3" in freq_lower:
            time_slot = "08:00 AM, 01:30 PM, 09:00 PM"
            if frequency == "Not specified": frequency = "Three times daily"
        elif "twice" in freq_lower or "2" in freq_lower:
            time_slot = "09:00 AM, 09:00 PM"
            if frequency == "Not specified": frequency = "Twice daily"
        elif "once" in freq_lower or "1" in freq_lower or "daily" in freq_lower:
            time_slot = "09:00 AM"
            if frequency == "Not specified": frequency = "Once daily"
        else:
            time_slot = "09:00 AM"

        grounded.append({
            "name": name,
            "dosage": dosage,
            "frequency": frequency if frequency != "Not specified" else "Once daily",
            "time_slot": time_slot,
            "before_after_food": "",
            "instructions": ""
        })

    if not grounded:
        raise ValueError("The AI response did not match any medicine name in the extracted prescription text. Review the source text and enter medicines manually.")
    return grounded

def parse_prescription_text_with_llm(raw_text, filename="Prescription"):
    """
    Uses Groq LLM to identify structured medicine information from extracted OCR text.
    Strictly follows Medical Safety rules: NEVER invents missing information.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("No prescription text was extracted. Upload a clearer file and try again.")

    client = get_groq_client()
    
    prompt = f"""You are CareVoice's specialized medical prescription parser AI.
Analyze the following raw extracted text from a prescription document named '{filename}' and structure the prescribed medications into a JSON array.

Extracted Prescription Text:
\"\"\"
{raw_text}
\"\"\"

For EACH distinct medicine mentioned, extract the following structured fields:
- name: (Exact medicine name from the text. If unreadable or missing, put 'Please verify')
- dosage: (Strength/dosage e.g. '5 mg', '500 mg'. If missing, put 'Not found')
- frequency: (Only use a frequency explicitly present in the source text; otherwise put 'Not specified')
- time_slot: (Only use a clock time explicitly present in the source text; otherwise put 'Not specified')
- before_after_food: (Only use meal timing explicitly present in the source text; otherwise put 'Not specified')
- instructions: (Clear user instructions based strictly on the prescription text. E.g. 'Take 1 tablet after breakfast for blood pressure'. Do NOT invent medical advice!)

STRICT RULES:
1. NEVER invent medicines, dosages, or instructions not indicated in the prescription text.
2. If prescription text does not specify something, mark as 'Not found' or 'Please verify'.
3. Return ONLY a valid JSON array of objects. Do NOT include markdown blocks, intro, or trailing chat.

"""

    if client:
        models_to_try = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
        for model_name in models_to_try:
            try:
                res = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=800
                )
                content = res.choices[0].message.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                
                parsed_json = json.loads(content.strip())
                if isinstance(parsed_json, list) and len(parsed_json) > 0:
                    return _ground_medicines(parsed_json, raw_text)
            except Exception:
                continue

    raise RuntimeError("Medicine details could not be extracted. Check your AI service connection or enter medicines manually.")
