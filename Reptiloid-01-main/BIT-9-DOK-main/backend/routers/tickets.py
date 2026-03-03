"""
BITARBITR P2P Platform - Tickets Router
Обработка тикетов поддержки
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import logging
import secrets

router = APIRouter(tags=["Tickets"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Глобальные зависимости
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_send_telegram = None
_manager = None
_site_url = "http://localhost:3000"


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256",
                telegram_func=None, ws_manager=None, site_url: str = None):
    """Инициализация роутера"""
    global _db, _jwt_secret, _jwt_algorithm, _send_telegram, _manager, _site_url
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    _send_telegram = telegram_func
    _manager = ws_manager
    if site_url:
        _site_url = site_url


def generate_id(prefix: str = "") -> str:
    """Генерация уникального ID"""
    return f"{prefix}{secrets.token_hex(6).upper()}"


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение текущего пользователя из JWT"""
    from jose import jwt, JWTError
    
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await _db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


def require_role(allowed_roles: list):
    """Проверка роли пользователя"""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access denied")
        return user
    return role_checker


# ================== MODELS ==================

class TicketCreate(BaseModel):
    subject: str
    message: str
    user_id: Optional[str] = None


class TicketReply(BaseModel):
    message: str


class TicketAssignStaff(BaseModel):
    staff_id: str


# ================== HELPER FUNCTIONS ==================

