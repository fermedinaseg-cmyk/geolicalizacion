import Database from 'better-sqlite3';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export type OrderStatus =
  | 'pending_payment' // esperando depósito
  | 'paid' // pago confirmado, falta enviar llaves
  | 'sending' // oferta en curso
  | 'completed' // oferta aceptada
  | 'expired' // no se pagó a tiempo
  | 'manual_review'; // algo raro: revisar a mano

export interface Order {
  id: number;
  status: OrderStatus;
  steam_id: string;
  trade_token: string;
  qty: number;
  total_micros: string; // bigint como texto
  deposit_address: string;
  paid_micros: string;
  offer_id: string | null;
  note: string | null;
  created_at: number;
  expires_at: number;
  updated_at: number;
}

export function openDb(path: string) {
  mkdirSync(dirname(path), { recursive: true });
  const db = new Database(path);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      status TEXT NOT NULL,
      steam_id TEXT NOT NULL,
      trade_token TEXT NOT NULL,
      qty INTEGER NOT NULL,
      total_micros TEXT NOT NULL,
      deposit_address TEXT NOT NULL DEFAULT '',
      paid_micros TEXT NOT NULL DEFAULT '0',
      offer_id TEXT,
      note TEXT,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS orders_status ON orders(status);
  `);
  return db;
}

export type Db = ReturnType<typeof openDb>;

export class Orders {
  constructor(private db: Db) {}

  /** Crea el pedido y asigna dirección de depósito = derivación del índice (id). */
  create(
    p: { steamId: string; token: string; qty: number; totalMicros: bigint; ttlMs: number },
    addressFor: (index: number) => string,
  ): Order {
    const now = Date.now();
    const tx = this.db.transaction(() => {
      const r = this.db
        .prepare(
          `INSERT INTO orders (status, steam_id, trade_token, qty, total_micros, created_at, expires_at, updated_at)
           VALUES ('pending_payment', ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(p.steamId, p.token, p.qty, p.totalMicros.toString(), now, now + p.ttlMs, now);
      const id = Number(r.lastInsertRowid);
      this.db.prepare('UPDATE orders SET deposit_address = ? WHERE id = ?').run(addressFor(id), id);
      return id;
    });
    return this.get(tx())!;
  }

  get(id: number): Order | undefined {
    return this.db.prepare('SELECT * FROM orders WHERE id = ?').get(id) as Order | undefined;
  }

  byStatus(status: OrderStatus): Order[] {
    return this.db.prepare('SELECT * FROM orders WHERE status = ?').all(status) as Order[];
  }

  /** Llaves comprometidas (pagadas o por pagar) que aún no salieron del inventario. */
  reservedKeys(): number {
    const row = this.db
      .prepare(
        `SELECT COALESCE(SUM(qty), 0) AS n FROM orders
         WHERE status IN ('pending_payment','paid','sending','manual_review')`,
      )
      .get() as { n: number };
    return row.n;
  }

  pendingForSteamId(steamId: string): number {
    const row = this.db
      .prepare(`SELECT COUNT(*) AS n FROM orders WHERE steam_id = ? AND status = 'pending_payment'`)
      .get(steamId) as { n: number };
    return row.n;
  }

  /** Transición atómica: solo cambia si el estado actual es `from`. Evita dobles envíos. */
  transition(id: number, from: OrderStatus, to: OrderStatus, extra: Partial<Pick<Order, 'paid_micros' | 'offer_id' | 'note'>> = {}): boolean {
    const r = this.db
      .prepare(
        `UPDATE orders SET status = ?, updated_at = ?,
           paid_micros = COALESCE(?, paid_micros),
           offer_id = COALESCE(?, offer_id),
           note = COALESCE(?, note)
         WHERE id = ? AND status = ?`,
      )
      .run(to, Date.now(), extra.paid_micros ?? null, extra.offer_id ?? null, extra.note ?? null, id, from);
    return r.changes === 1;
  }
}
