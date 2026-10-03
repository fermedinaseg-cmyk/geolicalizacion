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
    -9000: "Binance no permite leer el chat de esta orden con tu API Key (la API de chat puede estar limitada a "
           "cuentas de comerciante/anunciante).",
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

    def chat(self, numero_orden: str) -> list[dict]:
        """Mensajes del chat de una orden, del más antiguo al más nuevo."""
        mensajes, pagina = [], 1
        while pagina <= 30:
            datos = self._pedir("GET", "/sapi/v1/c2c/chat/retrieveChatMessagesWithPagination",
                                {"orderNo": numero_orden, "page": pagina, "rows": 100})
            lote = _lista(datos)
            mensajes.extend(normalizar_mensaje(m) for m in lote)
            if len(lote) < 100:
                break
            pagina += 1
        mensajes.sort(key=lambda m: m["hora_ms"])
        return mensajes

    def saldos(self, activo: str = "USDT") -> dict:
        """Cuánto {activo} tienes: billetera Spot y billetera de Fondos (donde llega el P2P)."""
        res: dict = {"activo": activo, "spot": None, "fondos": None, "errores": []}
        try:
            for b in self._pedir("GET", "/api/v3/account", {"omitZeroBalances": "true"}).get("balances", []):
                if b.get("asset") == activo:
                    res["spot"] = {"libre": _num(b.get("free")), "bloqueado": _num(b.get("locked"))}
            res["spot"] = res["spot"] or {"libre": 0.0, "bloqueado": 0.0}
        except ErrorBinance as e:
            res["errores"].append(f"Spot: {e}")
        try:
            lista = self._pedir("POST", "/sapi/v1/asset/get-funding-asset", {"asset": activo})
            fila = next((x for x in lista if x.get("asset") == activo), {}) if isinstance(lista, list) else {}
            res["fondos"] = {"libre": _num(fila.get("free")),
                             "bloqueado": _num(fila.get("locked")) + _num(fila.get("freeze")) + _num(fila.get("withdrawing"))}
        except ErrorBinance as e:
            res["errores"].append(f"Fondos: {e}")
        return res

    def detalle(self, numero_orden: str) -> dict:
        return self._pedir("POST", "/sapi/v1/c2c/orderMatch/getUserOrderDetail", {"adOrderNo": numero_orden})


def _lista(datos) -> list:
    d = datos.get("data") if isinstance(datos, dict) else datos
    if isinstance(d, dict):
        d = d.get("data") or d.get("list") or d.get("rows") or []
    return d if isinstance(d, list) else []


def _ms(v) -> int:
    n = int(_num(v))
    return n * 1000 if 0 < n < 10**11 else n


def normalizar_mensaje(m: dict) -> dict:
    """Mensaje de chat -> campos fijos. Binance puede nombrar los campos distinto, por eso se prueban varios."""
    primero = lambda *ks: next((m[k] for k in ks if m.get(k) not in (None, "")), "")
    tipo = str(primero("type", "chatMessageType", "msgType", "messageType")).lower()
    return {
        "hora_ms": _ms(primero("createTime", "chatTime", "sendTime", "time", "timestamp")),
        "de": str(primero("fromNickName", "nickName", "senderNickName", "fromNick", "sender", "fromUserNo")),
        "yo": bool(m.get("self") or m.get("isSelf") or m.get("mine")),
        "tipo": tipo,
        "texto": str(primero("content", "message", "text", "msg")),
        "imagen": str(primero("imageUrl", "imageUrlOriginal", "thumbnailUrl", "url")),
        "raw": m,
    }


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


def _estado(e: str) -> str:
    e = (e or "").upper()
    if e.startswith("COMPLETED"):
        return "completada"
    if e.startswith("CANCELLED") or e.startswith("EXPIRED"):
        return "cancelada"
    return "en_curso"


def calcular_balance(filas: list[dict], activo: str = "USDT") -> dict:
    """Balance por moneda local: lo comprado, lo vendido, la diferencia y la ganancia estimada."""
    por_fiat: dict[str, dict] = {}
    for f in filas:
        if f["activo"] != activo:
            continue
        b = por_fiat.setdefault(f["fiat"], {
            "fiat": f["fiat"], "comprado": 0.0, "pagado": 0.0, "n_compras": 0, "vendido": 0.0, "cobrado": 0.0,
            "n_ventas": 0, "comision": 0.0, "canceladas": 0, "en_curso_compra": 0.0, "en_curso_venta": 0.0, "n_en_curso": 0})
        est = _estado(f["estado"])
        compra = f["tipo"] == "BUY"
        if est == "completada":
            b["comision"] += f["comision_total"]
            if compra:
                b["comprado"] += f["cantidad"]; b["pagado"] += f["total_fiat"]; b["n_compras"] += 1
            else:
                b["vendido"] += f["cantidad"]; b["cobrado"] += f["total_fiat"]; b["n_ventas"] += 1
        elif est == "cancelada":
            b["canceladas"] += 1
        else:
            b["n_en_curso"] += 1
            b["en_curso_compra" if compra else "en_curso_venta"] += f["cantidad"]
    for b in por_fiat.values():
        b["precio_compra"] = b["pagado"] / b["comprado"] if b["comprado"] else 0.0
        b["precio_venta"] = b["cobrado"] / b["vendido"] if b["vendido"] else 0.0
        b["neto_usdt"] = b["comprado"] - b["vendido"]      # >0: acumulaste USDT; <0: vendiste más de lo que compraste
        b["neto_fiat"] = b["cobrado"] - b["pagado"]        # >0: entró más moneda local de la que salió
        pares = min(b["comprado"], b["vendido"])           # volumen "emparejado" compra/venta
        b["ganancia_estimada"] = pares * (b["precio_venta"] - b["precio_compra"]) if pares else 0.0
    return por_fiat
