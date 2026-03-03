"""
Merchant routes - profile, stats, transactions, withdrawals, approval
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List
import uuid

from core.database import db
from core.auth import require_role, get_current_user, hash_password, verify_password
from core.websocket import manager
from models.schemas import MerchantResponse, MerchantApproval

router = APIRouter(tags=["merchants"])


# ==================== ADMIN MERCHANT MANAGEMENT ====================

@router.get("/merchants/pending", response_model=List[MerchantResponse])
async def get_pending_merchants(user: dict = Depends(require_role(["admin"]))):
    """Get all pending merchant applications"""
    merchants = await db.merchants.find({"status": "pending"}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(100)
    return merchants


@router.get("/merchants/all", response_model=List[MerchantResponse])
async def get_all_merchants(user: dict = Depends(require_role(["admin"]))):
    """Get all merchants"""
    merchants = await db.merchants.find({}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(1000)
    return merchants


# IMPORTANT: /merchants/me MUST come BEFORE /merchants/{merchant_id}
@router.get("/merchants/me")
async def get_merchant_me(user: dict = Depends(require_role(["merchant"]))):
    """Get current merchant profile"""
    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "password": 0})
    if merchant:
        return merchant
    return {k: v for k, v in user.items() if k not in ("password_hash", "password")}


# Alias for frontend compatibility
@router.get("/merchant/profile")
async def get_merchant_profile(user: dict = Depends(require_role(["merchant"]))):
    """Get current merchant profile (alias)"""
    return await get_merchant_me(user)


# IMPORTANT: /merchants/stats MUST come BEFORE /merchants/{merchant_id}
@router.get("/merchants/stats")
async def get_merchant_stats(user: dict = Depends(require_role(["merchant"]))):
    """Get merchant statistics"""
    merchant_id = user["id"]
    
    # Get stats from trades (not payment_links)
    trades = await db.trades.find(
        {"merchant_id": merchant_id},
        {"_id": 0, "status": 1, "client_amount_rub": 1, "amount_rub": 1, "amount_usdt": 1, "merchant_receives_usdt": 1}
    ).to_list(1000)
    
    total_payments = len(trades)
    completed_trades = [t for t in trades if t.get("status") == "completed"]
    completed_payments = len(completed_trades)
    
    # Use client_amount_rub (сумма пополнения клиента), not amount_rub (сумма оплаты)
    total_volume_rub = sum([t.get("client_amount_rub") or t.get("amount_rub", 0) for t in completed_trades])
    total_volume_usdt = sum([t.get("amount_usdt", 0) for t in completed_trades])
    
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    
    # Get base rate from Rapira API settings
    rate_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = rate_settings.get("base_rate", 78) if rate_settings else 78
    
    # Calculate total commission: platform_fee_rub / base_rate (Rapira exchange rate)
    total_platform_fee_rub = sum([t.get("platform_fee_rub", 0) or 0 for t in completed_trades])
    total_commission = total_platform_fee_rub / base_rate if base_rate > 0 else 0
    
    avg_payment = total_volume_rub / completed_payments if completed_payments > 0 else 0
    success_rate = (completed_payments / total_payments * 100) if total_payments > 0 else 100
    
    return {
        "total_payments": total_payments,
        "completed_payments": completed_payments,
        "total_volume_rub": total_volume_rub,
        "total_volume_usdt": total_volume_usdt,
        "total_commission": total_commission,
        "avg_payment": avg_payment,
        "success_rate": success_rate
    }


# IMPORTANT: /merchants/transactions MUST come BEFORE /merchants/{merchant_id}
@router.get("/merchants/transactions")
async def get_merchant_transactions(user: dict = Depends(require_role(["merchant"]))):
    """Get merchant transaction history"""
    merchant_id = user["id"]
    transactions = []
    
    # Get completed trades as income - use client_amount_rub
    trades = await db.trades.find(
        {"merchant_id": merchant_id, "status": "completed"},
        {"_id": 0}
    ).to_list(500)
    
    for trade in trades:
        # Use client_amount_rub (сумма пополнения клиента)
        client_amount = trade.get("client_amount_rub") or trade.get("amount_rub", 0)
        transactions.append({
            "id": f"payment_{trade['id']}",
            "type": "payment_received",
            "amount": trade.get("merchant_receives_usdt", 0),  # Что получил мерчант
            "amount_rub": client_amount,  # Сумма пополнения клиента (для отображения)
            "description": f"Пополнение #{trade['id'][-8:]}",
            "created_at": trade.get("completed_at") or trade.get("created_at", "")
        })
    
    # Get withdrawals as expenses
    withdrawals = await db.merchant_withdrawals.find(
        {"merchant_id": merchant_id},
        {"_id": 0}
    ).to_list(500)
    
    for w in withdrawals:
        if w.get("status") == "completed":
            transactions.append({
                "id": f"withdrawal_{w['id']}",
                "type": "withdrawal",
                "amount": -w.get("amount", 0),
                "description": f"Вывод на {w.get('address', '')[:10]}...",
                "created_at": w.get("created_at", "")
            })
    
    # Sort by date
    transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return transactions


# IMPORTANT: /merchants/withdrawals MUST come BEFORE /merchants/{merchant_id}
@router.get("/merchants/withdrawals")
async def get_merchant_withdrawals(user: dict = Depends(require_role(["merchant"]))):
    """Get merchant withdrawal requests"""
    withdrawals = await db.merchant_withdrawals.find(
        {"merchant_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return withdrawals


@router.post("/merchants/withdrawals")
async def create_merchant_withdrawal(data: dict, user: dict = Depends(require_role(["merchant"]))):
    """Create withdrawal request"""
    amount = data.get("amount", 0)
    address = data.get("address", "")
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Некорректная сумма")
    
    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    # Check if balance is locked
    if merchant.get("is_balance_locked"):
        raise HTTPException(status_code=403, detail="Ваш баланс заблокирован. Вывод средств недоступен.")
    
    if amount > merchant.get("balance_usdt", 0):
        raise HTTPException(status_code=400, detail="Недостаточно средств")
    
    if not address or len(address) < 10:
        raise HTTPException(status_code=400, detail="Некорректный адрес кошелька")
    
    withdrawal = {
        "id": str(uuid.uuid4()),
        "merchant_id": user["id"],
        "amount": amount,
        "address": address,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.merchant_withdrawals.insert_one(withdrawal)
    
    # Reserve funds
    await db.merchants.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_usdt": -amount, "reserved_balance": amount}}
    )
    
    return {"status": "created", "withdrawal_id": withdrawal["id"]}


@router.post("/merchants/change-password")
async def change_merchant_password(data: dict, user: dict = Depends(require_role(["merchant"]))):
    """Change merchant password"""
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")
    
    merchant = await db.merchants.find_one({"id": user["id"]})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    # Support both 'password_hash' and 'password' field names
    stored_hash = merchant.get("password_hash") or merchant.get("password", "")
    if not stored_hash or not verify_password(old_password, stored_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Минимум 6 символов")
    
    new_hash = hash_password(new_password)
    await db.merchants.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": new_hash, "password": new_hash}}
    )
    
    return {"status": "success"}


@router.get("/merchants/payments")
async def get_merchant_payments(limit: int = 50, user: dict = Depends(require_role(["merchant"]))):
    """Get merchant payment history from trades"""
    # Get trades for this merchant
    trades = await db.trades.find(
        {"merchant_id": user["id"]},
        {"_id": 0, "id": 1, "client_amount_rub": 1, "amount_rub": 1, 
         "client_pays_rub": 1, "merchant_receives_rub": 1, "merchant_receives_usdt": 1,
         "status": 1, "created_at": 1, "completed_at": 1, "client_nickname": 1,
         "trader_login": 1, "payment_link_id": 1}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return trades


@router.get("/merchants/api-key")
async def get_merchant_api_key(user: dict = Depends(require_role(["merchant"]))):
    """Get current merchant API key and secret"""
    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "password": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    return {
        "api_key": merchant.get("api_key", ""),
        "api_secret": merchant.get("api_secret", ""),
        "webhook_url": merchant.get("webhook_url", "")
    }


@router.get("/merchants/webhook")
async def get_merchant_webhook(user: dict = Depends(require_role(["merchant"]))):
    """Get merchant webhook URL"""
    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0, "webhook_url": 1})
    return {"webhook_url": merchant.get("webhook_url", "") if merchant else ""}


@router.put("/merchants/webhook")
async def update_merchant_webhook(data: dict, user: dict = Depends(require_role(["merchant"]))):
    """Update merchant webhook URL"""
    webhook_url = data.get("webhook_url", "")
    await db.merchants.update_one(
        {"id": user["id"]},
        {"$set": {"webhook_url": webhook_url}}
    )
    return {"status": "success", "webhook_url": webhook_url}


@router.post("/merchants/regenerate-api-key")
async def regenerate_merchant_api_key(user: dict = Depends(require_role(["merchant"]))):
    """Generate new API key for merchant"""
    new_key = f"pk_live_{uuid.uuid4().hex}"
    
    await db.merchants.update_one(
        {"id": user["id"]},
        {"$set": {"api_key": new_key}}
    )
    
    return {"api_key": new_key}


@router.post("/merchants/regenerate-secret-key")
async def regenerate_merchant_secret_key(user: dict = Depends(require_role(["merchant"]))):
    """Generate new Secret key for merchant (used for signature generation)"""
    new_secret = f"sk_live_{uuid.uuid4().hex}"
    
    await db.merchants.update_one(
        {"id": user["id"]},
        {"$set": {"api_secret": new_secret}}
    )
    
    return {"secret_key": new_secret}


# Aliases for frontend compatibility
@router.post("/merchant/regenerate-api-key")
async def regenerate_api_key_alias(user: dict = Depends(require_role(["merchant"]))):
    """Alias for regenerate-api-key"""
    return await regenerate_merchant_api_key(user)


@router.post("/merchant/regenerate-secret-key")
async def regenerate_secret_key_alias(user: dict = Depends(require_role(["merchant"]))):
    """Alias for regenerate-secret-key"""
    return await regenerate_merchant_secret_key(user)


# ==================== MERCHANT BY ID ROUTES ====================

@router.get("/merchants/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(merchant_id: str, user: dict = Depends(get_current_user)):
    """Get merchant by ID"""
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    # Only admin or the merchant themselves can view
    if user.get("role") != "admin" and user.get("id") != merchant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return merchant


@router.get("/merchants/{merchant_id}/public")
async def get_merchant_public(merchant_id: str):
    """Public endpoint to get basic merchant info for payment pages"""
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0, "password_hash": 0, "password": 0, "api_key": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    return {
        "id": merchant["id"],
        "merchant_name": merchant.get("merchant_name", "Unknown"),
        "merchant_type": merchant.get("merchant_type", "other"),
        "status": merchant.get("status", "pending")
    }


@router.post("/merchants/{merchant_id}/approve")
async def approve_merchant(merchant_id: str, data: MerchantApproval, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Approve or reject merchant application"""
    # Try to find merchant by ID or by merchant application ID
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    
    # If not found, try merchant_applications
    if not merchant:
        app = await db.merchant_applications.find_one({"id": merchant_id}, {"_id": 0})
        if app:
            merchant = await db.merchants.find_one({"id": app.get("user_id")}, {"_id": 0})
            if merchant:
                merchant_id = merchant["id"]
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    if data.approved:
        settings = await db.commission_settings.find_one({}, {"_id": 0})
        commission_key = f"{merchant['merchant_type']}_commission"
        commission_rate = data.custom_commission if data.custom_commission else settings.get(commission_key, 0.5)
        withdrawal_commission = data.withdrawal_commission if data.withdrawal_commission else 3.0  # Default 3%
        
        api_key = f"merch_sk_{uuid.uuid4().hex[:32]}"
        
        await db.merchants.update_one(
            {"id": merchant_id},
            {"$set": {
                "status": "active",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approved_by": user["id"],
                "commission_rate": commission_rate,
                "withdrawal_commission": withdrawal_commission,
                "api_key": api_key
            }}
        )
        
        # Update merchant_application status
        await db.merchant_applications.update_one(
            {"user_id": merchant_id},
            {"$set": {"status": "approved"}}
        )
        
        # Update unified_conversation status
        app = await db.merchant_applications.find_one({"user_id": merchant_id}, {"_id": 0})
        app_id = app["id"] if app else merchant_id
        
        await db.unified_conversations.update_one(
            {"type": "merchant_application", "$or": [
                {"related_id": app_id},
                {"participants.user_id": merchant_id}
            ]},
            {"$set": {
                "status": "approved",
                "resolved": True,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "resolved_by": user["id"],
                "archived": True
            }}
        )
        
        # Send approval message to unified_messages
        conv = await db.unified_conversations.find_one(
            {"type": "merchant_application", "$or": [
                {"related_id": app_id},
                {"participants.user_id": merchant_id}
            ]},
            {"_id": 0}
        )
        if conv:
            unified_msg = {
                "id": str(uuid.uuid4()),
                "conversation_id": conv["id"],
                "sender_id": "system",
                "sender_nickname": "Система",
                "sender_role": "system",
                "content": f"🎉 Ваша заявка одобрена!\n\nТеперь вам доступен полный функционал:\n• Создание платежных ссылок\n• Просмотр баланса и истории\n• Настройки API\n• Заявки на продажу крипты\n• Вывод средств\n\n📊 Комиссия P2P: {commission_rate}%\n💰 Комиссия на выплаты: {withdrawal_commission}%",
                "is_system": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.unified_messages.insert_one(unified_msg)
        
        # Legacy message for WebSocket broadcast
        msg = {
            "id": str(uuid.uuid4()),
            "chat_id": f"chat_{merchant_id}",
            "sender_id": "system",
            "sender_type": "system",
            "sender_name": "Система",
            "content": f"🎉 Ваша заявка одобрена!\n\nТеперь вам доступен полный функционал:\n• Создание платежных ссылок\n• Просмотр баланса и истории\n• Настройки API\n• Вывод средств\n\nКомиссия: {commission_rate}%",
            "attachment_url": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.messages.insert_one(msg)
        await manager.broadcast(f"chat_{merchant_id}", msg)
        
        return {"status": "approved", "api_key": api_key}
    else:
        await db.merchants.update_one(
            {"id": merchant_id},
            {"$set": {
                "status": "rejected",
                "rejection_reason": data.reason or "Отказано администратором"
            }}
        )
        
        # Send rejection message
        msg = {
            "id": str(uuid.uuid4()),
            "chat_id": f"chat_{merchant_id}",
            "sender_id": "system",
            "sender_type": "system",
            "sender_name": "Система",
            "content": f"❌ К сожалению, ваша заявка отклонена.\n\nПричина: {data.reason or 'Не указана'}",
            "attachment_url": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.messages.insert_one(msg)
        await manager.broadcast(f"chat_{merchant_id}", msg)
        
        # Auto-archive the conversation for rejected merchant
        await db.unified_conversations.update_one(
            {"type": "merchant_application", "$or": [{"related_id": merchant_id}, {"participants": {"$in": [merchant_id]}}]},
            {"$set": {
                "status": "rejected",
                "resolved": True,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "resolved_by": user["id"],
                "archived": True
            }}
        )
        
        return {"status": "rejected"}


@router.post("/merchants/{merchant_id}/block")
async def block_merchant(merchant_id: str, user: dict = Depends(require_role(["admin"]))):
    """Block a merchant"""
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {"status": "blocked"}}
    )
    return {"status": "blocked"}


@router.post("/merchants/{merchant_id}/suspend")
async def suspend_merchant(merchant_id: str, user: dict = Depends(require_role(["admin"]))):
    """Suspend a merchant"""
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {"status": "suspended"}}
    )
    
    # Send notification message
    msg = {
        "id": str(uuid.uuid4()),
        "chat_id": f"chat_{merchant_id}",
        "sender_id": "system",
        "sender_type": "system",
        "sender_name": "Система",
        "content": "⏸️ Ваш аккаунт временно приостановлен администрацией. Свяжитесь с поддержкой для уточнения причин.",
        "attachment_url": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(msg)
    
    return {"status": "suspended"}


# ==================== DUPLICATE ROUTE FOR ADMIN PANEL ====================
# This route is used by AdminPanel.js for approving merchants

@router.post("/admin/merchants/{merchant_id}/approve")
async def admin_approve_merchant(merchant_id: str, data: MerchantApproval, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Admin endpoint to approve or reject merchant - delegates to main approve function"""
    return await approve_merchant(merchant_id, data, user)
