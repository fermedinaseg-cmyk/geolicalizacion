"""Almacén SQLite del activity log."""

import sqlite3
import threading

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ordenes (
    order_id TEXT PRIMARY KEY,
    creada_ms INTEGER, visto_ms INTEGER,
    estado TEXT, activo TEXT, monto_crypto REAL, monto_fiat REAL, fiat TEXT, comprador TEXT,
    ip TEXT DEFAULT '', pais TEXT DEFAULT '', ciudad TEXT DEFAULT '',
    proveedor TEXT DEFAULT '', origen_ip TEXT DEFAULT ''
)"""


class Almacen:
    def __init__(self, ruta: str = "p2p_log.db"):
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.con.execute(ESQUEMA)

    def guardar_orden(self, o: dict, visto_ms: int) -> bool:
        """Inserta o actualiza el estado. Devuelve True si la orden es nueva."""
        with self.lock, self.con:
            existe = self.con.execute("SELECT 1 FROM ordenes WHERE order_id=?", (o["order_id"],)).fetchone()
            if existe:
                self.con.execute("UPDATE ordenes SET estado=? WHERE order_id=?", (o["estado"], o["order_id"]))
                return False
            self.con.execute(
                "INSERT INTO ordenes(order_id,creada_ms,visto_ms,estado,activo,monto_crypto,monto_fiat,fiat,comprador)"
                " VALUES(:order_id,:creada_ms,:visto_ms,:estado,:activo,:monto_crypto,:monto_fiat,:fiat,:comprador)",
                {**o, "visto_ms": visto_ms})
            return True

    def poner_ip(self, order_id: str, ip: str, pais: str, ciudad: str, proveedor: str, origen: str) -> None:
        with self.lock, self.con:
            self.con.execute("UPDATE ordenes SET ip=?,pais=?,ciudad=?,proveedor=?,origen_ip=? WHERE order_id=?",
                             (ip, pais, ciudad, proveedor, origen, order_id))

    def sin_ip(self) -> list[str]:
        with self.lock:
            return [r[0] for r in self.con.execute("SELECT order_id FROM ordenes WHERE ip=''")]

    def listar(self, limite: int = 200) -> list[dict]:
        with self.lock:
            filas = self.con.execute("SELECT * FROM ordenes ORDER BY creada_ms DESC LIMIT ?", (limite,))
            return [dict(f) for f in filas]
