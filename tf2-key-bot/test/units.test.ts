import { describe, expect, it } from 'vitest';
import { formatMicros, makeQuote, orderTotalMicros, parseBackpackKeyUsd } from '../src/pricing.js';
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

describe('precio dinámico', () => {
  it('aplica márgenes y mantiene siempre spread positivo', () => {
    const q = makeQuote(2.5, 0.02, 0.02, 'fijo');
    expect(q.sellUsd).toBe(2.55);
    expect(q.buyUsd).toBe(2.45);
    const tight = makeQuote(2.5, 0, 0, 'fijo');
    expect(tight.buyUsd).toBeLessThan(tight.sellUsd);
  });
  it('lee backpack.tf y rechaza respuestas rotas', () => {
    const ok = { response: { currencies: { keys: { price: { value: 80 } }, metal: { price: { value: 0.03 } } } } };
    expect(parseBackpackKeyUsd(ok)).toBeCloseTo(2.4);
    expect(parseBackpackKeyUsd({ response: { success: 0 } })).toBeNull();
  });
});

describe('orders', () => {
  const base = { steamId: '1', token: 'abcd', qty: 2, unitMicros: 1n, totalMicros: 2_000_000n, ttlMs: 1000 };
  it('la transición es atómica (no hay doble envío)', () => {
    const o = new Orders(openDb(':memory:'));
    const ord = o.create({ ...base, side: 'sell' }, (i) => `addr${i}`);
    expect(ord.deposit_address).toBe(`addr${ord.id}`);
    expect(o.transition(ord.id, 'pending_payment', 'paid')).toBe(true);
    expect(o.transition(ord.id, 'pending_payment', 'paid')).toBe(false);
    expect(o.reservedOutgoingKeys()).toBe(2);
  });
  it('las compras reservan dinero y cupo, no inventario', () => {
    const o = new Orders(openDb(':memory:'));
    const b = o.create({ ...base, side: 'buy', payoutAddress: '0x1', payoutToken: 'USDC' }, () => '');
    expect(b.status).toBe('awaiting_items');
    expect(o.owedMicros()).toBe(2_000_000n);
    expect(o.incomingKeys()).toBe(2);
    expect(o.reservedOutgoingKeys()).toBe(0);
    expect(o.transition(b.id, 'awaiting_items', 'paying')).toBe(true);
    expect(o.transition(b.id, 'awaiting_items', 'paying')).toBe(false); // un solo pago
  });
});
