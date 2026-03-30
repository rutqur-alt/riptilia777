from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user
from .utils import create_marketplace_notification

router = APIRouter()

# ==================== GUARANTOR LOGIC ====================

@router.post("/purchases/{purchase_id}/confirm")
async def confirm_guarantor_purchase(purchase_id: str, user: dict = Depends(get_current_user)):
    """Confirm receipt of goods in guarantor deal"""
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id, "buyer_id": user["id"]})
    if not purchase:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # ATOMIC: Lock status to prevent double-confirmation race condition
    confirm_result = await db.marketplace_purchases.update_one(
        {"id": purchase_id, "buyer_id": user["id"], "status": "pending_confirmation"},
        {"$set": {"status": "completing"}}
    )
    if confirm_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Заказ не в статусе ожидания подтверждения")

    product_id = purchase["product_id"]
    seller_id = purchase["seller_id"]
    quantity = purchase["quantity"]
    total_with_guarantor = purchase.get("total_with_guarantor", purchase["total_price"])
    seller_receives = purchase["seller_receives"]
    platform_commission = purchase["commission"]
    reserved_content = purchase.get("reserved_content", [])

    # Release stock from reserved
    product = await db.shop_products.find_one({"id": product_id})
    if product:
        auto_content = product.get("auto_content", [])
        # Remove reserved items from auto_content
        new_content = [c for c in auto_content if c not in reserved_content]
        
        await db.shop_products.update_one(
            {"id": product_id},
            {
                "$set": {"auto_content": new_content},
                "$inc": {"reserved_count": -quantity, "sold_count": quantity}
            }
        )

    # Release escrow from buyer
    buyer_collection = db.traders if await db.traders.find_one({"id": user["id"]}) else db.merchants
    await buyer_collection.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_escrow": -total_with_guarantor}}
    )

    # Pay seller
    await db.traders.update_one(
        {"id": seller_id},
        {"$inc": {"shop_balance": seller_receives}}
    )

    now = datetime.now(timezone.utc)

    # Update purchase status
    await db.marketplace_purchases.update_one(
        {"id": purchase_id},
        {"$set": {
            "status": "completed",
            "delivered_content": reserved_content,
            "completed_at": now.isoformat(),
            "confirmed_by": "buyer"
        }}
    )

    # Record commission
    await db.commission_payments.insert_one({
        "id": str(uuid.uuid4()),
        "purchase_id": purchase_id,
        "buyer_id": user["id"],
        "seller_id": seller_id,
        "seller_type": "trader",
        "amount": platform_commission,
        "commission_rate": purchase.get("commission_rate", 5.0),
        "type": "marketplace_guarantor",
        "created_at": now.isoformat()
    })
    
    # Notify seller
    await create_marketplace_notification(
        seller_id,
        "shop_order_completed",
        "Заказ подтверждён",
        f"Покупатель подтвердил получение заказа #{purchase_id[:8]}. Средства зачислены.",
        "/trader/shop",
        purchase_id
    )

    # Update seller stats
    await db.traders.update_one(
        {"id": seller_id},
        {"$inc": {
            "shop_stats.total_sales": purchase["total_price"],
            "shop_stats.total_orders": 1,
            "shop_stats.total_commission_paid": platform_commission
        }}
    )

    return {"status": "completed", "delivered_content": reserved_content}


@router.post("/purchases/{purchase_id}/cancel")
async def cancel_guarantor_purchase(purchase_id: str, user: dict = Depends(get_current_user)):
    """Cancel guarantor purchase (only if not delivered/disputed)"""
    # Only admin or seller can cancel? Or buyer before delivery?
    # For now, let's say only admin or system can cancel via dispute
    # Or buyer if seller agrees?
    # Implementing basic cancellation for now
    
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id})
    if not purchase:
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    if purchase["buyer_id"] != user["id"] and purchase["seller_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа")
        
    # ATOMIC: Check status atomically (no actual cancel logic, just dispute redirect)
    if purchase["status"] != "pending_confirmation":
        raise HTTPException(status_code=400, detail="Нельзя отменить заказ в этом статусе")
        
    raise HTTPException(status_code=400, detail="Для отмены заказа откройте спор")


@router.post("/purchases/{purchase_id}/dispute")
async def open_purchase_dispute(purchase_id: str, reason: str = Body(..., embed=True), user: dict = Depends(get_current_user)):
    """Open dispute for a purchase"""
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id})
    if not purchase:
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    if purchase["buyer_id"] != user["id"] and purchase["seller_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа")
        
    # Create dispute
    dispute_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # ATOMIC: Update status to prevent double-dispute
    dispute_result = await db.marketplace_purchases.update_one(
        {"id": purchase_id, "status": "pending_confirmation"},
        {"$set": {"status": "disputed", "dispute_id": dispute_id}}
    )
    if dispute_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Спор можно открыть только для активного заказа")
    
    dispute = {
        "id": dispute_id,
        "purchase_id": purchase_id,
        "initiator_id": user["id"],
        "reason": reason,
        "status": "open",
        "created_at": now.isoformat(),
        "messages": []
    }
    
    await db.marketplace_disputes.insert_one(dispute)
    
    # Notify admins
    # TODO: Notify admins
    
    return {"status": "disputed", "dispute_id": dispute_id}


