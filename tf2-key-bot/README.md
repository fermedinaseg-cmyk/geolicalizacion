# TF2 Key Bot

Bot que **compra y vende** **Mann Co. Supply Crate Keys** de Team Fortress 2 por **USDC / USDT en Polygon**,
al estilo de clover.tf.

## Precio dinámico
Con `BACKPACK_TF_API_KEY` el precio base sale de backpack.tf (cada 5 min): `llaves en ref × valor USD del ref`.
Vendemos a `base × (1+SELL_MARGIN)` y compramos a `base × (1−BUY_MARGIN)` (siempre con spread positivo).
Sin API key, o si la lectura está fuera de `MIN_KEY_USD..MAX_KEY_USD`, se usa el último precio bueno / `KEY_PRICE_USD`.
El precio queda **fijado en el pedido** al crearlo. ⚠️ El parseo de la respuesta de backpack.tf no pudo probarse
(requiere API key); verifica en los logs `[precio]` que el valor base sea razonable antes de abrir al público.

## Flujo de VENTA (el cliente compra)
1. El cliente abre la web, pega su **Trade URL** y elige la cantidad.
2. Se crea un pedido con una **dirección de depósito única** (derivada de tu `xpub`, índice = id del pedido).
3. El servidor revisa cada 15 s el saldo USDC+USDT de esa dirección (con N confirmaciones).
4. Al llegar el monto → el bot de Steam envía la oferta con las llaves y la confirma con el `identity_secret`.
5. Cliente acepta → pedido `completed`.

## Flujo de COMPRA (el cliente vende)
1. El cliente da su Trade URL, cantidad, dirección Polygon y token (USDC/USDT).
2. Se comprueba: cupo (`MAX_STOCK`), liquidez real de la cartera caliente (menos lo ya adeudado) e inventario del cliente.
3. El bot **envía una oferta pidiendo sus llaves** (se rechaza si la cuenta tiene escrow).
4. Al aceptar, el bot paga desde la cartera caliente y espera 1 confirmación → `completed`.
5. Si la oferta se rechaza o caduca → `expired` (no se movió nada).

Ventas — estados: `pending_payment → paid → sending → completed`; además `expired` y `manual_review`
(pagos parciales, sobrepagos, ofertas rechazadas/fallidas: requieren que un humano decida/reembolse).

## Seguridad
- **Cartera caliente (`HOT_WALLET_PRIVATE_KEY`)**: para pagar compras el servidor SÍ necesita una clave privada.
  Úsala dedicada, con saldo mínimo (USDC/USDT + algo de POL para gas) y rellénala a mano. Si el servidor se compromete, solo se pierde eso.
- Los pagos nunca se reintentan a ciegas: si el envío falla o el proceso se cae a medias, el pedido va a `manual_review`
  para evitar pagar dos veces; revisa la cartera antes de repetirlo.
- Riesgo de mercado: el precio se fija al crear el pedido; el TTL corto (`ORDER_TTL_MINUTES`) limita el desfase.
- El servidor **solo tiene la xpub** (clave pública): no puede gastar los fondos. Genera la xpub offline
  desde tu frase semilla (cuenta `m/44'/60'/0'/0`) y barre las direcciones desde tu cartera fría.
- Transiciones de estado atómicas en SQLite → una orden nunca envía llaves dos veces.
- Las llaves se reservan al crear el pedido (stock = inventario − pedidos activos).
- Trade URL validada (dominio, partner, token), límite de peticiones y de pedidos pendientes por usuario.
- Usa una cuenta de Steam **dedicada**, solo con las llaves a vender.

## Puesta en marcha
```bash
cd tf2-key-bot
cp .env.example .env   # rellena credenciales, precio y xpub
npm install
npm test && npm run typecheck
npm start
```
`STEAM_SHARED_SECRET` / `STEAM_IDENTITY_SECRET` salen del autenticador móvil de la cuenta (p. ej. con SDA o `steamguard-cli`).
Usa un RPC propio (Alchemy/Infura/QuickNode) en producción en vez del público.

## Pendiente / ideas
- No probado contra Steam ni Polygon reales (sin credenciales en este entorno): pruébalo primero con 1 llave y poco dinero.
- Panel de administración para `manual_review`.
- Detección de escrow/ban de la cuenta del cliente antes de enviar.
- Cumple las condiciones de servicio de Steam y la normativa local (KYC/impuestos) de tu país.
