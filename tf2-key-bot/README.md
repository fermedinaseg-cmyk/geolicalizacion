# TF2 Key Bot

Bot que vende **Mann Co. Supply Crate Keys** de Team Fortress 2 por **USDC / USDT en Polygon**,
al estilo de clover.tf.

## Flujo
1. El cliente abre la web, pega su **Trade URL** y elige la cantidad.
2. Se crea un pedido con una **dirección de depósito única** (derivada de tu `xpub`, índice = id del pedido).
3. El servidor revisa cada 15 s el saldo USDC+USDT de esa dirección (con N confirmaciones).
4. Al llegar el monto → el bot de Steam envía la oferta con las llaves y la confirma con el `identity_secret`.
5. Cliente acepta → pedido `completed`.

Estados: `pending_payment → paid → sending → completed`; además `expired` y `manual_review`
(pagos parciales, sobrepagos, ofertas rechazadas/fallidas: requieren que un humano decida/reembolse).

## Seguridad
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
- Precio fijo en `.env`; se puede conectar a backpack.tf para precio dinámico.
- Panel de administración para `manual_review`, y compra de llaves (el bot ahora solo vende).
- Detección de escrow/ban de la cuenta del cliente antes de enviar.
- Cumple las condiciones de servicio de Steam y la normativa local (KYC/impuestos) de tu país.
