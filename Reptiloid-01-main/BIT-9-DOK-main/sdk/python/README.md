# BITARBITR Python SDK

Official Python SDK for integrating BITARBITR P2P Payment Gateway into your website.

## Installation

```bash
pip install bitarbitr-sdk
```

## Quick Start

```python
from bitarbitr_sdk import BitarbitrSDK

# Initialize SDK
sdk = BitarbitrSDK(
    api_key='sk_live_xxx...',
    secret_key='your_secret_key',
    merchant_id='merch_xxx...',
    base_url='https://your-bitarbitr-server.com'  # optional
)

# Get available payment methods
methods = sdk.get_payment_methods()
print(methods)
# [{'id': 'card', 'name': 'Банковская карта'}, {'id': 'sbp', 'name': 'СБП'}, ...]

# Create invoice
invoice = sdk.create_invoice(
    order_id=f'ORDER_{int(time.time())}',
    amount=1500,
    callback_url='https://yoursite.com/api/webhook',
    payment_method='card'
)

print(invoice['payment_url'])
# IMPORTANT: Open in NEW TAB!
# import webbrowser; webbrowser.open(invoice['payment_url'])
```

## Integration Flow

### 1. Get Payment Methods

```python
# Load available payment methods to show user on your site
methods = sdk.get_payment_methods()

# Display options to user:
# - card (Банковская карта)
# - sbp (СБП)
# - sim (Мобильный счёт)
```

### 2. Create Invoice

```python
invoice = sdk.create_invoice(
    order_id='unique_order_id',
    amount=1500,                          # Amount in RUB
    callback_url='https://yoursite.com/webhook',
    payment_method='card',                # Selected by user
    user_id='user123',                    # Optional
    description='Payment for order #123'  # Optional
)

# Response:
# {
#   'status': 'success',
#   'payment_id': 'inv_20250127_xxx',
#   'payment_url': 'https://server.com/pay/inv_xxx',
#   'details': {'type': 'waiting', 'amount': 1520, ...}
# }

# IMPORTANT: Open payment page in NEW TAB!
# Frontend: window.open(invoice['payment_url'], '_blank')
```

### 3. Handle Webhook (Recommended)

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    sign = data.pop('sign', '')
    
    # Verify signature
    if not sdk.verify_webhook(data, sign):
        return jsonify({'status': 'error', 'message': 'Invalid signature'}), 401
    
    # Process payment
    order_id = data['order_id']
    status = data['status']
    amount = data['amount']
    
    if status == 'paid':
        # Payment successful - credit user account
        print(f"Order {order_id} paid: {amount} RUB")
    elif status == 'cancelled':
        # Payment cancelled
        pass
    elif status == 'expired':
        # Payment expired
        pass
    elif status == 'dispute':
        # Dispute opened - check data['dispute_url']
        pass
    
    # IMPORTANT: Return { status: 'ok' } to confirm receipt
    return jsonify({'status': 'ok'})
```

### 4. Check Status (Alternative to Webhook)

```python
# Poll status if webhook not available
status = sdk.get_status(order_id='ORDER_123')
# or
status = sdk.get_status(payment_id='inv_xxx')

print(status)
# {
#   'status': 'paid',
#   'amount': 1500,
#   'paid_at': '2025-01-27T12:00:00Z',
#   ...
# }
```

## Async Client

For async/await support:

```python
from bitarbitr_sdk import AsyncBitarbitrSDK
import asyncio

async def main():
    sdk = AsyncBitarbitrSDK(
        api_key='sk_live_xxx',
        secret_key='your_secret',
        merchant_id='merch_xxx'
    )
    
    async with sdk:
        methods = await sdk.get_payment_methods()
        
        invoice = await sdk.create_invoice(
            order_id='ASYNC_ORDER_123',
            amount=1500,
            callback_url='https://yoursite.com/webhook'
        )
        
        print(invoice['payment_url'])

