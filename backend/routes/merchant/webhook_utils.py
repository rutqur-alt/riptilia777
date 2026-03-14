import aiohttp
import time
import hmac
import hashlib
import json
from datetime import datetime, timezone
from core.database import db

async def send_merchant_webhook(merchant_id: str, payment_link_id: str, status: str, extra_data: dict = None):
    """
    Send webhook to merchant.
    Supports retry logic and HMAC signature.
    """
    merchant = await db.merchants.find_one({"id": merchant_id})
    if not merchant or not merchant.get("webhook_url"):
        return
    
    # Get payment link or invoice
    payment = await db.payment_links.find_one({"id": payment_link_id})
    if not payment:
        payment = await db.merchant_invoices.find_one({"id": payment_link_id})
    
    if not payment:
        return

    # Prepare payload
    payload = {
        "payment_id": payment_link_id,
        "status": status,
        "amount_rub": payment.get("amount_rub"),
        "amount_usdt": payment.get("amount_usdt"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if extra_data:
        payload.update(extra_data)
        
    # Sign payload
    api_secret = merchant.get("api_secret", "")
    signature = hmac.new(
        api_secret.encode('utf-8'),
        json.dumps(payload, sort_keys=True).encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Merchant-ID": merchant_id
    }
    
    # Send with retry
    async with aiohttp.ClientSession() as session:
        for attempt in range(3):
            try:
                async with session.post(
                    merchant["webhook_url"],
                    json=payload,
                    headers=headers,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        # Log success
                        await db.webhook_logs.insert_one({
                            "merchant_id": merchant_id,
                            "payment_id": payment_link_id,
                            "status": "success",
                            "response_code": 200,
                            "payload": payload,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        })
                        return
            except Exception as e:
                print(f"Webhook attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    # Log failure
                    await db.webhook_logs.insert_one({
                        "merchant_id": merchant_id,
                        "payment_id": payment_link_id,
                        "status": "failed",
                        "error": str(e),
                        "payload": payload,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
            
            # Wait before retry
            import asyncio
            await asyncio.sleep(2 ** attempt)
