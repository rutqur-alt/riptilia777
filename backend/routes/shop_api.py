"""
Shop API - endpoints для демо-магазина и внешней интеграции
Обработка заказов и страницы оплаты
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from core.database import db
import secrets
import os

router = APIRouter(prefix="/shop", tags=["Shop API"])


def generate_id(prefix: str = "") -> str:
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"


@router.get("/merchant-info/{api_key}")
async def get_merchant_info_by_api_key(api_key: str):
    """
    Получить информацию о мерчанте по API ключу.
    Используется демо-магазином для проверки подключения.
    """
    merchant = await db.merchants.find_one({"api_key": api_key}, {"_id": 0})
    
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    if merchant.get("status") != "active":
        raise HTTPException(status_code=403, detail={
            "status": "error",
            "code": "MERCHANT_NOT_ACTIVE",
            "message": "Мерчант не активирован"
        })
    
    # Count completed transactions
    total_txs = await db.merchant_invoices.count_documents({"merchant_id": merchant["id"], "status": "completed"})
    
    # Sum what merchant ACTUALLY RECEIVED (after commission deduction)
    # Use trades collection where merchant_receives_rub is calculated
    pipeline = [
        {'$match': {'merchant_id': merchant['id'], 'status': 'completed'}},
        {'$group': {'_id': None, 'total_rub': {'$sum': '$merchant_receives_rub'}}}
    ]
    agg = await db.trades.aggregate(pipeline).to_list(1)
    
    # Баланс в РУБЛЯХ - реально полученная сумма после вычета комиссии
    balance_rub = agg[0].get('total_rub', 0) if agg else 0
    balance_rub = balance_rub or 0
    
    return {
        "merchant_id": merchant["id"],
        "company_name": merchant.get("merchant_name") or merchant.get("login", "Мерчант"),
        "status": merchant.get("status"),
        "fee_model": "merchant_pays",
        "commission_rate": merchant.get("commission_rate", 3.0),
        "balance_rub": round(balance_rub, 2),  # БАЛАНС В РУБЛЯХ
        "total_transactions": total_txs
    }


# ================== PAYMENT PAGE ENDPOINTS ==================

@router.get("/pay/{order_id}")
async def get_payment_info(order_id: str):
    """
    Получить информацию о заказе для страницы оплаты.
    Возвращает данные заказа и реквизиты (если трейдер уже принял).
    """
    # Сначала ищем в merchant_invoices (Invoice API)
    order = await db.merchant_invoices.find_one({"id": order_id}, {"_id": 0})
    
    # Если не найдено, ищем в payment_links
    if not order:
        order = await db.payment_links.find_one({"id": order_id}, {"_id": 0})
    
    # Также проверяем trades
    if not order:
        order = await db.trades.find_one({"id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Получаем реквизиты если есть trader_id
    payment_details = order.get("payment_details")
    
    if not payment_details and order.get("trader_id"):
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0})
        if trader:
            # Ищем реквизиты трейдера
            payment_method = order.get("requested_payment_method") or order.get("payment_method", "card")
            
            # Проверяем есть ли у трейдера оффер с этим методом
            offer = await db.offers.find_one({
                "trader_id": order["trader_id"],
                "status": "active",
                "payment_methods": payment_method
            }, {"_id": 0})
            
            if offer and offer.get("payment_details"):
                details = offer["payment_details"].get(payment_method, {})
                payment_details = {
                    "type": payment_method,
                    "card_number": details.get("card_number"),
                    "bank_name": details.get("bank"),
                    "holder_name": details.get("holder"),
                    "phone_number": details.get("phone")
                }
    
    return {
        "order": order,
        "payment_details": payment_details
    }


@router.post("/pay/{order_id}/confirm")
async def confirm_payment(order_id: str):
    """
    Покупатель подтверждает что оплатил.
    """
    order = await db.merchant_invoices.find_one({"id": order_id}, {"_id": 0})
    if not order:
        order = await db.trades.find_one({"id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Обновляем статус
    now = datetime.now(timezone.utc).isoformat()
    
    # Определяем коллекцию
    collection = db.merchant_invoices if await db.merchant_invoices.find_one({"id": order_id}) else db.trades
    
    await collection.update_one(
        {"id": order_id},
        {"$set": {
            "status": "waiting_trader_confirmation",
            "buyer_confirmed_at": now
        }}
    )
    
    return {"success": True, "message": "Оплата подтверждена. Ожидайте проверки трейдером."}


@router.post("/pay/{order_id}/cancel")
async def cancel_payment(order_id: str):
    """
    Покупатель отменяет заказ.
    """
    order = await db.merchant_invoices.find_one({"id": order_id}, {"_id": 0})
    if not order:
        order = await db.trades.find_one({"id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    final_statuses = ["completed", "cancelled", "failed", "expired"]
    if order.get("status") in final_statuses:
        raise HTTPException(status_code=400, detail=f"Нельзя отменить заказ в статусе: {order['status']}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Определяем коллекцию
    collection = db.merchant_invoices if await db.merchant_invoices.find_one({"id": order_id}) else db.trades
    
    # Если есть замороженные USDT у трейдера - размораживаем
    if order.get("trader_id"):
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0})
        if trader:
            amount_usdt = order.get("amount_usdt", 0)
            if amount_usdt > 0:
                await db.traders.update_one(
                    {"id": order["trader_id"]},
                    {"$inc": {
                        "balance_usdt": amount_usdt,
                        "frozen_usdt": -amount_usdt
                    }}
                )
    
    await collection.update_one(
        {"id": order_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now,
            "cancelled_by": "buyer"
        }}
    )
    
    return {"success": True, "message": "Заказ отменён"}


@router.post("/pay/{order_id}/dispute")
async def create_payment_dispute(order_id: str, reason: str = ""):
    """
    Создать спор по заказу (доступно через 10 минут после подтверждения оплаты).
    """
    order = await db.merchant_invoices.find_one({"id": order_id}, {"_id": 0})
    if not order:
        order = await db.trades.find_one({"id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    buyer_confirmed_at = order.get("buyer_confirmed_at")
    if not buyer_confirmed_at:
        raise HTTPException(status_code=400, detail="Спор можно открыть только после подтверждения оплаты")
    
    # Проверяем что прошло 10 минут
    confirmed_time = datetime.fromisoformat(buyer_confirmed_at.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    minutes_passed = (now - confirmed_time).total_seconds() / 60
    
    if minutes_passed < 10:
        remaining = int(10 - minutes_passed)
        raise HTTPException(
            status_code=400,
            detail=f"Спор можно открыть через {remaining} мин. Подождите, возможно трейдер ещё проверяет оплату."
        )
    
    # Генерируем публичный токен
    public_token = secrets.token_urlsafe(32)
    
    dispute = {
        "id": generate_id("DSP-"),
        "order_id": order_id,
        "merchant_id": order.get("merchant_id"),
        "trader_id": order.get("trader_id"),
        "status": "open",
        "reason": reason or "Покупатель открыл спор",
        "public_token": public_token,
        "initiated_by": "buyer",
        "created_at": now.isoformat()
    }
    
    await db.disputes.insert_one(dispute)
    
    # Обновляем заказ
    collection = db.merchant_invoices if await db.merchant_invoices.find_one({"id": order_id}) else db.trades
    
    await collection.update_one(
        {"id": order_id},
        {"$set": {
            "status": "disputed",
            "dispute_id": dispute["id"],
            "disputed_at": now.isoformat()
        }}
    )
    
    return {
        "success": True,
        "dispute_id": dispute["id"],
        "public_token": public_token,
        "message": "Спор открыт. Модератор рассмотрит вашу ситуацию."
    }


# ================== QUICK TEST PAYMENT ==================

class QuickPaymentCreate(BaseModel):
    amount_rub: int
    description: Optional[str] = "Пополнение баланса"
    merchant_api_key: Optional[str] = None


@router.post("/quick-payment")
async def create_quick_payment(data: QuickPaymentCreate):
    """
    Создать платёж для пополнения баланса мерчанта.
    Если передан merchant_api_key - привязывается к реальному мерчанту.
    """
    merchant_id = "test_merchant"
    merchant_name = "Тестовый магазин"
    
    # If merchant_api_key provided, link to real merchant
    if data.merchant_api_key:
        merchant = await db.merchants.find_one({"api_key": data.merchant_api_key}, {"_id": 0})
        if merchant:
            merchant_id = merchant["id"]
            merchant_name = merchant.get("merchant_name") or merchant.get("login", "Мерчант")
    
    # Генерируем ID платежа
    invoice_id = f"INV_{datetime.now(timezone.utc).strftime('%H%M%S')}_{secrets.token_hex(3).upper()}"
    
    # Получаем базовый курс из payout_settings (Rapira API)
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    exchange_rate = payout_settings.get("base_rate", 78.0) if payout_settings else 78.0
    if not exchange_rate or exchange_rate <= 0:
        comm_settings = await db.commission_settings.find_one({}, {"_id": 0})
        exchange_rate = comm_settings.get("default_price_rub", 78.0) if comm_settings else 78.0
    
    amount_usdt = round(data.amount_rub / exchange_rate, 2)
    
    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    
    # Создаём payment link
    payment_link = {
        'id': invoice_id,
        'merchant_id': merchant_id,
        'merchant_name': merchant_name,
        'amount_usdt': amount_usdt,
        'amount_rub': data.amount_rub,
        'currency': 'RUB',
        'description': data.description,
        'status': 'pending',
        'created_at': now,
        'expires_at': expires
    }
    
    await db.payment_links.insert_one(payment_link)
    
    return {
        "status": "success",
        "invoice_id": invoice_id,
        "amount_rub": data.amount_rub,
        "amount_usdt": amount_usdt,
        "payment_url": f"/select-operator/{invoice_id}"
    }


# ================== DEMO CALLBACK ENDPOINT ==================

class DemoCallbackData(BaseModel):
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[float] = None
    amount_usdt: Optional[float] = None
    timestamp: Optional[str] = None
    sign: Optional[str] = None
    
    class Config:
        extra = "allow"


@router.post("/demo/callback")
async def demo_callback(data: DemoCallbackData):
    """
    Demo callback endpoint для тестирования webhooks.
    """
    return {
        "status": "ok",
        "message": "Demo callback received",
        "received_data": {
            "order_id": data.order_id,
            "payment_id": data.payment_id,
            "status": data.status
        }
    }
