"""Ciclo de monitoreo: órdenes de Binance -> IP (desde correos o manual) -> geolocalización."""

import time

from geoip_outlook.extractor import extraer_ips
from geoip_outlook.geolocalizador import Geolocalizador

from .binance import ClienteBinance, normalizar
from .db import Almacen


def asignar_ip(db: Almacen, geo: Geolocalizador, order_id: str, ip: str, origen: str) -> dict:
    g = geo.localizar(ip)
    db.poner_ip(order_id, ip, g.pais, g.ciudad, g.proveedor, origen)
    return g.a_dict()


def buscar_ip_en_correos(db: Almacen, geo: Geolocalizador, correos: list[dict]) -> int:
    """Si un correo menciona el ID de una orden pendiente y contiene una IP, la asigna."""
    pendientes = db.sin_ip()
    asignadas = 0
    for correo in correos:
        texto = f"{correo.get('subject', '')}\n{correo.get('body', {}).get('content', '')}"
        for order_id in pendientes:
            if order_id in texto:
                ips = extraer_ips(texto)
                if ips:
                    asignar_ip(db, geo, order_id, ips[0], "correo")
                    pendientes.remove(order_id)
                    asignadas += 1
                    break
    return asignadas


class Monitor:
    def __init__(self, binance: ClienteBinance, db: Almacen, geo: Geolocalizador, outlook=None,
                 busqueda_correo: str = "from:binance.com"):
        self.binance, self.db, self.geo = binance, db, geo
        self.outlook, self.busqueda = outlook, busqueda_correo
        self.ultimo_error = ""
        self.ultima_consulta = 0

    def ciclo(self) -> int:
        """Una pasada. Devuelve cuántas órdenes nuevas se registraron."""
        nuevas = 0
        try:
            ahora = int(time.time() * 1000)
            for o in self.binance.ordenes_venta():
                if self.db.guardar_orden(normalizar(o), ahora):
                    nuevas += 1
            if self.outlook and self.db.sin_ip():
                buscar_ip_en_correos(self.db, self.geo, list(self.outlook.correos(self.busqueda, 50)))
            self.ultimo_error = ""
        except Exception as e:  # el monitor no debe morir por un fallo de red
            self.ultimo_error = str(e)
        self.ultima_consulta = int(time.time())
        return nuevas

    def bucle(self, segundos: int) -> None:
        while True:
            self.ciclo()
            time.sleep(segundos)
