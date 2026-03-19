# Requirements: P2P Platform - QR Aggregator + Merchant Webhooks

## Server Access
- Server: user@88.80.17.247
- Password: (see secrets)
- Backend path: /home/user/riptilia777/backend/
- Backend runs: uvicorn server:app --host 0.0.0.0 --port 8001 (from backend dir)
- Health check: curl http://localhost:8001/api/health
- Restart: kill PID, then cd /home/user/riptilia777/backend && nohup uvicorn server:app --host 0.0.0.0 --port 8001 > /tmp/backend.log 2>&1 &

## Repo
- GitHub: rutqur-alt/riptilia777
- Branch: devin/1772917820-qr-dispute-system
- Local clone: /home/ubuntu/repos/riptilia777_pr

## Completed Tasks

### 1. QR Aggregator Dispute System
- Backend: QR dispute endpoints (open, list, auto-create on "Oплата не прошла")
- Backend: Mark QR disputes with `is_qr_aggregator_dispute: true`
- Frontend: "Споры" tab in QR Provider Dashboard
- Frontend: "Споры" button in Admin QR Aggregator page
- Frontend: "Оплата не прошла" button creates dispute on payment page
- Admin chat: QR disputes appear in P2P Споры with "QR-Aggregator" label

### 2. Provider Balance Fix

### 3. SelectOperatorPage Loading State Fix

### 4. Merchant Webhook Accounting Fields
- Added `rate` (base USDT/RUB from Rapira) to all merchant webhooks
- Added `merchant_amount_usdt` (after commission) to all webhooks
- Added `merchant_receives_rub` to QR aggregator webhooks
- P2P trades (trades.py) - added rate + merchant_amount_usdt
- QR trades (qr_aggregator.py) - added all three fields
- invoice_api.py - no changes needed, extra_data flows through

### 5. QR Trade Fixes
- Auto-redirect to TrustGain payment page
- Handle QR trade response normalization
- Fix missing amount_usdt in qr_aggregator_buy
- Auto-hide QR offers when balance < 20 USDT
- Use original_amount_rub for TrustGain amount
- UUID-based client_id in buy-public

## Key Files
- Backend: routes/qr_aggregator.py, routes/trades.py, routes/invoice_api.py, routes/rate_service.py
- Frontend: QRProviderDashboard.jsx, QRAggregatorAdmin.jsx, DirectBuyPage.js, SelectOperatorPage.jsx

## Webhook Format (current)
```json
{
  "order_id": "...", "payment_id": "...", "status": "completed",
  "amount": 5000, "amount_usdt": 62.78,
  "rate": 79.64, "merchant_amount_usdt": 56.50,
  "merchant_receives_rub": 4500, "merchant_receives_usdt": 56.50,
  "timestamp": "...", "sign": "hmac_signature"
}
```

## Rate Service
- Primary: Rapira API, Fallback: Binance, CoinGecko
- Updates every 5 min in db.settings type="payout_settings" field "base_rate"

## Test Merchant
- Merchant ID: 5483bed1-965a-4ac3-aec9-dfff933259e9 (test_merchant)
- QR Provider ID: 92d3044d-2c60-4168-9cae-3854a1594909 (trustgain1)
