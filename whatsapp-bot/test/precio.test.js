import test from 'node:test';
import assert from 'node:assert/strict';
import { parsearClover, precioMayorVolumen, calcularPrecio } from '../src/precio.js';

test('parsea precios de clover.tf', () => {
  const html = '<span>Sell</span> <!-- -->to us for</span><span> $1.665 </span><span>Buy</span> from us for</span><span> $1.68</span>';
  assert.deepEqual(parsearClover(html), { sell: 1.665, buy: 1.68 });
});

test('clover sin precios lanza error', () => {
  assert.throws(() => parsearClover('<html></html>'));
});

test('elige el anuncio de mayor volumen', () => {
  const r = { data: [
    { adv: { price: '11.86', tradableQuantity: '193.30' } },
    { adv: { price: '11.90', tradableQuantity: '5000.00' } },
    { adv: { price: '11.80', tradableQuantity: '40' } },
  ] };
  assert.deepEqual(precioMayorVolumen(r), { precio: 11.9, volumen: 5000 });
});

test('calcula +1% y multiplica por USDT', () => {
  assert.ok(Math.abs(calcularPrecio(1.68, 11.9) - 1.68 * 1.01 * 11.9) < 1e-9);
});
