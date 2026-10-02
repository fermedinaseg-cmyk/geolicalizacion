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


def _guardar_env(key: str, secret: str) -> None:
    """Escribe las claves en .env conservando las demás líneas."""
    lineas = []
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8-sig") as f:
            lineas = [l.rstrip("\n") for l in f if not l.startswith(("BINANCE_API_KEY", "BINANCE_API_SECRET"))]
    lineas += [f"BINANCE_API_KEY={key}", f"BINANCE_API_SECRET={secret}"]
    with open(".env", "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


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
        if not sys.stdin.isatty():
            sys.exit("Faltan BINANCE_API_KEY y BINANCE_API_SECRET en .env")
        print("No encontre tus claves de Binance. Pegalas aqui (clic derecho = pegar) y pulsa Enter.")
        key = input("API Key: ").strip().strip("\"'")
        secret = input("Secret Key: ").strip().strip("\"'")
        if not key or not secret:
            sys.exit("No escribiste las claves. Vuelve a abrir el programa.")
        _guardar_env(key, secret)
        print(f"Claves guardadas en {os.path.abspath('.env')}. No tendras que escribirlas otra vez.\n")

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
