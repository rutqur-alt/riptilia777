from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import require_admin_level, log_admin_action

router = APIRouter()

# ==================== ADMIN: WITHDRAWALS ====================

@router.get("/admin/withdrawals")
async def get_pending_withdrawals(status_filter: str = "pending", user: dict = Depends(require_admin_level(50))):
    """Get withdrawal requests with filtering. Returns trader and merchant withdrawals separately."""
    query = {}
    if status_filter and status_filter != "all":
        query["status"] = status_filter
    
    trader_withdrawals = await db.withdrawals.find(
        {**query, "source": {"$ne": "merchant"}}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    merchant_withdrawals = await db.withdrawals.find(
        {**query, "source": "merchant"}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # If no source field exists, try to separate by user_type or return all as trader
    if not trader_withdrawals and not merchant_withdrawals:
        all_withdrawals = await db.withdrawals.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        trader_withdrawals = [w for w in all_withdrawals if w.get("user_type") != "merchant"]
        merchant_withdrawals = [w for w in all_withdrawals if w.get("user_type") == "merchant"]
    
    return {
        "trader_withdrawals": trader_withdrawals,
        "merchant_withdrawals": merchant_withdrawals
    }


@router.post("/admin/withdrawals/{withdrawal_id}/process")
async def process_withdrawal(withdrawal_id: str, decision: str = None, data: dict = None, user: dict = Depends(require_admin_level(50))):
    """Process withdrawal request (approve/reject)"""
    # Allow decision in query param or body
    if not decision and data:
        decision = data.get("decision")
    
    if decision not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid decision. Use 'approve' or 'reject'")
    
    withdrawal = await db.withdrawals.find_one({"id": withdrawal_id})
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    
    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Withdrawal already processed")
    
    now = datetime.now(timezone.utc).isoformat()
    
    if decision == "approve":
        # In a real system, this would trigger blockchain transfer
        # Here we just mark as completed since funds were already deducted
        await db.withdrawals.update_one(
            {"id": withdrawal_id},
            {"$set": {
                "status": "completed",
                "processed_at": now,
                "processed_by": user["id"],
                "tx_hash": f"mock_tx_{uuid.uuid4().hex[:10]}"
            }}
        )
        
        # Notify user
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": withdrawal["user_id"],
            "type": "withdrawal_completed",
            "title": "Вывод средств выполнен",
            "message": f"Ваш вывод {withdrawal['amount']} USDT успешно обработан.",
            "read": False,
            "created_at": now
        })
        
    else:
        # Reject - refund money
        await db.withdrawals.update_one(
            {"id": withdrawal_id},
            {"$set": {
                "status": "rejected",
                "processed_at": now,
                "processed_by": user["id"],
                "rejection_reason": data.get("reason", "Rejected by admin") if data else "Rejected by admin"
            }}
        )
        
        # Refund balance
        user_type = withdrawal.get("user_type", "trader")
        collection = db.merchants if user_type == "merchant" else db.traders
        
        await collection.update_one(
            {"id": withdrawal["user_id"]},
            {"$inc": {"balance_usdt": withdrawal["amount"] + withdrawal.get("fee", 0)}}
        )
        
        # Notify user
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": withdrawal["user_id"],
            "type": "withdrawal_rejected",
            "title": "Вывод средств отклонен",
            "message": f"Ваш вывод {withdrawal['amount']} USDT отклонен. Средства возвращены на баланс.",
            "read": False,
            "created_at": now
        })
    
    await log_admin_action(user["id"], "process_withdrawal", "withdrawal", withdrawal_id, {"decision": decision})
    
    return {"status": "success", "decision": decision}
