"""
BITARBITR P2P Platform - Disputes Router
Обработка споров между покупателями и трейдерами
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging
import secrets

router = APIRouter(tags=["Disputes"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Глобальные зависимости
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_send_telegram = None
_manager = None
_fetch_rate_func = None
_notify_dispute_message = None
_notify_dispute_resolved = None


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256",
                telegram_func=None, ws_manager=None, fetch_rate_func=None,
                notify_dispute_message_func=None, notify_dispute_resolved_func=None):
    """Инициализация роутера"""
    global _db, _jwt_secret, _jwt_algorithm, _send_telegram, _manager, _fetch_rate_func
    global _notify_dispute_message, _notify_dispute_resolved
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    _send_telegram = telegram_func
    _manager = ws_manager
    _fetch_rate_func = fetch_rate_func
    _notify_dispute_message = notify_dispute_message_func
    _notify_dispute_resolved = notify_dispute_resolved_func


async def get_current_rate():
    """Получение актуального курса USDT/RUB из единого источника"""
    if _fetch_rate_func:
        try:
            rate = await _fetch_rate_func()
            return rate
        except Exception as e:
            logger.error(f"Error fetching rate: {e}")
    # Fallback на базу данных
    settings = await _db.settings.find_one({"key": "exchange_rate"})
    return settings.get("value", 75.0) if settings else 75.0


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

class ChatMessageCreate(BaseModel):
    text: str


class BuyerMessageCreate(BaseModel):
    text: str
    contact: Optional[str] = None


class DisputeResolve(BaseModel):
    resolution: str  # "refund", "complete", "pay_buyer", "cancel"
    comment: Optional[str] = None


# ================== HELPER FUNCTIONS ==================

async def create_admin_notification(title: str, message: str, 
                                   notification_type: str, link: str = None):
    """Создать уведомление для всех админов"""
    staff = await _db.users.find(
        {"role": {"$in": ["admin", "support"]}},
        {"_id": 0, "id": 1}
    ).to_list(100)
    
    for s in staff:
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

@router.get("/disputes")
async def get_disputes(
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Получить список споров с данными о заказах"""
    if user["role"] in ["admin", "support"]:
        query = {}
        if status:
            query["status"] = status
        disputes = await _db.disputes.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    elif user["role"] == "trader":
        query = {"trader_id": user["id"]}
        if status:
            query["status"] = status
        disputes = await _db.disputes.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    else:
        disputes = []
    
    # Добавляем информацию о заказах к каждому спору
    for dispute in disputes:
        order = await _db.orders.find_one({"id": dispute.get("order_id")}, {"_id": 0})
        if order:
            dispute["order"] = order
            dispute["amount_rub"] = order.get("amount_rub")
            dispute["amount_usdt"] = order.get("amount_usdt")
    
    return {"disputes": disputes}


@router.get("/disputes/{dispute_id}")
async def get_dispute(dispute_id: str, user: dict = Depends(get_current_user)):
    """Получить спор по ID"""
    dispute = await _db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    # Получаем заказ для проверки доступа
    order = await _db.orders.find_one({"id": dispute["order_id"]}, {"_id": 0})
    
    # Проверка доступа
    allowed = user["role"] in ["admin", "support"]
    if user["role"] == "trader" and order:
        trader = await _db.traders.find_one({"id": order.get("trader_id")}, {"_id": 0})
        if trader and trader.get("user_id") == user["id"]:
            allowed = True
    
    if not allowed:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    return {"dispute": dispute, "order": order}


