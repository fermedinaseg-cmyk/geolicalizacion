"""Lee correos de Outlook (p. ej. de Binance), extrae las IPs y las geolocaliza.

Uso:
    python -m geoip_outlook                      # busca correos según .env
    python -m geoip_outlook --buscar "from:binance.com subject:IP" --max 20
    python -m geoip_outlook --salida resultados.csv
    python -m geoip_outlook --ip 8.8.8.8 1.1.1.1 # geolocaliza IPs sin usar Outlook
"""

import argparse
import csv
import json
import os
import sys

from dotenv import load_dotenv

from .extractor import extraer_ips
from .geolocalizador import Geolocalizador

COLUMNAS = [
    "fecha", "remitente", "asunto", "ip", "pais", "region", "ciudad",
    "latitud", "longitud", "proveedor", "mapa", "fuente", "error",
]


def _argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="geoip_outlook", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--buscar", default=os.getenv("OUTLOOK_BUSQUEDA", "from:binance.com"),
                   help="búsqueda KQL de Outlook (por defecto: %(default)s)")
    p.add_argument("--max", type=int, default=50, help="máximo de correos a revisar")
    p.add_argument("--salida", help="guardar resultados en .csv o .json")
    p.add_argument("--incluir-privadas", action="store_true",
                   help="no descartar IPs privadas/reservadas")
    p.add_argument("--ip", nargs="+", help="geolocalizar estas IPs directamente, sin Outlook")
    return p.parse_args(argv)


def _filas_desde_outlook(args, geo: Geolocalizador):
    from .outlook import ClienteOutlook

    client_id = os.getenv("OUTLOOK_CLIENT_ID")
    if not client_id:
        sys.exit("Falta OUTLOOK_CLIENT_ID en el archivo .env (ver README.md).")
    cliente = ClienteOutlook(client_id, os.getenv("OUTLOOK_TENANT", "consumers"))

    for correo in cliente.correos(args.buscar, args.max):
        cuerpo = correo.get("body", {}).get("content", "")
        texto = f"{correo.get('subject', '')}\n{cuerpo}"
        remitente = correo.get("from", {}).get("emailAddress", {}).get("address", "")
        for ip in extraer_ips(texto, args.incluir_privadas):
            yield {
                "fecha": correo.get("receivedDateTime", ""),
                "remitente": remitente,
                "asunto": correo.get("subject", ""),
                **geo.localizar(ip).a_dict(),
            }


def _filas_desde_ips(args, geo: Geolocalizador):
    for ip in args.ip:
        yield {"fecha": "", "remitente": "", "asunto": "", **geo.localizar(ip).a_dict()}


def _imprimir(fila: dict) -> None:
    lugar = ", ".join(x for x in (fila["ciudad"], fila["region"], fila["pais"]) if x)
    print(f"\n{fila['ip']}")
    if fila["asunto"]:
        print(f"  Correo:    {fila['fecha']}  {fila['asunto']}")
    if fila["error"]:
        print(f"  Error:     {fila['error']}")
        return
    print(f"  Ubicación: {lugar or 'desconocida'}")
    print(f"  Proveedor: {fila['proveedor']}")
    if fila["mapa"]:
        print(f"  Mapa:      {fila['mapa']}")


def _guardar(filas: list[dict], ruta: str) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        if ruta.lower().endswith(".json"):
            json.dump(filas, f, ensure_ascii=False, indent=2)
        else:
            escritor = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(filas)
    print(f"\nResultados guardados en {ruta}")


def main(argv=None) -> int:
    load_dotenv()
    args = _argumentos(argv)
    geo = Geolocalizador(os.getenv("IPINFO_TOKEN", ""))

    origen = _filas_desde_ips if args.ip else _filas_desde_outlook
    filas = []
    for fila in origen(args, geo):
        _imprimir(fila)
        filas.append(fila)

    if not filas:
        print("No se encontraron IPs." if args.ip else
              f"No se encontraron IPs en los correos que coinciden con: {args.buscar}")
    elif args.salida:
        _guardar(filas, args.salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
