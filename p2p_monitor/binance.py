"""Cliente de solo lectura para el historial de órdenes P2P de Binance."""

import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

BASE = "https://api.binance.com"
RUTA_HISTORIAL = "/sapi/v1/c2c/orderMatch/listUserOrderHistory"


class ClienteBinance:
    """Consulta órdenes P2P con una API key de SOLO LECTURA (sin permisos de trading/retiro)."""

    def __init__(self, api_key: str, api_secret: str, sesion: requests.Session | None = None):
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.sesion = sesion or requests.Session()

    def _firmar(self, params: dict) -> str:
        consulta = urlencode(params)
        firma = hmac.new(self.api_secret, consulta.encode(), hashlib.sha256).hexdigest()
        return f"{consulta}&signature={firma}"

    def ordenes_venta(self, paginas: int = 1) -> list[dict]:
        """Devuelve las órdenes de VENTA más recientes (100 por página)."""
        ordenes: list[dict] = []
        for pagina in range(1, paginas + 1):
            params = {"tradeType": "SELL", "page": pagina, "rows": 100,
                      "recvWindow": 10000, "timestamp": int(time.time() * 1000)}
            r = self.sesion.get(f"{BASE}{RUTA_HISTORIAL}?{self._firmar(params)}",
                                headers={"X-MBX-APIKEY": self.api_key}, timeout=20)
            datos = r.json()
            if r.status_code >= 400 or not datos.get("success", True):
                raise RuntimeError(f"Binance {r.status_code}: {datos.get('msg') or datos.get('message') or datos}")
            lote = datos.get("data") or []
            ordenes.extend(lote)
            if len(lote) < 100:
                break
        return ordenes


def normalizar(o: dict) -> dict:
    """Convierte una orden de Binance en la fila que guardamos."""
    return {
        "order_id": str(o["orderNumber"]),
        "creada_ms": int(o.get("createTime") or 0),
        "estado": o.get("orderStatus", ""),
        "activo": o.get("asset", "USDT"),
        "monto_crypto": float(o.get("amount") or 0),
        "monto_fiat": float(o.get("totalPrice") or 0),
        "fiat": o.get("fiat", ""),
        "comprador": o.get("counterPartNickName", ""),
    }