asyncio.run(main())
```

## API Reference

### Constructor

```python
BitarbitrSDK(
    api_key: str,      # Required: Your API key
    secret_key: str,   # Required: Your secret key for signing
    merchant_id: str,  # Required: Your merchant ID
    base_url: str = "https://bitarbitr.org",  # Optional
    timeout: int = 30  # Optional: Request timeout in seconds
)
```

### Methods

| Method | Description |
|--------|-------------|
| `get_payment_methods()` | Get available payment methods |
| `create_invoice(**params)` | Create new payment invoice |
| `get_status(order_id=, payment_id=)` | Check payment status |
| `get_transactions(**params)` | List all transactions |
| `get_stats(period)` | Get merchant statistics |
| `get_analytics(period)` | Get extended analytics |
| `verify_webhook(payload, sign)` | Verify webhook signature |

### Constants

```python
# Payment statuses
BitarbitrSDK.STATUS_WAITING_REQUISITES = 'waiting_requisites'
BitarbitrSDK.STATUS_PENDING = 'pending'
BitarbitrSDK.STATUS_PAID = 'paid'
BitarbitrSDK.STATUS_COMPLETED = 'completed'
BitarbitrSDK.STATUS_CANCELLED = 'cancelled'
BitarbitrSDK.STATUS_EXPIRED = 'expired'
BitarbitrSDK.STATUS_DISPUTE = 'dispute'

# Payment methods
BitarbitrSDK.METHOD_CARD = 'card'
BitarbitrSDK.METHOD_SBP = 'sbp'
BitarbitrSDK.METHOD_SIM = 'sim'
BitarbitrSDK.METHOD_MONO_BANK = 'mono_bank'
BitarbitrSDK.METHOD_SNG_SBP = 'sng_sbp'
BitarbitrSDK.METHOD_SNG_CARD = 'sng_card'
BitarbitrSDK.METHOD_QR_CODE = 'qr_code'
```

## Analytics

Get extended analytics including marker statistics and conversion rates:

```python
analytics = sdk.get_analytics(period='month')

# Response includes:
# - conversion_funnel: total, paid, cancelled, expired, disputed
# - markers: distribution and effectiveness
# - payment_methods: conversion by payment type
# - amount_distribution: order value breakdown
# - peak_hours: busiest hours for payments
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

**IMPORTANT:** Always verify the `sign` using `sdk.verify_webhook()` before processing!

## Error Handling

```python
from bitarbitr_sdk import (
    BitarbitrError,
    InvalidAPIKeyError,
    InvalidSignatureError,
    RateLimitError,
    OrderNotFoundError
)

try:
    invoice = sdk.create_invoice(...)
except InvalidAPIKeyError:
    print("Check your API key")
except InvalidSignatureError:
    print("Signature verification failed")
except RateLimitError as e:
    print(f"Rate limit exceeded. Reset in: {e.reset_in}s")
except BitarbitrError as e:
    print(f"API error: {e.message} (code: {e.code})")
```

### Error Codes

| Code | Exception | Description |
|------|-----------|-------------|
| `INVALID_API_KEY` | `InvalidAPIKeyError` | Invalid API key |
| `INVALID_SIGNATURE` | `InvalidSignatureError` | Invalid request signature |
| `DUPLICATE_ORDER_ID` | `DuplicateOrderError` | Order ID already exists |
| `INVALID_AMOUNT` | `InvalidAmountError` | Amount below minimum |
| `RATE_LIMIT_EXCEEDED` | `RateLimitError` | Too many requests |
| `NOT_FOUND` | `OrderNotFoundError` | Order not found |

## Django Integration

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    
    try:
        data = json.loads(request.body)
        sign = data.pop('sign', '')
        
        if not sdk.verify_webhook(data, sign):
            return JsonResponse({'status': 'error'}, status=401)
        
        # Process payment...
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
```

## FastAPI Integration

```python
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    sign = data.pop('sign', '')
    
    if not sdk.verify_webhook(data, sign):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process payment...
    
    return {"status": "ok"}
```

## License

MIT
