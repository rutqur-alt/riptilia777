from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid
from typing import Optional, List

from core.database import db
from core.auth import require_role, get_current_user, require_admin_level
from .models import CreateSupportTicketRequest, SendMessageRequest

router = APIRouter()

# Ticket categories
TICKET_CATEGORIES = {
    "general": "Общие вопросы",
    "technical": "Технические проблемы",
    "payment": "Вопросы по платежам",
    "verification": "Верификация",
    "shop_application": "Заявка на открытие магазина",
    "complaint": "Жалоба",
    "suggestion": "Предложение"
}

# ==================== USER SUPPORT ENDPOINTS ====================

@router.post("/support/tickets")
async def create_support_ticket(data: CreateSupportTicketRequest, user: dict = Depends(get_current_user)):
    """Create a new support ticket"""
    if data.category not in TICKET_CATEGORIES:
        raise HTTPException(status_code=400, detail="Неверная категория")
    
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    user_type = user.get("role", "trader")
    user_nickname = user.get("nickname", user.get("login", ""))
    
    ticket_doc = {
        "id": ticket_id,
        "user_id": user["id"],
        "user_type": user_type,
        "user_nickname": user_nickname,
        "category": data.category,
        "category_name": TICKET_CATEGORIES[data.category],
        "subject": data.subject,
        "status": "open",
        "priority": "normal",
        "assigned_to": None,
        "created_at": now,
        "updated_at": now,
        "last_message_at": now,
        "is_shop_application": data.category == "shop_application"
    }
    
    await db.support_tickets.insert_one(ticket_doc)
    
    message_doc = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "sender_id": user["id"],
        "sender_type": "user",
        "sender_nickname": user_nickname,
        "content": data.message,
        "created_at": now
    }
    await db.ticket_messages.insert_one(message_doc)
    
    return {"ticket_id": ticket_id, "status": "created"}


@router.get("/support/tickets")
async def get_my_tickets(user: dict = Depends(get_current_user)):
    """Get user's support tickets"""
    tickets = await db.support_tickets.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    
    for ticket in tickets:
        last_read = ticket.get("user_last_read")
        if last_read:
            unread = await db.ticket_messages.count_documents({
                "ticket_id": ticket["id"],
                "sender_type": "admin",
                "created_at": {"$gt": last_read}
            })
        else:
            unread = await db.ticket_messages.count_documents({
                "ticket_id": ticket["id"],
                "sender_type": "admin"
            })
        ticket["unread_count"] = unread
    
    return tickets


@router.get("/support/tickets/{ticket_id}")
async def get_ticket_details(ticket_id: str, user: dict = Depends(get_current_user)):
    """Get ticket details with messages"""
    ticket = await db.support_tickets.find_one(
        {"id": ticket_id, "user_id": user["id"]},
        {"_id": 0}
    )
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    messages = await db.ticket_messages.find(
        {"ticket_id": ticket_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {"user_last_read": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"ticket": ticket, "messages": messages}


@router.post("/support/tickets/{ticket_id}/message")
async def send_ticket_message(ticket_id: str, data: SendMessageRequest, user: dict = Depends(get_current_user)):
    """Send message to support ticket"""
    ticket = await db.support_tickets.find_one({"id": ticket_id, "user_id": user["id"]})
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    if ticket["status"] == "closed":
        raise HTTPException(status_code=400, detail="Тикет закрыт")
    
    now = datetime.now(timezone.utc).isoformat()
    
    message_doc = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "sender_id": user["id"],
        "sender_type": "user",
        "sender_nickname": user.get("nickname", user.get("login", "")),
        "content": data.content,
        "created_at": now
    }
    await db.ticket_messages.insert_one(message_doc)
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "updated_at": now,
            "last_message_at": now,
            "status": "open" if ticket["status"] == "resolved" else ticket["status"]
        }}
    )
    
    return {"status": "sent", "message_id": message_doc["id"]}


@router.get("/support/categories")
async def get_ticket_categories():
    """Get available ticket categories"""
    return TICKET_CATEGORIES