@router.get("/disputes/{dispute_id}/messages")
async def get_dispute_messages(dispute_id: str, user: dict = Depends(get_current_user)):
    """Получить сообщения чата диспута"""
    dispute = await _db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    # Получаем заказ для проверки доступа
    order = await _db.orders.find_one({"id": dispute["order_id"]}, {"_id": 0})
    
    # Проверка доступа
    allowed = user["role"] in ["admin", "support"]
    
    if user["role"] == "trader" and order:
        trader = await _db.traders.find_one({"id": order.get("trader_id")}, {"_id": 0})
        if trader and trader.get("user_id") == user["id"]:
            allowed = True
    
    if user["role"] == "merchant" and order:
        merchant = await _db.merchants.find_one({"user_id": user["id"]}, {"_id": 0})
        if merchant and merchant.get("id") == order.get("merchant_id"):
            allowed = True
    
    if not allowed:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    messages = await _db.dispute_messages.find(
        {"dispute_id": dispute_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return {"messages": messages, "dispute": dispute, "order": order}


@router.post("/disputes/{dispute_id}/messages")
async def send_dispute_message(
    dispute_id: str,
    data: ChatMessageCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Отправить сообщение в чат диспута"""
    dispute = await _db.disputes.find_one({"id": dispute_id})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    if dispute.get("status") != "open":
        raise HTTPException(status_code=400, detail="Спор закрыт")
    
    # Получаем заказ для проверки доступа
    order = await _db.orders.find_one({"id": dispute["order_id"]}, {"_id": 0})
    
    # Проверка доступа и определение роли отправителя
    sender_role = "unknown"
    if user["role"] in ["admin", "support"]:
        sender_role = "admin"  # Администрация
    elif user["role"] == "trader" and order:
        trader = await _db.traders.find_one({"id": order.get("trader_id")}, {"_id": 0})
        if trader and trader.get("user_id") == user["id"]:
            sender_role = "trader"
    elif user["role"] == "merchant" and order:
        # Проверяем что это мерчант этого заказа
        merchant = await _db.merchants.find_one({"id": order.get("merchant_id")}, {"_id": 0})
        if merchant and merchant.get("user_id") == user["id"]:
            sender_role = "merchant"
    
    if sender_role == "unknown":
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    now = datetime.now(timezone.utc).isoformat()
    message = {
        "id": generate_id("msg_"),
        "dispute_id": dispute_id,
        "sender_id": user["id"],
        "sender_role": sender_role,
        "sender_name": user.get("nickname", user.get("login", "User")),
        "text": data.text,
        "created_at": now
    }
    
    await _db.dispute_messages.insert_one(message)
    await _db.disputes.update_one(
        {"id": dispute_id},
        {"$set": {"updated_at": now}}
    )
    
    # Уведомляем участников о новом сообщении
    if _notify_dispute_message:
        background_tasks.add_task(
            _notify_dispute_message,
            dispute, order, user["id"], sender_role, data.text
        )
    
    message.pop("_id", None)
    return {"success": True, "message": message}


@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: str,
    data: DisputeResolve,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Разрешить спор (админ)"""
    dispute = await _db.disputes.find_one({"id": dispute_id})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    if dispute.get("status") != "open":
        raise HTTPException(status_code=400, detail="Спор уже закрыт")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await _db.disputes.update_one(
        {"id": dispute_id},
        {
            "$set": {
                "status": "resolved",
                "resolution": data.resolution,
                "resolution_comment": data.comment,
                "resolved_by": user["id"],
                "resolved_at": now,
                "updated_at": now
            }
        }
    )
    
    # Обновляем связанный ордер и распределяем USDT
    order = await _db.orders.find_one({"id": dispute.get("order_id")})
    if order:
        trader_id = order.get("trader_id")
        amount_usdt = order.get("amount_usdt", 0)
        
        # Получаем трейдера и его кошелёк
        trader = None
        trader_wallet = None
        if trader_id:
            trader = await _db.traders.find_one({"id": trader_id}, {"_id": 0})
            if trader:
                trader_wallet = await _db.wallets.find_one({"user_id": trader["user_id"]}, {"_id": 0})
        
        # Проверяем есть ли заблокированные средства
        locked_amount = trader_wallet.get("locked_balance_usdt", 0) if trader_wallet else 0
        has_locked_funds = locked_amount >= amount_usdt
        
        if data.resolution in ["refund", "cancel"]:
            # ============ ОТМЕНА: USDT возвращаются трейдеру ============
            await _db.orders.update_one(
                {"id": order["id"]},
                {"$set": {"status": "cancelled", "updated_at": now}}
            )
            
            # Обновляем invoice
            await _db.merchant_invoices.update_one(
                {"id": order["id"]},
                {"$set": {"status": "cancelled", "updated_at": now}}
            )
            
            # Возвращаем USDT трейдеру (из locked в available) ТОЛЬКО если средства были заблокированы
            if trader and has_locked_funds:
                await _db.wallets.update_one(
                    {"user_id": trader["user_id"]},
                    {
                        "$inc": {
                            "locked_balance_usdt": -round(amount_usdt, 4),
                            "available_balance_usdt": round(amount_usdt, 4)
                        }
                    }
                )
                # Корректируем погрешность округления
                wallet_check = await _db.wallets.find_one({"user_id": trader["user_id"]}, {"_id": 0, "locked_balance_usdt": 1})
                locked_val = wallet_check.get("locked_balance_usdt", 0) if wallet_check else 0
                if locked_val < 0 or (0 < locked_val < 0.001):
                    await _db.wallets.update_one({"user_id": trader["user_id"]}, {"$set": {"locked_balance_usdt": 0}})
                    
                logger.info(f"Returned {amount_usdt} USDT to trader {trader_id}")
            elif trader and not has_locked_funds:
                logger.warning(f"No locked funds to return for order {order['id']}, locked={locked_amount}, required={amount_usdt}")
            
        elif data.resolution in ["complete", "pay_buyer"]:
            # ============ В ПОЛЬЗУ ПОКУПАТЕЛЯ: Нормальное завершение ============
            from financial_logic import calculate_completion_distribution
            
            await _db.orders.update_one(
                {"id": order["id"]},
                {"$set": {"status": "completed", "completed_at": now, "updated_at": now}}
            )
            
            # Обновляем invoice
            await _db.merchant_invoices.update_one(
                {"id": order["id"]},
                {"$set": {"status": "completed", "paid_at": now, "updated_at": now}}
            )
            
            # Распределяем USDT как при обычном завершении ТОЛЬКО если средства были заблокированы
            if trader and amount_usdt > 0 and has_locked_funds:
                # Получаем настройки мерчанта
                merchant = await _db.merchants.find_one({"id": order.get("merchant_id")}, {"_id": 0})
                fee_model = merchant.get("fee_model", "customer_pays") if merchant else "customer_pays"
                merchant_fee_percent = merchant.get("total_fee_percent", 30.0) if merchant else 30.0
                
                # Получаем настройки трейдера
                trader_fee_percent = trader.get("fee_percent", trader.get("default_fee_percent", 10.0))
                
                # Получаем суммы из заказа (нужно до проверки интервалов)
                original_amount_rub = order.get("original_amount_rub", order.get("amount_rub_original", order.get("amount_rub", 0)))
                total_amount_rub = order.get("amount_rub", 0)
                marker_rub = order.get("marker", order.get("marker_rub", 0))
                
                # Проверяем интервалы комиссий трейдера
                fee_intervals = trader.get("fee_intervals", [])
                for interval in fee_intervals:
                    if interval.get("min_amount", 0) <= original_amount_rub <= interval.get("max_amount", float('inf')):
                        trader_fee_percent = interval.get("percent", trader_fee_percent)
                        break
                
                # Используем курс из заказа или единый источник
                usdt_rate = order.get("exchange_rate")
                if not usdt_rate:
                    usdt_rate = await get_current_rate()
                
                try:
                    distribution = calculate_completion_distribution(
                        original_amount_rub=original_amount_rub,
                        total_amount_rub=total_amount_rub,
                        marker_rub=marker_rub,
                        merchant_fee_percent=merchant_fee_percent,
                        trader_fee_percent=trader_fee_percent,
                        fee_model=fee_model,
                        usdt_rate=usdt_rate
                    )
                    
                    # Обновляем кошелёк трейдера: из locked вычитаем, в earned добавляем
                    await _db.wallets.update_one(
                        {"user_id": trader["user_id"]},
                        {"$inc": {
                            "locked_balance_usdt": -distribution.trader_locked_released_usdt,
                            "earned_balance_usdt": distribution.trader_earns_usdt
                        }}
                    )
                    
                    # Зачисляем мерчанту
                    if merchant and merchant.get("user_id"):
                        await _db.wallets.update_one(
                            {"user_id": merchant["user_id"]},
                            {"$inc": {"available_balance_usdt": distribution.merchant_receives_usdt}},
                            upsert=True
                        )
                    
                    # Записываем доход платформы
                    await _db.platform_income.insert_one({
                        "id": generate_id("pinc_"),
                        "order_id": order["id"],
                        "amount_rub": distribution.platform_receives_rub,
                        "amount_usdt": distribution.platform_receives_usdt,
                        "fee_model": fee_model,
                        "source": "dispute_resolution",
                        "created_at": now
                    })
                    
                    logger.info(f"Distributed via dispute: trader earned={distribution.trader_earns_usdt}, merchant={distribution.merchant_receives_usdt}, platform={distribution.platform_receives_usdt}")
                    
                except Exception as e:
                    logger.error(f"Error calculating distribution for dispute order {order['id']}: {e}")
                    # Fallback на простой расчёт
                    trader_commission = amount_usdt * 0.1  # 10%
                    merchant_amount = amount_usdt * 0.87   # 87%
                    platform_commission = amount_usdt * 0.03  # 3%
                    
                    await _db.wallets.update_one(
                        {"user_id": trader["user_id"]},
                        {"$inc": {"locked_balance_usdt": -amount_usdt, "earned_balance_usdt": trader_commission}}
                    )
                    if merchant and merchant.get("user_id"):
                        await _db.wallets.update_one(
                            {"user_id": merchant["user_id"]},
                            {"$inc": {"available_balance_usdt": merchant_amount}},
                            upsert=True
                        )
                    logger.info(f"Fallback distribution: trader={trader_commission}, merchant={merchant_amount}")
                    
            elif trader and not has_locked_funds:
                logger.warning(f"No locked funds to distribute for order {order['id']}, locked={locked_amount}, required={amount_usdt}")
    
    # Системное сообщение в чат
    resolution_labels = {
        "pay_buyer": "В пользу покупателя",
        "complete": "Сделка завершена",
        "refund": "Возврат средств",
        "cancel": "Отменено"
    }
    resolution_text = resolution_labels.get(data.resolution, data.resolution)
    
    system_msg = {
        "id": generate_id("msg_"),
        "dispute_id": dispute_id,
        "sender_id": "system",
        "sender_role": "moderator",
        "sender_name": "Система",
        "text": f"✅ Спор закрыт модератором.\n\nРешение: {resolution_text}" + (f"\nКомментарий: {data.comment}" if data.comment else ""),
        "created_at": now
    }
    await _db.dispute_messages.insert_one(system_msg)
    
    # Уведомляем участников о закрытии спора
    if _notify_dispute_resolved and order:
        background_tasks.add_task(
            _notify_dispute_resolved,
            dispute, order, data.resolution
        )
    
    return {"success": True, "resolution": data.resolution}


@router.get("/admin/disputes/stats")
async def get_disputes_stats(user: dict = Depends(require_role(["admin", "support"]))):
    """Статистика споров"""
    total = await _db.disputes.count_documents({})
    open_count = await _db.disputes.count_documents({"status": "open"})
    resolved = await _db.disputes.count_documents({"status": "resolved"})
    
    return {
        "total": total,
        "open": open_count,
        "resolved": resolved
    }


# ================== PUBLIC DISPUTE ACCESS (by token) ==================

@router.get("/public/dispute/{dispute_token}")
async def get_public_dispute_by_token(dispute_token: str):
    """
    Публичный доступ к спору по токену
    Для клиентов мерчанта - без авторизации
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Ищем спор по токену (поддержка public_token и dispute_token)
    dispute = await _db.disputes.find_one(
        {"$or": [{"public_token": dispute_token}, {"dispute_token": dispute_token}]}, 
        {"_id": 0}
    )
    
    if not dispute:
        # Пробуем найти по ID спора напрямую
        dispute = await _db.disputes.find_one({"id": dispute_token}, {"_id": 0})
    
    if not dispute:
        # Пробуем найти в orders
        order = await _db.orders.find_one(
            {"$or": [{"dispute_token": dispute_token}, {"public_token": dispute_token}]}, 
            {"_id": 0}
        )
        if order:
            dispute = await _db.disputes.find_one({"order_id": order["id"]}, {"_id": 0})
        
        if not dispute:
            raise HTTPException(status_code=404, detail="Спор не найден или ссылка недействительна")
    
    # Получаем order
    order = await _db.orders.find_one({"id": dispute.get("order_id")}, {"_id": 0})
    
    # Получаем сообщения
    messages = await _db.dispute_messages.find(
        {"dispute_id": dispute["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    # Формируем безопасный ответ (без sensitive данных)
    return {
        "dispute": {
            "id": dispute["id"],
            "status": dispute.get("status"),
            "reason": dispute.get("reason"),
            "created_at": dispute.get("created_at"),
            "resolved_at": dispute.get("resolved_at"),
            "resolution": dispute.get("resolution"),
            "resolution_comment": dispute.get("resolution_comment")
        },
        "order": {
            "id": order.get("id") if order else None,
            "external_id": order.get("external_id") if order else None,
            "amount_rub": order.get("amount_rub") if order else None,
            "status": order.get("status") if order else None,
            "created_at": order.get("created_at") if order else None
        } if order else None,
        "messages": messages,
        "can_send_message": dispute.get("status") == "open"
    }


@router.post("/public/dispute/{dispute_token}/message")
async def send_public_dispute_message(
    dispute_token: str,
    data: BuyerMessageCreate,
    background_tasks: BackgroundTasks
):
    """
    Отправка сообщения в спор (публичный доступ по токену)
    Для клиентов мерчанта
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Ищем спор (поддержка public_token и dispute_token)
    dispute = await _db.disputes.find_one(
        {"$or": [{"public_token": dispute_token}, {"dispute_token": dispute_token}]}
    )
    if not dispute:
        # Пробуем по ID
        dispute = await _db.disputes.find_one({"id": dispute_token})
    if not dispute:
        order = await _db.orders.find_one(
            {"$or": [{"dispute_token": dispute_token}, {"public_token": dispute_token}]}, 
            {"_id": 0}
        )
        if order:
            dispute = await _db.disputes.find_one({"order_id": order["id"]})
        if not dispute:
            raise HTTPException(status_code=404, detail="Спор не найден")
    
    if dispute.get("status") != "open":
        raise HTTPException(status_code=400, detail="Спор закрыт, отправка сообщений невозможна")
    
    now = datetime.now(timezone.utc).isoformat()
    
    message = {
        "id": generate_id("msg_"),
        "dispute_id": dispute["id"],
        "sender_id": "buyer",
        "sender_role": "buyer",
        "sender_name": data.contact or "Клиент",
        "text": data.text,
        "created_at": now
    }
    
    await _db.dispute_messages.insert_one(message)
    
    # Обновляем время спора
    await _db.disputes.update_one(
        {"id": dispute["id"]},
        {"$set": {"updated_at": now}}
    )
    
    # Уведомляем админов о новом сообщении
    await create_admin_notification(
        title="💬 Новое сообщение в споре",
        message=f"Клиент написал в спор #{dispute['id'][:8]}",
        notification_type="dispute_message",
        link=f"/dispute/{dispute['id']}"
    )
    
    message.pop("_id", None)
    return {"success": True, "message": message}


# ================== DISPUTE CHAT BY ID (для DisputeChat.jsx) ==================

@router.get("/disputes/{dispute_id}/public")
async def get_dispute_public_by_id(dispute_id: str):
    """
    Публичный доступ к спору по ID (для покупателей через параметр ?buyer=true)
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    dispute = await _db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    order = await _db.orders.find_one({"id": dispute.get("order_id")}, {"_id": 0})
    
    messages = await _db.dispute_messages.find(
        {"dispute_id": dispute_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return {
        "dispute": {
            "id": dispute["id"],
            "status": dispute.get("status"),
            "reason": dispute.get("reason"),
            "created_at": dispute.get("created_at"),
            "resolved_at": dispute.get("resolved_at"),
            "resolution": dispute.get("resolution"),
            "buyer_contact": dispute.get("buyer_contact")
        },
        "order": {
            "id": order.get("id") if order else None,
            "external_id": order.get("external_id") if order else None,
            "amount_rub": order.get("amount_rub") if order else None,
            "amount_usdt": order.get("amount_usdt") if order else None,
            "status": order.get("status") if order else None,
            "created_at": order.get("created_at") if order else None
        } if order else None,
        "messages": messages
    }


@router.post("/disputes/{dispute_id}/public/message")
async def send_dispute_message_public(
    dispute_id: str,
    data: BuyerMessageCreate,
    background_tasks: BackgroundTasks
):
    """
    Отправка сообщения покупателем (для DisputeChat с ?buyer=true)
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    dispute = await _db.disputes.find_one({"id": dispute_id})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    if dispute.get("status") not in ["open", "pending_review"]:
        raise HTTPException(status_code=400, detail="Спор закрыт")
    
    now = datetime.now(timezone.utc).isoformat()
    
    message = {
        "id": generate_id("msg_"),
        "dispute_id": dispute_id,
        "sender_id": "buyer",
        "sender_role": "buyer",
        "sender_name": data.contact or "Покупатель",
        "text": data.text,
        "created_at": now
    }
    
    await _db.dispute_messages.insert_one(message)
    
    # Сохраняем контакт покупателя если указан
    if data.contact:
        await _db.disputes.update_one(
            {"id": dispute_id},
            {"$set": {"buyer_contact": data.contact, "updated_at": now}}
        )
    else:
        await _db.disputes.update_one(
            {"id": dispute_id},
            {"$set": {"updated_at": now}}
        )
    
    # Уведомляем
    await create_admin_notification(
        title="💬 Сообщение от покупателя",
        message=f"Новое сообщение в споре #{dispute_id[:12]}",
        notification_type="dispute_message",
        link=f"/dispute/{dispute_id}"
    )
    
    message.pop("_id", None)
    return {"success": True, "message": message}


@router.post("/disputes/{dispute_id}/confirm-payment")
async def confirm_payment_by_trader(
    dispute_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Трейдер подтверждает получение платежа - закрывает спор и завершает сделку
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    dispute = await _db.disputes.find_one({"id": dispute_id})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    # Проверяем что это трейдер данного спора
    if user["role"] not in ["trader", "admin"]:
        raise HTTPException(status_code=403, detail="Только трейдер или админ может подтвердить платёж")
    
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if user["role"] == "trader" and (not trader or trader.get("id") != dispute.get("trader_id")):
        raise HTTPException(status_code=403, detail="Нет доступа к этому спору")
    
    order = await _db.orders.find_one({"id": dispute.get("order_id")}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Получаем трейдера по заказу (если текущий пользователь - админ)
    if user["role"] == "admin":
        trader = await _db.traders.find_one({"id": order.get("trader_id")}, {"_id": 0})
    
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    # Получаем данные для распределения
    merchant = await _db.merchants.find_one({"id": order.get("merchant_id")}, {"_id": 0})
    amount_usdt = order.get("amount_usdt", 0)
    original_amount_rub = order.get("original_amount_rub", order.get("amount_rub", 0))
    
    # Проверяем кошелёк трейдера
    trader_wallet = await _db.wallets.find_one({"user_id": trader["user_id"]})
    locked_amount = trader_wallet.get("locked_balance_usdt", 0) if trader_wallet else 0
    
    # Финансовое распределение
    distribution_done = False
    trader_earns = 0
    merchant_receives = 0
    
    try:
        from financial_logic import calculate_completion_distribution
        
        fee_model = merchant.get("fee_model", "customer_pays") if merchant else "customer_pays"
        merchant_fee_percent = order.get("merchant_fee_percent") or (merchant.get("total_fee_percent", 30.0) if merchant else 30.0)
        
        # Получаем настройки трейдера
        trader_fee_percent = trader.get("fee_percent", trader.get("default_fee_percent", 10.0))
        fee_intervals = trader.get("fee_intervals", [])
        for interval in fee_intervals:
            if interval.get("min_amount", 0) <= original_amount_rub <= interval.get("max_amount", float('inf')):
                trader_fee_percent = interval.get("percent", trader_fee_percent)
                break
        
        # Курс из заказа
        usdt_rate = order.get("exchange_rate")
        if not usdt_rate:
            usdt_rate = await get_current_rate()
        
        marker_rub = order.get("marker", order.get("marker_rub", 0))
        total_amount_rub = order.get("amount_rub", 0)
        
        distribution = calculate_completion_distribution(
            original_amount_rub=original_amount_rub,
            total_amount_rub=total_amount_rub,
            marker_rub=marker_rub,
            merchant_fee_percent=merchant_fee_percent,
            trader_fee_percent=trader_fee_percent,
            fee_model=fee_model,
            usdt_rate=usdt_rate
        )
        
        trader_earns = distribution.trader_earns_usdt
        merchant_receives = distribution.merchant_receives_usdt
        locked_usdt = distribution.trader_locked_released_usdt if hasattr(distribution, 'trader_locked_released_usdt') else amount_usdt
        
        # Обновляем кошелёк трейдера: из locked в earned
        if trader_wallet and locked_amount >= locked_usdt * 0.9:  # Допуск 10% на погрешность округления
            await _db.wallets.update_one(
                {"user_id": trader["user_id"]},
                {
                    "$inc": {
                        "locked_balance_usdt": -locked_usdt,
                        "earned_balance_usdt": trader_earns
                    }
                }
            )
            distribution_done = True
        
        # Обновляем баланс мерчанта
        if merchant and distribution_done:
            await _db.wallets.update_one(
                {"user_id": merchant["user_id"]},
                {"$inc": {"available_balance_usdt": merchant_receives}},
                upsert=True
            )
        
        logger.info(f"Dispute {dispute_id} resolved via financial_logic: trader earns {trader_earns} USDT, merchant {merchant_receives} USDT")
        
    except Exception as e:
        logger.error(f"Financial calculation error for dispute {dispute_id}: {e}")
    
    # Fallback: если distribution не выполнен, делаем простой расчёт
    if not distribution_done and trader_wallet and locked_amount > 0:
        logger.warning(f"Using fallback distribution for dispute {dispute_id}")
        # Простой расчёт: 10% трейдеру, 87% мерчанту, 3% платформе
        trader_earns = round(amount_usdt * 0.10, 4)
        merchant_receives = round(amount_usdt * 0.87, 4)
        
        await _db.wallets.update_one(
            {"user_id": trader["user_id"]},
            {
                "$inc": {
                    "locked_balance_usdt": -amount_usdt,
                    "earned_balance_usdt": trader_earns
                }
            }
        )
        
        if merchant:
            await _db.wallets.update_one(
                {"user_id": merchant["user_id"]},
                {"$inc": {"available_balance_usdt": merchant_receives}},
                upsert=True
            )
        
        distribution_done = True
        logger.info(f"Fallback distribution done: trader {trader_earns}, merchant {merchant_receives}")
    
    # Корректируем микро-остатки в locked_balance
    wallet_check = await _db.wallets.find_one({"user_id": trader["user_id"]}, {"_id": 0, "locked_balance_usdt": 1})
    if wallet_check:
        locked_val = wallet_check.get("locked_balance_usdt", 0)
        if locked_val < 0 or (0 < locked_val < 0.01):
            await _db.wallets.update_one({"user_id": trader["user_id"]}, {"$set": {"locked_balance_usdt": 0}})
    
    # Обновляем статистику трейдера
    if distribution_done:
        await _db.traders.update_one(
            {"id": trader["id"]},
            {
                "$inc": {
                    "total_deals": 1,
                    "successful_deals": 1,
                    "total_volume_rub": original_amount_rub,
                    "total_commission_usdt": trader_earns
                }
            }
        )
    
    # Закрываем спор
    await _db.disputes.update_one(
        {"id": dispute_id},
        {
            "$set": {
                "status": "resolved",
                "resolution": "pay_buyer",
                "resolution_comment": "Трейдер подтвердил получение платежа",
                "resolved_at": now,
                "updated_at": now
            }
        }
    )
    
    # Обновляем заказ
    await _db.orders.update_one(
        {"id": dispute.get("order_id")},
        {"$set": {"status": "completed", "completed_at": now}}
    )
    
    # Обновляем invoice
    await _db.merchant_invoices.update_one(
        {"id": order["id"]},
        {"$set": {"status": "completed", "paid_at": now, "updated_at": now}}
    )
    
    # Системное сообщение
    msg = {
        "id": generate_id("msg_"),
        "dispute_id": dispute_id,
        "sender_id": "system",
        "sender_role": "moderator",
        "sender_name": "Система",
        "text": "✅ Спор закрыт. Трейдер подтвердил получение платежа.",
        "created_at": now
    }
    await _db.dispute_messages.insert_one(msg)
    
    return {"success": True, "message": "Платёж подтверждён, спор закрыт", "distribution_done": distribution_done}


@router.post("/disputes/{dispute_id}/reject-payment")
async def reject_payment_by_trader(
    dispute_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Трейдер отклоняет платёж - эскалирует на модератора
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    dispute = await _db.disputes.find_one({"id": dispute_id})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    if user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Только трейдер")
    
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader or trader.get("id") != dispute.get("trader_id"):
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Эскалируем на модератора
    await _db.disputes.update_one(
        {"id": dispute_id},
        {
            "$set": {
                "status": "pending_review",
                "updated_at": now
            }
        }
    )
    
    # Системное сообщение
    msg = {
        "id": generate_id("msg_"),
        "dispute_id": dispute_id,
        "sender_id": "system",
        "sender_role": "moderator",
        "sender_name": "Система",
        "text": "⚠️ Трейдер сообщает, что платёж не получен. Спор передан модератору на проверку.",
        "created_at": now
    }
    await _db.dispute_messages.insert_one(msg)
    
    # Уведомляем админов
    await create_admin_notification(
        title="⚠️ Спор требует проверки",
        message=f"Трейдер отклонил платёж по спору #{dispute_id[:12]}",
        notification_type="dispute_escalation",
        link=f"/dispute/{dispute_id}"
    )
    
    return {"success": True, "message": "Спор передан модератору"}
