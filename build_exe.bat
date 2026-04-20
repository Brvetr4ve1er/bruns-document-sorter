@echo off
title BRUNs - Build Standalone EXE
color 0B
echo.
echo  Building BRUNs as standalone EXE...
echo  =====================================
echo.
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -q -r requirements.txt
)

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    pip install -q pyinstaller
)

if exist "dist\BRUNs" rmdir /s /q "dist\BRUNs"
if exist "build"      rmdir /s /q "build"

echo [BUILD] Running PyInstaller (2-3 minutes)...
pyinstaller bruns.spec

if errorlevel 1 (
    echo [ERROR] Build failed. See above.
    pause
    exit /b 1
)

echo.
echo [OK] Done! Output: dist\BRUNs\BRUNs.exe
echo.
echo Zip the entire dist\BRUNs\ folder and send it to your friend.
echo Your friend only needs Ollama - no Python required.
echo.
pause
