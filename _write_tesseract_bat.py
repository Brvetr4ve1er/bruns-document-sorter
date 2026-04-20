import os

base = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(base, 'install_tesseract.bat')

lines = [
    b'@echo off',
    b'title Install Tesseract OCR',
    b'echo.',
    b'echo  Installing Tesseract OCR for image-based PDF support',
    b'echo  =====================================================',
    b'echo.',
    b'echo Step 1: Downloading Tesseract installer...',
    b'powershell -Command "Invoke-WebRequest -Uri \'https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe\' -OutFile \'%TEMP%\\tesseract_setup.exe\' -UseBasicParsing"',
    b'echo.',
    b'echo Step 2: Installing Tesseract (requires admin)...',
    b'"%TEMP%\\tesseract_setup.exe" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES',
    b'echo.',
    b'echo Step 3: Installing Python bindings...',
    b'pip install pytesseract pillow -q',
    b'echo.',
    b'echo Done!',
    b'echo Tesseract is now installed at: C:\\Program Files\\Tesseract-OCR\\',
    b'echo Image-based PDFs will now be OCR-scanned automatically.',
    b'echo.',
    b'pause',
]

with open(path, 'wb') as f:
    f.write(b'\r\n'.join(lines) + b'\r\n')

print(f'Written: {path}')
