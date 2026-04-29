"""
PDF and Image text extractor — multi-strategy with OCR fallback.

Strategy order:
  1. PyMuPDF embedded text  (fast, zero deps, works on digital PDFs)
  2. Tesseract OCR via pytesseract  (handles scanned PDFs and Images)
  3. Ollama vision model  (if strategy 1+2 fail)
"""

import io
import os
import fitz  # PyMuPDF
from PIL import Image

MIN_TEXT_CHARS = 30   # below this → treat page as image-only

# Tesseract configuration — bundled binary lives in <repo>/tesseract_bin/
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOCAL_TESS = os.path.join(_REPO_ROOT, "tesseract_bin", "tesseract.exe")
_SYSTEM_TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_LOCAL_TESSDATA = os.path.join(_REPO_ROOT, "tessdata")

# CRITICAL: the bundled tesseract.exe was compiled with a hardcoded build-time
# tessdata path that doesn't exist on user machines. Without TESSDATA_PREFIX,
# Tesseract crashes on first OCR call: "Error opening data file ...eng.traineddata".
# We set it here unconditionally so every Tesseract invocation works regardless
# of who imports text_extractor.py first.
if os.path.isdir(_LOCAL_TESSDATA) and not os.environ.get("TESSDATA_PREFIX"):
    os.environ["TESSDATA_PREFIX"] = _LOCAL_TESSDATA

try:
    import pytesseract
    if os.path.exists(_LOCAL_TESS):
        pytesseract.pytesseract.tesseract_cmd = _LOCAL_TESS
    elif os.path.exists(_SYSTEM_TESS):
        pytesseract.pytesseract.tesseract_cmd = _SYSTEM_TESS
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(file_path: str) -> str:
    """
    Extract text from a PDF or Image using the best available method.
    Always returns a string (may be empty if all strategies fail).
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
        return _extract_from_image(file_path)
    elif ext == ".pdf":
        return _extract_from_pdf(file_path)
    else:
        print(f"  [extractor] unsupported extension {ext} for {os.path.basename(file_path)}")
        return ""

def _extract_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    page_texts = []

    for page_num, page in enumerate(doc):
        text = page.get_text().strip()

        if len(text) >= MIN_TEXT_CHARS:
            # Strategy 1: embedded text — done
            page_texts.append(text)
        else:
            # Page is image-only — try OCR
            print(f"  [extractor] page {page_num+1} has no embedded text -> trying OCR")
            ocr_text = _ocr_page(page, page_num, pdf_path)
            page_texts.append(ocr_text)

    doc.close()
    result = "\n".join(page_texts).strip()

    if result:
        print(f"  [extractor] extracted {len(result)} chars from {os.path.basename(pdf_path)}")
    else:
        print(f"  [extractor] WARNING: no text extracted from {os.path.basename(pdf_path)}")

    return result

def _extract_from_image(image_path: str) -> str:
    """Extract text from a standalone image file using Tesseract or Vision."""
    print(f"  [extractor] processing image {os.path.basename(image_path)}")
    try:
        doc = fitz.open(image_path)
        page = doc[0]
        text = _ocr_page(page, 0, image_path)
        doc.close()
        
        if text:
            print(f"  [extractor] extracted {len(text)} chars from image {os.path.basename(image_path)}")
        else:
            print(f"  [extractor] WARNING: no text extracted from image {os.path.basename(image_path)}")
            
        return text
    except Exception as e:
        print(f"  [extractor] error processing image {os.path.basename(image_path)}: {e}")
        return ""

def is_image_pdf(pdf_path: str) -> bool:
    """Return True if the PDF appears to be entirely image-based (no embedded text)."""
    try:
        doc = fitz.open(pdf_path)
        total_text = "".join(page.get_text() for page in doc).strip()
        doc.close()
        return len(total_text) < MIN_TEXT_CHARS
    except Exception:
        return True

# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2 — Tesseract OCR
# ─────────────────────────────────────────────────────────────────────────────

def _tesseract_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False

def _ocr_with_tesseract(page: fitz.Page) -> str:
    """Render page to image and run Tesseract OCR on it."""
    import pytesseract
    
    mat = fitz.Matrix(300 / 72, 300 / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_bytes = pix.tobytes("png")

    img = Image.open(io.BytesIO(img_bytes))
    try:
        text = pytesseract.image_to_string(img, lang="fra+eng")
    except Exception:
        text = pytesseract.image_to_string(img)

    return text.strip()

# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3 — Ollama vision model
# ─────────────────────────────────────────────────────────────────────────────

VISION_MODELS = ["llama3.2-vision", "llava", "llava:13b", "minicpm-v", "moondream"]

def _ollama_vision_available() -> tuple[bool, str]:
    """Check if a vision-capable model is available in Ollama."""
    try:
        import requests
        # Resolve config safely (might be imported differently in new structure)
        # We will hardcode default URL but ideally pull from global config
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
        base = ollama_url.replace("/api/generate", "")
        
        resp = requests.get(f"{base}/api/tags", timeout=4)
        if not resp.ok:
            return False, ""
            
        available = [m["name"].split(":")[0] for m in resp.json().get("models", [])]
        for vm in VISION_MODELS:
            if vm in available or any(vm in a for a in available):
                for a in resp.json().get("models", []):
                    if vm in a["name"]:
                        return True, a["name"]
        return False, ""
    except Exception:
        return False, ""

def _ocr_with_ollama_vision(page: fitz.Page, model: str) -> str:
    """Send page image to Ollama vision model for text extraction."""
    import requests, base64
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

    mat = fitz.Matrix(200 / 72, 200 / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_b64 = base64.b64encode(pix.tobytes("png")).decode()

    prompt = (
        "This is a page from a document. "
        "Extract ALL visible text exactly as written, preserving layout. "
        "Return only the extracted text, no commentary."
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        resp = requests.post(ollama_url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"  [extractor] Ollama vision failed: {e}")
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# OCR dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def _ocr_page(page: fitz.Page, page_num: int, file_path: str) -> str:
    """Try available OCR strategies for a single image page."""
    
    if _tesseract_available():
        print(f"  [extractor] using Tesseract OCR on page {page_num+1}")
        try:
            text = _ocr_with_tesseract(page)
            if text:
                return text
        except Exception as e:
            print(f"  [extractor] Tesseract error: {e}")

    vision_ok, vision_model = _ollama_vision_available()
    if vision_ok:
        print(f"  [extractor] using Ollama vision ({vision_model}) on page {page_num+1}")
        try:
            text = _ocr_with_ollama_vision(page, vision_model)
            if text:
                return text
        except Exception as e:
            print(f"  [extractor] vision model error: {e}")

    print(f"  [extractor] page {page_num+1}: no OCR method available — page will be skipped")
    return ""
