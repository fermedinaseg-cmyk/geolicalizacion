"""Panel web local (solo 127.0.0.1) con el activity log."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from geoip_outlook.extractor import extraer_ips

from .monitor import asignar_ip

PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Binance P2P - Activity Log</title>
<style>
body{font:14px system-ui,sans-serif;margin:0;background:#0f1419;color:#e6e8ea}
header{padding:14px 20px;background:#1a2027;display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
h1{font-size:18px;margin:0} #estado{color:#8b98a5;font-size:12px}.err{color:#f6465d!important}
main{padding:16px 20px;overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:760px}
th,td{padding:8px 10px;border-bottom:1px solid #26303a;text-align:left;white-space:nowrap}
th{color:#8b98a5;font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums}
.sinip{color:#f0b90b} input{background:#0f1419;color:inherit;border:1px solid #38434f;border-radius:4px;padding:3px 6px;width:130px}
button{background:#f0b90b;border:0;border-radius:4px;padding:4px 8px;cursor:pointer}
</style>
<header><h1>Binance P2P · Ventas USDT</h1><span id="estado">cargando…</span></header>
<main><table><thead><tr><th>Fecha</th><th>Hora</th><th>ID de orden</th><th class="num">Monto</th>
<th>Estado</th><th>IP</th><th>País</th><th>Origen IP</th></tr></thead><tbody id="filas"></tbody></table></main>
<script>
const fila=(o)=>{const tr=document.createElement('tr');const d=new Date(o.creada_ms);
const c=(t,cl)=>{const td=document.createElement('td');td.textContent=t;if(cl)td.className=cl;tr.append(td);return td};
c(d.toLocaleDateString());c(d.toLocaleTimeString());c(o.order_id);c(o.monto_crypto.toFixed(2)+' '+o.activo,'num');c(o.estado);
if(o.ip){c(o.ip);c([o.pais,o.ciudad].filter(Boolean).join(' · '));c(o.origen_ip)}
else{const td=c('','sinip');const i=document.createElement('input');i.placeholder='pegar IP';
const b=document.createElement('button');b.textContent='Guardar';
b.onclick=async()=>{const r=await fetch('/api/ip',{method:'POST',body:JSON.stringify({order_id:o.order_id,ip:i.value})});
if(!r.ok)alert((await r.json()).error);else cargar()};td.append(i,' ',b);c('sin IP','sinip');c('')}
return tr};
async function cargar(){if(document.activeElement&&document.activeElement.tagName==='INPUT'&&document.activeElement.value)return;
try{const r=await(await fetch('/api/ordenes')).json();const t=document.getElementById('filas');t.replaceChildren(...r.ordenes.map(fila));
const e=document.getElementById('estado');e.className=r.error?'err':'';
e.textContent=r.error?('Error: '+r.error):('Última consulta: '+new Date(r.ultima*1000).toLocaleTimeString()+' · '+r.ordenes.length+' órdenes')}catch(x){}}
cargar();setInterval(cargar,5000);
</script></html>"""


def servidor(monitor, puerto: int = 8765) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def _enviar(self, codigo, cuerpo, tipo="application/json"):
            datos = cuerpo.encode()
            self.send_response(codigo)
            self.send_header("Content-Type", f"{tipo}; charset=utf-8")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            if self.path == "/":
                self._enviar(200, PAGINA, "text/html")
            elif self.path == "/api/ordenes":
                self._enviar(200, json.dumps({"ordenes": monitor.db.listar(), "error": monitor.ultimo_error,
                                              "ultima": monitor.ultima_consulta}))
            else:
                self._enviar(404, "{}")

        def do_POST(self):
            if self.path != "/api/ip" or self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
                return self._enviar(404, "{}")
            try:
                datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                ips = extraer_ips(str(datos["ip"]))
                if not ips:
                    return self._enviar(400, json.dumps({"error": "IP no válida o no pública"}))
                asignar_ip(monitor.db, monitor.geo, str(datos["order_id"]), ips[0], "manual")
                self._enviar(200, "{}")
            except (ValueError, KeyError):
                self._enviar(400, json.dumps({"error": "solicitud inválida"}))

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
