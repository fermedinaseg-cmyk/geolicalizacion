import json
import threading
import unittest
import urllib.request

from p2p_completo.api import Binance, ErrorBinance, calcular_balance, normalizar, normalizar_mensaje
from p2p_completo.web import Estado, servidor

ORDEN = {"orderNumber": "99", "advNo": "7", "tradeType": "SELL", "asset": "USDT", "fiat": "BOB", "amount": "100",
         "unitPrice": "9.5", "totalPrice": "950", "commission": "0.1", "takerCommission": "0.05",
         "counterPartNickName": "Juan", "payMethodName": "QR", "orderStatus": "COMPLETED", "createTime": 1790000000000}


class Falso:
    def __init__(self, k, s):
        self.api_key = k

    def historial(self, tipo, a, b):
        return [ORDEN] if tipo == "SELL" else []

    def permisos(self):
        raise ErrorBinance(-2008, "Invalid Api-Key ID.")

    def saldos(self):
        return {"activo": "USDT", "spot": {"libre": 5.0, "bloqueado": 0.0}, "fondos": {"libre": 10.0, "bloqueado": 1.0}, "errores": []}

    def chat(self, n):
        return [normalizar_mensaje({"content": "hola", "fromNickName": "Juan", "createTime": 1790000000})]

    def detalle(self, n):
        return {"data": {"x": 1}}


class T(unittest.TestCase):
    def test_normalizar(self):
        n = normalizar(ORDEN)
        self.assertAlmostEqual(n["comision_total"], 0.15)
        self.assertEqual((n["contraparte"], n["fiat"], n["raw"]["advNo"]), ("Juan", "BOB", "7"))

    def test_balance(self):
        def o(tipo, cant, precio, estado="COMPLETED"):
            return normalizar({**ORDEN, "tradeType": tipo, "amount": cant, "totalPrice": cant * precio, "unitPrice": precio,
                               "orderStatus": estado, "commission": "0", "takerCommission": "0"})
        b = calcular_balance([o("BUY", 100, 9.0), o("SELL", 60, 9.5), o("SELL", 10, 9.5, "TRADING"), o("BUY", 5, 9, "CANCELLED")])["BOB"]
        self.assertEqual((b["comprado"], b["vendido"], b["neto_usdt"]), (100, 60, 40))
        self.assertAlmostEqual(b["neto_fiat"], 570 - 900)
        self.assertAlmostEqual(b["ganancia_estimada"], 60 * 0.5)
        self.assertEqual((b["n_en_curso"], b["en_curso_venta"], b["canceladas"]), (1, 10, 1))

    def test_mensaje(self):
        m = normalizar_mensaje({"content": "hola", "fromNickName": "Juan", "createTime": 1790000000, "self": True, "type": "TEXT"})
        self.assertEqual((m["texto"], m["de"], m["yo"], m["hora_ms"]), ("hola", "Juan", True, 1790000000000))

    def test_error_ayuda(self):
        self.assertIn("API Key", str(ErrorBinance(-2008, "x")))

    def test_firma(self):
        self.assertEqual(Binance("k", " s ").api_key, "k")

    def test_web(self):
        import os
        e = Estado(Falso)
        s = servidor(e, 8798)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        u = "http://127.0.0.1:8798"
        get = lambda p: json.load(urllib.request.urlopen(u + p))
        self.assertFalse(get("/api/estado")["conectado"])
        req = urllib.request.Request(u + "/api/conectar", json.dumps({"key": "ABCDEFGHIJ", "secret": "s"}).encode(), method="POST")
        urllib.request.urlopen(req)
        self.assertEqual(len(get("/api/ordenes?dias=30")["ordenes"]), 1)
        self.assertIn("Invalid", get("/api/probar")["error"])
        self.assertEqual(get("/api/saldos")["fondos"]["libre"], 10.0)
        self.assertIn("BOB", get("/api/ordenes?dias=30")["balance"])
        self.assertEqual(get("/api/chat?orden=99")["mensajes"][0]["texto"], "hola")
        self.assertFalse(os.path.exists("claves_p2p.json"))
        s.shutdown()


if __name__ == "__main__":
    unittest.main()
