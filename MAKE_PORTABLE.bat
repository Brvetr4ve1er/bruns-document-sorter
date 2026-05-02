@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BRUNs - Build Portable Bundle
color 0A

:: =============================================================================
::  Builds a SELF-CONTAINED, NO-INSTALL Windows bundle of the BRUNs app.
::
::  Output:  dist\BRUNs-Portable\
::    + dist\BRUNs-Portable.zip   (~ 800 MB to 1.2 GB)
::
::  The bundle includes:
::    - python\               Python 3.12 embeddable distribution (no install)
::    - .venv-libs\           All pip dependencies, pre-installed
::    - tesseract_bin\        Bundled Tesseract OCR binary + DLLs (if present)
::    - tessdata\             Language packs (eng/fra/ara, downloaded)
::    - core\, modules\, requirements.txt, etc.   (the app source)
::    - data\                 Pre-initialized SQLite databases + dirs
::    - START.bat             One-click launcher
::    - DIAGNOSE.bat          Diagnostic script
::    - README.txt            User-facing instructions
::
::  Recipient just unzips and runs START.bat. No Python install required,
::  no pip, no admin privileges. Ollama still needs to be installed
::  separately (download from https://ollama.com/download) — it is too
::  large to bundle (~4.7 GB model + GPU drivers).
:: =============================================================================

cd /d "%~dp0"

set "DIST=dist\BRUNs-Portable"
set "PY_VERSION=3.12.7"
set "PY_ZIP_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "TMP_DIR=%TEMP%\bruns_portable_%RANDOM%"

echo.
echo  ============================================================
echo    BRUNS PORTABLE BUNDLE BUILDER
echo  ============================================================
echo.
echo  This will produce a no-install Windows bundle in:
echo    %DIST%\
echo.
echo  Total build time: 5-10 minutes (downloads Python embed + pip deps)
echo  Final ZIP size:   ~ 800 MB to 1.2 GB
echo.
set /p "yn=  Continue? (Y/N): "
if /i "!yn!" NEQ "y" (
    echo  Aborted.
    exit /b 0
)

:: ── Sanity ──────────────────────────────────────────────────────────────────
if not exist "core\api\server.py" (
    echo  [!!] Run this from the BRUNs project root.
    pause
    exit /b 1
)

if exist "%DIST%" (
    echo.
    echo  [!] %DIST%\ already exists. Delete it? (Y/N)
    set /p "del_yn= "
    if /i "!del_yn!"=="y" (
        rmdir /s /q "%DIST%"
    ) else (
        echo  Aborted.
        exit /b 0
    )
)

mkdir "%DIST%"
mkdir "%TMP_DIR%"

:: ── Step 1: Download Python embeddable ──────────────────────────────────────
echo.
echo  [1/9] Downloading Python %PY_VERSION% embeddable...
set "PY_ZIP=%TMP_DIR%\python-embed.zip"
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%PY_ZIP_URL%' -OutFile '%PY_ZIP%' -UseBasicParsing"
if not exist "%PY_ZIP%" (
    echo  [!!] Download failed. Check internet connectivity.
    goto :cleanup_fail
)
echo        Extracting to %DIST%\python\ ...
mkdir "%DIST%\python"
powershell -NoProfile -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%DIST%\python' -Force"

:: ── Step 2: Patch python._pth so site-packages works ────────────────────────
echo.
echo  [2/9] Patching python._pth to enable site-packages...
:: Find the ._pth file (its name contains the version, e.g. python312._pth)
for %%f in ("%DIST%\python\python*._pth") do set "PTH_FILE=%%f"
if not defined PTH_FILE (
    echo  [!!] python._pth not found in embed distribution.
    goto :cleanup_fail
)
:: Append "Lib/site-packages" and uncomment "import site" so pip can install.
(
    echo python%PY_VERSION:.=%.zip
    echo .
    echo Lib\site-packages
    echo import site
) > "%PTH_FILE%"
echo        wrote: %PTH_FILE%

:: ── Step 3: Bootstrap pip into the embed Python ─────────────────────────────
echo.
echo  [3/9] Bootstrapping pip...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%TMP_DIR%\get-pip.py' -UseBasicParsing"
"%DIST%\python\python.exe" "%TMP_DIR%\get-pip.py" --no-warn-script-location
if !ERRORLEVEL! NEQ 0 goto :cleanup_fail

:: ── Step 4: Install all requirements into the embed Python ──────────────────
echo.
echo  [4/9] Installing all pip dependencies (3-5 minutes)...
"%DIST%\python\python.exe" -m pip install --no-warn-script-location -r requirements.txt
if !ERRORLEVEL! NEQ 0 goto :cleanup_fail

:: ── Step 5: Copy the application source ─────────────────────────────────────
echo.
echo  [5/9] Copying application source...
robocopy core              "%DIST%\core"              /E /NFL /NDL /NJH /NJS /NP >nul
robocopy modules           "%DIST%\modules"           /E /NFL /NDL /NJH /NJS /NP >nul
copy /y requirements.txt   "%DIST%\requirements.txt" >nul
if exist README.md         copy /y README.md          "%DIST%\README-source.md" >nul
if exist INSTALLATION.md   copy /y INSTALLATION.md    "%DIST%\INSTALLATION.md" >nul
if exist PACKAGING.md      copy /y PACKAGING.md       "%DIST%\PACKAGING.md" >nul

:: ── Step 6: Bundle Tesseract if present ─────────────────────────────────────
echo.
echo  [6/9] Bundling Tesseract OCR (if present locally)...
if exist "tesseract_bin\tesseract.exe" (
    echo        Copying tesseract_bin\ ...
    robocopy tesseract_bin "%DIST%\tesseract_bin" /E /NFL /NDL /NJH /NJS /NP >nul
    echo        [OK] tesseract bundled
) else (
    echo        [!] tesseract_bin\ not found locally. Recipient will need to
    echo            install Tesseract themselves (or run install_tesseract.bat
    echo            inside the bundle).
    if exist install_tesseract.bat copy /y install_tesseract.bat "%DIST%\install_tesseract.bat" >nul
)

:: ── Step 7: Bundle / download tessdata language packs ───────────────────────
echo.
echo  [7/9] Bundling tessdata language packs (eng/fra/ara)...
mkdir "%DIST%\tessdata"
for %%L in (eng fra ara) do (
    if exist "tessdata\%%L.traineddata" (
        copy /y "tessdata\%%L.traineddata" "%DIST%\tessdata\%%L.traineddata" >nul
        echo        [OK] %%L.traineddata copied from local tessdata
    ) else (
        echo        Downloading %%L.traineddata from GitHub...
        powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/%%L.traineddata' -OutFile '%DIST%\tessdata\%%L.traineddata' -UseBasicParsing"
    )
)

:: ── Step 8: Pre-create runtime dirs + initialize databases ──────────────────
echo.
echo  [8/9] Creating runtime data directories + initializing DBs...
mkdir "%DIST%\data"
mkdir "%DIST%\data\input\logistics" 2>nul
mkdir "%DIST%\data\input\travel" 2>nul
mkdir "%DIST%\data\logs" 2>nul
mkdir "%DIST%\data\vector" 2>nul
mkdir "%DIST%\data\exports" 2>nul

:: Use the bundle's own python to initialize the DBs so we know it works.
pushd "%DIST%"
python\python.exe -c "from core.storage.db import init_schema; from core.storage.migrations import run_migrations; init_schema('data/logistics.db'); init_schema('data/travel.db'); print('  applied logistics:', run_migrations('data/logistics.db')); print('  applied travel:   ', run_migrations('data/travel.db'))"
popd

:: ── Step 9: Write the launcher + diagnostics + README ───────────────────────
echo.
echo  [9/9] Writing portable launcher + DIAGNOSE.bat + README...

:: ───────── START.bat (the launcher inside the bundle) ─────────
> "%DIST%\START.bat" (
    echo @echo off
    echo setlocal EnableExtensions EnableDelayedExpansion
    echo title BRUNs Document Intelligence ^(portable^)
    echo color 0B
    echo cd /d "%%~dp0"
    echo.
    echo set PYTHONIOENCODING=utf-8
    echo set PYTHONUTF8=1
    echo set PORT=7845
    echo.
    echo echo.
    echo echo  ============================================================
    echo echo    BRUNS DOCUMENT INTELLIGENCE ^(portable build^)
    echo echo  ============================================================
    echo echo.
    echo.
    echo :: Verify the bundle is intact.
    echo if not exist "python\python.exe" ^(
    echo     echo  [!!] Bundle is incomplete: python\python.exe missing.
    echo     echo       Re-extract the ZIP completely.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo :: Pre-flight: import the app cleanly.
    echo python\python.exe -c "from core.api.server import app" 2^>nul
    echo if %%ERRORLEVEL%% NEQ 0 ^(
    echo     echo  [!!] Application import FAILED. Running diagnostic...
    echo     echo.
    echo     python\python.exe -m core.diagnostics
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo :: Ollama warning ^(soft^).
    echo powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop ^| Out-Null } catch { exit 1 }" ^>nul 2^>^&1
    echo if %%ERRORLEVEL%% NEQ 0 ^(
    echo     echo  [!] WARNING: Ollama is not running. Document processing will fail.
    echo     echo      Install from: https://ollama.com/download
    echo     echo      Then run:    ollama pull llama3
    echo     echo.
    echo     set /p "cont=  Continue anyway? ^(Y/N^): "
    echo     if /i "!cont!" NEQ "y" exit /b 0
    echo ^)
    echo.
    echo :: Port check.
    echo netstat -aon ^| findstr ":!PORT! " ^| findstr "LISTENING" ^>nul
    echo if %%ERRORLEVEL%% EQU 0 ^(
    echo     echo  [!] Port !PORT! already in use. Close the other instance first.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo echo  Starting Flask server on http://localhost:!PORT!/ ...
    echo echo  Stop with Ctrl+C.
    echo echo.
    echo start "" /min cmd /c "timeout /t 2 ^>nul ^&^& start http://localhost:!PORT!/"
    echo python\python.exe -m core.api.server
    echo pause
)

:: ───────── DIAGNOSE.bat (portable variant) ─────────
> "%DIST%\DIAGNOSE.bat" (
    echo @echo off
    echo setlocal EnableExtensions
    echo title BRUNs Diagnostic
    echo cd /d "%%~dp0"
    echo set PYTHONIOENCODING=utf-8
    echo set PYTHONUTF8=1
    echo if not exist "data\logs" mkdir "data\logs"
    echo python\python.exe -m core.diagnostics 2^>^&1 ^| powershell -NoProfile -Command "$input ^| Tee-Object -FilePath 'data\logs\diagnose.txt'"
    echo echo.
    echo echo  Full report saved to data\logs\diagnose.txt
    echo pause
)

:: ───────── README.txt for the recipient ─────────
> "%DIST%\README.txt" (
    echo BRUNs Document Intelligence Platform - Portable Bundle
    echo ============================================================
    echo.
    echo This folder contains everything needed to run BRUNs on Windows.
    echo No Python install, no admin rights, no internet during launch.
    echo.
    echo HOW TO RUN
    echo ----------
    echo   Double-click  START.bat
    echo   Browser opens at http://localhost:7845/
    echo.
    echo OLLAMA ^(REQUIRED FOR DOCUMENT PROCESSING^)
    echo -----------------------------------------
    echo The local LLM ^(Ollama^) is too large to bundle. Install once:
    echo   1. Download from https://ollama.com/download
    echo   2. Open PowerShell, run:  ollama pull llama3
    echo   3. Ollama runs as a background service after install.
    echo.
    echo IF SOMETHING IS WRONG
    echo ---------------------
    echo Run DIAGNOSE.bat. It writes a full report to:
    echo   data\logs\diagnose.txt
    echo Send that file with any bug report.
    echo.
    echo BUNDLE CONTENTS
    echo ---------------
    echo   python\           Python 3.12 embeddable + all pip deps
    echo   tesseract_bin\    OCR engine ^(Windows binary^)
    echo   tessdata\         OCR language packs ^(English, French, Arabic^)
    echo   core\, modules\   Application source code
    echo   data\             Empty databases + uploads + logs ^(persists between runs^)
    echo.
)

:: ── Cleanup ────────────────────────────────────────────────────────────────
echo.
echo  Cleaning up build temp...
rmdir /s /q "%TMP_DIR%" 2>nul

:: ── Optional: ZIP it up ────────────────────────────────────────────────────
echo.
echo  ============================================================
echo    BUNDLE BUILT
echo  ============================================================
echo    Location:  %DIST%\
echo.
set /p "zip_yn=  ZIP the bundle for distribution? (Y/N): "
if /i "!zip_yn!"=="y" (
    echo.
    echo  Compressing... ^(this can take 2-3 minutes^)
    powershell -NoProfile -Command "Compress-Archive -Path '%DIST%\*' -DestinationPath '%DIST%.zip' -Force"
    if exist "%DIST%.zip" (
        for %%F in ("%DIST%.zip") do echo        [OK] ZIP created: %%F  (%%~zF bytes^)
    ) else (
        echo        [!] ZIP creation failed.
    )
)

echo.
echo  Send the recipient the ZIP ^(or the whole %DIST%\ folder^).
echo  They unzip, double-click START.bat, and they're running.
echo.
pause
exit /b 0


:cleanup_fail
echo.
echo  [!!] Build aborted. Cleaning up partial output.
rmdir /s /q "%TMP_DIR%" 2>nul
rmdir /s /q "%DIST%" 2>nul
pause
exit /b 1
