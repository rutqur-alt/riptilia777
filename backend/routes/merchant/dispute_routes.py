from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import uuid
from core.database import db
from .models import OpenDisputeRequest, DisputeMessagesRequest, SendDisputeMessageRequest
from .utils import verify_merchant

router = APIRouter()

@router.post("/dispute/open")
async def open_dispute(data: OpenDisputeRequest):
    """
    Открыть спор по сделке.
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Get invoice
    invoice = await db.merchant_invoices.find_one(
        {"id": data.invoice_id, "merchant_id": data.merchant_id}
    )
    if not invoice:
        raise HTTPException(status_code=404, detail={"success": False, "error": "INVOICE_NOT_FOUND"})
    
    trade_id = invoice.get("trade_id")
    if not trade_id:
        raise HTTPException(status_code=400, detail={"success": False, "error": "TRADE_NOT_CREATED"})
    
    # Update trade status
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "dispute",
            "dispute_reason": data.reason,
            "dispute_opened_at": datetime.now(timezone.utc).isoformat(),
            "dispute_opened_by": "merchant"
        }}
    )
    
    # Create system message
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_role": "system",
        "content": f"Спор открыт мерчантом. Причина: {data.reason}",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(msg)
    
    return {
        "success": True,
        "status": "dispute",
        "trade_id": trade_id
    }


@router.post("/dispute/messages")
async def get_dispute_messages(data: DisputeMessagesRequest):
    """
    Получить сообщения чата спора.
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    invoice = await db.merchant_invoices.find_one(
        {"id": data.invoice_id, "merchant_id": data.merchant_id}
    )
    if not invoice or not invoice.get("trade_id"):
        raise HTTPException(status_code=404, detail={"success": False, "error": "TRADE_NOT_FOUND"})
    
    messages = await db.trade_messages.find(
        {"trade_id": invoice["trade_id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    return {
        "success": True,
        "messages": messages
    }


@router.post("/dispute/message")
async def send_dispute_message(data: SendDisputeMessageRequest):
    """
    Отправить сообщение в чат спора.
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    invoice = await db.merchant_invoices.find_one(
        {"id": data.invoice_id, "merchant_id": data.merchant_id}
    )
    if not invoice or not invoice.get("trade_id"):
        raise HTTPException(status_code=404, detail={"success": False, "error": "TRADE_NOT_FOUND"})
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": invoice["trade_id"],
        "sender_id": merchant["id"],
        "sender_role": "merchant",
        "sender_name": merchant.get("merchant_name", "Merchant"),
        "content": data.message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trade_messages.insert_one(msg)
    
    return {
        "success": True,
        "message_id": msg["id"]
    }
