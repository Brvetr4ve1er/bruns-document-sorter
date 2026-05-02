@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BRUNs Diagnostic
color 0E

:: =============================================================================
::  BRUNs - environment diagnostic
:: =============================================================================
::  Run this when "Internal Server Error" appears, or when the app refuses to
::  start. Prints a complete pass/fail report covering:
::    - Python version
::    - Repo layout (templates, static UI assets)
::    - Every pip dependency (with version)
::    - Tesseract binary + language packs (eng/fra/ara)
::    - Ollama daemon + llama3 model
::    - data/ directories + writability
::    - SQLite databases + table presence
::    - Schema migrations
::    - Flask app startup (imports, GET /, GET /logistics)
::
::  Output is also written to data\logs\diagnose.txt for sharing with support.
:: =============================================================================

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "OUT_FILE=data\logs\diagnose.txt"

echo.
echo  ============================================================
echo    BRUNS DIAGNOSTIC
echo  ============================================================
echo.

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo  [!] Virtual environment not found at %VENV_DIR%\.
    echo      Run INSTALL.bat first.
    echo.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

if not exist "data\logs" mkdir "data\logs"

:: Run the check, mirror to the log file with PowerShell tee.
:: We force UTF-8 stdio so the report renders correctly on cmd.exe with cp1252.
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python -m core.diagnostics 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%OUT_FILE%'"
set "RC=!ERRORLEVEL!"

echo.
echo  ============================================================
echo    Full report saved to:  %OUT_FILE%
echo  ============================================================
echo.
echo    If you see [FAIL] entries, send the contents of
echo    %OUT_FILE% along with your bug report.
echo.
pause
exit /b !RC!
