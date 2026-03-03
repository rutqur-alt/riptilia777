/**
 * BITARBITR SDK - Official Node.js SDK
 * P2P Payment Gateway Integration
 * 
 * @version 1.0.0
 * @license MIT
 */

const crypto = require('crypto');
const axios = require('axios');

class BitarbitrSDK {
  /**
   * Initialize the SDK
   * @param {Object} config - Configuration object
   * @param {string} config.apiKey - Your API key (X-Api-Key)
   * @param {string} config.secretKey - Your secret key for signing requests
   * @param {string} config.merchantId - Your merchant ID
   * @param {string} [config.baseUrl] - API base URL (default: https://bitarbitr.org)
   * @param {number} [config.timeout] - Request timeout in ms (default: 30000)
   */
  constructor(config) {
    if (!config.apiKey) throw new Error('apiKey is required');
    if (!config.secretKey) throw new Error('secretKey is required');
    if (!config.merchantId) throw new Error('merchantId is required');

    this.apiKey = config.apiKey;
    this.secretKey = config.secretKey;
    this.merchantId = config.merchantId;
    this.baseUrl = (config.baseUrl || 'https://bitarbitr.org').replace(/\/$/, '');
    this.timeout = config.timeout || 30000;

    // Axios instance
    this.client = axios.create({
      baseURL: `${this.baseUrl}/api/v1/invoice`,
      timeout: this.timeout,
      headers: {
        'X-Api-Key': this.apiKey,
        'Content-Type': 'application/json'
      }
    });
  }

  /**
   * Generate HMAC-SHA256 signature for request
   * @param {Object} params - Request parameters
   * @returns {string} - Hex signature
   */
  generateSignature(params) {
    // Filter out null/undefined and 'sign' field
    const signData = {};
    for (const [key, value] of Object.entries(params)) {
      if (key !== 'sign' && value !== null && value !== undefined) {
        // Normalize floats (remove .0 from integers)
        signData[key] = typeof value === 'number' && value === Math.floor(value) 
          ? Math.floor(value) 
          : value;
      }
    }

    // Sort by keys and build string
    const sortedKeys = Object.keys(signData).sort();
    const signString = sortedKeys.map(k => `${k}=${signData[k]}`).join('&') + this.secretKey;

    // HMAC-SHA256
    return crypto
      .createHmac('sha256', this.secretKey)
      .update(signString)
      .digest('hex');
  }

  /**
   * Get available payment methods
   * @returns {Promise<Array>} - List of payment methods
   * @example
   * const methods = await sdk.getPaymentMethods();
   * // [{ id: 'card', name: 'Банковская карта', description: '...' }, ...]
   */
  async getPaymentMethods() {
    const response = await this.client.get('/payment-methods');
    return response.data.payment_methods;
  }

  /**
   * Create a new invoice (payment request)
   * @param {Object} params - Invoice parameters
   * @param {string} params.orderId - Unique order ID in your system
   * @param {number} params.amount - Amount in RUB
   * @param {string} params.callbackUrl - URL for webhook notifications
   * @param {string} [params.paymentMethod] - Payment method ID (card, sbp, etc.)
   * @param {string} [params.userId] - User ID in your system (optional)
   * @param {string} [params.description] - Payment description (optional)
   * @returns {Promise<Object>} - Invoice data with payment_url
   * @example
   * const invoice = await sdk.createInvoice({
   *   orderId: 'ORDER_123',
   *   amount: 1500,
   *   callbackUrl: 'https://mysite.com/callback',
   *   paymentMethod: 'card'
   * });
   * // Open invoice.payment_url in new tab: window.open(invoice.payment_url, '_blank')
   */
  async createInvoice(params) {
    const requestData = {
      merchant_id: this.merchantId,
      order_id: params.orderId,
      amount: params.amount,
      currency: 'RUB',
      callback_url: params.callbackUrl,
      payment_method: params.paymentMethod || null,
      user_id: params.userId || null,
      description: params.description || null
    };

    requestData.sign = this.generateSignature(requestData);

    const response = await this.client.post('/create', requestData);
    
    return {
      status: response.data.status,
      paymentId: response.data.payment_id,
      paymentUrl: response.data.payment_url,
      details: response.data.details
    };
  }

