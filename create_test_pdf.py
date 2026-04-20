"""
Run once to create a sample test PDF in data/input/.
Requires: pip install reportlab
If you don't have reportlab, use any real logistics PDF.
"""
import os

SAMPLE_TEXT = """
BOOKING CONFIRMATION

TAN Number: TAN-2024-00123
Vessel Name: EVER GIVEN
ETD: 2024-06-15
ETA: 2024-07-02
Port of Loading: Shanghai (CNSHA)
Port of Discharge: Rotterdam (NLRTM)

Containers:
1. TCKU3456789 - 40HC
2. MSCU1234567 - 20GP
3. CAIU9876543 - 40GP

Shipper: BRUNS LOGISTICS LTD
Consignee: EUROPEAN TRADE BV
"""

def create_with_reportlab():
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4

    os.makedirs("data/input", exist_ok=True)
    out = os.path.join("data", "input", "sample_booking.pdf")
    c = rl_canvas.Canvas(out, pagesize=A4)
    c.setFont("Helvetica", 12)
    y = 750
    for line in SAMPLE_TEXT.strip().splitlines():
        c.drawString(50, y, line)
        y -= 18
        if y < 50:
            c.showPage()
            y = 750
    c.save()
    print(f"Created: {out}")


def create_with_fitz():
    """Fallback: create PDF using PyMuPDF (already a dependency)."""
    import fitz

    os.makedirs("data/input", exist_ok=True)
    out = os.path.join("data", "input", "sample_booking.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), SAMPLE_TEXT, fontsize=11)
    doc.save(out)
    doc.close()
    print(f"Created: {out}")


if __name__ == "__main__":
    try:
        create_with_reportlab()
    except ImportError:
        create_with_fitz()
