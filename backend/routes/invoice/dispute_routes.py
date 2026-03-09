from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Request
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging

from core.database import db
from .models import DisputeOpenRequest, DisputeMessageRequest
from .utils import check_rate_limit, get_rate_limit_info
from routes.trades.utils import send_merchant_webhook_on_trade

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/disputes")
async def get_merchant_disputes(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    limit: int = 20,
    offset: int = 0
):
    """Получить список споров мерчанта"""
    
    # 1. Verify API key
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # 2. Get disputes (trades with status 'dispute' or 'disputed')
    # We need to find trades linked to this merchant that are in dispute
    
    # First find invoices for this merchant
    # Actually trades have merchant_id field
    
    query = {
        "merchant_id": merchant["id"],
        "status": {"$in": ["dispute", "disputed"]}
    }
    
    disputes = await db.trades.find(query).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    result = []
    for dispute in disputes:
        # Find linked invoice to get order_id
        invoice = await db.merchant_invoices.find_one({"trade_id": dispute["id"]})
        
        result.append({
            "dispute_id": dispute["id"], # Use trade_id as dispute_id
            "payment_id": invoice["id"] if invoice else None,
            "order_id": invoice["external_order_id"] if invoice else None,
            "amount": dispute["amount_rub"],
            "amount_usdt": dispute["amount_usdt"],
            "status": dispute["status"],
            "created_at": dispute["created_at"],
            "dispute_reason": dispute.get("dispute_reason"),
            "dispute_opened_at": dispute.get("dispute_opened_at")
        })
        
    return {
        "status": "success",
        "disputes": result,
        "count": len(result)
    }


@router.post("/dispute/open")
async def merchant_open_dispute(
    request: DisputeOpenRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """Открыть спор по сделке (от лица мерчанта)"""
    
    # 1. Verify API key
    merchant = await db.merchants.find_one({"api_key": x_api_key})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
        
    # 2. Find trade/invoice
    # Request can have payment_id (invoice_id) or order_id
    
    query = {"merchant_id": merchant["id"]}
    if request.payment_id:
        query["id"] = request.payment_id
    elif request.order_id:
        query["external_order_id"] = request.order_id
    else:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MISSING_ID",
            "message": "Необходимо указать payment_id или order_id"
        })
        
    invoice = await db.merchant_invoices.find_one(query)
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
        
    trade = await db.trades.find_one({"id": trade_id})
    if not trade:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "TRADE_NOT_FOUND",
            "message": "Сделка не найдена"
        })
        
    # 3. Check if dispute can be opened
    # Can open dispute if status is paid or pending (if paid but not confirmed)
    # Or completed? Usually dispute is for paid but not completed, or completed but issue
    
    if trade["status"] not in ["paid", "completed", "cancelled"]:
        # Allow dispute on cancelled too (e.g. paid but cancelled by timeout)
        # But usually dispute is on active trades
        pass
        
    if trade["status"] == "dispute" or trade["status"] == "disputed":
        return {
            "status": "success",
            "message": "Спор уже открыт",
            "dispute_id": trade["id"]
        }
        
    # 4. Open dispute
    from routes.trades.dispute_routes import open_dispute_internal
    
    try:
        result = await open_dispute_internal(
            trade_id=trade_id,
            user_id=merchant["id"], # Merchant is opening
            reason=request.reason,
            is_merchant=True
        )
        
        # Send webhook
        background_tasks.add_task(
            send_merchant_webhook_on_trade,
            trade,
            "dispute_opened",
            {
                "trade_id": trade_id,
                "reason": request.reason,
                "dispute_opened_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        return {
            "status": "success",
            "message": "Спор успешно открыт",
            "dispute_id": trade["id"]
        }
        
    except Exception as e:
        logger.error(f"Error opening dispute for invoice {invoice['id']}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dispute/messages")
async def get_merchant_dispute_messages(
    payment_id: Optional[str] = None,
    order_id: Optional[str] = None,
    x_api_key: str = Header(..., alias="X-Api-Key"),
    limit: int = 50
):
    """Получить сообщения спора"""
    
    # 1. Verify API key
    merchant = await db.merchants.find_one({"api_key": x_api_key})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
        
    # 2. Find invoice/trade
    query = {"merchant_id": merchant["id"]}
    if payment_id:
        query["id"] = payment_id
    elif order_id:
        query["external_order_id"] = order_id
    else:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MISSING_ID",
            "message": "Необходимо указать payment_id или order_id"
        })
        
    invoice = await db.merchant_invoices.find_one(query)
    if not invoice or not invoice.get("trade_id"):
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "NOT_FOUND",
            "message": "Сделка не найдена"
        })
        
    trade_id = invoice["trade_id"]
    
    # 3. Get messages
    messages = await db.trade_messages.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(limit)
    
    return {"status": "success", "messages": messages}


@router.post("/dispute/message")
async def merchant_send_dispute_message(
    request: DisputeMessageRequest,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """Отправить сообщение в спор"""
    
    # 1. Verify API key
    merchant = await db.merchants.find_one({"api_key": x_api_key})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
        
    # 2. Find invoice/trade
    query = {"merchant_id": merchant["id"]}
    if request.payment_id:
        query["id"] = request.payment_id
    elif request.order_id:
        query["external_order_id"] = request.order_id
    else:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MISSING_ID",
            "message": "Необходимо указать payment_id или order_id"
        })
        
    invoice = await db.merchant_invoices.find_one(query)
    if not invoice or not invoice.get("trade_id"):
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "NOT_FOUND",
            "message": "Сделка не найдена"
        })
        
    trade_id = invoice["trade_id"]
    
    # 3. Send message
    from routes.trades.chat_routes import send_trade_message_internal
    
    try:
        message = await send_trade_message_internal(
            trade_id=trade_id,
            sender_id=merchant["id"], # Merchant is sender
            text=request.message,
            is_system=False,
            is_merchant=True # Flag that it's merchant
        )
        
        return {"status": "success", "message": message}
        
    except Exception as e:
        logger.error(f"Error sending dispute message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
