@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BRUNs Document Intelligence Platform - Installer
color 0B

:: =============================================================================
::  BRUNs - first-time installer for Windows
:: =============================================================================
::  Walks a clean Windows 10/11 machine through every step:
::    1. Verifies Python 3.10+ is on PATH
::    2. Creates the .venv virtual environment
::    3. Installs all Python dependencies from requirements.txt
::    4. Verifies (or installs) Tesseract OCR + downloads language packs
::    5. Verifies Ollama is reachable + offers to pull llama3
::    6. Creates the runtime data directories
::    7. Runs the database migrations
::
::  Re-running this script is safe — every step is idempotent.
:: =============================================================================

echo.
echo  ============================================================
echo    BRUNS DOCUMENT INTELLIGENCE PLATFORM - INSTALLER
echo  ============================================================
echo.

set "VENV_DIR=.venv"
set "MIN_PY_MAJOR=3"
:: 3.11 is the floor — pandas 3.x dropped Python 3.10 wheels, so installs on
:: 3.10 try to build pandas from source and fail without Visual C++ Tools.
set "MIN_PY_MINOR=11"

:: ── Step 1: Python check ────────────────────────────────────────────────────
echo  [1/7] Checking Python installation...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!!] Python is not on PATH.
    echo.
    echo       Install Python 3.10 or newer from:
    echo         https://www.python.org/downloads/
    echo.
    echo       During install, CHECK the box "Add python.exe to PATH".
    echo       Then re-run INSTALL.bat.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo       Found: Python !PY_VER!
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)
if !PY_MAJOR! LSS %MIN_PY_MAJOR% goto :py_too_old
if !PY_MAJOR! EQU %MIN_PY_MAJOR% if !PY_MINOR! LSS %MIN_PY_MINOR% goto :py_too_old
echo       [OK] Python version is supported.
goto :py_ok

:py_too_old
echo.
echo  [!!] Python !PY_VER! is too old. Need 3.%MIN_PY_MINOR%+.
echo       Install Python 3.10 or newer from:
echo         https://www.python.org/downloads/
echo.
pause
exit /b 1

:py_ok
echo.

:: ── Step 2: Virtual environment ─────────────────────────────────────────────
echo  [2/7] Setting up virtual environment...
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo       [OK] %VENV_DIR%\ already exists, reusing it.
) else (
    echo       Creating %VENV_DIR%\ ...
    python -m venv "%VENV_DIR%"
    if %ERRORLEVEL% NEQ 0 (
        echo  [!!] venv creation failed.
        pause
        exit /b 1
    )
    echo       [OK] virtual environment created.
)
call "%VENV_DIR%\Scripts\activate.bat"
echo.

:: ── Step 3: Python dependencies ─────────────────────────────────────────────
echo  [3/7] Installing Python dependencies (this can take 3-5 minutes)...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo  [!!] pip install failed. Inspect the error above.
    pause
    exit /b 1
)
echo       [OK] Python dependencies installed.
echo.

:: ── Step 4: Tesseract + language packs ──────────────────────────────────────
echo  [4/7] Checking Tesseract OCR...
set "TESS_LOCAL=%~dp0tesseract_bin\tesseract.exe"
set "TESS_SYS=C:\Program Files\Tesseract-OCR\tesseract.exe"

if exist "%TESS_LOCAL%" (
    echo       [OK] Bundled tesseract found at: tesseract_bin\
    set "TESS_PATH=%TESS_LOCAL%"
) else if exist "%TESS_SYS%" (
    echo       [OK] System Tesseract found at: %TESS_SYS%
    set "TESS_PATH=%TESS_SYS%"
) else (
    echo.
    echo  [!] Tesseract OCR is not installed.
    echo      It is required for scanned PDF processing.
    echo.
    set /p "yn=  Install Tesseract now via install_tesseract.bat? (Y/N): "
    if /i "!yn!"=="y" (
        echo.
        call "%~dp0install_tesseract.bat"
        if exist "%TESS_SYS%" (
            set "TESS_PATH=%TESS_SYS%"
        ) else (
            echo  [!] Tesseract install did not complete. You can re-run install_tesseract.bat later.
        )
    ) else (
        echo  [skipped] You can run install_tesseract.bat later if needed.
    )
)
echo.

