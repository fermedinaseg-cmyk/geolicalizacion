"""Monitor de órdenes de VENTA de USDT en Binance P2P con panel web.

Uso:  python -m p2p_monitor [--puerto 8765] [--intervalo 30]
"""

import argparse
import os
import sys
import threading

from dotenv import load_dotenv

from geoip_outlook.geolocalizador import Geolocalizador

from .binance import ClienteBinance
from .db import Almacen
from .monitor import Monitor
from .web import servidor


def main(argv=None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(prog="p2p_monitor", description=__doc__)
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("--intervalo", type=int, default=30, help="segundos entre consultas a Binance")
    p.add_argument("--db", default="p2p_log.db")
    args = p.parse_args(argv)

    key = os.getenv("BINANCE_API_KEY", "").strip().strip("\"'")
    secret = os.getenv("BINANCE_API_SECRET", "").strip().strip("\"'")
    if not key or not secret:
        ruta = os.path.abspath(".env")
        falta = [n for n, v in (("BINANCE_API_KEY", key), ("BINANCE_API_SECRET", secret)) if not v]
        sys.exit(
            f"Falta: {', '.join(falta)}\n"
            f"El programa busca el archivo: {ruta}\n"
            f"{'Ese archivo SI existe pero esas lineas estan vacias.' if os.path.exists(ruta) else 'Ese archivo NO existe (revisa que no se llame .env.txt).'}\n"
            "Cada linea debe verse asi, sin espacios ni comillas:  BINANCE_API_KEY=tuclave"
        )

    outlook = None
    if os.getenv("OUTLOOK_CLIENT_ID"):
        from geoip_outlook.outlook import ClienteOutlook
        outlook = ClienteOutlook(os.getenv("OUTLOOK_CLIENT_ID"), os.getenv("OUTLOOK_TENANT", "consumers"))
        outlook.token()  # login (si hace falta) antes de arrancar los hilos

    monitor = Monitor(ClienteBinance(key, secret), Almacen(args.db), Geolocalizador(os.getenv("IPINFO_TOKEN", "")),
                      outlook, os.getenv("OUTLOOK_BUSQUEDA", "from:binance.com"))
    threading.Thread(target=monitor.bucle, args=(args.intervalo,), daemon=True).start()
    print(f"Panel: http://127.0.0.1:{args.puerto}   (Ctrl+C para salir)")
    try:
        servidor(monitor, args.puerto).serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
