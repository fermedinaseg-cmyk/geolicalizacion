import 'node:process';

function req(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Falta la variable de entorno ${name}`);
  return v;
}

export interface Config {
  steamUser: string;
  steamPassword: string;
  sharedSecret: string;
  identitySecret: string;
  keyPriceUsd: number; // precio base fijo / respaldo
  backpackApiKey?: string;
  sellMargin: number;
  buyMargin: number;
  minKeyUsd: number;
  maxKeyUsd: number;
  maxStock: number;
  hotWalletKey: string;
  maxKeysPerOrder: number;
  xpub: string;
  rpcUrl: string;
  confirmations: number;
  orderTtlMs: number;
  port: number;
  dbPath: string;
}

export function loadConfig(): Config {
  return {
    steamUser: req('STEAM_USER'),
    steamPassword: req('STEAM_PASSWORD'),
    sharedSecret: req('STEAM_SHARED_SECRET'),
    identitySecret: req('STEAM_IDENTITY_SECRET'),
    keyPriceUsd: Number(process.env.KEY_PRICE_USD ?? '2.30'),
    backpackApiKey: process.env.BACKPACK_TF_API_KEY || undefined,
    sellMargin: Number(process.env.SELL_MARGIN ?? '0.02'),
    buyMargin: Number(process.env.BUY_MARGIN ?? '0.02'),
    minKeyUsd: Number(process.env.MIN_KEY_USD ?? '1'),
    maxKeyUsd: Number(process.env.MAX_KEY_USD ?? '10'),
    maxStock: Number(process.env.MAX_STOCK ?? '200'),
    hotWalletKey: req('HOT_WALLET_PRIVATE_KEY'),
    maxKeysPerOrder: Number(process.env.MAX_KEYS_PER_ORDER ?? '50'),
    xpub: req('PAYMENT_XPUB'),
    rpcUrl: process.env.POLYGON_RPC_URL ?? 'https://polygon-rpc.com',
    confirmations: Number(process.env.CONFIRMATIONS ?? '20'),
    orderTtlMs: Number(process.env.ORDER_TTL_MINUTES ?? '30') * 60_000,
    port: Number(process.env.PORT ?? '3000'),
    dbPath: process.env.DB_PATH ?? './data/bot.sqlite',
  };
}