echo       Checking language packs (eng/fra/ara)...
if not exist "tessdata" mkdir "tessdata"
call :ensure_traineddata eng
call :ensure_traineddata fra
call :ensure_traineddata ara
echo       [OK] Tesseract language packs ready.
echo.

:: ── Step 5: Ollama check ────────────────────────────────────────────────────
echo  [5/7] Checking Ollama (local LLM runtime)...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo       [OK] Ollama is running on http://localhost:11434
    echo       Checking for llama3 model...
    powershell -NoProfile -Command "$r = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing; if ($r.Content -match 'llama3') { exit 0 } else { exit 1 }" >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo       [OK] llama3 model is available.
    ) else (
        echo.
        echo  [!] llama3 model not found in Ollama.
        set /p "ynm=  Pull it now? (downloads ~4.7 GB) (Y/N): "
        if /i "!ynm!"=="y" (
            echo       Pulling llama3 ...
            ollama pull llama3
        ) else (
            echo       [skipped] Pull manually with: ollama pull llama3
        )
    )
) else (
    echo.
    echo  [!] Ollama is not running.
    echo      The app will install but you will not be able to process documents
    echo      until you install + start Ollama.
    echo.
    echo      Install from:  https://ollama.com/download
    echo      After install: open PowerShell and run:  ollama pull llama3
    echo.
    set /p "ack=  Press Enter to continue with install (Ollama can be added later): "
)
echo.

:: ── Step 6: Runtime directories ─────────────────────────────────────────────
echo  [6/7] Creating runtime directories...
if not exist "data"               mkdir "data"
if not exist "data\input"         mkdir "data\input"
if not exist "data\input\logistics" mkdir "data\input\logistics"
if not exist "data\input\travel"  mkdir "data\input\travel"
if not exist "data\logs"          mkdir "data\logs"
if not exist "data\vector"        mkdir "data\vector"
if not exist "data\exports"       mkdir "data\exports"
echo       [OK] data\ tree ready.
echo.

:: ── Step 7: Database init + migrations ──────────────────────────────────────
echo  [7/7] Initialising databases (run migrations)...
python -c "from core.storage.db import init_schema; from core.storage.migrations import run_migrations; import os; os.makedirs('data', exist_ok=True); init_schema('data/logistics.db'); init_schema('data/travel.db'); print('  applied logistics:', run_migrations('data/logistics.db')); print('  applied travel:', run_migrations('data/travel.db'))"
if %ERRORLEVEL% NEQ 0 (
    echo  [!!] Database init failed. Inspect the error above.
    pause
    exit /b 1
)
echo       [OK] databases ready.
echo.

:: ── Done ────────────────────────────────────────────────────────────────────
echo  ============================================================
echo    INSTALL COMPLETE
echo  ============================================================
echo.
echo    Next step: double-click START_APP.bat
echo.
echo    The browser will open at http://localhost:7845/
echo.
pause
exit /b 0


:: =============================================================================
::  Subroutine: download a tessdata language pack from GitHub if missing.
::  Usage:  call :ensure_traineddata <lang_code>
:: =============================================================================
:ensure_traineddata
set "LANG=%~1"
set "TFILE=tessdata\%LANG%.traineddata"
if exist "%TFILE%" (
    echo         [OK] %LANG%.traineddata already present
    goto :eof
)
echo         Downloading %LANG%.traineddata ...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/%LANG%.traineddata' -OutFile '%TFILE%' -UseBasicParsing -ErrorAction Stop } catch { Write-Host '         [!] download failed:' $_.Exception.Message; exit 1 }"
if not exist "%TFILE%" (
    echo         [!] %LANG%.traineddata download failed. Image-based PDFs in this language will fail.
)
goto :eof
