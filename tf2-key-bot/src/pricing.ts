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
