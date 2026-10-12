// Todo el dinero se maneja en "micros" (6 decimales): coincide con USDC/USDT en Polygon.
export const MICROS = 1_000_000n;

export function usdToMicros(usd: number): bigint {
  return BigInt(Math.round(usd * 1_000_000));
}

export function orderTotalMicros(priceUsd: number, qty: number): bigint {
  return usdToMicros(priceUsd) * BigInt(qty);
}

export function formatMicros(m: bigint): string {
  const whole = m / MICROS;
  const frac = (m % MICROS).toString().padStart(6, '0').replace(/0+$/, '').padEnd(2, '0');
  return `${whole}.${frac}`;
}

export interface Quote {
  sellUsd: number; // lo que paga el cliente por llave
  buyUsd: number; // lo que pagamos al cliente por llave
  baseUsd: number;
  source: 'backpack.tf' | 'fijo';
  updatedAt: number;
}

/** Calcula venta/compra desde un precio base aplicando margen; garantiza spread mínimo. */
export function makeQuote(baseUsd: number, sellMargin: number, buyMargin: number, source: Quote['source']): Quote {
  const r = (n: number) => Math.round(n * 100) / 100; // centavos
  const sellUsd = r(baseUsd * (1 + sellMargin));
  let buyUsd = r(baseUsd * (1 - buyMargin));
  if (buyUsd >= sellUsd) buyUsd = r(sellUsd - 0.01); // nunca comprar al precio o por encima de venta
  return { sellUsd, buyUsd, baseUsd, source, updatedAt: Date.now() };
}

/** Extrae el precio USD de una llave de la respuesta de backpack.tf IGetCurrencies. */
export function parseBackpackKeyUsd(json: any): number | null {
  const c = json?.response?.currencies;
  const keyRef = Number(c?.keys?.price?.value);
  const refUsd = Number(c?.metal?.price?.value);
  const usd = keyRef * refUsd;
  return Number.isFinite(usd) && usd > 0 ? usd : null;
}

export class PriceService {
  private quote: Quote;

  constructor(
    private opts: { fixedUsd: number; sellMargin: number; buyMargin: number; apiKey?: string; minUsd: number; maxUsd: number },
  ) {
    this.quote = makeQuote(opts.fixedUsd, opts.sellMargin, opts.buyMargin, 'fijo');
  }

  get current(): Quote {
    return this.quote;
  }

  async refresh(): Promise<void> {
    if (!this.opts.apiKey) return;
    try {
      const r = await fetch(`https://backpack.tf/api/IGetCurrencies/v1?key=${encodeURIComponent(this.opts.apiKey)}`);
      const base = parseBackpackKeyUsd(await r.json());
      // Cinturón de seguridad: si el valor es absurdo (cambio de formato, manipulación), se queda el último bueno.
      if (base === null || base < this.opts.minUsd || base > this.opts.maxUsd) {
        console.error(`[precio] valor de backpack.tf fuera de rango o ilegible (${base}); se mantiene ${this.quote.baseUsd}`);
        return;
      }
      this.quote = makeQuote(base, this.opts.sellMargin, this.opts.buyMargin, 'backpack.tf');
      console.log(`[precio] base $${base.toFixed(3)} → vendemos $${this.quote.sellUsd}, compramos $${this.quote.buyUsd}`);
    } catch (e) {
      console.error('[precio] fallo al consultar backpack.tf:', (e as Error).message);
    }
  }
}
