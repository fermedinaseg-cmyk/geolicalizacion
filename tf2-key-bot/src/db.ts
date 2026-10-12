import Database from 'better-sqlite3';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export type OrderStatus =
  | 'pending_payment' // [venta] esperando depósito del cliente
  | 'paid' // [venta] pago confirmado, falta enviar llaves
  | 'awaiting_items' // [compra] oferta enviada al cliente pidiendo sus llaves
  | 'paying' // [compra] llaves recibidas, pagando en cripto
  | 'sending' // [venta] oferta de llaves en curso
  | 'completed'
  | 'expired'
  | 'manual_review'; // algo raro: revisar a mano

/** sell = el bot VENDE llaves al cliente; buy = el bot COMPRA llaves al cliente. */
export type Side = 'sell' | 'buy';
export type PayToken = 'USDC' | 'USDT';

export interface Order {
  id: number;
  side: Side;
  status: OrderStatus;
  steam_id: string;
  trade_token: string;
  qty: number;
  unit_micros: string; // precio por llave fijado al crear el pedido
  total_micros: string; // bigint como texto
  deposit_address: string; // [venta] dirección donde paga el cliente
  payout_address: string | null; // [compra] dónde le pagamos
  payout_token: PayToken | null;
  tx_hash: string | null;
  paid_micros: string;
  offer_id: string | null;
  note: string | null;
  created_at: number;
  expires_at: number;
  updated_at: number;
}

type Extra = Partial<Pick<Order, 'paid_micros' | 'offer_id' | 'note' | 'tx_hash'>>;

export function openDb(path: string) {
  if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true });
  const db = new Database(path);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      side TEXT NOT NULL DEFAULT 'sell',
      status TEXT NOT NULL,
      steam_id TEXT NOT NULL,
      trade_token TEXT NOT NULL,
      qty INTEGER NOT NULL,
      unit_micros TEXT NOT NULL DEFAULT '0',
      total_micros TEXT NOT NULL,
      deposit_address TEXT NOT NULL DEFAULT '',
      payout_address TEXT,
      payout_token TEXT,
      tx_hash TEXT,
      paid_micros TEXT NOT NULL DEFAULT '0',
      offer_id TEXT,
      note TEXT,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS orders_status ON orders(status);
  `);
  // Migración ligera para bases creadas con la versión solo-venta.
  const cols = (db.prepare('PRAGMA table_info(orders)').all() as { name: string }[]).map((c) => c.name);
  const add = (name: string, ddl: string) => !cols.includes(name) && db.exec(`ALTER TABLE orders ADD COLUMN ${ddl}`);
  add('side', `side TEXT NOT NULL DEFAULT 'sell'`);
  add('unit_micros', `unit_micros TEXT NOT NULL DEFAULT '0'`);
  add('payout_address', 'payout_address TEXT');
  add('payout_token', 'payout_token TEXT');
  add('tx_hash', 'tx_hash TEXT');
  return db;
}

export type Db = ReturnType<typeof openDb>;

export interface NewOrder {
  side: Side;
  steamId: string;
  token: string;
  qty: number;
  unitMicros: bigint;
  totalMicros: bigint;
  ttlMs: number;
  payoutAddress?: string;
  payoutToken?: PayToken;
}

export class Orders {
  constructor(private db: Db) {}

  /** Crea el pedido; en ventas asigna dirección de depósito = derivación del índice (id). */
  create(p: NewOrder, addressFor: (index: number) => string): Order {
    const now = Date.now();
    const tx = this.db.transaction(() => {
      const r = this.db
        .prepare(
          `INSERT INTO orders (side, status, steam_id, trade_token, qty, unit_micros, total_micros,
                               payout_address, payout_token, created_at, expires_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          p.side,
          p.side === 'sell' ? 'pending_payment' : 'awaiting_items',
          p.steamId,
          p.token,
          p.qty,
          p.unitMicros.toString(),
          p.totalMicros.toString(),
          p.payoutAddress ?? null,
          p.payoutToken ?? null,
          now,
          now + p.ttlMs,
          now,
        );
      const id = Number(r.lastInsertRowid);
      if (p.side === 'sell') this.db.prepare('UPDATE orders SET deposit_address = ? WHERE id = ?').run(addressFor(id), id);
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

  /** Llaves de VENTA comprometidas que aún no salieron del inventario. */
  reservedOutgoingKeys(): number {
    const row = this.db
      .prepare(
        `SELECT COALESCE(SUM(qty), 0) AS n FROM orders
         WHERE side = 'sell' AND status IN ('pending_payment','paid','sending','manual_review')`,
      )
      .get() as { n: number };
    return row.n;
  }

  /** Llaves de COMPRA que esperamos recibir (cuentan contra MAX_STOCK). */
  incomingKeys(): number {
    const row = this.db
      .prepare(`SELECT COALESCE(SUM(qty), 0) AS n FROM orders WHERE side = 'buy' AND status = 'awaiting_items'`)
      .get() as { n: number };
    return row.n;
  }

  /** Dinero (micros) que debemos pagar por compras activas: se reserva del saldo de la cartera caliente. */
  owedMicros(): bigint {
    const rows = this.db
      .prepare(
        `SELECT total_micros FROM orders WHERE side = 'buy' AND status IN ('awaiting_items','paying','manual_review')`,
      )
      .all() as { total_micros: string }[];
    return rows.reduce((a, r) => a + BigInt(r.total_micros), 0n);
  }

  pendingForSteamId(steamId: string): number {
    const row = this.db
      .prepare(`SELECT COUNT(*) AS n FROM orders WHERE steam_id = ? AND status IN ('pending_payment','awaiting_items')`)
      .get(steamId) as { n: number };
    return row.n;
  }

  /** Transición atómica: solo cambia si el estado actual es `from`. Evita dobles envíos/pagos. */
  transition(id: number, from: OrderStatus, to: OrderStatus, extra: Extra = {}): boolean {
    const r = this.db
      .prepare(
        `UPDATE orders SET status = ?, updated_at = ?,
           paid_micros = COALESCE(?, paid_micros),
           offer_id = COALESCE(?, offer_id),
           note = COALESCE(?, note),
           tx_hash = COALESCE(?, tx_hash)
         WHERE id = ? AND status = ?`,
      )
      .run(to, Date.now(), extra.paid_micros ?? null, extra.offer_id ?? null, extra.note ?? null, extra.tx_hash ?? null, id, from);
    return r.changes === 1;
  }
}
