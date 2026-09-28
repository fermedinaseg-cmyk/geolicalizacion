"""Geolocalización de direcciones IP mediante servicios públicos."""

from dataclasses import asdict, dataclass
from typing import Optional

import requests

TIMEOUT = 10


@dataclass
class Geolocalizacion:
    ip: str
    pais: str = ""
    region: str = ""
    ciudad: str = ""
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    proveedor: str = ""  # ISP / organización dueña de la IP
    fuente: str = ""
    error: str = ""

    @property
    def mapa(self) -> str:
        if self.latitud is None or self.longitud is None:
            return ""
        return f"https://www.google.com/maps?q={self.latitud},{self.longitud}"

    def a_dict(self) -> dict:
        datos = asdict(self)
        datos["mapa"] = self.mapa
        return datos


def _con_ipinfo(ip: str, token: str, sesion: requests.Session) -> Geolocalizacion:
    params = {"token": token} if token else None
    r = sesion.get(f"https://ipinfo.io/{ip}/json", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    if d.get("bogon"):
        raise ValueError("IP no enrutable (bogon)")
    lat = lon = None
    if d.get("loc"):
        lat, lon = (float(v) for v in d["loc"].split(","))
    return Geolocalizacion(
        ip=ip,
        pais=d.get("country", ""),
        region=d.get("region", ""),
        ciudad=d.get("city", ""),
        latitud=lat,
        longitud=lon,
        proveedor=d.get("org", ""),
        fuente="ipinfo.io",
    )


def _con_ipwhois(ip: str, sesion: requests.Session) -> Geolocalizacion:
    # Gratuito, HTTPS y sin token.
    r = sesion.get(f"https://ipwho.is/{ip}", timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    if not d.get("success", False):
        raise ValueError(d.get("message", "respuesta sin éxito"))
    return Geolocalizacion(
        ip=ip,
        pais=d.get("country", ""),
        region=d.get("region", ""),
        ciudad=d.get("city", ""),
        latitud=d.get("latitude"),
        longitud=d.get("longitude"),
        proveedor=(d.get("connection") or {}).get("isp", ""),
        fuente="ipwho.is",
    )


class Geolocalizador:
    """Consulta ipinfo.io y, si falla, ipwho.is. Guarda en caché cada IP."""

    def __init__(self, token_ipinfo: str = "", sesion: Optional[requests.Session] = None):
        self.token = token_ipinfo
        self.sesion = sesion or requests.Session()
        self._cache: dict[str, Geolocalizacion] = {}

    def localizar(self, ip: str) -> Geolocalizacion:
        if ip in self._cache:
            return self._cache[ip]
        errores = []
        for consulta in (
            lambda: _con_ipinfo(ip, self.token, self.sesion),
            lambda: _con_ipwhois(ip, self.sesion),
        ):
            try:
                resultado = consulta()
                break
            except (requests.RequestException, ValueError, KeyError) as e:
                errores.append(str(e))
        else:
            resultado = Geolocalizacion(ip=ip, error=" | ".join(errores))
        self._cache[ip] = resultado
        return resultado
