import { Contract, HDNodeWallet, JsonRpcProvider } from 'ethers';
import type { Config } from './config.js';
import type { Order, Orders } from './db.js';

// Tokens nativos en Polygon PoS (ambos con 6 decimales)
export const TOKENS = {
  USDC: '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359',
  USDT: '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
} as const;

const ERC20_ABI = ['function balanceOf(address) view returns (uint256)'];

export class Payments {
  private provider: JsonRpcProvider;
  private root: HDNodeWallet;
  private contracts: Contract[];

  constructor(private cfg: Config, private orders: Orders) {
    this.provider = new JsonRpcProvider(cfg.rpcUrl);
    // xpub (solo pública): el servidor puede derivar direcciones pero NO gastar fondos.
    this.root = HDNodeWallet.fromExtendedKey(cfg.xpub) as HDNodeWallet;
    this.contracts = Object.values(TOKENS).map((a) => new Contract(a, ERC20_ABI, this.provider));
  }

  addressFor = (index: number): string => this.root.deriveChild(index).address;

  /** Saldo combinado USDC+USDT (micros) en la dirección, a `confirmations` bloques de profundidad. */
  async confirmedBalance(address: string): Promise<bigint> {
    const head = await this.provider.getBlockNumber();
    const blockTag = head - this.cfg.confirmations;
    let total = 0n;
    for (const c of this.contracts) {
      total += (await c.getFunction('balanceOf')(address, { blockTag })) as bigint;
    }
    return total;
  }

  /** Revisa pedidos pendientes: marca pagados o expirados. */
  async poll(onPaid: (o: Order) => void): Promise<void> {
    for (const o of this.orders.byStatus('pending_payment')) {
      try {
        const bal = await this.confirmedBalance(o.deposit_address);
        const need = BigInt(o.total_micros);
        if (bal >= need) {
          // Pagó de más: se entrega igual, pero se anota para reembolso manual.
          const note = bal > need ? `Sobrepago de ${bal - need} micros: reembolsar manualmente` : undefined;
          if (this.orders.transition(o.id, 'pending_payment', 'paid', { paid_micros: bal.toString(), note })) {
            onPaid(this.orders.get(o.id)!);
          }
        } else if (Date.now() > o.expires_at) {
          // Pago parcial tardío: pasa a revisión manual en vez de perder el rastro.
          if (bal > 0n) {
            this.orders.transition(o.id, 'pending_payment', 'manual_review', {
              paid_micros: bal.toString(),
              note: 'Pago parcial; reembolsar o completar',
            });
          } else {
            this.orders.transition(o.id, 'pending_payment', 'expired');
          }
        }
      } catch (e) {
        console.error(`[pagos] error revisando pedido ${o.id}:`, (e as Error).message);
      }
    }
  }
}