  /**
   * Check invoice/payment status
   * @param {Object} params - Query parameters
   * @param {string} [params.orderId] - Order ID in your system
   * @param {string} [params.paymentId] - Payment ID from BITARBITR
   * @returns {Promise<Object>} - Payment status data
   * @example
   * const status = await sdk.getStatus({ orderId: 'ORDER_123' });
   * // { status: 'paid', amount: 1500, ... }
   */
  async getStatus(params) {
    if (!params.orderId && !params.paymentId) {
      throw new Error('Either orderId or paymentId is required');
    }

    const signData = { merchant_id: this.merchantId };
    if (params.orderId) signData.order_id = params.orderId;
    if (params.paymentId) signData.payment_id = params.paymentId;

    const sign = this.generateSignature(signData);

    const queryParams = new URLSearchParams({
      merchant_id: this.merchantId,
      sign: sign
    });
    if (params.orderId) queryParams.append('order_id', params.orderId);
    if (params.paymentId) queryParams.append('payment_id', params.paymentId);

    const response = await this.client.get(`/status?${queryParams.toString()}`);
    
    return {
      orderId: response.data.data.order_id,
      paymentId: response.data.data.payment_id,
      status: response.data.data.status,
      amount: response.data.data.amount,
      amountUsdt: response.data.data.amount_usdt,
      createdAt: response.data.data.created_at,
      paidAt: response.data.data.paid_at,
      disputeUrl: response.data.data.dispute_url
    };
  }

  /**
   * Get list of transactions
   * @param {Object} [params] - Query parameters
   * @param {string} [params.status] - Filter by status (active, completed, dispute)
   * @param {number} [params.limit] - Max results (default: 50)
   * @param {number} [params.offset] - Offset for pagination (default: 0)
   * @returns {Promise<Object>} - Transactions list with pagination
   */
  async getTransactions(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.status) queryParams.append('status', params.status);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());

    const response = await this.client.get(`/transactions?${queryParams.toString()}`);
    
    return {
      transactions: response.data.data.transactions,
      total: response.data.data.total,
      limit: response.data.data.limit,
      offset: response.data.data.offset
    };
  }

  /**
   * Get merchant statistics
   * @param {string} [period] - Time period (today, week, month, all)
   * @returns {Promise<Object>} - Statistics data
   */
  async getStats(period = 'today') {
    const response = await this.client.get(`/stats?period=${period}`);
    return response.data.data;
  }

  /**
   * Verify webhook signature
   * @param {Object} payload - Webhook payload received
   * @param {string} providedSign - Signature from payload
   * @returns {boolean} - True if signature is valid
   * @example
   * app.post('/webhook', (req, res) => {
   *   const { sign, ...data } = req.body;
   *   if (!sdk.verifyWebhook(data, sign)) {
   *     return res.status(401).json({ status: 'error' });
   *   }
   *   // Process webhook...
   *   res.json({ status: 'ok' });
   * });
   */
  verifyWebhook(payload, providedSign) {
    const expectedSign = this.generateSignature(payload);
    return expectedSign.toLowerCase() === providedSign.toLowerCase();
  }
}

// Payment statuses enum
BitarbitrSDK.STATUS = {
  WAITING_REQUISITES: 'waiting_requisites',
  PENDING: 'pending',
  PAID: 'paid',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  EXPIRED: 'expired',
  DISPUTE: 'dispute'
};

// Payment methods enum
BitarbitrSDK.PAYMENT_METHODS = {
  CARD: 'card',
  SBP: 'sbp',
  SIM: 'sim',
  MONO_BANK: 'mono_bank',
  SNG_SBP: 'sng_sbp',
  SNG_CARD: 'sng_card',
  QR_CODE: 'qr_code'
};

module.exports = BitarbitrSDK;
