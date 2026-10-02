@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Monitor Binance P2P

set PY=python
python --version >nul 2>&1
if errorlevel 1 (
  set PY=py
  py --version >nul 2>&1
  if errorlevel 1 (
    echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
    pause
    exit /b
  )
)

if not exist .venv (
  echo Preparando el programa por primera vez, espera un momento...
  %PY% -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

if not exist .env (
  copy .env.example .env >nul
  echo.
  echo Se abrira el Bloc de notas. Escribe tu BINANCE_API_KEY y BINANCE_API_SECRET
  echo despues del signo =, guarda con Ctrl+S y cierra el Bloc de notas.
  notepad .env
)

start "" http://127.0.0.1:8765
python -m p2p_monitor
pause
