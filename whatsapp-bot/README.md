# Bot de WhatsApp: precio de llaves TF2

Cuando escribes `.price` en un chat, el bot responde con el precio de venta de una llave en Bs:

```
precio = precio Clover (USD) × 1.01 × precio USDT/BOB
```

- **Clover**: https://www.clover.tf/ — por defecto "Buy from us for" (lo que te cuesta la llave). Con `CLOVER_LADO=sell` usa "Sell to us for".
- **USDT/BOB**: Binance P2P, pestaña *Comprar*, el anuncio con mayor volumen disponible.
- El margen es `MARGEN=0.01` (1%) y se puede cambiar por variable de entorno.

## Uso

```bash
npm install
npm start          # escanea el QR con WhatsApp > Dispositivos vinculados
npm run precio     # prueba el cálculo sin WhatsApp
npm test
```

La sesión queda guardada en `.wwebjs_auth/`. Si Chromium no se descarga solo, define `CHROMIUM_PATH`.
El bot responde también a tus propios mensajes, y a los de cualquier contacto en los chats donde esté activo.