@router.post("/admin/purchases/{purchase_id}/resolve")
async def resolve_purchase_dispute(
    purchase_id: str, 
    decision: str = Body(..., embed=True), 
    user: dict = Depends(get_current_user)
):
    """Resolve dispute (admin only)"""
    if user.get("role") not in ["admin", "mod_market", "owner"]:
        raise HTTPException(status_code=403, detail="Только для администрации")
        
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id})
    if not purchase:
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    now = datetime.now(timezone.utc)
    
    # ATOMIC: Lock status to prevent double-resolution
    resolve_result = await db.marketplace_purchases.update_one(
        {"id": purchase_id, "status": "disputed"},
        {"$set": {"status": "resolving"}}
    )
    if resolve_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Заказ не в статусе спора или уже разрешается")
    
    if decision == "refund_buyer":
        # Refund buyer
        total_with_guarantor = purchase.get("total_with_guarantor", purchase["total_price"])
        
        buyer_collection = db.traders if await db.traders.find_one({"id": purchase["buyer_id"]}) else db.merchants
        await buyer_collection.update_one(
            {"id": purchase["buyer_id"]},
            {"$inc": {"balance_usdt": total_with_guarantor, "balance_escrow": -total_with_guarantor}}
        )
        
        # Release stock
        product_id = purchase["product_id"]
        quantity = purchase["quantity"]
        await db.shop_products.update_one(
            {"id": product_id},
            {"$inc": {"reserved_count": -quantity}}
        )
        
        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {
                "status": "cancelled",
                "resolved_at": now.isoformat(),
                "resolution": "refunded_buyer",
                "resolved_by": user["id"]
            }}
        )
        
    elif decision == "release_to_seller":
        # Pay seller
        seller_id = purchase["seller_id"]
        seller_receives = purchase["seller_receives"]
        platform_commission = purchase["commission"]
        total_with_guarantor = purchase.get("total_with_guarantor", purchase["total_price"])
        
        # Release escrow from buyer
        buyer_collection = db.traders if await db.traders.find_one({"id": purchase["buyer_id"]}) else db.merchants
        await buyer_collection.update_one(
            {"id": purchase["buyer_id"]},
            {"$inc": {"balance_escrow": -total_with_guarantor}}
        )
        
        # Pay seller
        await db.traders.update_one(
            {"id": seller_id},
            {"$inc": {"shop_balance": seller_receives}}
        )
        
        # Update stock (sold)
        product_id = purchase["product_id"]
        quantity = purchase["quantity"]
        reserved_content = purchase.get("reserved_content", [])
        
        product = await db.shop_products.find_one({"id": product_id})
        if product:
            auto_content = product.get("auto_content", [])
            new_content = [c for c in auto_content if c not in reserved_content]
            
            await db.shop_products.update_one(
                {"id": product_id},
                {
                    "$set": {"auto_content": new_content},
                    "$inc": {"reserved_count": -quantity, "sold_count": quantity}
                }
            )
            
        # Record commission
        await db.commission_payments.insert_one({
            "id": str(uuid.uuid4()),
            "purchase_id": purchase_id,
            "buyer_id": purchase["buyer_id"],
            "seller_id": seller_id,
            "seller_type": "trader",
            "amount": platform_commission,
            "commission_rate": purchase.get("commission_rate", 5.0),
            "type": "marketplace_guarantor_dispute",
            "created_at": now.isoformat()
        })
        
        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {
                "status": "completed",
                "resolved_at": now.isoformat(),
                "resolution": "released_to_seller",
                "resolved_by": user["id"],
                "delivered_content": reserved_content
            }}
        )
        
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")
        
    return {"status": "resolved", "decision": decision}

@router.get("/guarantor/chat/{purchase_id}")
async def get_guarantor_chat_info(purchase_id: str, user: dict = Depends(get_current_user)):
    """Get chat info for guarantor deal"""
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id})
    if not purchase:
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    # Check access
    is_buyer = purchase["buyer_id"] == user["id"]
    is_seller = purchase["seller_id"] == user["id"]
    is_admin = user.get("role") in ["admin", "mod_market", "owner"]
    
    if not (is_buyer or is_seller or is_admin):
        raise HTTPException(status_code=403, detail="Нет доступа")
        
    # Find or create conversation
    conversation = await db.unified_conversations.find_one({
        "type": "marketplace_guarantor",
        "related_id": purchase_id
    })
    
    if not conversation:
        # Create new conversation
        participants = [
            {"user_id": purchase["buyer_id"], "role": "buyer", "name": purchase.get("buyer_nickname", "Покупатель")},
            {"user_id": purchase["seller_id"], "role": "seller", "name": purchase.get("seller_nickname", "Продавец")}
        ]
        
        conv_id = str(uuid.uuid4())
        conversation = {
            "id": conv_id,
            "type": "marketplace_guarantor",
            "status": "active",
            "related_id": purchase_id,
            "title": f"Сделка #{purchase_id[:8]}",
            "participants": participants,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.unified_conversations.insert_one(conversation)
        
    return conversation
