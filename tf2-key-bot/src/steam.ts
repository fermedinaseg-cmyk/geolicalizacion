import SteamUser from 'steam-user';
import SteamCommunity from 'steamcommunity';
import TradeOfferManager from 'steam-tradeoffer-manager';
import SteamTotp from 'steam-totp';
import type { Config } from './config.js';
import type { Order, Orders } from './db.js';

const TF2_APPID = 440;
const TF2_CONTEXT = 2;
const KEY_NAME = 'Mann Co. Supply Crate Key';

export class SteamBot {
  private client = new SteamUser();
  private community = new SteamCommunity();
  private manager: any;
  private ready = false;
  private cachedKeys = 0;

  constructor(private cfg: Config, private orders: Orders) {
    this.manager = new TradeOfferManager({
      steam: this.client,
      community: this.community,
      language: 'en',
      pollInterval: 10_000,
    });

    this.client.on('webSession', (_sid: string, cookies: string[]) => {
      this.manager.setCookies(cookies, (err: Error | null) => {
        if (err) return console.error('[steam] setCookies:', err.message);
        this.community.setCookies(cookies);
        this.ready = true;
        console.log('[steam] sesión web lista');
        void this.refreshStock();
      });
    });
    this.client.on('error', (e: Error) => {
      this.ready = false;
      console.error('[steam] error:', e.message);
    });
    this.client.on('disconnected', () => (this.ready = false));
    this.client.on('loggedOn', () => console.log('[steam] conectado'));

    this.manager.on('sentOfferChanged', (offer: any) => this.onOfferChanged(offer));
  }

  login(): void {
    this.client.logOn({
      accountName: this.cfg.steamUser,
      password: this.cfg.steamPassword,
      twoFactorCode: SteamTotp.generateAuthCode(this.cfg.sharedSecret),
    });
  }

  get isReady() {
    return this.ready;
  }

  /** Llaves en inventario (cacheado; se refresca tras cada envío). */
  get keyCount() {
    return this.cachedKeys;
  }

  refreshStock(): Promise<number> {
    return new Promise((resolve) => {
      this.manager.getInventoryContents(TF2_APPID, TF2_CONTEXT, true, (err: Error | null, inv: any[]) => {
        if (err) {
          console.error('[steam] inventario:', err.message);
          return resolve(this.cachedKeys);
        }
        this.cachedKeys = inv.filter((i) => i.market_hash_name === KEY_NAME && i.tradable).length;
        resolve(this.cachedKeys);
      });
    });
  }

  /** Envía las llaves del pedido. Devuelve el id de la oferta. */
  async sendKeys(order: Order): Promise<string> {
    if (!this.ready) throw new Error('Bot de Steam no está listo');
    const inv: any[] = await new Promise((res, rej) =>
      this.manager.getInventoryContents(TF2_APPID, TF2_CONTEXT, true, (e: Error | null, i: any[]) => (e ? rej(e) : res(i))),
    );
    const keys = inv.filter((i) => i.market_hash_name === KEY_NAME && i.tradable).slice(0, order.qty);
    if (keys.length < order.qty) throw new Error(`Inventario insuficiente (${keys.length}/${order.qty})`);

    const offer = this.manager.createOffer(order.steam_id);
    offer.setToken(order.trade_token);
    offer.addMyItems(keys);
    offer.setMessage(`Pedido #${order.id} - ${order.qty} llave(s) TF2. ¡Gracias!`);

    await new Promise<void>((res, rej) => offer.send((e: Error | null) => (e ? rej(e) : res())));
    // Las ofertas salientes requieren confirmación móvil: se acepta con identity_secret.
    if (offer.state === TradeOfferManager.ETradeOfferState.CreatedNeedsConfirmation) {
      await new Promise<void>((res, rej) =>
        this.community.acceptConfirmationForObject(this.cfg.identitySecret, offer.id, (e: Error | null) => (e ? rej(e) : res())),
      );
    }
    return String(offer.id);
  }

  private onOfferChanged(offer: any): void {
    const order = this.orders.byStatus('sending').find((o) => o.offer_id === String(offer.id));
    if (!order) return;
    const S = TradeOfferManager.ETradeOfferState;
    if (offer.state === S.Accepted) {
      this.orders.transition(order.id, 'sending', 'completed');
      console.log(`[steam] pedido ${order.id} completado`);
      void this.refreshStock();
    } else if ([S.Declined, S.Canceled, S.Expired, S.InvalidItems, S.CanceledBySecondFactor].includes(offer.state)) {
      // El cliente rechazó o la oferta caducó: las llaves siguen en el bot; decide un humano (reembolso/reenvío).
      this.orders.transition(order.id, 'sending', 'manual_review', {
        note: `Oferta ${offer.id} terminó en estado ${S[offer.state]}`,
      });
    }
  }
}
