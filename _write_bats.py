"""Writes launch.bat and build_exe.bat with correct Windows CRLF line endings."""
import os

base = os.path.dirname(os.path.abspath(__file__))

def wb(filename, lines):
    path = os.path.join(base, filename)
    with open(path, 'wb') as f:
        for line in lines:
            f.write(line.encode('utf-8') + b'\r\n')
    with open(path, 'rb') as f:
        raw = f.read()
    print(f"  {filename}: {len(raw)} bytes, CRLF={b'\\r\\n' in raw}, >nul={b'>nul' in raw}")

wb('launch.bat', [
    '@echo off',
    'title BRUNs Logistics Dashboard',
    'color 0A',
    'echo.',
    'echo  BRUNs Logistics Dashboard - Phase 3',
    'echo  =====================================',
    'echo.',
    'cd /d "%~dp0"',
    '',
    'python --version >nul 2>&1',
    'if errorlevel 1 (',
    '    echo [ERROR] Python not found. Install from https://python.org',
    '    pause',
    '    exit /b 1',
    ')',
    '',
    'if not exist ".venv" (',
    '    echo [SETUP] First run: creating virtual environment...',
    r'    python -m venv .venv',
    r'    echo [SETUP] Installing dependencies (1-2 min)...',
    r'    .venv\Scripts\pip install -q --upgrade pip',
    r'    .venv\Scripts\pip install -q -r requirements.txt',
    '    echo [SETUP] Done!',
    '    echo.',
    ')',
    '',
    r'call .venv\Scripts\activate.bat',
    '',
    r'if not exist "data\input" mkdir "data\input"',
    r'if not exist "data\logs"  mkdir "data\logs"',
    '',
    'echo [OK] Starting at http://localhost:8501',
    'echo [OK] Press Ctrl+C to stop',
    'echo.',
    '',
    'streamlit run app_new.py --server.port 8501 --server.headless false --browser.gatherUsageStats false --theme.base dark --theme.primaryColor "#6366F1" --theme.backgroundColor "#0B1020" --theme.secondaryBackgroundColor "#141A2E" --theme.textColor "#E6E9F2"',
    '',
    'echo.',
    'echo Server stopped.',
    'pause',
])

wb('build_exe.bat', [
    '@echo off',
    'title BRUNs - Build Standalone EXE',
    'color 0B',
    'echo.',
    'echo  Building BRUNs as standalone EXE...',
    'echo  =====================================',
    'echo.',
    'cd /d "%~dp0"',
    '',
    'python --version >nul 2>&1',
    'if errorlevel 1 (',
    '    echo [ERROR] Python not found.',
    '    pause',
    '    exit /b 1',
    ')',
    '',
    r'if exist ".venv\Scripts\activate.bat" (',
    r'    call .venv\Scripts\activate.bat',
    ') else (',
    '    python -m venv .venv',
    r'    call .venv\Scripts\activate.bat',
    r'    pip install -q -r requirements.txt',
    ')',
    '',
    'pyinstaller --version >nul 2>&1',
    'if errorlevel 1 (',
    '    pip install -q pyinstaller',
    ')',
    '',
    r'if exist "dist\BRUNs" rmdir /s /q "dist\BRUNs"',
    'if exist "build"      rmdir /s /q "build"',
    '',
    'echo [BUILD] Running PyInstaller (2-3 minutes)...',
    'pyinstaller bruns.spec',
    '',
    'if errorlevel 1 (',
    '    echo [ERROR] Build failed. See above.',
    '    pause',
    '    exit /b 1',
    ')',
    '',
    'echo.',
    r'echo [OK] Done! Output: dist\BRUNs\BRUNs.exe',
    'echo.',
    r'echo Zip the entire dist\BRUNs\ folder and send it to your friend.',
    'echo Your friend only needs Ollama - no Python required.',
    'echo.',
    'pause',
])

print("Done.")
