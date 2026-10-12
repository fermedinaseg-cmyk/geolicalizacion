import express from 'express';
import rateLimit from 'express-rate-limit';
import { fileURLToPath } from 'node:url';
import type { Config } from './config.js';
import type { Order, Orders, PayToken } from './db.js';
import type { SteamBot } from './steam.js';
import { isValidPayoutAddress, type Payments, type Payouts } from './payments.js';
import { formatMicros, usdToMicros, type PriceService } from './pricing.js';
import { parseTradeUrl } from './tradeUrl.js';

const publicOrder = (o: Order) => ({
  id: o.id,
  side: o.side,
  status: o.status,
  qty: o.qty,
  unit: formatMicros(BigInt(o.unit_micros)),
  total: formatMicros(BigInt(o.total_micros)),
  // venta: dirección donde paga el cliente; compra: dónde le pagamos
  address: o.side === 'sell' ? o.deposit_address : o.payout_address,
  payoutToken: o.payout_token,
  txHash: o.tx_hash,
  network: 'Polygon',
  tokens: ['USDC', 'USDT'],
  expiresAt: o.expires_at,
});

export interface Deps {
  cfg: Config;
  orders: Orders;
  bot: SteamBot;
  pay: Payments;
  payouts: Payouts;
  prices: PriceService;
  /** Lanza la solicitud de llaves al cliente (compra). */
  startBuy: (orderId: number) => void;
}

export function createServer({ cfg, orders, bot, pay, payouts, prices, startBuy }: Deps) {
  const app = express();
  app.set('trust proxy', 1);
  app.use(express.json({ limit: '2kb' }));
  app.use(express.static(fileURLToPath(new URL('../public', import.meta.url))));
  app.use('/api', rateLimit({ windowMs: 60_000, limit: 30 }));

  const sellStock = () => Math.max(0, bot.keyCount - orders.reservedOutgoingKeys());
  const buyRoom = () => Math.max(0, cfg.maxStock - bot.keyCount - orders.incomingKeys());

  app.get('/api/info', (_req, res) => {
    const q = prices.current;
    res.json({
      sellUsd: q.sellUsd, // el cliente PAGA esto por llave
      buyUsd: q.buyUsd, // el cliente RECIBE esto por llave
      priceSource: q.source,
      priceUpdatedAt: q.updatedAt,
      sellStock: sellStock(),
      buyRoom: buyRoom(),
      maxPerOrder: cfg.maxKeysPerOrder,
      online: bot.isReady,
    });
  });

  app.post('/api/orders', async (req, res) => {
    const side = req.body?.side === 'buy' ? 'buy' : 'sell'; // 'buy' = el bot compra, el cliente vende
    const qty = Number(req.body?.qty);
    const parsed = parseTradeUrl(String(req.body?.tradeUrl ?? ''));
    if (!parsed) return res.status(400).json({ error: 'Trade URL inválida' });
    if (!Number.isInteger(qty) || qty < 1 || qty > cfg.maxKeysPerOrder)
      return res.status(400).json({ error: `Cantidad entre 1 y ${cfg.maxKeysPerOrder}` });
    if (!bot.isReady) return res.status(503).json({ error: 'Bot fuera de línea, intenta en unos minutos' });
    if (orders.pendingForSteamId(parsed.steamId) >= 2)
      return res.status(429).json({ error: 'Ya tienes pedidos pendientes; complétalos o espera a que expiren' });

    const quote = prices.current; // el precio queda fijado en el pedido
    const base = { steamId: parsed.steamId, token: parsed.token, qty, ttlMs: cfg.orderTtlMs };

    if (side === 'sell') {
      if (qty > sellStock()) return res.status(409).json({ error: `Solo hay ${sellStock()} llaves disponibles` });
      const unit = usdToMicros(quote.sellUsd);
      const order = orders.create({ ...base, side, unitMicros: unit, totalMicros: unit * BigInt(qty) }, pay.addressFor);
      return res.status(201).json(publicOrder(order));
    }

    // --- Compra: el cliente nos vende llaves y le pagamos USDC/USDT ---
    const payoutAddress = String(req.body?.payoutAddress ?? '').trim();
    const payoutToken = req.body?.payoutToken as PayToken;
    if (!isValidPayoutAddress(payoutAddress)) return res.status(400).json({ error: 'Dirección de pago (Polygon) inválida' });
    if (payoutToken !== 'USDC' && payoutToken !== 'USDT') return res.status(400).json({ error: 'Elige USDC o USDT' });
    if (qty > buyRoom()) return res.status(409).json({ error: `Solo podemos comprar ${buyRoom()} llaves ahora mismo` });

    const unit = usdToMicros(quote.buyUsd);
    const total = unit * BigInt(qty);
    try {
      // Que haya fondos reales para pagar, descontando lo ya comprometido con otros clientes.
      const available = (await payouts.balance(payoutToken)) - orders.owedMicros();
      if (available < total) return res.status(409).json({ error: 'Sin liquidez suficiente para esa compra, prueba con menos llaves' });
    } catch {
      return res.status(503).json({ error: 'No se pudo verificar liquidez, intenta de nuevo' });
    }
    const order = orders.create({ ...base, side, unitMicros: unit, totalMicros: total, payoutAddress, payoutToken }, pay.addressFor);
    startBuy(order.id);
    res.status(201).json(publicOrder(order));
  });

  app.get('/api/orders/:id', (req, res) => {
    const o = orders.get(Number(req.params.id));
    if (!o) return res.status(404).json({ error: 'No existe' });
    res.json(publicOrder(o));
  });

  return app;
}
