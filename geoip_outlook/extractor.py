"""Extracción de direcciones IP desde el texto de un correo."""

import html
import ipaddress
import re

# Candidatos amplios; la validación real la hace el módulo ipaddress.
_IPV4 = r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"
_IPV6 = r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])"
_CANDIDATO = re.compile(f"{_IPV4}|{_IPV6}")
_ETIQUETA_HTML = re.compile(r"<[^>]+>")


def limpiar_html(texto: str) -> str:
    """Convierte un cuerpo HTML en texto plano aproximado."""
    return html.unescape(_ETIQUETA_HTML.sub(" ", texto))


def extraer_ips(texto: str, incluir_privadas: bool = False) -> list[str]:
    """Devuelve las IPs válidas encontradas en ``texto``, sin duplicados y en orden.

    Por defecto descarta IPs privadas, de loopback, reservadas, etc., que no se
    pueden geolocalizar.
    """
    vistas: list[str] = []
    for candidato in _CANDIDATO.findall(limpiar_html(texto)):
        try:
            ip = ipaddress.ip_address(candidato)
        except ValueError:
            continue
        if not incluir_privadas and not ip.is_global:
            continue
        normalizada = str(ip)
        if normalizada not in vistas:
            vistas.append(normalizada)
    return vistas
