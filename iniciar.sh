#!/bin/bash
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Instala Python desde https://www.python.org/downloads/"; exit 1; }
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/python -m pip install requests; }
.venv/bin/python -m p2p_completo
