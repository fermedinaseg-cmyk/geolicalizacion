import pkg from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import { obtenerPrecio, formatear } from './precio.js';

const { Client, LocalAuth } = pkg;
const COMANDO = '.price';

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: '.wwebjs_auth' }),
  puppeteer: {
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  },
});

client.on('qr', (qr) => {
  console.log('Escanea este QR en WhatsApp > Dispositivos vinculados:');
  qrcode.generate(qr, { small: true });
});
client.on('ready', () => console.log('Bot listo. Escribe', COMANDO, 'en cualquier chat.'));

// message_create incluye tus propios mensajes (fromMe), que es lo que necesitas
// si quieres que responda cuando TÚ escribes .price en el chat.
client.on('message_create', async (msg) => {
  if (msg.body.trim().toLowerCase() !== COMANDO) return;
  try {
    await msg.reply(formatear(await obtenerPrecio()));
  } catch (e) {
    console.error(e);
    await msg.reply('No pude obtener el precio ahora, intenta en un momento.');
  }
});

client.initialize();
