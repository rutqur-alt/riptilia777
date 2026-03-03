# BITARBITR Node.js SDK

Official Node.js SDK for integrating BITARBITR P2P Payment Gateway into your website.

## Installation

```bash
npm install bitarbitr-sdk
# or
yarn add bitarbitr-sdk
```

## Quick Start

```javascript
const BitarbitrSDK = require('bitarbitr-sdk');

// Initialize SDK
const sdk = new BitarbitrSDK({
  apiKey: 'sk_live_xxx...',
  secretKey: 'your_secret_key',
  merchantId: 'merch_xxx...',
  baseUrl: 'https://your-bitarbitr-server.com' // optional
});

// Get available payment methods
const methods = await sdk.getPaymentMethods();
console.log(methods);
// [{ id: 'card', name: 'Банковская карта' }, { id: 'sbp', name: 'СБП' }, ...]

// Create invoice
const invoice = await sdk.createInvoice({
  orderId: 'ORDER_' + Date.now(),
  amount: 1500,
  callbackUrl: 'https://yoursite.com/api/webhook',
  paymentMethod: 'card'
});

console.log(invoice.paymentUrl);
// IMPORTANT: Open in NEW TAB!
// window.open(invoice.paymentUrl, '_blank');
```

## Integration Flow

### 1. Get Payment Methods

```javascript
// Load available payment methods to show user on your site
const methods = await sdk.getPaymentMethods();

// Display options to user:
// - card (Банковская карта)
// - sbp (СБП)
// - sim (Мобильный счёт)
// etc.
```

### 2. Create Invoice

```javascript
const invoice = await sdk.createInvoice({
  orderId: 'unique_order_id',
  amount: 1500,                          // Amount in RUB
  callbackUrl: 'https://yoursite.com/webhook',
  paymentMethod: 'card',                 // Selected by user
  userId: 'user123',                     // Optional
  description: 'Payment for order #123'  // Optional
});

// Response:
// {
//   status: 'success',
//   paymentId: 'inv_20250127_xxx',
//   paymentUrl: 'https://server.com/pay/inv_xxx',
//   details: { type: 'waiting', amount: 1520, ... }
// }

// IMPORTANT: Open payment page in NEW TAB!
// Frontend: window.open(invoice.paymentUrl, '_blank')
```

### 3. Handle Webhook (Recommended)

```javascript
const express = require('express');
const app = express();

app.post('/webhook', express.json(), (req, res) => {
  const { sign, ...payload } = req.body;
  
  // Verify signature
  if (!sdk.verifyWebhook(payload, sign)) {
    return res.status(401).json({ status: 'error', message: 'Invalid signature' });
  }
  
  // Process payment
  const { order_id, payment_id, status, amount } = payload;
  
  switch (status) {
    case 'paid':
      // Payment successful - credit user account
      console.log(`Order ${order_id} paid: ${amount} RUB`);
      break;
    case 'cancelled':
      // Payment cancelled
      break;
    case 'expired':
      // Payment expired
      break;
    case 'dispute':
      // Dispute opened - check payload.dispute_url
      break;
  }
  
  // IMPORTANT: Return { status: 'ok' } to confirm receipt
  res.json({ status: 'ok' });
});
```

### 4. Check Status (Alternative to Webhook)

```javascript
// Poll status if webhook not available
const status = await sdk.getStatus({ orderId: 'ORDER_123' });
// or
const status = await sdk.getStatus({ paymentId: 'inv_xxx' });

console.log(status);
// {
//   status: 'paid',
//   amount: 1500,
//   paidAt: '2025-01-27T12:00:00Z',
//   ...
// }
```

## API Reference

### Constructor

```javascript
new BitarbitrSDK({
  apiKey: string,      // Required: Your API key
  secretKey: string,   // Required: Your secret key for signing
  merchantId: string,  // Required: Your merchant ID
  baseUrl?: string,    // Optional: API server URL
  timeout?: number     // Optional: Request timeout in ms (default: 30000)
})
```

### Methods

| Method | Description |
|--------|-------------|
| `getPaymentMethods()` | Get available payment methods |
| `createInvoice(params)` | Create new payment invoice |
| `getStatus(params)` | Check payment status |
| `getTransactions(params)` | List all transactions |
| `getStats(period)` | Get merchant statistics |
| `verifyWebhook(payload, sign)` | Verify webhook signature |

### Constants

```javascript
// Payment statuses
BitarbitrSDK.STATUS = {
  WAITING_REQUISITES: 'waiting_requisites',
  PENDING: 'pending',
  PAID: 'paid',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  EXPIRED: 'expired',
  DISPUTE: 'dispute'
};

// Payment methods
BitarbitrSDK.PAYMENT_METHODS = {
  CARD: 'card',
  SBP: 'sbp',
  SIM: 'sim',
  MONO_BANK: 'mono_bank',
  SNG_SBP: 'sng_sbp',
  SNG_CARD: 'sng_card',
  QR_CODE: 'qr_code'
};
```

## Webhook Payload

When payment status changes, we send POST request to your `callback_url`:

```json
{
  "order_id": "ORDER_123",
  "payment_id": "inv_20250127_xxx",
  "status": "paid",
  "amount": 1500,
  "amount_usdt": 15.5,
  "timestamp": "2025-01-27T12:00:00Z",
  "sign": "abc123..."
}
```

**IMPORTANT:** Always verify the `sign` using `sdk.verifyWebhook()` before processing!

### Webhook Retry Policy

If your server doesn't respond with HTTP 200 and `{ status: 'ok' }`:
- Retry 1: after 1 minute
- Retry 2: after 5 minutes
- Retry 3: after 15 minutes
- Retry 4: after 1 hour
- Retry 5: after 2 hours
- Retry 6: after 4 hours
- Retry 7: after 12 hours
- Retry 8: after 24 hours

## Error Handling

```javascript
try {
  const invoice = await sdk.createInvoice({ ... });
} catch (error) {
  if (error.response) {
    // API error
    console.error(error.response.data);
    // { status: 'error', code: 'INVALID_SIGNATURE', message: '...' }
  } else {
    // Network error
    console.error(error.message);
  }
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `INVALID_API_KEY` | Invalid API key |
| `INVALID_SIGNATURE` | Invalid request signature |
| `DUPLICATE_ORDER_ID` | Order ID already exists |
| `INVALID_AMOUNT` | Amount below minimum (100 RUB) |
| `INVALID_PAYMENT_METHOD` | Unknown payment method |
| `RATE_LIMIT_EXCEEDED` | Too many requests |

## TypeScript Support

SDK includes TypeScript definitions:

```typescript
import BitarbitrSDK, { 
  CreateInvoiceParams, 
  InvoiceResponse 
} from 'bitarbitr-sdk';

const sdk = new BitarbitrSDK({
  apiKey: 'sk_live_xxx',
  secretKey: 'secret',
  merchantId: 'merch_xxx'
});

const invoice: InvoiceResponse = await sdk.createInvoice({
  orderId: 'ORDER_123',
  amount: 1500,
  callbackUrl: 'https://example.com/webhook'
});
```

## License

MIT
