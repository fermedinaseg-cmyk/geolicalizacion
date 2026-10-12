import { loadConfig } from './config.js';
import { openDb, Orders } from './db.js';
import { Payments } from './payments.js';
import { SteamBot } from './steam.js';
import { createServer } from './server.js';

const cfg = loadConfig();
const orders = new Orders(openDb(cfg.dbPath));
const pay = new Payments(cfg, orders);
const bot = new SteamBot(cfg, orders);

async function fulfill(orderId: number) {
  // La transición atómica paid -> sending garantiza que solo un proceso envíe.
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

// Pedidos 'paid' que quedaron colgados (p. ej. el bot estaba offline): reintentar.
async function retryPaid() {
  if (!bot.isReady) return;
  for (const o of orders.byStatus('paid')) await fulfill(o.id);
}

bot.login();
createServer(cfg, orders, bot, pay).listen(cfg.port, () => console.log(`[web] http://localhost:${cfg.port}`));

let polling = false;
setInterval(async () => {
  if (polling) return;
  polling = true;
  try {
    await pay.poll((o) => void fulfill(o.id));
    await retryPaid();
  } finally {
    polling = false;
  }
}, 15_000);
setInterval(() => void bot.refreshStock(), 5 * 60_000);
