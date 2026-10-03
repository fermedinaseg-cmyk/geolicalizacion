"""Servidor local (solo 127.0.0.1) + página del panel."""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .api import Binance, ErrorBinance, DIA_MS, enmascarar, normalizar

ARCHIVO_CLAVES = "claves_p2p.json"
PAGINA = open(os.path.join(os.path.dirname(__file__), "pagina.html"), encoding="utf-8").read()


class Estado:
    def __init__(self, fabrica=Binance):
        self.fabrica = fabrica
        self.cliente = None
        self.cache: dict = {}
        self.cargar_guardadas()

    def conectar(self, key: str, secret: str, recordar: bool) -> None:
        self.cliente, self.cache = self.fabrica(key, secret), {}
        if recordar:
            with open(ARCHIVO_CLAVES, "w", encoding="utf-8") as f:
                json.dump({"key": key.strip(), "secret": secret.strip()}, f)
            try:
                os.chmod(ARCHIVO_CLAVES, 0o600)
            except OSError:
                pass

    def cargar_guardadas(self) -> None:
        try:
            with open(ARCHIVO_CLAVES, encoding="utf-8") as f:
                d = json.load(f)
            self.cliente = self.fabrica(d["key"], d["secret"])
        except (OSError, ValueError, KeyError):
            pass

    def olvidar(self) -> None:
        self.cliente, self.cache = None, {}
        if os.path.exists(ARCHIVO_CLAVES):
            os.remove(ARCHIVO_CLAVES)

    def ordenes(self, dias: int) -> dict:
        hit = self.cache.get(dias)
        if hit and time.time() - hit["t"] < 15:
            return hit["datos"]
        ahora = int(time.time() * 1000)
        filas = []
        for tipo in ("BUY", "SELL"):
            filas += [normalizar(o) for o in self.cliente.historial(tipo, ahora - dias * DIA_MS, ahora)]
        filas.sort(key=lambda f: f["creada_ms"], reverse=True)
        datos = {"ordenes": filas, "actualizado": int(time.time())}
        self.cache[dias] = {"t": time.time(), "datos": datos}
        return datos


def servidor(estado: Estado, puerto: int = 8766) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def _json(self, codigo, obj):
            cuerpo = json.dumps(obj).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _local(self) -> bool:
            return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

        def do_GET(self):
            if not self._local():
                return self._json(403, {})
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path == "/":
                cuerpo = PAGINA.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            elif url.path == "/api/estado":
                self._json(200, {"conectado": estado.cliente is not None,
                                 "clave": enmascarar(estado.cliente.api_key) if estado.cliente else ""})
            elif not estado.cliente:
                self._json(401, {"error": "Primero conecta tu API Key."})
            else:
                try:
                    if url.path == "/api/ordenes":
                        self._json(200, estado.ordenes(max(1, min(int(q.get("dias", ["30"])[0]), 365))))
                    elif url.path == "/api/probar":
                        p = estado.cliente.permisos()
                        self._json(200, {"clave": enmascarar(estado.cliente.api_key), "permisos": p})
                    elif url.path == "/api/chat":
                        self._json(200, {"mensajes": estado.cliente.chat(q["orden"][0])})
                    elif url.path == "/api/detalle":
                        self._json(200, estado.cliente.detalle(q["orden"][0]))
                    else:
                        self._json(404, {})
                except ErrorBinance as e:
                    self._json(200 if url.path == "/api/probar" else 502, {"error": str(e),
                               "clave": enmascarar(estado.cliente.api_key)})
                except Exception as e:
                    self._json(502, {"error": f"No se pudo consultar Binance: {e}"})

        def do_POST(self):
            if not self._local():
                return self._json(403, {})
            try:
                datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/api/conectar":
                    if not str(datos.get("key", "")).strip() or not str(datos.get("secret", "")).strip():
                        return self._json(400, {"error": "Escribe la API Key y la Secret Key."})
                    estado.conectar(str(datos["key"]), str(datos["secret"]), bool(datos.get("recordar")))
                    self._json(200, {"ok": True})
                elif self.path == "/api/desconectar":
                    estado.olvidar()
                    self._json(200, {"ok": True})
                else:
                    self._json(404, {})
            except ValueError:
                self._json(400, {"error": "solicitud inválida"})

        def log_message(self, *a):
            pass

    return ThreadingHTTPServer(("127.0.0.1", puerto), H)
