# Geolocalización de IPs desde correos de Outlook

Lee tu buzón de Outlook con la **API de Microsoft Graph**, busca los correos de
Binance (u otro remitente), extrae las direcciones IP que aparecen en ellos y las
geolocaliza (país, región, ciudad, coordenadas, proveedor de Internet y enlace a
Google Maps).

## 1. Registrar la aplicación en Azure (una sola vez)

Para leer tu correo por API, Microsoft exige una aplicación registrada (es gratis):

1. Entra a <https://entra.microsoft.com> (o portal.azure.com) → **Registros de aplicaciones** → **Nuevo registro**.
2. Nombre: `geolocalizacion-ip`.
3. Tipos de cuenta admitidos:
   - Cuenta personal (@outlook.com, @hotmail.com, @live.com): **"Solo cuentas personales de Microsoft"**.
   - Cuenta de trabajo/escuela: **"Solo cuentas de este directorio organizativo"**.
4. Deja vacío el URI de redirección y pulsa **Registrar**.
5. Copia el **Id. de aplicación (cliente)**.
6. En **Autenticación** → **Configuración avanzada** activa **"Permitir flujos de clientes públicos"** → Guardar.
7. En **Permisos de API** → **Agregar un permiso** → **Microsoft Graph** → **Permisos delegados** → marca `Mail.Read`.

## 2. Instalar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Edita `.env`:

| Variable            | Valor                                                                      |
|---------------------|----------------------------------------------------------------------------|
| `OUTLOOK_CLIENT_ID` | El Id. de aplicación del paso 1.5                                          |
| `OUTLOOK_TENANT`    | `consumers` (cuenta personal), `organizations` o el ID de tu tenant        |
| `OUTLOOK_BUSQUEDA`  | Qué correos revisar, p. ej. `from:binance.com`                             |
| `IPINFO_TOKEN`      | Opcional. Token gratuito de <https://ipinfo.io> para más consultas         |

## 3. Usar

```bash
python -m geoip_outlook
```

La primera vez aparecerá un mensaje como:

```
To sign in, use a web browser to open the page https://microsoft.com/devicelogin
and enter the code ABCD1234 to authenticate.
```

Abre el enlace, pega el código e inicia sesión con tu cuenta de Outlook. El token
se guarda en `.token_cache.json`, así que las siguientes ejecuciones no piden login.

Ejemplo de salida:

```
185.199.108.153
  Correo:    2026-09-27T14:03:11Z  [Binance] Inicio de sesión desde una nueva IP
  Ubicación: San Francisco, California, US
  Proveedor: AS54113 Fastly, Inc.
  Mapa:      https://www.google.com/maps?q=37.7621,-122.3971
```

### Opciones

```bash
# Filtrar mejor los correos (sintaxis de búsqueda de Outlook)
python -m geoip_outlook --buscar "from:binance.com subject:IP" --max 20
python -m geoip_outlook --buscar "from:binance.com received>=2026-09-01"

# Guardar resultados en CSV (para Excel) o JSON
python -m geoip_outlook --salida resultados.csv
python -m geoip_outlook --salida resultados.json

# Geolocalizar IPs a mano, sin conectarse a Outlook
python -m geoip_outlook --ip 185.199.108.153 2606:4700:4700::1111
```

Se descartan automáticamente las IPs privadas o reservadas (192.168.x.x, 10.x.x.x,
127.0.0.1…) porque no se pueden geolocalizar; usa `--incluir-privadas` para verlas.

## Alternativas sin Azure

**A) Carpeta de archivos `.eml` (la más simple y fiable).** En Outlook, arrastra los
correos de Binance a una carpeta del escritorio (se guardan como `.eml`) y ejecuta:

```bash
python -m geoip_outlook --eml ./correos --salida resultados.csv
```

**B) IMAP con contraseña de aplicación.** Activa la verificación en dos pasos en tu
cuenta Microsoft, crea una *contraseña de aplicación*, rellena `IMAP_USUARIO` e
`IMAP_CLAVE` en `.env` y ejecuta `python -m geoip_outlook --imap`. Ojo: Microsoft ha
ido restringiendo IMAP con contraseña (en cuentas de trabajo suele estar bloqueado),
así que si falla usa la opción A.

## Número de orden y país de origen

Cada fila de resultados incluye `orden` (número de orden P2P extraído del correo)
junto a `ip` y `pais` (país de origen obtenido al geolocalizar la IP), listo para
cruzarlo con el panel de monitoreo P2P mediante `--salida resultados.csv|json`.

## Cómo funciona

| Archivo                            | Qué hace                                                        |
|------------------------------------|-----------------------------------------------------------------|
| `geoip_outlook/outlook.py`         | Login con MSAL (código de dispositivo) y lectura vía Graph API  |
| `geoip_outlook/extractor.py`       | Busca y valida IPv4/IPv6 en el asunto y el cuerpo del correo    |
| `geoip_outlook/geolocalizador.py`  | Consulta ipinfo.io y, si falla, ipwho.is (con caché por IP)     |
| `geoip_outlook/__main__.py`        | Línea de comandos, salida por pantalla y exportación CSV/JSON   |

## Importante

- La geolocalización por IP es **aproximada** (normalmente a nivel de ciudad o
  del proveedor de Internet). No identifica un domicilio. Si la IP es de una VPN,
  proxy o centro de datos, mostrará la ubicación de ese servidor.
- El permiso `Mail.Read` es de solo lectura: el programa no modifica ni borra correos.
- No subas `.env` ni `.token_cache.json` a GitHub (ya están en `.gitignore`).

## Pruebas

```bash
python -m unittest -v
```
