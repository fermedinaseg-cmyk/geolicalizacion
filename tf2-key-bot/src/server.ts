import express from 'express';
import rateLimit from 'express-rate-limit';
import { fileURLToPath } from 'node:url';
import type { Config } from './config.js';
import type { Order, Orders } from './db.js';
import type { SteamBot } from './steam.js';
import type { Payments } from './payments.js';
import { formatMicros, orderTotalMicros } from './pricing.js';
import { parseTradeUrl } from './tradeUrl.js';

const publicOrder = (o: Order) => ({
  id: o.id,
  status: o.status,
  qty: o.qty,
  total: formatMicros(BigInt(o.total_micros)),
  address: o.deposit_address,
  network: 'Polygon',
  tokens: ['USDC', 'USDT'],
  expiresAt: o.expires_at,
});

export function createServer(cfg: Config, orders: Orders, bot: SteamBot, pay: Payments) {
  const app = express();
  app.set('trust proxy', 1);
  app.use(express.json({ limit: '2kb' }));
  app.use(express.static(fileURLToPath(new URL('../public', import.meta.url))));

  const limiter = rateLimit({ windowMs: 60_000, limit: 30 });
  app.use('/api', limiter);

  const available = () => Math.max(0, bot.keyCount - orders.reservedKeys());

  app.get('/api/info', (_req, res) => {
    res.json({ priceUsd: cfg.keyPriceUsd, stock: available(), maxPerOrder: cfg.maxKeysPerOrder, online: bot.isReady });
  });

  app.post('/api/orders', (req, res) => {
    const qty = Number(req.body?.qty);
    const parsed = parseTradeUrl(String(req.body?.tradeUrl ?? ''));
    if (!parsed) return res.status(400).json({ error: 'Trade URL inválida' });
    if (!Number.isInteger(qty) || qty < 1 || qty > cfg.maxKeysPerOrder)
      return res.status(400).json({ error: `Cantidad entre 1 y ${cfg.maxKeysPerOrder}` });
    if (!bot.isReady) return res.status(503).json({ error: 'Bot fuera de línea, intenta en unos minutos' });
    if (qty > available()) return res.status(409).json({ error: `Solo hay ${available()} llaves disponibles` });
    if (orders.pendingForSteamId(parsed.steamId) >= 2)
      return res.status(429).json({ error: 'Ya tienes pedidos pendientes; págalos o espera a que expiren' });

    const order = orders.create(
      { steamId: parsed.steamId, token: parsed.token, qty, totalMicros: orderTotalMicros(cfg.keyPriceUsd, qty), ttlMs: cfg.orderTtlMs },
      pay.addressFor,
    );
    res.status(201).json(publicOrder(order));
  });

  app.get('/api/orders/:id', (req, res) => {
    const o = orders.get(Number(req.params.id));
    if (!o) return res.status(404).json({ error: 'No existe' });
    res.json(publicOrder(o));
  });

  return app;
}
