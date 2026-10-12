// Cálculo del precio de venta de una llave de TF2 en bolivianos (BOB).
//
//   precio_bob = precio_clover_usd * (1 + MARGEN) * precio_usdt_bob
//
// - precio_clover_usd: lo que cuesta una llave en https://www.clover.tf/
//   ("Buy from us for"). Con CLOVER_LADO=sell se usa "Sell to us for".
// - precio_usdt_bob: de Binance P2P (BOB/USDT), pestaña "Comprar", anuncio con
//   mayor volumen disponible.

const CLOVER_URL = 'https://www.clover.tf/';
const BINANCE_URL = 'https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search';
const MARGEN = Number(process.env.MARGEN ?? 0.01);
const CLOVER_LADO = (process.env.CLOVER_LADO ?? 'buy').toLowerCase();
const TIMEOUT_MS = 15000;

const HEADERS = { 'User-Agent': 'Mozilla/5.0 (compatible; precio-llaves-bot/1.0)' };

/** Extrae los precios de la portada de clover.tf (HTML renderizado en servidor). */
export function parsearClover(html) {
  const texto = html.replace(/<!--.*?-->/gs, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ');
  const sell = /Sell to us for\s*\$\s*([0-9]+(?:\.[0-9]+)?)/i.exec(texto);
  const buy = /Buy from us for\s*\$\s*([0-9]+(?:\.[0-9]+)?)/i.exec(texto);
  if (!sell || !buy) throw new Error('No pude leer los precios en clover.tf (¿cambió la página?)');
  return { sell: Number(sell[1]), buy: Number(buy[1]) };
}

/** Elige el anuncio con mayor volumen disponible y devuelve su precio. */
export function precioMayorVolumen(respuesta) {
  const anuncios = (respuesta?.data ?? []).map((d) => ({
    precio: Number(d.adv?.price),
    volumen: Number(d.adv?.tradableQuantity ?? d.adv?.surplusAmount),
  })).filter((a) => a.precio > 0 && a.volumen > 0);
  if (!anuncios.length) throw new Error('Binance P2P no devolvió anuncios');
  return anuncios.reduce((mejor, a) => (a.volumen > mejor.volumen ? a : mejor));
}

export function calcularPrecio(usd, usdtBob, margen = MARGEN) {
  return usd * (1 + margen) * usdtBob;
}

async function pedir(url, opciones = {}) {
  const res = await fetch(url, { ...opciones, headers: { ...HEADERS, ...opciones.headers }, signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!res.ok) throw new Error(`${url} respondió ${res.status}`);
  return res;
}

export async function obtenerClover() {
  const precios = parsearClover(await (await pedir(CLOVER_URL)).text());
  return CLOVER_LADO === 'sell' ? precios.sell : precios.buy;
}

export async function obtenerUsdtBob() {
  const res = await pedir(BINANCE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fiat: 'BOB', asset: 'USDT', tradeType: 'BUY', page: 1, rows: 20,
      payTypes: [], countries: [], publisherType: null,
      proMerchantAds: false, shieldMerchantAds: false,
    }),
  });
  return precioMayorVolumen(await res.json());
}

export async function obtenerPrecio() {
  const [usd, anuncio] = await Promise.all([obtenerClover(), obtenerUsdtBob()]);
  const bob = calcularPrecio(usd, anuncio.precio);
  return { usd, usdtBob: anuncio.precio, volumen: anuncio.volumen, bob };
}

export function formatear({ usd, usdtBob, bob }) {
  return [
    '🔑 *Llave TF2*',
    `Precio: *Bs ${bob.toFixed(2)}*`,
    `(Clover $${usd.toFixed(3)} + ${(MARGEN * 100).toFixed(0)}% × ${usdtBob.toFixed(2)} Bs/USDT)`,
  ].join('\n');
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  obtenerPrecio().then((p) => console.log(formatear(p), '\n', p)).catch((e) => { console.error(e.message); process.exit(1); });
}
