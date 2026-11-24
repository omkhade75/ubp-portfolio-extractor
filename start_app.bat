@echo off
title UBP Portfolio Statement Extraction System
echo ===================================================
echo Starting UBP Portfolio Statement Extraction System
echo ===================================================

cd /d "%~dp0"

echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "UBP Extraction Backend" cmd /k "set PYTHONPATH=%~dp0backend&& python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Launching Vite Frontend on http://localhost:5173 ...
start "UBP Extraction Frontend" cmd /k "cd frontend && npx vite --host localhost --port 5173"

timeout /t 3 >nul
echo Opening browser at http://localhost:5173 ...
start http://localhost:5173

echo ===================================================
echo Applications launched successfully!
echo Backend:  http://127.0.0.1:8000 (API & Docs: /docs)
echo Frontend: http://localhost:5173
echo ===================================================
pause
