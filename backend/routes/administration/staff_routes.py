from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
import uuid

from core.database import db, ADMIN_ROLES, ROLE_PERMISSIONS
from core.auth import require_admin_level, log_admin_action, hash_password
from .utils import get_msg_role_info

router = APIRouter()

# ==================== ADMIN: STAFF MANAGEMENT ====================

@router.get("/admin/staff")
async def get_staff_list(user: dict = Depends(require_admin_level(80))):
    """Get all staff members"""
    staff = await db.admins.find({}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(100)
    return staff


@router.post("/admin/staff/create")
async def create_staff_member(data: dict, user: dict = Depends(require_admin_level(100))):
    """Create new staff member (owner only)"""
    login = data.get("login")
    password = data.get("password")
    admin_role = data.get("role", "support")  # owner, admin, mod_p2p, mod_market, support
    nickname = data.get("nickname", login)
    
    if not login or not password:
        raise HTTPException(status_code=400, detail="Login and password required")
    
    if admin_role not in ADMIN_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {list(ADMIN_ROLES.keys())}")
    
    # Check if creating owner/admin requires owner role
    if admin_role in ["owner", "admin"] and ADMIN_ROLES.get(user.get("admin_role", "admin"), 0) < 100:
        raise HTTPException(status_code=403, detail="Only owner can create admins")
    
    existing = await db.admins.find_one({"login": login})
    if existing:
        raise HTTPException(status_code=400, detail="Login already exists")
    
    staff_doc = {
        "id": str(uuid.uuid4()),
        "login": login,
        "nickname": nickname,
        "password_hash": hash_password(password),
        "role": "admin",  # For auth system
        "admin_role": admin_role,  # Specific admin role
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
        "balance_usdt": 0.0  # Staff wallet
    }
    
    await db.admins.insert_one(staff_doc)
    
    await log_admin_action(user["id"], "create_staff", "admin", staff_doc["id"], {"login": login, "role": admin_role})
    
    return {"status": "success", "id": staff_doc["id"]}


@router.delete("/admin/staff/{staff_id}")
async def delete_staff_member(staff_id: str, user: dict = Depends(require_admin_level(100))):
    """Delete staff member (owner only)"""
    staff = await db.admins.find_one({"id": staff_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    if staff.get("admin_role") == "owner":
        raise HTTPException(status_code=403, detail="Cannot delete owner")
    
    await db.admins.delete_one({"id": staff_id})
    
    await log_admin_action(user["id"], "delete_staff", "admin", staff_id, {"login": staff.get("login")})
    
    return {"status": "deleted"}


@router.put("/admin/staff/{staff_id}/permissions")
async def update_staff_permissions(staff_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Update staff member's custom permissions"""
    staff = await db.admins.find_one({"id": staff_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    if staff.get("admin_role") == "owner":
        raise HTTPException(status_code=403, detail="Cannot modify owner permissions")
    
    custom_permissions = data.get("permissions", [])
    
    await db.admins.update_one(
        {"id": staff_id},
        {"$set": {"custom_permissions": custom_permissions}}
    )
    
    await log_admin_action(user["id"], "update_staff_permissions", "admin", staff_id, {"permissions": custom_permissions})
    
    return {"status": "updated", "permissions": custom_permissions}


@router.get("/admin/staff/{staff_id}")
async def get_staff_member(staff_id: str, user: dict = Depends(require_admin_level(50))):
    """Get single staff member details"""
    staff = await db.admins.find_one({"id": staff_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Add default permissions based on role
    role = staff.get("admin_role", "support")
    staff["role_permissions"] = ROLE_PERMISSIONS.get(role, [])
    staff["custom_permissions"] = staff.get("custom_permissions", [])
    
    return staff


@router.get("/admin/permissions/list")
async def get_all_permissions(user: dict = Depends(require_admin_level(50))):
    """Get list of all available permissions"""
    return {
        "permissions": [
            {"key": "view_users", "label": "Просмотр пользователей", "category": "users"},
            {"key": "view_user_stats", "label": "Статистика пользователей", "category": "users"},
            {"key": "block_users", "label": "Блокировка пользователей", "category": "users"},
            {"key": "view_p2p_trades", "label": "Просмотр P2P сделок", "category": "p2p"},
            {"key": "view_p2p_offers", "label": "Просмотр объявлений", "category": "p2p"},
            {"key": "resolve_p2p_disputes", "label": "Решение споров P2P", "category": "p2p"},
            {"key": "view_shops", "label": "Просмотр магазинов", "category": "market"},
            {"key": "block_shops", "label": "Блокировка магазинов", "category": "market"},
            {"key": "approve_shops", "label": "Одобрение магазинов", "category": "market"},
            {"key": "view_products", "label": "Просмотр товаров", "category": "market"},
            {"key": "act_as_guarantor", "label": "Гарант сделок", "category": "market"},
            {"key": "view_messages", "label": "Просмотр сообщений", "category": "support"},
            {"key": "send_messages", "label": "Отправка сообщений", "category": "support"},
            {"key": "view_tickets", "label": "Просмотр тикетов", "category": "support"},
            {"key": "answer_tickets", "label": "Ответы на тикеты", "category": "support"},
            {"key": "escalate_to_moderator", "label": "Эскалация модератору", "category": "support"},
            {"key": "escalate_to_admin", "label": "Эскалация админу", "category": "support"},
        ],
        "role_defaults": ROLE_PERMISSIONS
    }


# ==================== EXTENDED ADMIN FUNCTIONS (from staff_admin.py) ====================

@router.get("/admin/activity-monitor")
async def get_staff_activity_monitor(user: dict = Depends(require_admin_level(80))):
    """Get staff activity monitoring data (admin only)"""
    now = datetime.now(timezone.utc)
    
    all_staff = await db.admins.find({"is_active": True}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(100)
    
    cutoff = (now - timedelta(seconds=60)).isoformat()
    online_staff = await db.admin_online.find({"last_seen": {"$gte": cutoff}}, {"_id": 0}).to_list(100)
    online_ids = {s.get("admin_id") for s in online_staff}
    
    staff_stats = []
    for staff in all_staff:
        staff_id = staff.get("id")
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        decisions_today = await db.decisions.count_documents({
            "decided_by": staff_id,
            "created_at": {"$gte": today_start}
        })
        
        messages_today = await db.unified_messages.count_documents({
            "sender_id": staff_id,
            "created_at": {"$gte": today_start}
        })
        
        last_decision = await db.decisions.find_one(
            {"decided_by": staff_id},
            {"_id": 0, "created_at": 1, "decision_type": 1},
            sort=[("created_at", -1)]
        )
        
        staff_stats.append({
            "id": staff_id,
            "login": staff.get("login"),
            "nickname": staff.get("nickname"),
            "role": staff.get("admin_role"),
            "is_online": staff_id in online_ids,
            "decisions_today": decisions_today,
            "messages_today": messages_today,
            "last_decision": last_decision
        })
    
    return {"staff": staff_stats, "total_online": len(online_ids), "total_staff": len(all_staff)}


@router.post("/admin/decisions/{decision_id}/review")
async def review_moderator_decision(
    decision_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_admin_level(80))
):
    """Admin reviews and potentially overturns a moderator's decision"""
    action = data.get("action")
    new_decision = data.get("new_decision")
    reason = data.get("reason", "")
    
    if action not in ["confirm", "overturn"]:
        raise HTTPException(status_code=400, detail="Действие должно быть: confirm или overturn")
    
    original = await db.decisions.find_one({"id": decision_id}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Решение не найдено")
    
    if original.get("reviewed"):
        raise HTTPException(status_code=400, detail="Решение уже пересмотрено")
    
    now = datetime.now(timezone.utc)
    
    await db.decisions.update_one(
        {"id": decision_id},
        {"$set": {
            "reviewed": True,
            "reviewed_by": user["id"],
            "reviewed_at": now.isoformat(),
            "review_action": action,
            "review_reason": reason
        }}
    )
    
    if action == "overturn":
        if not new_decision:
            raise HTTPException(status_code=400, detail="Новое решение обязательно при пересмотре")
        
        new_decision_doc = {
            "id": str(uuid.uuid4()),
            "order_id": original.get("order_id"),
            "conversation_id": original.get("conversation_id"),
            "decision_type": new_decision,
            "is_overturn": True,
            "original_decision_id": decision_id,
            "decided_by": user["id"],
            "decided_by_role": "admin",
            "decided_by_name": user.get("nickname", user.get("login", "")),
            "reason": reason,
            "status": "pending_execution",
            "created_at": now.isoformat()
        }
        await db.decisions.insert_one(new_decision_doc)
        
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": original.get("decided_by"),
            "type": "decision_overturned",
            "title": "Ваше решение пересмотрено",
            "message": f"Администратор пересмотрел ваше решение по заказу {original.get('order_id', '')[:8]}. Причина: {reason}",
            "read": False,
            "created_at": now.isoformat()
        })
        
        return {"status": "overturned", "new_decision_id": new_decision_doc["id"]}
    
    return {"status": "confirmed", "message": "Решение подтверждено"}


# ==================== STAFF PAYMENTS ====================

@router.post("/admin/staff/pay")
async def pay_staff_member(
    data: dict = Body(...),
    user: dict = Depends(require_admin_level(80))
):
    """Pay salary/bonus to staff member"""
    staff_id = data.get("staff_id")
    amount = data.get("amount")
    reason = data.get("reason", "Salary")
    
    if not staff_id or not amount:
        raise HTTPException(status_code=400, detail="Missing required fields")
        
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
        
    staff = await db.admins.find_one({"id": staff_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
        
    # Add to staff balance
    await db.admins.update_one(
        {"id": staff_id},
        {"$inc": {"balance_usdt": amount}}
    )
    
    # Log transaction
    tx_id = str(uuid.uuid4())
    await db.transactions.insert_one({
        "id": tx_id,
        "user_id": staff_id,
        "type": "staff_payment",
        "amount": amount,
        "currency": "USDT",
        "description": reason,
        "status": "completed",
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    await log_admin_action(user["id"], "pay_staff", "admin", staff_id, {"amount": amount, "reason": reason})
    
    return {"status": "success", "transaction_id": tx_id}
