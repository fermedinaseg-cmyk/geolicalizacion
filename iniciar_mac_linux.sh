#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo "Instala Python desde https://www.python.org/downloads/"; exit 1
fi
if [ ! -d .venv ]; then
  echo "Preparando el programa por primera vez..."
  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
else
  source .venv/bin/activate
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Abre el archivo .env, escribe BINANCE_API_KEY y BINANCE_API_SECRET, guarda y vuelve a ejecutar."
  open -e .env 2>/dev/null || xdg-open .env 2>/dev/null
  exit 0
fi
(sleep 2; open http://127.0.0.1:8765 2>/dev/null || xdg-open http://127.0.0.1:8765 2>/dev/null) &
python -m p2p_monitor
