from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import get_current_user
from core.database import db

router = APIRouter(tags=["crypto"])

@router.post("/merchant/crypto-orders/{order_id}/dispute")
async def merchant_open_crypto_dispute(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Open dispute for a completed crypto order (merchant only)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
        
    reason = data.get("reason")
    if not reason:
        raise HTTPException(status_code=400, detail="Укажите причину спора")
        
    order = await db.crypto_orders.find_one(
        {"id": order_id, "merchant_id": user["id"]},
        {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    if order["status"] != "completed":
        raise HTTPException(status_code=400, detail="Спор можно открыть только по завершённому заказу")
        
    # Check dispute window
    if not order.get("dispute_window_until"):
        raise HTTPException(status_code=400, detail="Срок открытия спора истёк")
        
    dispute_until = datetime.fromisoformat(order["dispute_window_until"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > dispute_until:
        raise HTTPException(status_code=400, detail="Срок открытия спора истёк (5 дней)")
        
    now = datetime.now(timezone.utc).isoformat()
    
    # Update order status
    await db.crypto_orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "dispute",
            "dispute_opened_at": now,
            "dispute_reason": reason,
            "updated_at": now
        }, "$push": {
            "status_history": {
                "status": "dispute",
                "timestamp": now,
                "by": user["id"],
                "action": "merchant_opened_dispute"
            }
        }}
    )
    
    # Create dispute conversation if not exists or update existing
    conv = await db.unified_conversations.find_one({"related_id": order_id, "type": "crypto_order"})
    if conv:
        await db.unified_conversations.update_one(
            {"id": conv["id"]},
            {"$set": {"status": "dispute", "updated_at": now}}
        )
        
        # Add system message
        await db.unified_messages.insert_one({
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "text": f"Мерчант открыл спор. Причина: {reason}",
            "is_system": True,
            "created_at": now,
            "read_by": []
        })
    
    return {"status": "dispute"}
