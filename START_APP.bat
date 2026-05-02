@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BRUNs Document Intelligence Platform
color 0B

:: =============================================================================
::  Quick-launch — Flask + HTMX + DaisyUI on port 7845.
::  If install hasn't been run, offers to run INSTALL.bat automatically.
:: =============================================================================
set "VENV_DIR=.venv"
set "PORT=7845"

cd /d "%~dp0"

echo.
echo  ============================================================
echo    BRUNS DOCUMENT INTELLIGENCE PLATFORM
echo  ============================================================
echo.

:: ── Sanity: make sure we're in the right directory ──────────────────────────
if not exist "core\api\server.py" (
    echo  [!!] core\api\server.py not found.
    echo       This script must be run from the BRUNs project root.
    echo       Current directory: %CD%
    echo.
    pause
    exit /b 1
)

:: ── Check 1: venv exists ────────────────────────────────────────────────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo  [!] Virtual environment not found at %VENV_DIR%\.
    echo.
    echo      First-time setup is required.
    set /p "yn=     Run INSTALL.bat now? (Y/N): "
    if /i "!yn!"=="y" (
        echo.
        call "%~dp0INSTALL.bat"
        if !ERRORLEVEL! NEQ 0 (
            echo.
            echo  [!!] Installer did not finish. Resolve the error above and try again.
            pause
            exit /b 1
        )
        echo.
        echo  --- Installer complete, continuing to launch ---
        echo.
    ) else (
        echo.
        echo      Run INSTALL.bat manually when ready.
        pause
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"

:: ── Check 2: requirements.txt vs installed packages ─────────────────────────
:: Quick smoke test: try importing flask. If it fails, deps are not installed.
python -c "import flask, pydantic, chromadb" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [!] Some Python dependencies are missing.
    echo      Re-running INSTALL.bat to repair...
    echo.
    call "%~dp0INSTALL.bat"
    if !ERRORLEVEL! NEQ 0 (
        echo  [!!] Repair failed. See error above.
        pause
        exit /b 1
    )
    call "%VENV_DIR%\Scripts\activate.bat"
)

:: ── Check 3: Ollama (warning only, not a hard requirement) ──────────────────
echo  Checking Ollama connectivity...
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!] WARNING: Ollama is not running.
    echo      Document processing requires Ollama to be active.
    echo      You can still browse existing data without it.
    echo.
    echo      Install:  https://ollama.com/download
    echo      Then:     ollama pull llama3
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

:: ── Check 4: port 7845 is free ──────────────────────────────────────────────
netstat -aon | findstr ":%PORT% " | findstr "LISTENING" >nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo  [!] Port %PORT% is already in use.
    echo      Another BRUNs instance may be running. Close it first, or
    echo      kill the process holding the port:
    echo        netstat -aon ^| findstr :%PORT%
    echo        taskkill /F /PID ^<pid^>
    echo.
    pause
    exit /b 1
)

:: ── Launch ──────────────────────────────────────────────────────────────────
echo.
echo  Starting Flask server on http://localhost:%PORT% ...
echo  Open your browser at: http://localhost:%PORT%/
echo.
echo  To stop: press Ctrl+C in this window, then close it.
echo.

:: Open the URL after a short delay so the browser doesn't beat the server up.
start "" /min cmd /c "timeout /t 2 >nul && start http://localhost:%PORT%/"

python -m core.api.server

pause
