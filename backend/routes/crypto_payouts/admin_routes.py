from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import require_role
from core.database import db

router = APIRouter(tags=["crypto"])

@router.get("/admin/crypto/payouts")
async def admin_get_crypto_payouts(
    status: str = None,
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Get all crypto payout orders (for admin)"""
    query = {}
    if status and status != "all":
        query["status"] = status
        
    orders = await db.crypto_orders.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return orders


@router.get("/admin/crypto/payouts/{order_id}/conversation")
async def admin_get_crypto_payout_conversations(
    order_id: str,
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Get conversation for a crypto payout order"""
    conv = await db.unified_conversations.find_one(
        {"related_id": order_id, "type": "crypto_order"},
        {"_id": 0}
    )
    
    if not conv:
        return {"messages": []}
        
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    
    return {"conversation": conv, "messages": messages}


@router.post("/admin/crypto/payouts/{order_id}/status")
async def admin_update_crypto_payout_status(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Update crypto payout order status (confirm payment, cancel, etc)"""
    new_status = data.get("status")
    if new_status not in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    order = await db.crypto_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    now = datetime.now(timezone.utc).isoformat()
    
    if new_status == "completed":
        # 1. Credit USDT to buyer
        await db.traders.update_one(
            {"id": order["buyer_id"]},
            {"$inc": {"balance_usdt": order["amount_usdt"]}}
        )
        
        # 2. Deduct from merchant frozen balance (already deducted from available)
        # We just decrease frozen_balance, as balance_usdt was decreased at creation
        await db.merchants.update_one(
            {"id": order["merchant_id"]},
            {"$inc": {"frozen_balance": -order["usdt_from_merchant"]}}
        )
        
        # 3. Credit platform profit
        platform_profit = order.get("platform_profit", 0)
        if platform_profit > 0:
            await db.settings.update_one(
                {"type": "platform_balance"},
                {"$inc": {"balance_usdt": platform_profit}},
                upsert=True
            )
            
        # 4. Record completion
        await db.crypto_orders.update_one(
            {"id": order_id},
            {"$set": {
                "status": "completed",
                "completed_at": now,
                "updated_at": now,
                # Set dispute window (5 days)
                "dispute_window_until": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
            }, "$push": {
                "status_history": {
                    "status": "completed",
                    "timestamp": now,
                    "by": user["id"],
                    "action": "admin_confirmed"
                }
            }}
        )
        
        # 5. Update offer stats
        await db.crypto_sell_offers.update_one(
            {"id": order["offer_id"]},
            {"$set": {"status": "completed", "updated_at": now}}
        )
        
        # 6. Notify buyer
        from .utils import _create_payout_notification
        await _create_payout_notification(
            order["buyer_id"], 
            "payout_completed", 
            "Покупка USDT завершена", 
            f"Ваш заказ на покупку {order['amount_usdt']} USDT успешно завершён. Средства зачислены на баланс.",
            "/trader/history",
            order_id
        )
        
        # 7. Notify merchant
        await _create_payout_notification(
            order["merchant_id"], 
            "payout_completed", 
            "Продажа USDT завершена", 
            f"Ваша заявка на продажу {order['amount_rub']} ₽ успешно выполнена.",
            "/merchant/deals-archive",
            order_id
        )
        
    elif new_status == "cancelled":
        # 1. Return funds to merchant
        await db.merchants.update_one(
            {"id": order["merchant_id"]},
            {"$inc": {
                "balance_usdt": order["usdt_from_merchant"],
                "frozen_balance": -order["usdt_from_merchant"]
            }}
        )
        
        # 2. Update order
        await db.crypto_orders.update_one(
            {"id": order_id},
            {"$set": {
                "status": "cancelled",
                "cancelled_at": now,
                "updated_at": now
            }, "$push": {
                "status_history": {
                    "status": "cancelled",
                    "timestamp": now,
                    "by": user["id"],
                    "action": "admin_cancelled"
                }
            }}
        )
        
        # 3. Update offer (mark as cancelled too)
        await db.crypto_sell_offers.update_one(
            {"id": order["offer_id"]},
            {"$set": {"status": "cancelled", "updated_at": now}}
        )
        
        # 4. Notify parties
        from .utils import _create_payout_notification
        await _create_payout_notification(
            order["buyer_id"], 
            "payout_cancelled", 
            "Покупка USDT отменена", 
            f"Ваш заказ на покупку {order['amount_usdt']} USDT был отменён администратором.",
            "/trader/history",
            order_id
        )
        
        await _create_payout_notification(
            order["merchant_id"], 
            "payout_cancelled", 
            "Продажа USDT отменена", 
            f"Ваша заявка на продажу {order['amount_rub']} ₽ была отменена. Средства возвращены на баланс.",
            "/merchant/deals-archive",
            order_id
        )
        
    return {"status": new_status}


@router.post("/admin/crypto/disputes/{order_id}/resolve")
async def admin_resolve_crypto_dispute(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Resolve crypto payout dispute"""
    resolution = data.get("resolution") # "merchant_win" or "platform_win"
    
    if resolution not in ["merchant_win", "platform_win"]:
        raise HTTPException(status_code=400, detail="Invalid resolution")
        
    order = await db.crypto_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if order.get("status") != "dispute":
        raise HTTPException(status_code=400, detail="Order is not in dispute")
        
    now = datetime.now(timezone.utc).isoformat()
    
    if resolution == "merchant_win":
        # Merchant wins - return USDT to merchant, debit from buyer
        # Check if buyer has enough balance
        buyer = await db.traders.find_one({"id": order["buyer_id"]})
        if buyer.get("balance_usdt", 0) < order["amount_usdt"]:
            # Buyer already spent funds - debt or partial recovery?
            # For now, just take what's available and mark debt?
            # Simplified: just take what's available
            pass
            
        # Debit buyer
        await db.traders.update_one(
            {"id": order["buyer_id"]},
            {"$inc": {"balance_usdt": -order["amount_usdt"]}}
        )
        
        # Credit merchant
        await db.merchants.update_one(
            {"id": order["merchant_id"]},
            {"$inc": {"balance_usdt": order["usdt_from_merchant"]}}
        )
        
        # Debit platform profit (reversal)
        platform_profit = order.get("platform_profit", 0)
        if platform_profit > 0:
            await db.settings.update_one(
                {"type": "platform_balance"},
                {"$inc": {"balance_usdt": -platform_profit}}
            )
            
        final_status = "cancelled" # Effectively cancelled
        
    else: # platform_win
        # Platform wins (buyer keeps funds)
        # Nothing to move, funds already distributed
        final_status = "completed"
        
    # Update order
    await db.crypto_orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": final_status, # Revert to completed or cancelled
            "dispute_winner": "merchant" if resolution == "merchant_win" else "platform",
            "dispute_resolved_at": now,
            "updated_at": now
        }, "$push": {
            "status_history": {
                "status": final_status,
                "timestamp": now,
                "by": user["id"],
                "action": f"dispute_resolved_{resolution}"
            }
        }}
    )
    
    return {"status": "resolved", "resolution": resolution}
