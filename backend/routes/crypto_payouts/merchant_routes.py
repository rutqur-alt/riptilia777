from fastapi import APIRouter, HTTPException, Depends
from core.auth import get_current_user
from core.database import db

router = APIRouter(tags=["crypto"])

@router.get("/merchant/deals-archive")
async def get_merchant_deals_archive(user: dict = Depends(get_current_user)):
    """Get merchant's deals archive (completed/cancelled trades + crypto orders)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    # 1. Get P2P trades (where merchant was the recipient)
    p2p_trades = await db.trades.find(
        {"merchant_id": user["id"], "status": {"$in": ["completed", "cancelled", "dispute_resolved"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # 2. Get Crypto Sell Orders (payouts)
    crypto_orders = await db.crypto_orders.find(
        {"merchant_id": user["id"], "status": {"$in": ["completed", "cancelled", "dispute_resolved"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Normalize and combine
    archive = []
    
    for trade in p2p_trades:
        archive.append({
            "id": trade["id"],
            "type": "p2p_payment",
            "amount_rub": trade.get("amount_rub", 0),
            "amount_usdt": trade.get("amount_usdt", 0),
            "status": trade["status"],
            "created_at": trade["created_at"],
            "completed_at": trade.get("completed_at") or trade.get("cancelled_at"),
            "counterparty": "P2P Trader"
        })
        
    for order in crypto_orders:
        archive.append({
            "id": order["id"],
            "type": "crypto_payout",
            "amount_rub": order.get("amount_rub", 0),
            "amount_usdt": order.get("usdt_from_merchant", 0), # Merchant spent this much
            "status": order["status"],
            "created_at": order["created_at"],
            "completed_at": order.get("completed_at") or order.get("cancelled_at"),
            "counterparty": order.get("buyer_nickname", "Trader")
        })
    
    # Sort by date desc
    archive.sort(key=lambda x: x["created_at"], reverse=True)
    
    return archive[:100]


@router.get("/merchant/deals/{deal_id}")
async def get_merchant_deal_details(deal_id: str, user: dict = Depends(get_current_user)):
    """Get details of a specific deal (trade or crypto order)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    # Try find in trades
    trade = await db.trades.find_one({"id": deal_id, "merchant_id": user["id"]}, {"_id": 0})
    if trade:
        return {**trade, "deal_type": "p2p_payment"}
        
    # Try find in crypto orders
    order = await db.crypto_orders.find_one({"id": deal_id, "merchant_id": user["id"]}, {"_id": 0})
    if order:
        return {**order, "deal_type": "crypto_payout"}
        
    raise HTTPException(status_code=404, detail="Сделка не найдена")


@router.get("/merchant/crypto-orders/{order_id}/chat")
async def get_merchant_crypto_order_chat(order_id: str, user: dict = Depends(get_current_user)):
    """Get chat history for a crypto order (read-only for merchant)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    # Verify ownership
    order = await db.crypto_orders.find_one({"id": order_id, "merchant_id": user["id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    # Find conversation
    conv = await db.unified_conversations.find_one({"related_id": order_id, "type": "crypto_order"})
    if not conv:
        return {"messages": []}
        
    # Get messages
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    
    return {"messages": messages}
