"""Cliente de solo lectura de Binance para órdenes P2P (historial, detalle y permisos de la API key)."""

import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

BASE = "https://api.binance.com"
DIA_MS = 86_400_000
VENTANA_MS = 30 * DIA_MS  # Binance limita cada consulta del historial a 30 días

AYUDA_ERRORES = {
    -2008: "Binance no reconoce esa API Key. Revisa que sea la API Key (no la Secret), que sea de la cuenta "
           "principal de Binance.com (no Binance.US ni testnet) y que la hayas creado como 'Generada por el sistema'.",
    -2014: "El formato de la API Key no es válido (¿se cortó al copiar o tiene espacios?).",
    -2015: "La clave existe pero no tiene permiso o tu IP no está permitida. Activa 'Habilitar lectura' "
           "y quita la restricción de IP (o agrega la IP de este computador).",
    -1022: "La Secret Key es incorrecta (o es de otra API Key).",
    -1021: "La hora de tu computador está desfasada. Sincroniza el reloj de Windows.",
}


class ErrorBinance(Exception):
    def __init__(self, codigo, mensaje):
        self.codigo, self.mensaje = codigo, mensaje
        ayuda = AYUDA_ERRORES.get(codigo, "")
        super().__init__(f"Binance {codigo}: {mensaje}" + (f"\n→ {ayuda}" if ayuda else ""))


def enmascarar(clave: str) -> str:
    return f"{clave[:4]}…{clave[-4:]} ({len(clave)} caracteres)" if len(clave) > 8 else f"({len(clave)} caracteres)"


class Binance:
    def __init__(self, api_key: str, api_secret: str, sesion: requests.Session | None = None):
        self.api_key = api_key.strip().strip("\"'")
        self._secret = api_secret.strip().strip("\"'").encode()
        self.sesion = sesion or requests.Session()

    def _pedir(self, metodo: str, ruta: str, params: dict | None = None):
        params = {**(params or {}), "recvWindow": 20000, "timestamp": int(time.time() * 1000)}
        consulta = urlencode(params)
        firma = hmac.new(self._secret, consulta.encode(), hashlib.sha256).hexdigest()
        r = self.sesion.request(metodo, f"{BASE}{ruta}?{consulta}&signature={firma}",
                                headers={"X-MBX-APIKEY": self.api_key}, timeout=25)
        try:
            datos = r.json()
        except ValueError:
            raise ErrorBinance(r.status_code, r.text[:200])
        if r.status_code >= 400 or (isinstance(datos, dict) and datos.get("code") not in (None, "000000", 0, "0") and not datos.get("success")):
            raise ErrorBinance(datos.get("code", r.status_code), datos.get("msg") or datos.get("message") or str(datos))
        return datos

    def permisos(self) -> dict:
        """Permisos de la API key (lectura, restricción de IP...). Sirve para diagnosticar la conexión."""
        return self._pedir("GET", "/sapi/v1/account/apiRestrictions")

    def historial(self, tipo: str, desde_ms: int, hasta_ms: int) -> list[dict]:
        """Órdenes P2P de un tipo (BUY/SELL) entre dos fechas, partiendo en ventanas de 30 días."""
        todas, fin = [], hasta_ms
        while fin > desde_ms:
            ini = max(desde_ms, fin - VENTANA_MS)
            pagina = 1
            while True:
                datos = self._pedir("GET", "/sapi/v1/c2c/orderMatch/listUserOrderHistory", {
                    "tradeType": tipo, "startTimestamp": ini, "endTimestamp": fin, "page": pagina, "rows": 100})
                lote = datos.get("data") or []
                todas.extend(lote)
                if len(lote) < 100 or pagina >= 50:
                    break
                pagina += 1
            fin = ini - 1
        return todas

    def detalle(self, numero_orden: str) -> dict:
        return self._pedir("POST", "/sapi/v1/c2c/orderMatch/getUserOrderDetail", {"adOrderNo": numero_orden})


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def normalizar(o: dict) -> dict:
    """Campos principales + la orden completa tal como la entrega Binance (en 'raw')."""
    maker, taker = _num(o.get("commission")), _num(o.get("takerCommission"))
    return {
        "orden": str(o.get("orderNumber", "")),
        "anuncio": str(o.get("advNo", "")),
        "creada_ms": int(_num(o.get("createTime"))),
        "tipo": o.get("tradeType", ""),
        "activo": o.get("asset", ""),
        "fiat": o.get("fiat", ""),
        "cantidad": _num(o.get("amount")),
        "precio": _num(o.get("unitPrice")),
        "total_fiat": _num(o.get("totalPrice")),
        "comision_maker": maker,
        "comision_taker": taker,
        "comision_total": maker + taker,
        "contraparte": o.get("counterPartNickName", ""),
        "metodo_pago": o.get("payMethodName", ""),
        "estado": o.get("orderStatus", ""),
        "raw": o,
    }