async def create_notification(user_id: str, title: str, message: str, 
                             notification_type: str, link: str = None):
    """Создать уведомление для пользователя"""
    notification = {
        "id": generate_id("notif_"),
        "user_id": user_id,
        "title": title,
        "message": message,
        "type": notification_type,
        "link": link,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await _db.user_notifications.insert_one(notification)
    return notification


async def create_admin_notification(title: str, message: str, 
                                   notification_type: str, link: str = None,
                                   target_user_id: str = None):
    """Создать уведомление для админов"""
    # Получаем всех админов и саппортов
    staff = await _db.users.find(
        {"role": {"$in": ["admin", "support"]}},
        {"_id": 0, "id": 1}
    ).to_list(100)
    
    for s in staff:
        if target_user_id and s["id"] != target_user_id:
            continue
        notification = {
            "id": generate_id("admin_notif_"),
            "user_id": s["id"],
            "title": title,
            "message": message,
            "type": notification_type,
            "link": link,
            "read": False,
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await _db.admin_notifications.insert_one(notification)


# ================== ENDPOINTS ==================

@router.get("/tickets")
async def get_tickets(
    filter_role: Optional[str] = None,
    filter_type: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Получить тикеты"""
    if user["role"] in ["admin", "support"]:
        query = {}
        if filter_role:
            query["user_role"] = filter_role
        if filter_type:
            # Если фильтр "approval" - ищем все типы заявок
            if filter_type == "approval":
                query["type"] = {"$in": ["trader_approval", "merchant_approval", "approval"]}
            else:
                query["type"] = filter_type
        tickets = await _db.tickets.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
        
        for ticket in tickets:
            ticket_user = await _db.users.find_one({"id": ticket["user_id"]}, {"_id": 0, "password_hash": 0})
            if ticket_user:
                ticket["user_login"] = ticket_user.get("login", "")
                ticket["user_nickname"] = ticket_user.get("nickname", "")
    else:
        tickets = await _db.tickets.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("updated_at", -1).to_list(100)
    
    return {"tickets": tickets}


@router.post("/tickets")
async def create_ticket(
    data: TicketCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Создать тикет"""
    # Проверка для pending пользователей
    if user["role"] in ["trader", "merchant"] and user.get("approval_status") == "pending":
        raise HTTPException(
            status_code=403, 
            detail="Ваш аккаунт ожидает подтверждения. Создание тикетов недоступно."
        )
    
    target_user_id = user["id"]
    ticket_type = "support"
    is_admin_initiated = False
    
    # Админ может создать тикет для пользователя
    if user["role"] in ["admin", "support"] and data.user_id:
        target_user = await _db.users.find_one({"id": data.user_id})
        if not target_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        target_user_id = data.user_id
        ticket_type = "admin_message"
        is_admin_initiated = True
    
    ticket_id = generate_id("ticket_")
    now = datetime.now(timezone.utc).isoformat()
    
    target_user_data = await _db.users.find_one({"id": target_user_id}, {"_id": 0})
    
    ticket = {
        "id": ticket_id,
        "user_id": target_user_id,
        "user_role": target_user_data.get("role", "user") if target_user_data else user["role"],
        "subject": data.subject,
        "status": "open",
        "type": ticket_type,
        "messages": [{
            "id": generate_id("msg_"),
            "sender_id": user["id"],
            "sender_role": user["role"],
            "sender_name": user.get("nickname", user.get("login", "User")),
            "message": data.message,
            "created_at": now
        }],
        "unread_by_admin": 0 if is_admin_initiated else 1,
        "unread_by_user": 1 if is_admin_initiated else 0,
        "assigned_staff": [],
        "created_at": now,
        "updated_at": now
    }
    
    await _db.tickets.insert_one(ticket)
    
    # Уведомления
    if is_admin_initiated:
        await create_notification(
            target_user_id,
            "Новое сообщение от поддержки",
            f"Тема: {data.subject}",
            "private_message",
            f"/support?ticket={ticket_id}"
        )
        if _send_telegram:
            background_tasks.add_task(
                _send_telegram,
                target_user_id,
                f"📩 Новое сообщение от поддержки\n\nТема: {data.subject}\n\n{_site_url}/support?ticket={ticket_id}"
            )
    else:
        await create_admin_notification(
            "Новый тикет",
            f"От: {user.get('nickname', user.get('login'))}\nТема: {data.subject}",
            "new_ticket",
            f"/admin/tickets?ticket={ticket_id}"
        )
        if _send_telegram:
            staff = await _db.users.find({"role": {"$in": ["admin", "support"]}}).to_list(100)
            for s in staff:
                background_tasks.add_task(
                    _send_telegram,
                    s["id"],
                    f"🎫 Новый тикет\n\nОт: {user.get('nickname', user.get('login'))}\nТема: {data.subject}\n\n{_site_url}/admin/tickets?ticket={ticket_id}"
                )
    
    ticket.pop("_id", None)
    return {"success": True, "ticket": ticket}


@router.get("/tickets/unread-count")
async def get_tickets_unread_count(user: dict = Depends(get_current_user)):
    """Получить количество непрочитанных тикетов"""
    if user["role"] in ["admin", "support"]:
        count = await _db.tickets.count_documents({"unread_by_admin": {"$gt": 0}})
    else:
        count = await _db.tickets.count_documents({
            "user_id": user["id"],
            "unread_by_user": {"$gt": 0}
        })
    return {"unread_count": count}


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
    """Получить тикет по ID"""
    ticket = await _db.tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    # Проверка доступа
    if user["role"] not in ["admin", "support"] and ticket["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому тикету")
    
    # Добавляем информацию о пользователе
    ticket_user = await _db.users.find_one({"id": ticket["user_id"]}, {"_id": 0, "password_hash": 0})
    if ticket_user:
        ticket["user_login"] = ticket_user.get("login", "")
        ticket["user_nickname"] = ticket_user.get("nickname", "")
    
    # Получаем информацию о назначенных сотрудниках
    assigned_staff = []
    if ticket.get("assigned_staff"):
        staff_list = await _db.users.find(
            {"id": {"$in": ticket["assigned_staff"]}},
            {"_id": 0, "id": 1, "login": 1, "nickname": 1, "role": 1}
        ).to_list(100)
        assigned_staff = staff_list
    
    # Возвращаем в формате, ожидаемом фронтендом
    return {
        "ticket": ticket,
        "messages": ticket.get("messages", []),
        "user": ticket_user,
        "assigned_staff": assigned_staff
    }


@router.post("/tickets/{ticket_id}/reply")
async def reply_to_ticket(
    ticket_id: str,
    data: TicketReply,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Ответить на тикет"""
    ticket = await _db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    if user["role"] not in ["admin", "support"] and ticket["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    now = datetime.now(timezone.utc).isoformat()
    message = {
        "id": generate_id("msg_"),
        "sender_id": user["id"],
        "sender_role": user["role"],
        "sender_name": user.get("nickname", user.get("login", "User")),
        "message": data.message,
        "created_at": now
    }
    
    update = {
        "$push": {"messages": message},
        "$set": {"updated_at": now, "status": "open"}
    }
    
    is_staff = user["role"] in ["admin", "support"]
    if is_staff:
        update["$set"]["unread_by_user"] = ticket.get("unread_by_user", 0) + 1
        update["$set"]["unread_by_admin"] = 0
    else:
        update["$set"]["unread_by_admin"] = ticket.get("unread_by_admin", 0) + 1
        update["$set"]["unread_by_user"] = 0
    
    await _db.tickets.update_one({"id": ticket_id}, update)
    
    # Уведомления
    if is_staff:
        await create_notification(
            ticket["user_id"],
            "Ответ на тикет",
            f"Тема: {ticket['subject']}",
            "ticket_reply",
            f"/support?ticket={ticket_id}"
        )
        if _send_telegram:
            background_tasks.add_task(
                _send_telegram,
                ticket["user_id"],
                f"💬 Ответ на тикет\n\nТема: {ticket['subject']}\n\n{_site_url}/support?ticket={ticket_id}"
            )
    else:
        await create_admin_notification(
            "Ответ на тикет",
            f"От: {user.get('nickname', user.get('login'))}\nТема: {ticket['subject']}",
            "ticket_reply",
            f"/admin/tickets?ticket={ticket_id}"
        )
    
    return {"success": True, "message": message}


@router.post("/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
    """Закрыть тикет"""
    ticket = await _db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    if user["role"] not in ["admin", "support"] and ticket["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    await _db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {"status": "closed", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"success": True}


@router.post("/tickets/{ticket_id}/mark-read")
async def mark_ticket_read(ticket_id: str, user: dict = Depends(get_current_user)):
    """Отметить тикет как прочитанный"""
    ticket = await _db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    if user["role"] in ["admin", "support"]:
        await _db.tickets.update_one({"id": ticket_id}, {"$set": {"unread_by_admin": 0}})
    elif ticket["user_id"] == user["id"]:
        await _db.tickets.update_one({"id": ticket_id}, {"$set": {"unread_by_user": 0}})
    
    return {"success": True}


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(
    ticket_id: str, 
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Удалить тикет (только админ)"""
    result = await _db.tickets.delete_one({"id": ticket_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    return {"success": True}


@router.post("/tickets/{ticket_id}/assign")
async def assign_staff_to_ticket(
    ticket_id: str,
    data: TicketAssignStaff,
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Назначить сотрудника на тикет"""
    ticket = await _db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    staff = await _db.users.find_one({"id": data.staff_id, "role": {"$in": ["admin", "support"]}})
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    assigned = ticket.get("assigned_staff", [])
    if data.staff_id in assigned:
        raise HTTPException(status_code=400, detail="Сотрудник уже назначен")
    
    await _db.tickets.update_one(
        {"id": ticket_id},
        {
            "$push": {"assigned_staff": data.staff_id},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    return {"success": True, "message": f"Сотрудник {staff.get('nickname', staff['login'])} назначен"}


@router.delete("/tickets/{ticket_id}/assign/{staff_id}")
async def unassign_staff_from_ticket(
    ticket_id: str,
    staff_id: str,
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Снять сотрудника с тикета"""
    result = await _db.tickets.update_one(
        {"id": ticket_id},
        {
            "$pull": {"assigned_staff": staff_id},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Тикет или назначение не найдено")
    
    return {"success": True}


@router.get("/tickets/{ticket_id}/staff")
async def get_ticket_staff(
    ticket_id: str,
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Получить список назначенных сотрудников"""
    ticket = await _db.tickets.find_one({"id": ticket_id}, {"_id": 0, "assigned_staff": 1})
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    staff_ids = ticket.get("assigned_staff", [])
    staff_list = await _db.users.find(
        {"id": {"$in": staff_ids}},
        {"_id": 0, "id": 1, "login": 1, "nickname": 1, "role": 1}
    ).to_list(100)
    
    return {"staff": staff_list}


@router.get("/admin/tickets/stats")
async def get_tickets_stats(user: dict = Depends(require_role(["admin", "support"]))):
    """Статистика тикетов"""
    total = await _db.tickets.count_documents({})
    open_count = await _db.tickets.count_documents({"status": "open"})
    closed = await _db.tickets.count_documents({"status": "closed"})
    unread = await _db.tickets.count_documents({"unread_by_admin": {"$gt": 0}})
    
    return {
        "total": total,
        "open": open_count,
        "closed": closed,
        "unread": unread
    }
