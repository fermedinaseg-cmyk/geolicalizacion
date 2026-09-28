import unittest
from unittest import mock

import requests

from geoip_outlook.extractor import extraer_ips
from geoip_outlook.geolocalizador import Geolocalizador

CORREO_BINANCE = """
<p>Nuevo inicio de sesión detectado</p>
<table><tr><td>Dirección IP:</td><td>185.199.108.153</td></tr>
<tr><td>IP secundaria</td><td>2606:4700:4700::1111</td></tr></table>
Router local 192.168.1.1, versión 1.2.3.4.5, hora 12:30:45, repetida 185.199.108.153
"""


class TestExtractor(unittest.TestCase):
    def test_extrae_ips_publicas_sin_duplicados(self):
        self.assertEqual(extraer_ips(CORREO_BINANCE), ["185.199.108.153", "2606:4700:4700::1111"])

    def test_incluir_privadas(self):
        self.assertIn("192.168.1.1", extraer_ips(CORREO_BINANCE, incluir_privadas=True))

    def test_descarta_octetos_invalidos(self):
        self.assertEqual(extraer_ips("IP: 300.1.1.1"), [])


def _respuesta(datos, status=200):
    r = mock.Mock()
    r.json.return_value = datos
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(str(status))
    return r


class TestGeolocalizador(unittest.TestCase):
    def test_ipinfo(self):
        sesion = mock.Mock()
        sesion.get.return_value = _respuesta({
            "ip": "8.8.8.8", "city": "Mountain View", "region": "California",
            "country": "US", "loc": "37.4056,-122.0775", "org": "AS15169 Google LLC",
        })
        g = Geolocalizador(sesion=sesion).localizar("8.8.8.8")
        self.assertEqual((g.ciudad, g.pais, g.fuente), ("Mountain View", "US", "ipinfo.io"))
        self.assertEqual(g.mapa, "https://www.google.com/maps?q=37.4056,-122.0775")

    def test_respaldo_ipwhois_y_cache(self):
        sesion = mock.Mock()
        sesion.get.side_effect = [
            _respuesta({}, status=429),
            _respuesta({"success": True, "country": "Spain", "region": "Madrid",
                        "city": "Madrid", "latitude": 40.4, "longitude": -3.7,
                        "connection": {"isp": "Telefonica"}}),
        ]
        geo = Geolocalizador(sesion=sesion)
        g = geo.localizar("80.58.61.250")
        self.assertEqual((g.ciudad, g.proveedor, g.fuente), ("Madrid", "Telefonica", "ipwho.is"))
        geo.localizar("80.58.61.250")
        self.assertEqual(sesion.get.call_count, 2)

    def test_error_si_fallan_ambos(self):
        sesion = mock.Mock()
        sesion.get.side_effect = requests.ConnectionError("sin red")
        g = Geolocalizador(sesion=sesion).localizar("1.1.1.1")
        self.assertIn("sin red", g.error)


if __name__ == "__main__":
    unittest.main()