@router.post("/support/shop-application")
async def create_shop_application_ticket(user: dict = Depends(get_current_user)):
    """Create a shop application ticket"""
    if user.get("role") != "trader":
        raise HTTPException(status_code=403, detail="Только для трейдеров")
    
    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    
    if trader.get("has_shop"):
        raise HTTPException(status_code=400, detail="У вас уже есть магазин")
    
    existing = await db.support_tickets.find_one({
        "user_id": user["id"],
        "category": "shop_application",
        "status": {"$nin": ["closed", "rejected"]}
    })
    
    if existing:
        return {"ticket_id": existing["id"], "status": "exists"}
    
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    ticket_doc = {
        "id": ticket_id,
        "user_id": user["id"],
        "user_type": "trader",
        "user_nickname": user.get("nickname", user.get("login", "")),
        "category": "shop_application",
        "category_name": "Заявка на открытие магазина",
        "subject": "Заявка на открытие магазина",
        "status": "open",
        "priority": "normal",
        "is_shop_application": True,
        "shop_approved": False,
        "assigned_to": None,
        "created_at": now,
        "updated_at": now,
        "last_message_at": now
    }
    
    await db.support_tickets.insert_one(ticket_doc)
    
    welcome_msg = """👋 Здравствуйте! Вы подали заявку на открытие магазина.

Пожалуйста, расскажите нам:
• Название вашего магазина
• Какие товары планируете продавать
• Ваш опыт в продажах (если есть)
• Telegram для связи

Администратор рассмотрит вашу заявку и ответит в этом чате."""

    system_msg = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_nickname": "Система",
        "content": welcome_msg,
        "created_at": now
    }
    await db.ticket_messages.insert_one(system_msg)
    
    return {"ticket_id": ticket_id, "status": "created"}


