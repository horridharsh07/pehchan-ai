@echo off
title PEHCHAAN - Dual Server Launcher
echo ========================================================
echo       PEHCHAAN: AI Identity Screening System
echo ========================================================
echo.

echo [1/2] Starting ML Backend Engine on https://127.0.0.1:8001...
start "PEHCHAAN ML Engine" cmd /k "cd /d c:\Users\DELL\Downloads\PS188\Pehchaan\backend && .venv\Scripts\python.exe run_engine.py --port 8001"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Gateway & Web UI on http://localhost:3000...
start "PEHCHAAN Gateway" cmd /k "cd /d c:\Users\DELL\Downloads\PS188\Pehchaan\Pehchaan && npm run dev"

timeout /t 2 /nobreak >nul

echo.
echo ========================================================
echo   Both servers launched!
echo   Open in browser: http://localhost:3000
echo ========================================================
echo.
pause
