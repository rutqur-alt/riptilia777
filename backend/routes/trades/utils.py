from datetime import datetime, timezone
import uuid
from bson import ObjectId
from core.database import db
from pydantic import BaseModel
from typing import Optional, Dict, List

try:
    from routes.websockets import ws_manager
except ImportError:
    ws_manager = None

async def _ws_broadcast(channel: str, data: dict):
    """Broadcast via WebSocket if available"""
    if ws_manager:
        await ws_manager.broadcast(channel, data)

async def send_merchant_webhook_on_trade(trade: dict, status: str, extra_data: dict = None):
    """Send webhook to merchant when trade status changes.
    Supports both old payment_link system and new Invoice API.
    Also syncs invoice status with trade status.
    """
    try:
        # Try Invoice API webhook first (new system)
        if trade.get("invoice_id"):
            from routes.invoice.webhook_routes import send_webhook_notification
            
            # Sync invoice status with trade status
            await db.merchant_invoices.update_one(
                {"id": trade["invoice_id"]},
                {"$set": {
                    "status": status,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            await send_webhook_notification(trade["invoice_id"], status, extra_data)
            return
        
        # Fallback to old merchant_api webhook
        from routes.merchant_api import send_merchant_webhook
        if trade.get("merchant_id") and trade.get("payment_link_id"):
            await send_merchant_webhook(
                trade["merchant_id"],
                trade["payment_link_id"],
                status,
                extra_data
            )
    except Exception as e:
        print(f"Webhook error: {e}")

async def _create_trade_notification(user_id: str, notif_type: str, title: str, message: str, link: str = None, trade_id: str = None):
    """Create a trade event notification in both collections"""
    # Legacy notifications collection
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "link": link,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    # New event_notifications collection
    await db.event_notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "link": link,
        "reference_id": trade_id,
        "reference_type": "trade",
        "extra_data": {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

def _payment_detail_to_requisite(detail: dict) -> dict:
    """Convert payment_details document to legacy requisites shape {id, type, data: {...}}."""
    pt = detail.get("payment_type") or detail.get("type")
    req_type = pt
    data = {}
    if pt in ("card", "sng_card"):
        req_type = "card"
        holder = detail.get("holder_name")
        data = {"bank_name": detail.get("bank_name"), "card_number": detail.get("card_number"), "holder_name": holder, "card_holder": holder}
    elif pt in ("sbp", "sng_sbp"):
        req_type = "sbp"
        data = {"bank_name": detail.get("bank_name"), "phone": detail.get("phone_number")}
    elif pt == "sim":
        req_type = "sim"
        data = {"operator": detail.get("operator_name") or detail.get("bank_name"), "phone": detail.get("phone_number")}
    elif pt == "qr_code":
        req_type = "qr"
        data = {"bank_name": detail.get("bank_name"), "qr_data": detail.get("qr_link") or detail.get("qr_data"), "description": detail.get("comment")}
    else:
        req_type = pt or "other"
        data = {"bank_name": detail.get("bank_name")}
    clean_data = {k: v for k, v in data.items() if v not in (None, "")}
    return {"id": detail.get("id"), "trader_id": detail.get("trader_id"), "type": req_type, "data": clean_data}

def _is_legacy_requisite(item: dict) -> bool:
    """Check if item is already in legacy requisite format {id, type, data: {...}}"""
    return "data" in item and "type" in item and isinstance(item.get("data"), dict)

def _clean_doc(doc):
    """Recursively remove MongoDB _id fields and convert ObjectId to string"""
    if isinstance(doc, dict):
        return {k: _clean_doc(v) for k, v in doc.items() if k != "_id"}
    elif isinstance(doc, list):
        return [_clean_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc

class TradeResponse(BaseModel):
    id: str
    offer_id: str
    trader_id: str
    buyer_id: str
    amount_usdt: float
    amount_rub: float
    rate: float
    status: str
    created_at: datetime
    payment_method: str
    requisites: Optional[Dict] = None
    chat_id: Optional[str] = None
    dispute_id: Optional[str] = None
    is_buyer: bool = False
    can_dispute: bool = False
    can_cancel: bool = False
    can_confirm: bool = False
    qr_aggregator_trade: bool = False
    trade_number: Optional[str] = None

class DirectTradeCreate(BaseModel):
    offer_id: str
    amount_usdt: float
    requisite_id: Optional[str] = None
    payment_method: Optional[str] = None
