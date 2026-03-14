from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Request
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging

from core.database import db
from .models import SendMessageRequest
from .utils import check_rate_limit, get_rate_limit_info
from .webhook_routes import send_webhook_notification
from routes.trades.utils import send_merchant_webhook_on_trade

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{invoice_id}/paid")
async def mark_invoice_paid(
    invoice_id: str,
    background_tasks: BackgroundTasks
):
    """Отметить инвойс как оплаченный (для ручного подтверждения)"""
    
    # 1. Find invoice
    invoice = await db.merchant_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "INVOICE_NOT_FOUND",
            "message": "Инвойс не найден"
        })
    
    if invoice["status"] != "pending":
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_STATUS",
            "message": "Инвойс не ожидает оплаты"
        })
        
    # 2. Update status
    now = datetime.now(timezone.utc)
    
    await db.merchant_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": "paid",
            "paid_at": now.isoformat()
        }}
    )
    
    # 3. If linked to a trade, update trade status
    trade_id = invoice.get("trade_id")
    if trade_id:
        trade = await db.trades.find_one({"id": trade_id})
        if trade and trade["status"] == "pending":
            # Mark trade as paid
            await db.trades.update_one(
                {"id": trade_id},
                {"$set": {
                    "status": "paid",
                    "payment_confirmed_at": now.isoformat()
                }}
            )
            
            # Notify trader via websocket/notification (omitted here, handled by trade logic)
            
            # Send webhook to merchant
            background_tasks.add_task(
                send_merchant_webhook_on_trade,
                trade,
                "paid",
                {
                    "trade_id": trade_id,
                    "amount_usdt": trade["amount_usdt"],
                    "client_amount_rub": trade.get("client_amount_rub"),
                    "merchant_receives_rub": trade.get("merchant_receives_rub"),
                    "merchant_receives_usdt": trade.get("merchant_receives_usdt"),
                    "paid_at": now
                }
            )
    else:
        # Just send webhook for invoice
        background_tasks.add_task(
            send_webhook_notification,
            invoice_id,
            "paid"
        )
    
    return {
        "status": "success",
        "message": "Инвойс отмечен как оплаченный"
    }


@router.get("/{invoice_id}/messages")
async def get_invoice_messages(invoice_id: str):
    """Получить сообщения по инвойсу (чата с трейдером)"""
    
    # 1. Find invoice
    invoice = await db.merchant_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "INVOICE_NOT_FOUND",
            "message": "Инвойс не найден"
        })
        
    trade_id = invoice.get("trade_id")
    if not trade_id:
        return {"status": "success", "messages": []}
        
    # 2. Get messages from trade chat
    messages = await db.trade_messages.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    return {"status": "success", "messages": messages}


@router.post("/{invoice_id}/messages")
async def send_invoice_message(
    invoice_id: str,
    request: SendMessageRequest
):
    """Отправить сообщение в чат инвойса"""
    
    # 1. Find invoice
    invoice = await db.merchant_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "INVOICE_NOT_FOUND",
            "message": "Инвойс не найден"
        })
        
    trade_id = invoice.get("trade_id")
    if not trade_id:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "NO_TRADE",
            "message": "Сделка еще не создана"
        })
        
    # 2. Create message
    # We treat this as message from "buyer" (the merchant's client)
    # But since they are anonymous, we use a special sender_id or just "client"
    
    from routes.trades.chat_routes import send_trade_message_internal
    
    try:
        message = await send_trade_message_internal(
            trade_id=trade_id,
            sender_id="anonymous_client", # Special ID
            text=request.message,
            is_system=False,
            is_merchant_client=True
        )
        
        return {"status": "success", "message": message}
        
    except Exception as e:
        logger.error(f"Error sending message for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
