@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BRUNs Document Intelligence Platform
color 0B

:: ─────────────────────────────────────────────────────────────────────────────
::  Quick-launch (post-install) — Flask + HTMX + DaisyUI on port 7845.
::  Runs INSTALL.bat first if you have not.
:: ─────────────────────────────────────────────────────────────────────────────
set "VENV_DIR=.venv"
set "PORT=7845"

echo.
echo  ============================================================
echo    BRUNS DOCUMENT INTELLIGENCE PLATFORM
echo  ============================================================
echo.

:: ── Sanity checks ────────────────────────────────────────────────────────────

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo  [!!] Virtual environment not found.
    echo      Please run INSTALL.bat first.
    echo.
    pause
    exit /b
)

call %VENV_DIR%\Scripts\activate.bat

:: ── Check Ollama ─────────────────────────────────────────────────────────────
echo  Checking Ollama connectivity...
powershell -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!] WARNING: Ollama is not running.
    echo      Document processing requires Ollama to be active.
    echo      You can still browse existing data without it.
    echo.
    set /p "cont=  Continue anyway? (Y/N): "
    if /i "!cont!" NEQ "y" (
        echo  Exiting...
        timeout /t 2 >nul
        exit /b
    )
) else (
    echo  [OK] Ollama is ready.
)

:: ── Launch ───────────────────────────────────────────────────────────────────
echo.
echo  Starting Flask server on http://localhost:%PORT% ...
echo  Open your browser at: http://localhost:%PORT%/
echo.
echo  To stop: press Ctrl+C in this window, then close it.
echo.

:: Open the URL after a short delay so the browser doesn't beat the server up
start "" /min cmd /c "timeout /t 2 >nul && start http://localhost:%PORT%/"

python -m core.api.server

pause
