@echo off
title BRUNs BI API Server
echo.
echo  ============================================
echo   BRUNs BI API Server - Starting...
echo   Connect Power BI to: http://localhost:7845
echo  ============================================
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set BRUNS_DATA_DIR=%~dp0data
python -m core.api.server
pause