@router.get("/support/shop-application")
async def get_shop_application_ticket(user: dict = Depends(get_current_user)):
    """Get user's shop application ticket if exists"""
    if user.get("role") != "trader":
        raise HTTPException(status_code=403, detail="Только для трейдеров")
    
    ticket = await db.support_tickets.find_one(
        {
            "user_id": user["id"],
            "category": "shop_application",
            "status": {"$nin": ["closed"]}
        },
        {"_id": 0}
    )
    
    if not ticket:
        return None
    
    messages = await db.ticket_messages.find(
        {"ticket_id": ticket["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return {"ticket": ticket, "messages": messages}


# ==================== ADMIN SUPPORT ENDPOINTS ====================

@router.get("/admin/support/tickets")
async def admin_get_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get all support tickets for admin"""
    query = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    
    tickets = await db.support_tickets.find(query, {"_id": 0}).sort("updated_at", -1).to_list(200)
    
    for ticket in tickets:
        last_read = ticket.get("admin_last_read")
        if last_read:
            unread = await db.ticket_messages.count_documents({
                "ticket_id": ticket["id"],
                "sender_type": "user",
                "created_at": {"$gt": last_read}
            })
        else:
            unread = await db.ticket_messages.count_documents({
                "ticket_id": ticket["id"],
                "sender_type": "user"
            })
        ticket["unread_count"] = unread
    
    return tickets


@router.get("/admin/support/tickets/{ticket_id}")
async def admin_get_ticket_details(ticket_id: str, user: dict = Depends(require_admin_level(30))):
    """Get ticket details for admin"""
    ticket = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    messages = await db.ticket_messages.find(
        {"ticket_id": ticket_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {"admin_last_read": datetime.now(timezone.utc).isoformat()}}
    )
    
    ticket_user = await db.traders.find_one({"id": ticket["user_id"]}, {"_id": 0, "login": 1, "nickname": 1, "balance_usdt": 1})
    if not ticket_user:
        ticket_user = await db.merchants.find_one({"id": ticket["user_id"]}, {"_id": 0, "login": 1, "merchant_name": 1, "balance_usdt": 1})
    
    return {"ticket": ticket, "messages": messages, "user_info": ticket_user}


@router.post("/admin/support/tickets/{ticket_id}/message")
async def admin_send_ticket_message(ticket_id: str, data: SendMessageRequest, user: dict = Depends(require_admin_level(30))):
    """Admin sends message to ticket"""
    ticket = await db.support_tickets.find_one({"id": ticket_id})
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    now = datetime.now(timezone.utc).isoformat()
    
    message_doc = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "sender_id": user["id"],
        "sender_type": "admin",
        "sender_role": user.get("admin_role", "support"),
        "sender_nickname": user.get("nickname", user.get("login", "Поддержка")),
        "content": data.content,
        "created_at": now
    }
    await db.ticket_messages.insert_one(message_doc)
    
    update_data = {
        "updated_at": now,
        "last_message_at": now,
        "admin_last_read": now
    }
    
    if ticket["status"] == "open":
        update_data["status"] = "in_progress"
    if not ticket.get("assigned_to"):
        update_data["assigned_to"] = user["id"]
    
    await db.support_tickets.update_one({"id": ticket_id}, {"$set": update_data})
    
    return {"status": "sent", "message_id": message_doc["id"]}


@router.post("/admin/support/tickets/{ticket_id}/status")
async def admin_update_ticket_status(ticket_id: str, status: str = Body(..., embed=True), user: dict = Depends(require_admin_level(30))):
    """Update ticket status"""
    valid_statuses = ["open", "in_progress", "resolved", "closed"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    ticket = await db.support_tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {"status": status, "updated_at": now}}
    )
    
    status_messages = {
        "in_progress": "📋 Тикет взят в работу",
        "resolved": "✅ Вопрос решён. Если у вас остались вопросы, напишите в этот чат.",
        "closed": "🔒 Тикет закрыт"
    }
    
    if status in status_messages:
        system_msg = {
            "id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "sender_id": "system",
            "sender_type": "system",
            "sender_nickname": "Система",
            "content": status_messages[status],
            "created_at": now
        }
        await db.ticket_messages.insert_one(system_msg)
    
    return {"status": "updated"}


@router.post("/admin/support/tickets/{ticket_id}/approve-shop")
async def admin_approve_shop_application(ticket_id: str, shop_name: str = Body(None, embed=True), user: dict = Depends(require_admin_level(50))):
    """Approve shop application"""
    ticket = await db.support_tickets.find_one({"id": ticket_id})
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    if not ticket.get("is_shop_application"):
        raise HTTPException(status_code=400, detail="Это не заявка на магазин")
    
    if ticket.get("shop_approved"):
        raise HTTPException(status_code=400, detail="Магазин уже одобрен")
    
    trader = await db.traders.find_one({"id": ticket["user_id"]})
    if not trader:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    now = datetime.now(timezone.utc).isoformat()
    final_shop_name = shop_name or trader.get("nickname", trader.get("login", "")) + "'s Shop"
    
    await db.traders.update_one(
        {"id": ticket["user_id"]},
        {"$set": {
            "has_shop": True,
            "shop_settings": {
                "shop_name": final_shop_name,
                "description": "",
                "approved": True,
                "approved_at": now,
                "approved_by": user["id"]
            }
        }}
    )
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "shop_approved": True,
            "shop_name": final_shop_name,
            "status": "resolved",
            "updated_at": now
        }}
    )
    
    approval_msg = f"""🎉 Поздравляем! Ваша заявка на открытие магазина одобрена!

🏪 Название магазина: {final_shop_name}

Теперь вы можете:
• Добавлять товары в раздел "Мой магазин"
• Настроить описание магазина
• Начать продавать

Удачных продаж! 🚀"""

    system_msg = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_nickname": "Система",
        "content": approval_msg,
        "created_at": now
    }
    await db.ticket_messages.insert_one(system_msg)
    
    return {"status": "approved", "shop_name": final_shop_name}


@router.post("/admin/support/tickets/{ticket_id}/reject-shop")
async def admin_reject_shop_application(ticket_id: str, reason: str = Body(None, embed=True), user: dict = Depends(require_admin_level(50))):
    """Reject shop application"""
    ticket = await db.support_tickets.find_one({"id": ticket_id})
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    if not ticket.get("is_shop_application"):
        raise HTTPException(status_code=400, detail="Это не заявка на магазин")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "rejected",
            "rejection_reason": reason,
            "updated_at": now
        }}
    )
    
    rejection_msg = f"""❌ К сожалению, ваша заявка на открытие магазина отклонена.

Причина: {reason or "Не соответствует требованиям"}

Вы можете подать новую заявку после устранения замечаний."""

    system_msg = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_nickname": "Система",
        "content": rejection_msg,
        "created_at": now
    }
    await db.ticket_messages.insert_one(system_msg)
    
    return {"status": "rejected"}
