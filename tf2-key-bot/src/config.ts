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
  keyPriceUsd: number;
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
    maxKeysPerOrder: Number(process.env.MAX_KEYS_PER_ORDER ?? '50'),
    xpub: req('PAYMENT_XPUB'),
    rpcUrl: process.env.POLYGON_RPC_URL ?? 'https://polygon-rpc.com',
    confirmations: Number(process.env.CONFIRMATIONS ?? '20'),
    orderTtlMs: Number(process.env.ORDER_TTL_MINUTES ?? '30') * 60_000,
    port: Number(process.env.PORT ?? '3000'),
    dbPath: process.env.DB_PATH ?? './data/bot.sqlite',
  };
}
