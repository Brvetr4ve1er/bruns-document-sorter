"""
PDF text extractor — multi-strategy with OCR fallback.

Strategy order:
  1. PyMuPDF embedded text  (fast, zero deps, works on digital PDFs)
  2. Tesseract OCR via pytesseract  (if installed — handles scanned PDFs)
  3. Ollama vision model  (if strategy 1+2 both fail — uses llava/llama3.2-vision)

A page is considered "image-only" when get_text() returns fewer than
MIN_TEXT_CHARS meaningful characters.
"""

import io
import os
import fitz  # PyMuPDF

MIN_TEXT_CHARS = 30   # below this → treat page as image-only

# Tesseract configuration
_LOCAL_TESS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tesseract.exe")
_SYSTEM_TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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

def extract_text(pdf_path: str) -> str:
    """
    Extract text from a PDF using the best available method.
    Always returns a string (may be empty if all strategies fail).
    Logs which strategy was used to stdout.
    """
    doc = fitz.open(pdf_path)
    page_texts = []

    for page_num, page in enumerate(doc):
        text = page.get_text().strip()

        if len(text) >= MIN_TEXT_CHARS:
            # Strategy 1: embedded text — done
            page_texts.append(text)
        else:
            # Page is image-only — try OCR
            print(f"  [extractor] page {page_num+1} has no embedded text → trying OCR")
            ocr_text = _ocr_page(page, page_num, pdf_path)
            page_texts.append(ocr_text)

    doc.close()
    result = "\n".join(page_texts).strip()

    if result:
        print(f"  [extractor] extracted {len(result)} chars from {os.path.basename(pdf_path)}")
    else:
        print(f"  [extractor] WARNING: no text extracted from {os.path.basename(pdf_path)}")

    return result


def is_image_pdf(pdf_path: str) -> bool:
    """Return True if the PDF appears to be entirely image-based (no embedded text)."""
    doc = fitz.open(pdf_path)
    total_text = "".join(page.get_text() for page in doc).strip()
    doc.close()
    return len(total_text) < MIN_TEXT_CHARS


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
    from PIL import Image

    # Render at 300 DPI for good OCR accuracy
    mat = fitz.Matrix(300 / 72, 300 / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_bytes = pix.tobytes("png")

    img = Image.open(io.BytesIO(img_bytes))
    # Try French + English (logistics docs often mix both)
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
        import requests, config
        base = config.OLLAMA_URL.replace("/api/generate", "")
        resp = requests.get(f"{base}/api/tags", timeout=4)
        if not resp.ok:
            return False, ""
        available = [m["name"].split(":")[0] for m in resp.json().get("models", [])]
        for vm in VISION_MODELS:
            if vm in available or any(vm in a for a in available):
                # Return the full model name
                for a in resp.json().get("models", []):
                    if vm in a["name"]:
                        return True, a["name"]
        return False, ""
    except Exception:
        return False, ""


def _ocr_with_ollama_vision(page: fitz.Page, model: str) -> str:
    """Send page image to Ollama vision model for text extraction."""
    import requests, base64, config

    # Render page to PNG
    mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI — balance quality vs speed
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_b64 = base64.b64encode(pix.tobytes("png")).decode()

    prompt = (
        "This is a page from a shipping/logistics document. "
        "Extract ALL visible text exactly as written, preserving layout. "
        "Include container numbers, TAN numbers, dates, carrier names, "
        "vessel names, port names, and any other logistics data. "
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
        resp = requests.post(config.OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"  [extractor] Ollama vision failed: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# OCR dispatcher — tries strategies in order
# ─────────────────────────────────────────────────────────────────────────────

def _ocr_page(page: fitz.Page, page_num: int, pdf_path: str) -> str:
    """Try available OCR strategies for a single image page."""

    # Strategy 2: Tesseract
    if _tesseract_available():
        print(f"  [extractor] using Tesseract OCR on page {page_num+1}")
        try:
            text = _ocr_with_tesseract(page)
            if text:
                print(f"  [extractor] Tesseract extracted {len(text)} chars")
                return text
        except Exception as e:
            print(f"  [extractor] Tesseract error: {e}")

    # Strategy 3: Ollama vision
    vision_ok, vision_model = _ollama_vision_available()
    if vision_ok:
        print(f"  [extractor] using Ollama vision ({vision_model}) on page {page_num+1}")
        try:
            text = _ocr_with_ollama_vision(page, vision_model)
            if text:
                print(f"  [extractor] vision model extracted {len(text)} chars")
                return text
        except Exception as e:
            print(f"  [extractor] vision model error: {e}")

    # Nothing worked
    print(f"  [extractor] page {page_num+1}: no OCR method available — page will be skipped")
    print(f"  [extractor] TIP: install Tesseract for reliable OCR:")
    print(f"  [extractor]   Windows: https://github.com/UB-Mannheim/tesseract/wiki")
    print(f"  [extractor]   Then: pip install pytesseract")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic helper — call from settings page or CLI
# ─────────────────────────────────────────────────────────────────────────────

def ocr_diagnostic() -> dict:
    """
    Returns a dict describing what OCR capabilities are available.
    Used by the Settings page to show the user their OCR status.
    """
    result = {
        "pymupdf": fitz.version[0],
        "tesseract": None,
        "pytesseract": False,
        "ollama_vision": False,
        "ollama_vision_model": None,
    }

    # Tesseract
    try:
        import pytesseract
        v = pytesseract.get_tesseract_version()
        result["pytesseract"] = True
        result["tesseract"] = str(v)
    except Exception:
        pass

    # Ollama vision
    ok, model = _ollama_vision_available()
    result["ollama_vision"] = ok
    result["ollama_vision_model"] = model if ok else None

    return result
