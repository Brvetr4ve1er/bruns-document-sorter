@echo off
title BRUNs Logistics Dashboard
color 0A
echo.
echo  BRUNs Logistics Dashboard - Phase 3
echo  =====================================
echo.
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [SETUP] First run: creating virtual environment...
    python -m venv .venv
    echo [SETUP] Installing dependencies (1-2 min)...
    .venv\Scripts\pip install -q --upgrade pip
    .venv\Scripts\pip install -q -r requirements.txt
    echo [SETUP] Done!
    echo.
)

call .venv\Scripts\activate.bat

if not exist "data\input" mkdir "data\input"
if not exist "data\logs"  mkdir "data\logs"

echo [OK] Starting at http://localhost:8501
echo [OK] Press Ctrl+C to stop
echo.

streamlit run app_new.py --server.port 8501 --server.headless false --browser.gatherUsageStats false --theme.base dark --theme.primaryColor "#6366F1" --theme.backgroundColor "#0B1020" --theme.secondaryBackgroundColor "#141A2E" --theme.textColor "#E6E9F2"

echo.
echo Server stopped.
pause
