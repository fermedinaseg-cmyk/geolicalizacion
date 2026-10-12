import { loadConfig } from './config.js';
import { openDb, Orders } from './db.js';
import { Payments, Payouts } from './payments.js';
import { PriceService } from './pricing.js';
import { SteamBot } from './steam.js';
import { createServer } from './server.js';

const cfg = loadConfig();
const orders = new Orders(openDb(cfg.dbPath));
const pay = new Payments(cfg, orders);
const payouts = new Payouts(cfg, pay.provider);
const bot = new SteamBot(cfg, orders);
const prices = new PriceService({
  fixedUsd: cfg.keyPriceUsd,
  sellMargin: cfg.sellMargin,
  buyMargin: cfg.buyMargin,
  apiKey: cfg.backpackApiKey,
  minUsd: cfg.minKeyUsd,
  maxUsd: cfg.maxKeyUsd,
});
console.log(`[hot wallet] ${payouts.wallet.address}`);

// ---------- VENTA: pago recibido -> enviar llaves ----------
async function fulfillSell(orderId: number) {
  // La transición atómica paid -> sending garantiza que solo se envíe una vez.
  if (!orders.transition(orderId, 'paid', 'sending')) return;
  const order = orders.get(orderId)!;
  try {
    const offerId = await bot.sendKeys(order);
    orders.transition(orderId, 'sending', 'sending', { offer_id: offerId });
    console.log(`[pedido ${orderId}] oferta ${offerId} enviada`);
  } catch (e) {
    console.error(`[pedido ${orderId}] fallo al enviar:`, (e as Error).message);
    orders.transition(orderId, 'sending', 'manual_review', { note: `Fallo al enviar: ${(e as Error).message}` });
  }
}

// ---------- COMPRA: pedir llaves al cliente ----------
async function startBuy(orderId: number) {
  const order = orders.get(orderId)!;
  try {
    const offerId = await bot.requestKeys(order);
    orders.transition(orderId, 'awaiting_items', 'awaiting_items', { offer_id: offerId });
    console.log(`[pedido ${orderId}] oferta de compra ${offerId} enviada`);
  } catch (e) {
    // Aún no se movió nada: se cierra el pedido y el cliente ve el motivo.
    orders.transition(orderId, 'awaiting_items', 'expired', { note: (e as Error).message });
  }
}

// ---------- COMPRA: llaves recibidas -> pagar al cliente ----------
async function payBuy(order: ReturnType<Orders['get']> & {}) {
  if (order.tx_hash) return; // ya enviado; lo confirma el bucle de recuperación
  try {
    const hash = await payouts.send(order.payout_token!, order.payout_address!, BigInt(order.total_micros));
    orders.transition(order.id, 'paying', 'paying', { tx_hash: hash });
    console.log(`[pedido ${order.id}] pago enviado ${hash}`);
  } catch (e) {
    // Si falla el envío, las llaves ya son nuestras: revisión manual (nunca reintento ciego, para no pagar doble).
    orders.transition(order.id, 'paying', 'manual_review', { note: `Fallo al pagar: ${(e as Error).message}` });
  }
}
bot.onBuyAccepted = (o) => void payBuy(o);

/** Cierra pagos enviados y detecta pedidos que quedaron a medias tras un reinicio. */
async function settlePayouts() {
  for (const o of orders.byStatus('paying')) {
    if (!o.tx_hash) {
      // Pudo haberse difundido sin guardar el hash: no se reenvía automáticamente.
      if (Date.now() - o.updated_at > 2 * 60_000)
        orders.transition(o.id, 'paying', 'manual_review', { note: 'Pago sin hash registrado: verificar en la cartera caliente antes de reintentar' });
      continue;
    }
    try {
      const ok = await payouts.confirmed(o.tx_hash);
      if (ok === true) orders.transition(o.id, 'paying', 'completed', { paid_micros: o.total_micros });
      else if (ok === false) orders.transition(o.id, 'paying', 'manual_review', { note: `Transacción ${o.tx_hash} revertida` });
    } catch (e) {
      console.error(`[pagos] receipt ${o.id}:`, (e as Error).message);
    }
  }
}

// Ofertas de compra no aceptadas a tiempo: cancelar.
function expireBuys() {
  for (const o of orders.byStatus('awaiting_items')) {
    if (Date.now() > o.expires_at && o.offer_id) bot.cancelOffer(o.offer_id);
    else if (Date.now() > o.expires_at + 60_000) orders.transition(o.id, 'awaiting_items', 'expired');
  }
}

bot.login();
void prices.refresh();
createServer({ cfg, orders, bot, pay, payouts, prices, startBuy: (id) => void startBuy(id) }).listen(cfg.port, () =>
  console.log(`[web] http://localhost:${cfg.port}`),
);

let polling = false;
setInterval(async () => {
  if (polling) return;
  polling = true;
  try {
    await pay.poll((o) => void fulfillSell(o.id));
    if (bot.isReady) for (const o of orders.byStatus('paid')) await fulfillSell(o.id);
    await settlePayouts();
    expireBuys();
  } finally {
    polling = false;
  }
}, 15_000);
setInterval(() => void prices.refresh(), 5 * 60_000);
setInterval(() => void bot.refreshStock(), 5 * 60_000);
