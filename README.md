# Monitor de órdenes P2P de Binance

Panel local para ver tus órdenes P2P (compras y ventas de USDT) con todos los datos que entrega Binance.

## Cómo usarlo (Windows)
1. Instala Python desde <https://www.python.org/downloads/> (una sola vez).
2. Descarga el ZIP del repositorio, clic derecho → **Extraer todo…** y mueve la carpeta al Escritorio.
3. Doble clic en **`INICIAR.bat`**. La primera vez se prepara solo.
4. Se abre http://127.0.0.1:8766. Pega tu **API Key** y tu **Secret Key**.

En Mac/Linux usa `iniciar.sh`.

## API Key de Binance
Perfil → Gestión de API → Crear API → **Generada por el sistema** → activa solo **"Habilitar lectura"**.
La Secret Key solo se muestra una vez al crearla. Nunca la compartas.

## Qué muestra
Fecha, hora, ID de orden, tipo (compra/venta), cantidad, precio, total en moneda local (p. ej. BOB),
comisiones, contraparte, método de pago y estado. Incluye filtros, totales, vista de todos los campos
de cada orden (clic en la fila), detalle de la orden y descarga en CSV. Botón **Probar conexión** para
diagnosticar problemas con la API Key.

**Chat:** el botón 💬 de cada fila (o *Ver chat* dentro de la orden) muestra los mensajes del chat P2P de esa orden.
Binance puede limitar esta función a cuentas de comerciante; si la rechaza, el panel muestra el motivo.

**Balance general:** arriba del panel se ve cuántos USDT tienes ahora (billetera de Fondos, donde llega el P2P, y Spot) y,
por cada moneda local (p. ej. BOB), lo comprado, lo vendido, precios promedio, diferencias, ganancia estimada, comisiones y
órdenes en curso, con barras comparativas. Se calcula con las órdenes completadas del periodo elegido (7 a 365 días).

## Archivos
| Archivo | Qué hace |
|---|---|
| `INICIAR.bat` / `iniciar.sh` | Arrancan el programa |
| `p2p_completo/api.py` | Consulta a Binance (solo lectura) |
| `p2p_completo/web.py` | Servidor local (solo 127.0.0.1) |
| `p2p_completo/pagina.html` | La pantalla del panel |

## Pruebas
```bash
python -m unittest -v
```
