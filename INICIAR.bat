@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Binance P2P - Panel completo

echo %~dp0 | findstr /i "\\Temp\\" >nul
if not errorlevel 1 (
  echo ERROR: estas abriendo el programa DENTRO del archivo ZIP.
  echo Haz clic derecho en el ZIP, elige "Extraer todo..." y abre este archivo desde la carpeta extraida.
  pause
  exit /b
)

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

if not exist .venv\Scripts\python.exe (
  echo Preparando el programa por primera vez, espera un momento...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo ERROR: no se pudo preparar el programa. Mueve la carpeta al Escritorio e intenta de nuevo.
    rmdir /s /q .venv 2>nul
    pause
    exit /b
  )
  .venv\Scripts\python.exe -m pip install requests
  if errorlevel 1 (
    echo ERROR: no se pudo instalar. Revisa tu conexion a internet.
    rmdir /s /q .venv 2>nul
    pause
    exit /b
  )
)

.venv\Scripts\python.exe -m p2p_completo
pause
