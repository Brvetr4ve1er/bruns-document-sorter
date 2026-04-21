@echo off
setlocal Envextensions
title BRUNs Logistics - Smart Data Scraper

:: ─────────────────────────────────────────────────────────────────────────────
::  Configuration
:: ─────────────────────────────────────────────────────────────────────────────
set "VENV_DIR=.venv"
set "REQUIREMENTS=requirements.txt"
set "APP_ENTRY=app.py"

:: ─────────────────────────────────────────────────────────────────────────────
::  Introduction
:: ─────────────────────────────────────────────────────────────────────────────
echo.
echo  ============================================================
echo    BRUNS LOGISTICS - SMART DATA SCRAPER
echo  ============================================================
echo.

:: 1. Check if Ollama is running
echo [1/4] Checking Ollama connectivity...
powershell -Command "try { $resp = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2; exit 0 } catch { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] WARNING: Ollama does not seem to be running.
    echo     PDF parsing requires Ollama to be active.
    echo     Please start Ollama and try again.
    echo.
    set /p "cont=Continue anyway? (y/n): "
    if /i "%cont%" NEQ "y" exit /b
) else (
    echo [OK] Ollama is ready.
)

:: 2. Setup Virtual Environment
if not exist "%VENV_DIR%" (
    echo [2/4] First-time setup: Creating virtual environment...
    python -m venv %VENV_DIR%
    if %ERRORLEVEL% NEQ 0 (
        echo [!] ERROR: Failed to create virtual environment. Ensure Python is installed.
        pause
        exit /b
    )
) else (
    echo [2/4] Virtual environment found.
)

:: 3. Install Dependencies
echo [3/4] Checking dependencies...
call %VENV_DIR%\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -q -r %REQUIREMENTS%
if %ERRORLEVEL% NEQ 0 (
    echo [!] ERROR: Dependency installation failed.
    pause
    exit /b
)
echo [OK] Dependencies verified.

:: 4. Launch Application
echo [4/4] Launching Logistics Dashboard...
echo.
echo  - Dashboard will open in your browser shortly...
echo  - Press Ctrl+C in this window to stop the application.
echo.

streamlit run "%APP_ENTRY%" --theme.base="dark" --theme.primaryColor="#6366F1" --theme.backgroundColor="#0B1020" --theme.secondaryBackgroundColor="#141A2E" --theme.textColor="#E6E9F2"

pause
