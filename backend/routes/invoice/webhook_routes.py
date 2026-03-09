import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from core.database import db
from .utils import generate_id, generate_signature

logger = logging.getLogger(__name__)

# Retry intervals для webhook (в секундах)
WEBHOOK_RETRY_INTERVALS = [60, 300, 900, 3600, 7200, 14400, 43200, 86400]


async def send_webhook(callback_url: str, payload: Dict[str, Any], retry_count: int = 0) -> bool:
    """Отправка webhook с retry логикой"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                callback_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                try:
                    resp_data = response.json()
                    if resp_data.get("status") == "ok":
                        return True
                except:
                    pass
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    
    # Schedule retry
    if retry_count < len(WEBHOOK_RETRY_INTERVALS):
        delay = WEBHOOK_RETRY_INTERVALS[retry_count]
        await db.webhook_queue.insert_one({
            "id": generate_id("wbq"),
            "callback_url": callback_url,
            "payload": payload,
            "retry_count": retry_count + 1,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    return False


async def send_webhook_notification(invoice_id: str, new_status: str, extra_data: dict = None):
    """Отправляет webhook-уведомление мерчанту"""
    try:
        invoice = await db.merchant_invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not invoice:
            return
        
        callback_url = invoice.get("callback_url")
        if not callback_url:
            return
        
        merchant = await db.merchants.find_one({"id": invoice.get("merchant_id")}, {"_id": 0})
        if not merchant:
            return
        
        secret_key = merchant.get("api_secret") or merchant.get("api_key", "")
        
        callback_data = {
            "order_id": invoice.get("external_order_id", invoice_id),
            "payment_id": invoice_id,
            "status": new_status,
            "amount": invoice.get("original_amount_rub") or invoice.get("amount_rub"),
            "amount_usdt": invoice.get("amount_usdt"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Add rate and merchant_amount_usdt if available (from trade)
        if extra_data:
            # If trade object is passed in extra_data (internal usage), extract fields
            if "trade_obj" in extra_data:
                trade = extra_data.pop("trade_obj")
                # Add rate if available
                if "exchange_rate" in trade:
                    callback_data["rate"] = trade["exchange_rate"]
                # Add merchant_amount_usdt if available
                if "merchant_receives_usdt" in trade:
                    callback_data["merchant_amount_usdt"] = trade["merchant_receives_usdt"]
                elif "amount_usdt" in trade and "merchant_commission_percent" in trade:
                     # Fallback calculation if field is missing
                     amount = trade["amount_usdt"]
                     comm_percent = trade["merchant_commission_percent"]
                     callback_data["merchant_amount_usdt"] = amount * (1 - comm_percent / 100)
                
                # Add merchant_receives_rub if available
                if "merchant_receives_rub" in trade:
                    callback_data["merchant_receives_rub"] = trade["merchant_receives_rub"]

            callback_data.update(extra_data)
        
        callback_data["sign"] = generate_signature(callback_data, secret_key)
        
        # Save webhook to history
        webhook_record = {
            "id": generate_id("whk"),
            "invoice_id": invoice_id,
            "merchant_id": invoice.get("merchant_id"),
            "callback_url": callback_url,
            "payload": callback_data,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.webhook_history.insert_one(webhook_record)
        
        # Send webhook (test_webhooks will be saved by test-webhook-receiver endpoint)
        success = await send_webhook(callback_url, callback_data, 0)
        
        await db.webhook_history.update_one(
            {"id": webhook_record["id"]},
            {"$set": {
                "status": "delivered" if success else "retry_scheduled",
                "delivered_at": datetime.now(timezone.utc).isoformat() if success else None
            }}
        )
        
    except Exception as e:
        logger.error(f"Error sending webhook for invoice {invoice_id}: {e}")
