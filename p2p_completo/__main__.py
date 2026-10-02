"""Panel completo de órdenes P2P de Binance. Uso: python -m p2p_completo"""

import sys
import threading
import webbrowser

from .web import Estado, servidor

PUERTO = 8766


def main() -> int:
    s = servidor(Estado(), PUERTO)
    url = f"http://127.0.0.1:{PUERTO}"
    print(f"Panel: {url}   (cierra esta ventana para detener el programa)")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
