/**
 * TypeScript definitions for BITARBITR SDK
 */

declare module 'bitarbitr-sdk' {
  export interface SDKConfig {
    apiKey: string;
    secretKey: string;
    merchantId: string;
    baseUrl?: string;
    timeout?: number;
  }

  export interface PaymentMethod {
    id: string;
    name: string;
    description: string;
  }

  export interface CreateInvoiceParams {
    orderId: string;
    amount: number;
    callbackUrl: string;
    paymentMethod?: string;
    userId?: string;
    description?: string;
  }

  export interface InvoiceResponse {
    status: string;
    paymentId: string;
    paymentUrl: string;
    details: {
      type: string;
      message: string;
      amount: number;
      expires_at: string;
    };
  }

  export interface StatusParams {
    orderId?: string;
    paymentId?: string;
  }

  export interface StatusResponse {
    orderId: string;
    paymentId: string;
    status: string;
    amount: number;
    amountUsdt: number;
    createdAt: string;
    paidAt: string | null;
    disputeUrl: string | null;
  }

  export interface TransactionsParams {
    status?: 'active' | 'completed' | 'dispute';
    limit?: number;
    offset?: number;
  }

  export interface TransactionsResponse {
    transactions: any[];
    total: number;
    limit: number;
    offset: number;
  }

  export interface StatsResponse {
    period: string;
    summary: {
      total_invoices: number;
      paid: number;
      pending: number;
      failed: number;
      disputes: number;
    };
    volume: {
      total_rub: number;
      total_usdt: number;
      average_amount_rub: number;
    };
    conversion_rate: number;
  }

  export default class BitarbitrSDK {
    static STATUS: {
      WAITING_REQUISITES: 'waiting_requisites';
      PENDING: 'pending';
      PAID: 'paid';
      COMPLETED: 'completed';
      CANCELLED: 'cancelled';
      EXPIRED: 'expired';
      DISPUTE: 'dispute';
    };

    static PAYMENT_METHODS: {
      CARD: 'card';
      SBP: 'sbp';
      SIM: 'sim';
      MONO_BANK: 'mono_bank';
      SNG_SBP: 'sng_sbp';
      SNG_CARD: 'sng_card';
      QR_CODE: 'qr_code';
    };

    constructor(config: SDKConfig);

    generateSignature(params: Record<string, any>): string;
    getPaymentMethods(): Promise<PaymentMethod[]>;
    createInvoice(params: CreateInvoiceParams): Promise<InvoiceResponse>;
    getStatus(params: StatusParams): Promise<StatusResponse>;
    getTransactions(params?: TransactionsParams): Promise<TransactionsResponse>;
    getStats(period?: 'today' | 'week' | 'month' | 'all'): Promise<StatsResponse>;
    verifyWebhook(payload: Record<string, any>, providedSign: string): boolean;
  }
}
