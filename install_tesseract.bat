@echo off
title Install Tesseract OCR
echo.
echo  Installing Tesseract OCR for image-based PDF support
echo  =====================================================
echo.
echo Step 1: Downloading Tesseract installer...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe' -OutFile '%TEMP%\tesseract_setup.exe' -UseBasicParsing"
echo.
echo Step 2: Installing Tesseract (requires admin)...
"%TEMP%\tesseract_setup.exe" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
echo.
echo Step 3: Installing Python bindings...
pip install pytesseract pillow -q
echo.
echo Done!
echo Tesseract is now installed at: C:\Program Files\Tesseract-OCR\
echo Image-based PDFs will now be OCR-scanned automatically.
echo.
pause
