@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Monitor Binance P2P

echo %~dp0 | findstr /i "\\Temp\\" >nul
if not errorlevel 1 (
  echo.
  echo ERROR: estas abriendo el programa DENTRO del archivo ZIP.
  echo Cierra esta ventana, haz clic derecho en el ZIP descargado,
  echo elige "Extraer todo..." y abre INICIAR_WINDOWS.bat desde la carpeta extraida.
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

if not exist .venv (
  echo Preparando el programa por primera vez, espera un momento...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo ERROR: no se pudo preparar el programa. Mueve la carpeta a C:\ o al Escritorio e intenta de nuevo.
    rmdir /s /q .venv 2>nul
    pause
    exit /b
  )
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
  if errorlevel 1 (
    echo ERROR: no se pudieron instalar las dependencias. Revisa tu conexion a internet.
    rmdir /s /q .venv 2>nul
    pause
    exit /b
  )
) else (
  call .venv\Scripts\activate.bat
)

start "" cmd /c "timeout /t 5 >nul & start http://127.0.0.1:8765"
python -m p2p_monitor
pause
