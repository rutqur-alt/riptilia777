"""
BITARBITR P2P Platform - Shop & Payment Router
Handles shop orders and payment processing
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import secrets
import hmac
import hashlib
import logging
import os

router = APIRouter(tags=["Shop & Payment"])
logger = logging.getLogger(__name__)

# Global dependencies
_db = None
_fetch_rate = None
_ws_manager = None
_notify_order_paid = None


def init_router(database, fetch_rate_func=None, ws_manager=None, notify_order_paid_func=None):
    """Initialize router"""
    global _db, _fetch_rate, _ws_manager, _notify_order_paid
    _db = database
    _fetch_rate = fetch_rate_func
    _ws_manager = ws_manager
    _notify_order_paid = notify_order_paid_func


def generate_id(prefix: str = "") -> str:
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"


def verify_hmac_signature(api_key: str, secret_key: str, params: dict, signature: str) -> bool:
    """Verify HMAC-SHA256 signature"""
    if not secret_key:
        return False
    
    sorted_params = sorted(params.items())
    message = "&".join(f"{k}={v}" for k, v in sorted_params if k != "signature")
    
    expected = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected.lower(), signature.lower())


# ================== MODELS ==================

class ShopOrderCreate(BaseModel):
    api_key: str
    amount_rub: float
    description: Optional[str] = ""


class SecureShopOrderCreate(BaseModel):
    api_key: str
    amount_rub: float
    description: Optional[str] = ""
    timestamp: int
    signature: str


# ================== SHOP ENDPOINTS ==================

@router.get("/shop/merchant-info/{api_key}")
async def get_shop_merchant_info(api_key: str):
    """Get merchant info for shop"""
    merchant = await _db.merchants.find_one({"api_key": api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    user = await _db.users.find_one({"id": merchant["user_id"]}, {"_id": 0})
    
    return {
        "merchant_id": merchant["id"],
        "company_name": merchant.get("company_name") or (user.get("nickname") if user else "Shop"),
        "commission_rate": merchant.get("commission_rate", 0.25)
    }


@router.post("/shop/create-order")
async def shop_create_order(data: ShopOrderCreate, background_tasks: BackgroundTasks):
    """Create order from shop"""
    merchant = await _db.merchants.find_one({"api_key": data.api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Invalid API key")
    
    # Get rate
    usdt_rate = 75.0
    if _fetch_rate:
        try:
            usdt_rate = await _fetch_rate()
        except:
            pass
    
    if usdt_rate <= 0:
        raise HTTPException(status_code=500, detail="Cannot get exchange rate")
    
    amount_usdt = round(data.amount_rub / usdt_rate, 2)
    
    order = {
        "id": generate_id("ord"),
        "merchant_id": merchant["id"],
        "trader_id": None,
        "status": "new",
        "amount_rub": data.amount_rub,
        "amount_usdt": amount_usdt,
        "exchange_rate": usdt_rate,
        "description": data.description or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    }
    
    await _db.orders.insert_one(order)
    
    # Update merchant stats
    await _db.merchants.update_one(
        {"id": merchant["id"]},
        {"$inc": {"total_orders": 1}}
    )
    
    return {
        "success": True,
        "order_id": order["id"],
        "amount_rub": order["amount_rub"],
        "amount_usdt": order["amount_usdt"],
        "exchange_rate": usdt_rate,
        "payment_url": f"https://bitarbitr.org/pay/{order['id']}"
    }


@router.post("/shop/create-order-secure")
async def shop_create_order_secure(data: SecureShopOrderCreate, background_tasks: BackgroundTasks):
    """Create order with HMAC-SHA256 verification"""
    merchant = await _db.merchants.find_one({"api_key": data.api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Check timestamp (not older than 5 minutes)
    current_time = int(datetime.now(timezone.utc).timestamp())
    if abs(current_time - data.timestamp) > 300:
        raise HTTPException(status_code=401, detail="Request expired")
    
    # Verify signature
    params = {
        "api_key": data.api_key,
        "amount_rub": data.amount_rub,
        "description": data.description,
        "timestamp": data.timestamp
    }
    
    if not verify_hmac_signature(data.api_key, merchant.get("secret_key", ""), params, data.signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Get rate and create order
    usdt_rate = 75.0
    if _fetch_rate:
        try:
            usdt_rate = await _fetch_rate()
        except:
            pass
    
    amount_usdt = round(data.amount_rub / usdt_rate, 2)
    
    order = {
        "id": generate_id("ord"),
        "merchant_id": merchant["id"],
        "trader_id": None,
        "status": "new",
        "amount_rub": data.amount_rub,
        "amount_usdt": amount_usdt,
        "exchange_rate": usdt_rate,
        "description": data.description or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "is_secure": True
    }
    
    await _db.orders.insert_one(order)
    
    return {
        "success": True,
        "order_id": order["id"],
        "amount_rub": order["amount_rub"],
        "amount_usdt": order["amount_usdt"],
        "exchange_rate": usdt_rate
    }


# ================== PAYMENT ENDPOINTS ==================

@router.get("/pay/{order_id}")
async def get_payment_info(order_id: str):
    """Get payment information for order"""
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Реквизиты уже сохранены в заказе когда трейдер его принял
    payment_details = order.get("payment_details")
    
    # Если реквизиты ещё не в заказе, попробуем найти по trader_id
    if not payment_details and order.get("trader_id"):
        trader = await _db.traders.find_one({"id": order["trader_id"]}, {"_id": 0})
        if trader:
            # Получаем реквизиты трейдера по ID который был использован
            detail_id = order.get("payment_details_id")
            if detail_id:
                details = await _db.payment_details.find_one(
                    {"id": detail_id},
                    {"_id": 0}
                )
            else:
                # Fallback - первый активный реквизит нужного типа
                payment_method = order.get("requested_payment_method") or order.get("payment_method")
                details = await _db.payment_details.find_one(
                    {
                        "trader_id": order["trader_id"], 
                        "is_active": True,
                        "payment_type": payment_method
                    },
                    {"_id": 0}
                )
            
            if details:
                payment_details = {
                    "type": details.get("payment_type") or details.get("type"),
                    "card_number": details.get("card_number"),
                    "bank_name": details.get("bank_name"),
                    "holder_name": details.get("holder_name"),
                    "phone_number": details.get("phone_number"),
                    "manual_text": details.get("manual_text"),
                    "qr_data": details.get("qr_data"),
                    "operator_name": details.get("operator_name"),
                    "account_number": details.get("account_number"),
                    "recipient_name": details.get("recipient_name")
                }
    
    return {
        "order": order,
        "payment_details": payment_details
    }


@router.post("/pay/{order_id}/confirm")
async def confirm_payment(order_id: str):
    """Buyer confirms payment was sent"""
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order["status"] not in ["new", "pending", "waiting_buyer_confirmation"]:
        raise HTTPException(status_code=400, detail=f"Cannot confirm order in status: {order['status']}")
    
    # Статус меняется на waiting_trader_confirmation - ждём подтверждения от трейдера
    await _db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "waiting_trader_confirmation",
            "buyer_confirmed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Уведомляем трейдера что покупатель оплатил
    if _notify_order_paid:
        order["status"] = "waiting_trader_confirmation"
        import asyncio
        asyncio.create_task(_notify_order_paid(order))
    
    return {"success": True, "message": "Payment confirmed"}


@router.post("/pay/{order_id}/cancel")
async def cancel_payment(order_id: str):
    """Cancel order - buyer can cancel at any time except final statuses"""
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Нельзя отменить только финальные статусы
    final_statuses = ["completed", "cancelled", "failed", "expired"]
    if order["status"] in final_statuses:
        raise HTTPException(status_code=400, detail=f"Cannot cancel order in status: {order['status']}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Если заказ уже взят трейдером - нужно разморозить USDT
    if order.get("trader_id"):
        trader = await _db.traders.find_one({"id": order["trader_id"]}, {"_id": 0})
        if trader:
            amount_usdt = order.get("amount_usdt", 0)
            try:
                wallet = await _db.wallets.find_one({"user_id": trader["user_id"]})
                if wallet and amount_usdt > 0:
                    await _db.wallets.update_one(
                        {"user_id": trader["user_id"]},
                        {
                            "$inc": {
                                "available_balance_usdt": round(amount_usdt, 4),
                                "locked_balance_usdt": -round(amount_usdt, 4)
                            }
                        }
                    )
                    # Исправляем микро-остатки
                    wallet_check = await _db.wallets.find_one({"user_id": trader["user_id"]}, {"_id": 0, "locked_balance_usdt": 1})
                    if wallet_check:
                        locked_val = wallet_check.get("locked_balance_usdt", 0)
                        if locked_val < 0 or (0 < locked_val < 0.01):
                            await _db.wallets.update_one({"user_id": trader["user_id"]}, {"$set": {"locked_balance_usdt": 0}})
                    logger.info(f"✅ Returned {amount_usdt} USDT to trader {trader['id']} after buyer cancel")
            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to unfreeze {amount_usdt} USDT for trader {trader['id']} on cancel order {order_id}: {e}")
    
    await _db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now,
            "cancelled_by": "buyer"
        }}
    )
    
    # Отправляем webhook мерчанту
    from routers.invoice_api import send_webhook_notification
    import asyncio
    asyncio.create_task(send_webhook_notification(order_id, "cancelled", {
        "cancelled_by": "buyer"
    }))
    
    return {"success": True, "message": "Order cancelled"}


@router.post("/pay/{order_id}/dispute")
async def create_payment_dispute(
    order_id: str,
    reason: str = ""
):
    """Create dispute for order - only available 10 minutes after payment confirmation"""
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Проверяем что покупатель подтвердил оплату
    buyer_confirmed_at = order.get("buyer_confirmed_at")
    if not buyer_confirmed_at:
        raise HTTPException(
            status_code=400, 
            detail="Спор можно открыть только после подтверждения оплаты"
        )
    
    # Проверяем что прошло минимум 10 минут
    confirmed_time = datetime.fromisoformat(buyer_confirmed_at.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    minutes_passed = (now - confirmed_time).total_seconds() / 60
    
    if minutes_passed < 10:
        remaining = int(10 - minutes_passed)
        raise HTTPException(
            status_code=400, 
            detail=f"Спор можно открыть через {remaining} мин. Подождите, возможно трейдер ещё проверяет оплату."
        )
    
    # Check if dispute already exists
    existing = await _db.disputes.find_one({"order_id": order_id}, {"_id": 0})
    if existing:
        return {"success": True, "dispute_id": existing["id"], "public_token": existing.get("public_token"), "message": "Dispute already exists"}
    
    # Generate public token
    public_token = secrets.token_urlsafe(32)
    
    # Get short order ID for display
    short_order_id = order_id.split('_')[-1] if '_' in order_id else order_id[-6:]
    
    dispute = {
        "id": generate_id("DSP-"),
        "order_id": order_id,
        "merchant_id": order.get("merchant_id"),
        "trader_id": order.get("trader_id"),
        "status": "open",
        "reason": reason or "Покупатель открыл спор",
        "public_token": public_token,
        "initiated_by": "buyer",
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await _db.disputes.insert_one(dispute)
    
    # Update order
    await _db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "disputed", 
            "dispute_id": dispute["id"],
            "disputed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Create auto-message with dispute link
    # Используем SITE_URL или REACT_APP_BACKEND_URL
    site_url = os.environ.get("SITE_URL", "")
    if not site_url:
        backend_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        if "/api" in backend_url:
            site_url = backend_url.replace("/api", "")
        else:
            site_url = backend_url
    
    dispute_link = f"{site_url}/dispute/{public_token}?buyer=true"
    
    auto_message = {
        "id": generate_id("MSG-"),
        "dispute_id": dispute["id"],
        "sender_role": "admin",
        "sender_id": "system",
        "sender_name": "Система",
        "text": f"📋 Спор по заказу #{short_order_id} открыт.\n\n🔗 Ссылка на чат спора:\n{dispute_link}",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await _db.dispute_messages.insert_one(auto_message)
    
    # Отправляем webhook мерчанту
    from routers.invoice_api import send_webhook_notification
    import asyncio
    asyncio.create_task(send_webhook_notification(order_id, "dispute", {
        "dispute_url": f"{site_url}/dispute/{public_token}",
        "reason": reason or "Покупатель открыл спор"
    }))
    
    return {
        "success": True,
        "dispute_id": dispute["id"],
        "public_token": public_token,
        "dispute_url": f"/dispute/{public_token}?buyer=true"
    }



@router.post("/pay/{order_id}/cancel-dispute")
async def cancel_dispute_by_buyer(order_id: str):
    """
    Покупатель отменяет спор.
    USDT возвращается трейдеру, заказ отменяется.
    Покупатель больше не сможет открыть спор по этому заказу.
    """
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if order.get("status") != "disputed":
        raise HTTPException(status_code=400, detail="Заказ не в статусе спора")
    
    # Получаем спор
    dispute = await _db.disputes.find_one({"order_id": order_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    # Получаем трейдера
    trader = await _db.traders.find_one({"id": order.get("trader_id")}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    # Возвращаем USDT трейдеру из locked в available через коллекцию wallets
    amount_usdt = order.get("amount_usdt", 0)
    
    await _db.wallets.update_one(
        {"user_id": trader.get("user_id")},
        {"$inc": {
            "locked_balance_usdt": -round(amount_usdt, 4),
            "available_balance_usdt": round(amount_usdt, 4)
        }}
    )
    
    # Очищаем микро-остатки в locked
    wallet_check = await _db.wallets.find_one(
        {"user_id": trader.get("user_id")}, 
        {"_id": 0, "locked_balance_usdt": 1}
    )
    if wallet_check:
        locked_val = wallet_check.get("locked_balance_usdt", 0)
        if locked_val < 0 or (0 < locked_val < 0.01):
            await _db.wallets.update_one(
                {"user_id": trader.get("user_id")},
                {"$set": {"locked_balance_usdt": 0}}
            )
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Обновляем статус заказа - помечаем что спор нельзя открыть снова
    await _db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now,
            "cancelled_by": "buyer",
            "dispute_cancelled": True,
            "can_open_dispute": False  # Больше нельзя открыть спор
        }}
    )
    
    # Закрываем спор
    await _db.disputes.update_one(
        {"id": dispute["id"]},
        {"$set": {
            "status": "cancelled",
            "resolution": "cancelled_by_buyer",
            "resolution_comment": "Покупатель отменил спор",
            "resolved_at": now
        }}
    )
    
    # Добавляем системное сообщение
    short_order_id = order_id.split('_')[-1] if '_' in order_id else order_id[-6:]
    system_message = {
        "id": f"MSG-{secrets.token_hex(8).upper()}",
        "dispute_id": dispute["id"],
        "sender_role": "admin",
        "sender_id": "system",
        "sender_name": "Система",
        "text": f"❌ Спор по заказу #{short_order_id} отменён покупателем.\n\nСредства ({amount_usdt:.2f} USDT) возвращены трейдеру.",
        "created_at": now
    }
    await _db.dispute_messages.insert_one(system_message)
    
    logger.info(f"Dispute {dispute['id']} cancelled by buyer for order {order_id}. Returned {amount_usdt} USDT to trader {trader['id']}")
    
    return {
        "success": True,
        "message": "Спор отменён. Средства возвращены трейдеру."
    }


# ==================== DEMO CALLBACK ENDPOINT ====================

class DemoCallbackData(BaseModel):
    """Webhook callback data from demo/testing"""
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[float] = None
    amount_usdt: Optional[float] = None
    timestamp: Optional[str] = None
    sign: Optional[str] = None
    # Allow any extra fields
    class Config:
        extra = "allow"


@router.post("/demo/callback")
async def demo_callback(data: DemoCallbackData):
    """
    Demo callback endpoint for testing webhooks from DemoShop.
    This endpoint accepts webhook notifications and simply acknowledges them.
    Used for testing integration without a real merchant backend.
    """
    logger.info(f"Demo callback received: order_id={data.order_id}, status={data.status}")
    
    # Simply acknowledge the callback
    return {
        "status": "ok",
        "message": "Demo callback received",
        "received_data": {
            "order_id": data.order_id,
            "payment_id": data.payment_id,
            "status": data.status
        }
    }

