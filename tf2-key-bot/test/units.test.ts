import { describe, expect, it } from 'vitest';
import { formatMicros, orderTotalMicros } from '../src/pricing.js';
import { parseTradeUrl } from '../src/tradeUrl.js';
import { openDb, Orders } from '../src/db.js';

describe('pricing', () => {
  it('calcula totales sin errores de coma flotante', () => {
    expect(orderTotalMicros(2.3, 3)).toBe(6_900_000n);
    expect(formatMicros(6_900_000n)).toBe('6.90');
    expect(formatMicros(2_345_678n)).toBe('2.345678');
  });
});

describe('tradeUrl', () => {
  it('acepta URL válida', () => {
    const r = parseTradeUrl('https://steamcommunity.com/tradeoffer/new/?partner=1&token=abcDEF12');
    expect(r).toEqual({ steamId: '76561197960265729', token: 'abcDEF12' });
  });
  it('rechaza dominios falsos y tokens raros', () => {
    expect(parseTradeUrl('https://evil.com/tradeoffer/new/?partner=1&token=abcDEF12')).toBeNull();
    expect(parseTradeUrl('https://steamcommunity.com/tradeoffer/new/?partner=1&token=<x>')).toBeNull();
  });
});

describe('orders', () => {
  it('la transición es atómica (no hay doble envío)', () => {
    const o = new Orders(openDb(':memory:'));
    const ord = o.create({ steamId: '1', token: 'abcd', qty: 2, totalMicros: 1n, ttlMs: 1000 }, (i) => `addr${i}`);
    expect(ord.deposit_address).toBe(`addr${ord.id}`);
    expect(o.transition(ord.id, 'pending_payment', 'paid')).toBe(true);
    expect(o.transition(ord.id, 'pending_payment', 'paid')).toBe(false);
    expect(o.reservedKeys()).toBe(2);
  });
});
