import unittest

from geoip_outlook.geolocalizador import Geolocalizacion
from p2p_monitor.binance import ClienteBinance, normalizar
from p2p_monitor.db import Almacen
from p2p_monitor.monitor import Monitor, buscar_ip_en_correos

ORDEN = {"orderNumber": 2233, "createTime": 1790000000000, "orderStatus": "COMPLETED",
         "asset": "USDT", "amount": "150.50", "totalPrice": "600000", "fiat": "VES", "counterPartNickName": "x"}


class GeoFalso:
    def localizar(self, ip):
        return Geolocalizacion(ip=ip, pais="VE", ciudad="Caracas")


class BinanceFalso:
    def ordenes_venta(self):
        return [ORDEN]


class TestP2P(unittest.TestCase):
    def setUp(self):
        self.db = Almacen(":memory:")

    def test_normalizar(self):
        n = normalizar(ORDEN)
        self.assertEqual((n["order_id"], n["monto_crypto"]), ("2233", 150.5))

    def test_firma_hmac(self):
        c = ClienteBinance("k", "secret")
        self.assertTrue(c._firmar({"a": 1}).startswith("a=1&signature="))

    def test_ciclo_no_duplica(self):
        m = Monitor(BinanceFalso(), self.db, GeoFalso())
        self.assertEqual(m.ciclo(), 1)
        self.assertEqual(m.ciclo(), 0)
        self.assertEqual(len(self.db.listar()), 1)

    def test_ip_desde_correo(self):
        Monitor(BinanceFalso(), self.db, GeoFalso()).ciclo()
        correos = [{"subject": "x", "body": {"content": "Orden 2233 pagada desde 8.8.8.8"}}]
        self.assertEqual(buscar_ip_en_correos(self.db, GeoFalso(), correos), 1)
        fila = self.db.listar()[0]
        self.assertEqual((fila["ip"], fila["pais"], fila["origen_ip"]), ("8.8.8.8", "VE", "correo"))

    def test_error_no_mata_ciclo(self):
        class Roto:
            def ordenes_venta(self):
                raise RuntimeError("sin red")
        m = Monitor(Roto(), self.db, GeoFalso())
        m.ciclo()
        self.assertEqual(m.ultimo_error, "sin red")


if __name__ == "__main__":
    unittest.main()
