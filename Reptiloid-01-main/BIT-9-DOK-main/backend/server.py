from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect, BackgroundTasks, Body, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import secrets
import bcrypt
from jose import jwt, JWTError
import httpx
import httpcore
import asyncio
import json
import pyotp
import qrcode
import io
import base64
import random
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import routers
from routers.notifications import router as notifications_router, init_router as init_notifications
from routers.tickets import router as tickets_router, init_router as init_tickets
from routers.disputes import router as disputes_router, init_router as init_disputes
from routers.auth import router as auth_router, init_router as init_auth
from routers.trader import router as trader_router, init_router as init_trader
from routers.merchant import router as merchant_router, init_router as init_merchant
from routers.invoice_api import router as invoice_router, init_router as init_invoice
from routers.wallet import router as wallet_router, init_router as init_wallet
from routers.rates import router as rates_router
from routers.admin import router as admin_router, init_router as init_admin
from routers.usdt import router as usdt_router, init_router as init_usdt
from routers.shop import router as shop_router, init_router as init_shop

# Optional casino module
try:
    from test_casino import router as casino_router, init_casino_db
    CASINO_AVAILABLE = True
except ImportError:
    CASINO_AVAILABLE = False
    casino_router = None

# TON SDK для реальных транзакций
try:
    from tonutils.client import TonapiClient
    from tonutils.wallet import WalletV4R2
    from tonutils.jetton import JettonMasterStandard, JettonWalletStandard
    from tonsdk.utils import to_nano, from_nano
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    TON_SDK_AVAILABLE = True
    logging.info("TON SDK loaded successfully")
except ImportError as e:
    TON_SDK_AVAILABLE = False
    logging.warning(f"TON SDK not available - auto-withdraw will be limited: {e}")

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=False)

# MongoDB connection - с настройками для Atlas
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')

# Настройки для MongoDB Atlas (улучшенная устойчивость к сетевым проблемам)
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=30000,  # 30 секунд на выбор сервера
    connectTimeoutMS=20000,  # 20 секунд на подключение
    socketTimeoutMS=30000,  # 30 секунд на операции
    retryWrites=True,
    retryReads=True,
    maxPoolSize=50,
    minPoolSize=5,
    maxIdleTimeMS=60000,
    directConnection=False,  # Важно для replica set
    w='majority',  # Write concern для надёжности
)
db = client[os.environ.get('DB_NAME', 'bitarbitr')]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 168  # 7 days - longer session for better UX

# CAPTCHA Secret for challenge generation
CAPTCHA_SECRET = os.environ.get('CAPTCHA_SECRET', secrets.token_hex(32))

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ADMIN_CHAT_ID = os.environ.get('TELEGRAM_ADMIN_CHAT_ID', '')

# Site URL for notifications
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:3000')

# ================== TON / USDT CONFIGURATION ==================
# TON Center API for USDT transactions
TONCENTER_API_KEY = os.environ.get('TONCENTER_API_KEY', '')
TONCENTER_API_URL = "https://toncenter.com/api/v2"

# Platform TON wallet address
PLATFORM_TON_ADDRESS = os.environ.get('PLATFORM_TON_ADDRESS', '')

# USDT Jetton contract on TON
USDT_JETTON_CONTRACT = os.environ.get('USDT_JETTON_CONTRACT', '')

# USDT withdrawal settings
USDT_WITHDRAWAL_FEE_PERCENT = 0.0  # Без комиссии платформы
USDT_WITHDRAWAL_MIN_FEE = 0.0  # Без минимальной комиссии
USDT_NETWORK_FEE = 0.0  # Без комиссии сети (пока)
USDT_MIN_DEPOSIT = 0.0  # Без ограничения - пополнение от любой суммы
USDT_MIN_WITHDRAWAL = 0.0  # Без ограничения на минимальный вывод
USDT_CONFIRMATIONS_REQUIRED = 1  # 1 подтверждение достаточно в TON

# Кэш настроек платформы
platform_settings_cache = {
    "settings": None,
    "updated_at": None
}

async def get_platform_usdt_settings():
    """Получить настройки USDT/TON платформы из БД с кэшированием"""
    global platform_settings_cache
    
    # Проверяем кэш (обновляем каждые 30 секунд)
    if platform_settings_cache["settings"] and platform_settings_cache["updated_at"]:
        cache_age = (datetime.now(timezone.utc) - platform_settings_cache["updated_at"]).seconds
        # Проверяем что кэшированные данные валидны (есть API ключ)
        if cache_age < 30 and platform_settings_cache["settings"].get("toncenter_api_key"):
            return platform_settings_cache["settings"]
    
    settings = await db.platform_settings.find_one({"type": "usdt_ton"}, {"_id": 0})
    
    # Проверяем настройки автовывода для адреса кошелька и API ключа
    auto_withdraw_config = await db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
    
    if settings:
        # Если есть настроенный кошелёк автовывода - используем его для депозитов тоже
        if auto_withdraw_config:
            if auto_withdraw_config.get("wallet_address"):
                settings["platform_ton_address"] = auto_withdraw_config["wallet_address"]
            if auto_withdraw_config.get("toncenter_api_key"):
                settings["toncenter_api_key"] = auto_withdraw_config["toncenter_api_key"]
        platform_settings_cache["settings"] = settings
        platform_settings_cache["updated_at"] = datetime.now(timezone.utc)
        return settings
    
    # Возвращаем дефолтные настройки
    default_settings = {
        "platform_ton_address": PLATFORM_TON_ADDRESS,
        "toncenter_api_key": TONCENTER_API_KEY,
        "usdt_jetton_contract": USDT_JETTON_CONTRACT,
        "withdrawal_fee_percent": USDT_WITHDRAWAL_FEE_PERCENT * 100,
        "withdrawal_min_fee": USDT_WITHDRAWAL_MIN_FEE,
        "network_fee": USDT_NETWORK_FEE,
        "min_deposit": USDT_MIN_DEPOSIT,
        "min_withdrawal": USDT_MIN_WITHDRAWAL,
        "confirmations_required": USDT_CONFIRMATIONS_REQUIRED
    }
    
    # Если есть настроенный кошелёк автовывода - используем его
    if auto_withdraw_config:
        if auto_withdraw_config.get("wallet_address"):
            default_settings["platform_ton_address"] = auto_withdraw_config["wallet_address"]
        if auto_withdraw_config.get("toncenter_api_key"):
            default_settings["toncenter_api_key"] = auto_withdraw_config["toncenter_api_key"]
    
    # Cache the default settings too
    platform_settings_cache["settings"] = default_settings
    platform_settings_cache["updated_at"] = datetime.now(timezone.utc)
    
    return default_settings

# Commission settings - теперь индивидуальные для каждого пользователя
# Значения по умолчанию (будут перезаписаны из БД)
DEFAULT_TRADER_COMMISSION = 0.10  # 10% по умолчанию для трейдера
DEFAULT_MERCHANT_COMMISSION = 0.25  # 25% по умолчанию для мерчанта (включает 10% трейдера + 15% платформы)

# Deposit request settings
DEPOSIT_REQUEST_EXPIRY_MINUTES = 120  # 2 часа

# Кэш курса USDT/RUB (обновляется каждые 20 секунд с Rapira)
usdt_rate_cache = {
    "rate": 94.0,  # Fallback курс 1 USDT ≈ 94 RUB (близко к реальному)
    "updated_at": None,
    "source": "fallback"
}

async def fetch_usdt_rub_rate():
    """Получить актуальный курс USDT/RUB из единственного источника - Rapira Exchange"""
    global usdt_rate_cache
    
    # Проверяем кэш (20 секунд)
    if usdt_rate_cache["updated_at"]:
        diff = (datetime.now(timezone.utc) - usdt_rate_cache["updated_at"]).seconds
        if diff < 20:
            return usdt_rate_cache["rate"]
    
    # Единственный источник - Rapira Exchange
    try:
        rate, source = await fetch_rate_rapira()
        if rate and rate > 0:
            usdt_rate_cache["rate"] = round(rate, 2)
            usdt_rate_cache["updated_at"] = datetime.now(timezone.utc)
            usdt_rate_cache["source"] = source
            logger.info(f"USDT/RUB rate updated: {usdt_rate_cache['rate']} (source: {source})")
            return usdt_rate_cache["rate"]
    except Exception as e:
        logger.warning(f"Rapira rate source failed: {e}")
    
    # Fallback только на кэш, НЕ на другие источники
    return usdt_rate_cache["rate"]

async def fetch_rate_rapira():
    """Получить курс USDT/RUB через Rapira Exchange API (единственный источник)
    
    API: GET https://api.rapira.net/open/market/rates
    - Публичный, бесплатный, без API-ключа
    - Лимиты: 5 req/sec, 100 req/min
    - Используем mid price = (askPrice + bidPrice) / 2
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://api.rapira.net/open/market/rates",
            headers={"Accept": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            rates_list = data.get("data", [])
            
            # Ищем USDT/RUB пару
            for pair in rates_list:
                symbol = pair.get("symbol", "")
                if symbol == "USDT/RUB":
                    ask_price = pair.get("askPrice")
                    bid_price = pair.get("bidPrice")
                    
                    # Mid price - наиболее справедливый курс
                    if ask_price and bid_price:
                        mid_price = (float(ask_price) + float(bid_price)) / 2
                        return mid_price, "rapira"
                    
                    # Если нет ask/bid - используем close
                    close_price = pair.get("close")
                    if close_price:
                        return float(close_price), "rapira"
            
            logger.warning("USDT/RUB pair not found in Rapira response")
    return None, None

# ================== TELEGRAM NOTIFICATIONS SYSTEM ==================

async def send_telegram_message(chat_id: str, message: str, bot_token: str = None):
    """Low-level function to send Telegram message"""
    token = bot_token or TELEGRAM_BOT_TOKEN
    if not token:
        return False
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
            )
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram API error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.warning(f"Failed to send Telegram message: {e}")
    return False

async def send_telegram_to_admin(message: str):
    """Отправить уведомление админу в Telegram"""
    if not TELEGRAM_ADMIN_CHAT_ID:
        return False
    return await send_telegram_message(TELEGRAM_ADMIN_CHAT_ID, message)

async def send_telegram_notification(user_id: str, message: str, notification_type: str = "general"):
    """Отправить уведомление пользователю через Telegram"""
    try:
        # Сначала пробуем настройки из БД (type: "telegram")
        settings = await db.platform_settings.find_one({"type": "telegram"}, {"_id": 0})
        bot_token = settings.get("bot_token") if settings and settings.get("enabled") else None
        
        # Если нет в БД, используем env переменную
        if not bot_token:
            bot_token = TELEGRAM_BOT_TOKEN
        
        if not bot_token:
            return False
        
        # Получаем telegram_id пользователя
        user = await db.users.find_one({"id": user_id}, {"telegram_id": 1})
        if not user or not user.get("telegram_id"):
            return False
        
        result = await send_telegram_message(user["telegram_id"], message, bot_token)
        if result:
            logger.info(f"Telegram notification sent to user {user_id}")
        return result
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")
    return False

async def create_user_notification(user_id: str, title: str, message: str, notification_type: str = "info", link: str = None):
    """Создать уведомление для пользователя и отправить в Telegram"""
    notification = {
        "id": generate_id("untf"),
        "user_id": user_id,
        "title": title,
        "message": message,
        "type": notification_type,
        "link": link,
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_notifications.insert_one(notification)
    
    # Отправляем через WebSocket
    await manager.send_to_user(user_id, {
        "event": "notification",
        "notification": notification
    })
    
    # Отправляем в Telegram
    telegram_msg = f"🔔 <b>{title}</b>\n\n{message}"
    await send_telegram_notification(user_id, telegram_msg, notification_type)
    
    return notification

async def notify_new_order(order: dict):
    """Уведомление о новом заказе"""
    logger.info(f"notify_new_order called for order {order.get('id')}, trader_id={order.get('trader_id')}")
    
    # Если заказ ещё не назначен трейдеру - уведомляем ВСЕХ доступных трейдеров
    if not order.get("trader_id"):
        logger.info("Order has no trader - broadcasting to all available traders")
        
        # Получаем всех доступных трейдеров
        available_traders = await db.traders.find({"is_available": True}, {"_id": 0, "id": 1, "user_id": 1}).to_list(100)
        logger.info(f"Found {len(available_traders)} available traders")
        
        for trader in available_traders:
            trader_user_id = trader["user_id"]
            
            # Колокольчик
            await db.user_notifications.insert_one({
                "id": generate_id("unot"),
                "user_id": trader_user_id,
                "type": "new_order_available",
                "title": "🆕 Новая заявка доступна",
                "message": f"Заявка на {order['amount_rub']:.2f} ₽ ожидает трейдера",
                "link": "/trader/workspace",
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Telegram
            msg = f"""🆕 <b>Новая заявка доступна!</b>

💰 Сумма: <b>{order['amount_rub']:.2f} ₽</b>
💵 USDT: <b>{order['amount_usdt']:.4f}</b>
💳 Метод: {order.get('requested_payment_method', 'Любой')}

⚡ Возьмите заявку в работу!
🔗 <a href="{SITE_URL}/trader/workspace">Открыть</a>"""
            await send_telegram_notification(trader_user_id, msg, "new_order")
        
        # WebSocket broadcast
        try:
            await manager.broadcast({
                "type": "new_order_available",
                "order_id": order["id"],
                "amount_rub": order["amount_rub"],
                "amount_usdt": order["amount_usdt"],
                "payment_method": order.get("requested_payment_method")
            })
            logger.info("WebSocket broadcast sent for new order")
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed: {ws_err}")
    
    # Уведомляем конкретного трейдера (если назначен) - колокольчик + telegram
    elif order.get("trader_id"):
        # Получаем user_id трейдера
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0, "user_id": 1})
        if trader:
            trader_user_id = trader["user_id"]
            
            # Колокольчик
            await db.user_notifications.insert_one({
                "id": generate_id("unot"),
                "user_id": trader_user_id,
                "type": "new_order",
                "title": "🆕 Новый заказ",
                "message": f"Заказ #{order['id'][-8:]}, {order['amount_rub']:.2f} ₽ - ожидает подтверждения",
                "link": "/trader/workspace",
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Telegram
            msg = f"""🆕 <b>Новый заказ #{order['id'][-8:]}</b>

💰 Сумма: <b>{order['amount_rub']:.2f} ₽</b>
💵 USDT: <b>{order['amount_usdt']:.4f}</b>

⏰ Ожидает вашего подтверждения!
🔗 <a href="{SITE_URL}/trader/orders">Открыть</a>"""
            await send_telegram_notification(trader_user_id, msg, "new_order")
    
    # Уведомляем главного админа через TELEGRAM_ADMIN_CHAT_ID
    admin_msg = f"""📋 <b>Новый заказ в системе</b>

🆔 ID: #{order['id'][-8:]}
💰 Сумма: {order['amount_rub']:.2f} ₽
💵 USDT: {order['amount_usdt']:.4f}
🏪 Мерчант: {order.get('merchant_id', 'N/A')[-8:]}
🔗 <a href="{SITE_URL}/admin/orders">Открыть</a>"""
    await send_telegram_to_admin(admin_msg)
    
    # Уведомляем админов в системе - колокольчик
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1, "telegram_id": 1}).to_list(100)
    for admin in admins:
        # Колокольчик
        await db.admin_notifications.insert_one({
            "id": generate_id("anot"),
            "user_id": admin["id"],
            "type": "new_order",
            "title": "📋 Новый заказ в системе",
            "message": f"Заказ #{order['id'][-8:]}, {order['amount_rub']:.2f} ₽",
            "data": {"order_id": order["id"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram для админов с привязанным telegram_id
        if admin.get("telegram_id"):
            msg = f"""📋 <b>Новый заказ в системе</b>

🆔 ID: #{order['id'][-8:]}
💰 Сумма: {order['amount_rub']:.2f} ₽
🏪 Мерчант: {order.get('merchant_id', 'N/A')[:10]}..."""
            await send_telegram_notification(admin["id"], msg, "admin_order")

async def notify_order_confirmed(order: dict):
    """Уведомление о подтверждении заказа - мерчанту (колокольчик + telegram)"""
    if order.get("merchant_id"):
        # Колокольчик
        await db.user_notifications.insert_one({
            "id": generate_id("unot"),
            "user_id": order["merchant_id"],
            "type": "order_confirmed",
            "title": "✅ Заказ подтверждён",
            "message": f"Заказ #{order['id'][-8:]}, {order['amount_rub']:.2f} ₽ - покупатель скоро оплатит",
            "link": "/merchant/orders",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""✅ <b>Заказ подтверждён трейдером</b>

🆔 Заказ: #{order['id'][-8:]}
💰 Сумма: <b>{order['amount_rub']:.2f} ₽</b>
💵 USDT: <b>{order['amount_usdt']:.4f}</b>

Покупатель скоро оплатит!"""
        await send_telegram_notification(order["merchant_id"], msg, "order_confirmed")

async def notify_order_paid(order: dict):
    """Уведомление об оплате - трейдеру (колокольчик + telegram)"""
    if order.get("trader_id"):
        # Получаем user_id трейдера
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0, "user_id": 1})
        if not trader:
            return
        
        trader_user_id = trader["user_id"]
        
        # Колокольчик
        await db.user_notifications.insert_one({
            "id": generate_id("unot"),
            "user_id": trader_user_id,
            "type": "order_paid",
            "title": "💸 Покупатель оплатил!",
            "message": f"Заказ #{order['id'][-8:]}, {order['amount_rub']:.2f} ₽ - проверьте!",
            "link": "/trader/workspace",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""💸 <b>Покупатель подтвердил оплату!</b>

🆔 Заказ: #{order['id'][-8:]}
💰 Сумма: <b>{order['amount_rub']:.2f} ₽</b>

⚠️ Проверьте поступление средств и подтвердите!
🔗 <a href="{SITE_URL}/trader/orders">Открыть</a>"""
        await send_telegram_notification(trader_user_id, msg, "order_paid")

async def notify_order_completed(order: dict, commission_usdt: float):
    """Уведомление о завершении заказа - мерчанту и трейдеру"""
    # Уведомляем мерчанта (колокольчик + telegram)
    if order.get("merchant_id"):
        # Колокольчик
        await db.user_notifications.insert_one({
            "id": generate_id("unot"),
            "user_id": order["merchant_id"],
            "type": "order_completed",
            "title": "🎉 Заказ завершён",
            "message": f"Заказ #{order['id'][-8:]}, зачислено {order['amount_usdt'] - commission_usdt:.4f} USDT",
            "link": "/merchant/orders",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""🎉 <b>Заказ успешно завершён!</b>

🆔 Заказ: #{order['id'][-8:]}
💵 Зачислено: <b>{order['amount_usdt'] - commission_usdt:.4f} USDT</b>

Средства добавлены на ваш баланс!"""
        await send_telegram_notification(order["merchant_id"], msg, "order_completed")
    
    # Уведомляем трейдера (колокольчик + telegram)
    if order.get("trader_id"):
        # Получаем user_id трейдера
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0, "user_id": 1})
        if trader:
            trader_user_id = trader["user_id"]
            
            # Колокольчик
            await db.user_notifications.insert_one({
                "id": generate_id("unot"),
                "user_id": trader_user_id,
                "type": "order_completed",
                "title": "✨ Сделка завершена",
                "message": f"Заказ #{order['id'][-8:]}, комиссия получена!",
                "link": "/trader/workspace",
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Telegram
            msg = f"""✨ <b>Сделка завершена!</b>

🆔 Заказ: #{order['id'][-8:]}
💰 Получено: <b>{order['amount_rub']:.2f} ₽</b>

Отличная работа!"""
            await send_telegram_notification(trader_user_id, msg, "order_completed")

async def notify_dispute_opened(dispute: dict, order: dict):
    """Уведомление об открытии спора - трейдеру, мерчанту и админам"""
    
    dispute_reason = dispute.get('reason', 'Не указана')[:100]
    order_short_id = order['id'][-8:]
    amount_rub = order.get('amount_rub', 0)
    amount_usdt = order.get('amount_usdt', 0)
    
    # 1. Уведомляем ТРЕЙДЕРА
    if order.get("trader_id"):
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0, "user_id": 1})
        if trader:
            trader_user_id = trader["user_id"]
            # Колокольчик
            await db.user_notifications.insert_one({
                "id": generate_id("noti"),
                "user_id": trader_user_id,
                "type": "dispute_opened",
                "title": "⚠️ Открыт спор по вашей сделке",
                "message": f"Заказ #{order_short_id}, сумма {amount_rub:.2f} ₽. Причина: {dispute_reason}",
                "link": f"/dispute/{dispute['id']}",
                "data": {"dispute_id": dispute["id"], "order_id": order["id"]},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            # Telegram
            msg = f"""⚠️ <b>Открыт спор по вашей сделке!</b>

🆔 Заказ: #{order_short_id}
💰 Сумма: {amount_rub:.2f} ₽ ({amount_usdt:.4f} USDT)
📝 Причина: {dispute_reason}

🔗 <a href="{SITE_URL}/dispute/{dispute['id']}">Перейти в спор</a>"""
            await send_telegram_notification(trader_user_id, msg, "dispute_opened")
    
    # 2. Уведомляем МЕРЧАНТА
    if order.get("merchant_id"):
        # Колокольчик
        await db.user_notifications.insert_one({
            "id": generate_id("noti"),
            "user_id": order["merchant_id"],
            "type": "dispute_opened",
            "title": "⚠️ Открыт спор по заказу",
            "message": f"Заказ #{order_short_id}, сумма {amount_rub:.2f} ₽. Причина: {dispute_reason}",
            "link": f"/merchant/orders",
            "data": {"dispute_id": dispute["id"], "order_id": order["id"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        # Telegram
        msg = f"""⚠️ <b>Открыт спор по вашему заказу!</b>

🆔 Заказ: #{order_short_id}
💰 Сумма: {amount_rub:.2f} ₽ ({amount_usdt:.4f} USDT)
📝 Причина: {dispute_reason}

Ожидайте решения модератора."""
        await send_telegram_notification(order["merchant_id"], msg, "dispute_opened")
    
    # 3. Отправляем в главный админ чат
    admin_msg = f"""⚠️ <b>Открыт новый спор!</b>

🆔 Заказ: #{order_short_id}
💰 Сумма: {amount_rub:.2f} ₽ ({amount_usdt:.4f} USDT)
📝 Причина: {dispute_reason}

🔗 <a href="{SITE_URL}/admin/disputes">Рассмотреть</a>"""
    await send_telegram_to_admin(admin_msg)
    
    # 4. Уведомляем всех админов и саппортов
    staff = await db.users.find(
        {"role": {"$in": ["admin", "support"]}, "is_active": True},
        {"_id": 0, "id": 1, "telegram_id": 1}
    ).to_list(100)
    
    for s in staff:
        # Колокольчик
        await db.admin_notifications.insert_one({
            "id": generate_id("anot"),
            "user_id": s["id"],
            "type": "new_dispute",
            "title": "⚠️ Открыт новый спор",
            "message": f"Заказ #{order_short_id}, сумма {amount_rub:.2f} ₽",
            "data": {"dispute_id": dispute["id"], "order_id": order["id"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram для привязанных аккаунтов
        if s.get("telegram_id"):
            msg = f"""⚠️ <b>Открыт новый спор!</b>

🆔 Заказ: #{order_short_id}
💰 Сумма: {amount_rub:.2f} ₽
📝 Причина: {dispute_reason}

🔗 <a href="{SITE_URL}/admin/disputes">Рассмотреть</a>"""
            await send_telegram_notification(s["id"], msg, "dispute")

async def notify_withdrawal_request(withdrawal: dict, user: dict):
    """Уведомление о запросе на вывод - админам (колокольчик + telegram)"""
    # Проверяем статус доверия
    auto_approve = user.get("withdrawal_auto_approve", False)
    
    if not auto_approve:
        # Отправляем в главный админ чат
        admin_msg = f"""💳 <b>Новая заявка на вывод</b>

👤 Пользователь: {user.get('nickname') or user.get('login')}
💵 Сумма: <b>{withdrawal['amount']:.4f} USDT</b>
📍 Адрес: <code>{withdrawal['address']}</code>

⚠️ Требуется подтверждение!
🔗 <a href="{SITE_URL}/admin/finances">Обработать</a>"""
        await send_telegram_to_admin(admin_msg)
        
        # Уведомляем админов о заявке на подтверждение
        admins = await db.users.find(
            {"role": "admin", "is_active": True},
            {"_id": 0, "id": 1, "telegram_id": 1}
        ).to_list(100)
        
        for admin in admins:
            # Колокольчик
            await db.admin_notifications.insert_one({
                "id": generate_id("anot"),
                "user_id": admin["id"],
                "type": "withdrawal_request",
                "title": "💳 Заявка на вывод",
                "message": f"{user.get('nickname') or user.get('login')}: {withdrawal['amount']:.4f} USDT",
                "data": {"withdrawal_id": withdrawal.get("id"), "user_id": user["id"]},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Telegram
            if admin.get("telegram_id"):
                msg = f"""💳 <b>Новая заявка на вывод</b>

👤 Пользователь: {user.get('nickname') or user.get('login')}
💵 Сумма: <b>{withdrawal['amount']:.4f} USDT</b>
📍 Адрес: {withdrawal['address'][:20]}...

⚠️ Требуется подтверждение!
🔗 <a href="{SITE_URL}/admin/finances">Обработать</a>"""
                await send_telegram_notification(admin["id"], msg, "withdrawal")
    else:
        # Уведомляем пользователя об автоматическом выводе - колокольчик + telegram
        # Колокольчик
        await db.user_notifications.insert_one({
            "id": generate_id("unot"),
            "user_id": user["id"],
            "type": "withdrawal_processing",
            "title": "✅ Вывод обрабатывается",
            "message": f"{withdrawal['amount']:.4f} USDT → {withdrawal['address'][:15]}...",
            "link": "/trader/finances",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""✅ <b>Вывод обрабатывается</b>

💵 Сумма: <b>{withdrawal['amount']:.4f} USDT</b>
📍 Адрес: {withdrawal['address'][:20]}...

Средства будут отправлены автоматически!"""
        await send_telegram_notification(user["id"], msg, "withdrawal")

async def notify_deposit_credited(user_id: str, amount: float):
    """Уведомление о зачислении депозита - колокольчик + telegram"""
    # Колокольчик
    await db.user_notifications.insert_one({
        "id": generate_id("unot"),
        "user_id": user_id,
        "type": "deposit_credited",
        "title": "💰 Депозит зачислен",
        "message": f"На ваш баланс добавлено {amount:.4f} USDT",
        "link": "/trader/finances",
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Telegram
    msg = f"""💰 <b>Депозит зачислен!</b>

💵 Сумма: <b>{amount:.4f} USDT</b>

Средства добавлены на ваш баланс!"""
    await send_telegram_notification(user_id, msg, "deposit")

async def notify_new_ticket(ticket: dict, user: dict):
    """Уведомление о новом тикете - админам и саппортам (колокольчик + telegram)"""
    staff = await db.users.find(
        {"role": {"$in": ["admin", "support"]}, "is_active": True},
        {"_id": 0, "id": 1, "telegram_id": 1}
    ).to_list(100)
    
    user_name = user.get('nickname') or user.get('login') or 'Пользователь'
    
    for s in staff:
        # Колокольчик
        await db.admin_notifications.insert_one({
            "id": generate_id("anot"),
            "user_id": s["id"],
            "type": "new_ticket",
            "title": f"📩 Новый тикет от {user_name}",
            "message": f"{ticket.get('subject', 'Без темы')[:50]}",
            "data": {"ticket_id": ticket["id"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        if s.get("telegram_id"):
            msg = f"""📩 <b>Новый тикет</b>

📌 Тема: {ticket.get('subject', 'Без темы')[:50]}
👤 От: {user_name}
📅 {ticket.get('created_at', '')[:10]}

🔗 <a href="{SITE_URL}/admin/tickets">Ответить</a>"""
            await send_telegram_notification(s["id"], msg, "ticket")

async def notify_ticket_reply(ticket_id: str, sender_id: str, is_from_staff: bool):
    """Уведомление об ответе в тикете - колокольчик + telegram"""
    ticket = await db.tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        return
    
    if is_from_staff:
        # Уведомляем пользователя (колокольчик + telegram)
        await db.user_notifications.insert_one({
            "id": generate_id("unot"),
            "user_id": ticket["user_id"],
            "type": "ticket_reply",
            "title": "💬 Ответ от поддержки",
            "message": f"Новый ответ в тикете: {ticket.get('subject', 'Тикет')[:50]}",
            "link": f"/support/{ticket_id}",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        msg = f"""💬 <b>Ответ в тикете</b>

📌 Тема: {ticket.get('subject', 'Тикет')[:50]}

У вас новый ответ от поддержки!
🔗 <a href="{SITE_URL}/support/{ticket_id}">Открыть</a>"""
        await send_telegram_notification(ticket["user_id"], msg, "ticket_reply")
    else:
        # Уведомляем всех админов и саппортов (колокольчик + telegram)
        staff = await db.users.find(
            {"role": {"$in": ["admin", "support"]}, "is_active": True},
            {"_id": 0, "id": 1, "telegram_id": 1}
        ).to_list(100)
        
        sender_info = await db.users.find_one({"id": sender_id}, {"_id": 0, "nickname": 1, "login": 1, "role": 1})
        sender_name = sender_info.get("nickname") or sender_info.get("login") or "Пользователь" if sender_info else "Пользователь"
        
        for s in staff:
            # Колокольчик
            await db.admin_notifications.insert_one({
                "id": generate_id("anot"),
                "user_id": s["id"],
                "type": "ticket_reply",
                "title": f"💬 Ответ от {sender_name}",
                "message": f"Тикет: {ticket.get('subject', 'Тикет')[:50]}",
                "data": {"ticket_id": ticket_id},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Telegram
            if s.get("telegram_id"):
                msg = f"""💬 <b>Ответ в тикете</b>

📌 {ticket.get('subject', 'Тикет')[:50]}

От: {sender_name}
🔗 <a href="{SITE_URL}/admin/tickets">Открыть</a>"""
                await send_telegram_notification(s["id"], msg, "ticket_reply")

async def notify_dispute_message(dispute: dict, order: dict, sender_id: str, sender_role: str, message_text: str):
    """Уведомление о новом сообщении в споре - всем участникам"""
    sender = await db.users.find_one({"id": sender_id}, {"_id": 0, "nickname": 1, "login": 1})
    sender_name = sender.get("nickname") or sender.get("login") or "Пользователь" if sender else "Пользователь"
    short_msg = message_text[:50] + "..." if len(message_text) > 50 else message_text
    
    # Определяем получателей в зависимости от отправителя
    recipients_to_notify = []
    
    # 1. Получаем трейдера
    if order.get("trader_id"):
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0, "user_id": 1})
        if trader and trader.get("user_id") != sender_id:
            recipients_to_notify.append({
                "user_id": trader["user_id"],
                "role": "trader",
                "notification_db": "user_notifications"
            })
    
    # 2. Получаем мерчанта
    if order.get("merchant_id") and order.get("merchant_id") != sender_id:
        recipients_to_notify.append({
            "user_id": order["merchant_id"],
            "role": "merchant",
            "notification_db": "user_notifications"
        })
    
    # 3. Если отправитель не админ - уведомляем админов
    if sender_role not in ["admin", "support"]:
        staff = await db.users.find(
            {"role": {"$in": ["admin", "support"]}, "is_active": True},
            {"_id": 0, "id": 1}
        ).to_list(100)
        for s in staff:
            recipients_to_notify.append({
                "user_id": s["id"],
                "role": "admin",
                "notification_db": "admin_notifications"
            })
    
    # Отправляем уведомления
    for recipient in recipients_to_notify:
        # Колокольчик
        notification = {
            "id": generate_id("noti"),
            "user_id": recipient["user_id"],
            "type": "dispute_message",
            "title": f"💬 Сообщение в споре #{dispute['id'][-8:]}",
            "message": f"От {sender_name}: {short_msg}",
            "link": f"/disputes/{dispute['id']}" if recipient["role"] != "admin" else f"/admin/disputes",
            "data": {"dispute_id": dispute["id"], "order_id": order["id"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        if recipient["notification_db"] == "admin_notifications":
            await db.admin_notifications.insert_one(notification)
        else:
            await db.user_notifications.insert_one(notification)
        
        # Telegram
        msg = f"""💬 <b>Новое сообщение в споре</b>

🆔 Заказ: #{order['id'][-8:]}
👤 От: {sender_name}
💬 {short_msg}

🔗 <a href="{SITE_URL}/{'admin/disputes' if recipient['role'] == 'admin' else 'disputes/' + dispute['id']}">Открыть</a>"""
        await send_telegram_notification(recipient["user_id"], msg, "dispute_message")


async def notify_dispute_resolved(dispute: dict, order: dict, resolution: str, winner: str = None):
    """Уведомление о закрытии спора - трейдеру и мерчанту"""
    resolution_text = {
        "refund": "🔄 Возврат средств покупателю",
        "complete": "✅ Сделка подтверждена",
        "manual": "⚙️ Решено вручную"
    }.get(resolution, resolution)
    
    recipients = []
    
    # Трейдер
    if order.get("trader_id"):
        trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0, "user_id": 1})
        if trader:
            recipients.append(trader["user_id"])
    
    # Мерчант  
    if order.get("merchant_id"):
        recipients.append(order["merchant_id"])
    
    for user_id in recipients:
        # Колокольчик
        await db.user_notifications.insert_one({
            "id": generate_id("noti"),
            "user_id": user_id,
            "type": "dispute_resolved",
            "title": f"✅ Спор #{dispute['id'][-8:]} закрыт",
            "message": resolution_text,
            "link": f"/orders",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""✅ <b>Спор закрыт</b>

🆔 Заказ: #{order['id'][-8:]}
💰 Сумма: {order.get('amount_rub', 0):.2f} ₽
📋 Решение: {resolution_text}

🔗 <a href="{SITE_URL}/orders">Перейти к заказам</a>"""
        await send_telegram_notification(user_id, msg, "dispute_resolved")


async def notify_unidentified_deposit(tx_data: dict):
    """Уведомление админам о неопознанном депозите"""
    staff = await db.users.find(
        {"role": "admin", "is_active": True},
        {"_id": 0, "id": 1}
    ).to_list(100)
    
    for admin in staff:
        # Колокольчик
        await db.admin_notifications.insert_one({
            "id": generate_id("anot"),
            "user_id": admin["id"],
            "type": "unidentified_deposit",
            "title": "❓ Неопознанный депозит",
            "message": f"{tx_data.get('amount', 0):.4f} USDT, комментарий: {tx_data.get('comment', 'нет')[:30]}",
            "data": tx_data,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""❓ <b>Неопознанный депозит</b>

💵 Сумма: <b>{tx_data.get('amount', 0):.4f} USDT</b>
💬 Комментарий: {tx_data.get('comment', 'нет')}
📍 От: <code>{tx_data.get('from_address', 'неизвестно')[:20]}...</code>

⚠️ Требуется ручная привязка!
🔗 <a href="{SITE_URL}/admin/finances">Открыть</a>"""
        await send_telegram_notification(admin["id"], msg, "unidentified_deposit")


async def notify_unidentified_withdrawal(tx_data: dict):
    """Уведомление админам о неопознанном выводе"""
    staff = await db.users.find(
        {"role": "admin", "is_active": True},
        {"_id": 0, "id": 1}
    ).to_list(100)
    
    for admin in staff:
        # Колокольчик
        await db.admin_notifications.insert_one({
            "id": generate_id("anot"),
            "user_id": admin["id"],
            "type": "unidentified_withdrawal",
            "title": "❗ Неопознанный вывод",
            "message": f"{tx_data.get('amount', 0):.4f} USDT, комментарий: {tx_data.get('comment', 'нет')[:30]}",
            "data": tx_data,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""❗ <b>Неопознанный вывод</b>

💵 Сумма: <b>{tx_data.get('amount', 0):.4f} USDT</b>
💬 Комментарий: {tx_data.get('comment', 'нет')}
📍 Куда: <code>{tx_data.get('to_address', 'неизвестно')[:20]}...</code>

⚠️ Вывод не инициирован через платформу!
🔗 <a href="{SITE_URL}/admin/finances">Открыть</a>"""
        await send_telegram_notification(admin["id"], msg, "unidentified_withdrawal")


async def notify_new_trader_application(user: dict, application: dict):
    """Уведомление админам о новой заявке на трейдера"""
    staff = await db.users.find(
        {"role": "admin", "is_active": True},
        {"_id": 0, "id": 1}
    ).to_list(100)
    
    user_name = user.get('nickname') or user.get('login') or 'Пользователь'
    
    for admin in staff:
        # Колокольчик
        await db.admin_notifications.insert_one({
            "id": generate_id("anot"),
            "user_id": admin["id"],
            "type": "trader_application",
            "title": "👤 Заявка на трейдера",
            "message": f"Пользователь {user_name} подал заявку",
            "data": {"user_id": user["id"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""👤 <b>Новая заявка на трейдера</b>

🆔 Пользователь: {user_name}

🔗 <a href="{SITE_URL}/admin/users">Рассмотреть</a>"""
        await send_telegram_notification(admin["id"], msg, "trader_application")


async def notify_new_merchant_application(user: dict, application: dict):
    """Уведомление админам о новой заявке на мерчанта"""
    staff = await db.users.find(
        {"role": "admin", "is_active": True},
        {"_id": 0, "id": 1}
    ).to_list(100)
    
    user_name = user.get('nickname') or user.get('login') or 'Пользователь'
    
    for admin in staff:
        # Колокольчик
        await db.admin_notifications.insert_one({
            "id": generate_id("anot"),
            "user_id": admin["id"],
            "type": "merchant_application",
            "title": "🏪 Заявка на мерчанта",
            "message": f"Пользователь {user_name} подал заявку",
            "data": {"user_id": user["id"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Telegram
        msg = f"""🏪 <b>Новая заявка на мерчанта</b>

🆔 Пользователь: {user_name}

🔗 <a href="{SITE_URL}/admin/users">Рассмотреть</a>"""
        await send_telegram_notification(admin["id"], msg, "merchant_application")


async def notify_withdrawal_completed(user_id: str, withdrawal: dict):
    """Уведомление пользователю о завершении вывода"""
    # Колокольчик
    await db.user_notifications.insert_one({
        "id": generate_id("noti"),
        "user_id": user_id,
        "type": "withdrawal_completed",
        "title": "✅ Вывод завершён",
        "message": f"{withdrawal.get('amount', 0):.4f} USDT отправлено на ваш кошелёк",
        "link": "/finances",
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Telegram
    msg = f"""✅ <b>Вывод завершён</b>

💵 Сумма: <b>{withdrawal.get('amount', 0):.4f} USDT</b>
📍 Адрес: <code>{withdrawal.get('address', '')[:20]}...</code>

🔗 Транзакция отправлена в блокчейн!"""
    await send_telegram_notification(user_id, msg, "withdrawal_completed")


# CAPTCHA challenges cache (in-memory for simplicity)
captcha_challenges = {}

# Stateless CAPTCHA token verification function
def verify_captcha_token_stateless(token: str) -> bool:
    """Verify CAPTCHA token without database - using HMAC signature"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return False
        
        random_part, expires_str, signature = parts
        
        # Verify signature
        token_data = f"{random_part}:{expires_str}"
        expected_signature = hmac.new(CAPTCHA_SECRET.encode(), token_data.encode(), hashlib.sha256).hexdigest()[:16]
        
        if signature != expected_signature:
            return False
        
        # Check expiration
        expires = datetime.strptime(expires_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return False
        
        return True
    except Exception:
        return False


# ================== MAINTENANCE MIDDLEWARE ==================

class MaintenanceMiddleware(BaseHTTPMiddleware):
    """Middleware для блокировки доступа в режиме техобслуживания"""
    
    # Эндпоинты которые всегда доступны (для админов и системы)
    ALLOWED_PATHS = [
        "/health",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/register",
        "/api/auth/me",  # Получение данных текущего пользователя
        "/api/public/maintenance",  # Проверка статуса техобслуживания
        "/api/admin",  # Все админские роуты
        "/api/rates",  # Курсы валют
    ]
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Пропускаем разрешённые пути
        for allowed in self.ALLOWED_PATHS:
            if path.startswith(allowed):
                return await call_next(request)
        
        # Проверяем режим техобслуживания
        try:
            settings = await db.platform_settings.find_one({"key": "maintenance"})
            if settings and settings.get("enabled", False):
                # Проверяем токен - админы могут работать
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
                    try:
                        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                        user_role = payload.get("role", "")
                        if user_role in ["admin", "support"]:
                            return await call_next(request)
                    except:
                        pass
                
                # Для всех остальных - блокируем
                message = settings.get("message", "Платформа находится на техническом обслуживании")
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": message,
                        "maintenance": True
                    }
                )
        except Exception:
            # Если БД недоступна - пропускаем
            pass
        
        return await call_next(request)


# Create the main app
app = FastAPI(title="BITARBITR P2P Platform", version="1.0.0")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# Корневой health endpoint для Kubernetes (должен быть СРАЗУ после создания app)
@app.get("/health")
async def root_health_check():
    return {"status": "healthy"}


# Публичный эндпоинт для проверки режима техобслуживания
@app.get("/api/public/maintenance")
async def get_public_maintenance_status(role: str = None):
    """Публичная проверка статуса техобслуживания"""
    try:
        settings = await db.platform_settings.find_one({"key": "maintenance"})
        if settings and settings.get("enabled", False):
            # Админы и поддержка всегда имеют доступ
            if role in ["admin", "support"]:
                return {"active": False}
            return {
                "active": True,
                "message": settings.get("message", "Платформа находится на техническом обслуживании")
            }
    except:
        pass
    return {"active": False}


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================== MODELS ==================

class UserCreate(BaseModel):
    login: str
    nickname: str
    password: str
    role: str = "trader"
    captcha_token: Optional[str] = None  # CAPTCHA verification token
    referral_code: Optional[str] = None  # Реферальный код пригласившего

class UserLogin(BaseModel):
    login: str
    password: str
    two_factor_code: Optional[str] = None  # 2FA code if enabled
    captcha_token: Optional[str] = None  # CAPTCHA verification token

# Модель прав доступа для админов/саппортов
class UserPermissions(BaseModel):
    approve_traders: bool = False      # Одобрение трейдеров
    block_users: bool = False          # Блокировка пользователей
    delete_users: bool = False         # Удаление пользователей
    view_orders: bool = False          # Просмотр ордеров
    manage_disputes: bool = False      # Управление спорами
    view_accounting: bool = False      # Просмотр бухгалтерии
    manage_rates: bool = False         # Управление курсами валют
    create_admins: bool = False        # Создание администраторов
    manage_tickets: bool = False       # Управление тикетами

# Права по умолчанию для ролей
DEFAULT_PERMISSIONS = {
    "admin": {
        "approve_traders": True,
        "block_users": True,
        "delete_users": True,
        "view_orders": True,
        "manage_disputes": True,
        "view_accounting": True,
        "manage_rates": True,
        "create_admins": True,
        "manage_tickets": True
    },
    "support": {
        "approve_traders": True,
        "block_users": True,
        "delete_users": False,
        "view_orders": True,
        "manage_disputes": True,
        "view_accounting": False,
        "manage_rates": False,
        "create_admins": False,
        "manage_tickets": True
    }
}

class CreateStaffUser(BaseModel):
    login: str
    nickname: str
    password: str
    role: str  # admin или support
    permissions: Optional[Dict[str, bool]] = None

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    login: str
    nickname: str
    role: str
    is_active: bool
    is_verified: bool
    two_factor_enabled: bool
    created_at: str
    telegram_id: Optional[int] = None

class TraderProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    rating: float = 5.0
    total_deals: int = 0
    successful_deals: int = 0
    total_volume_rub: float = 0.0
    total_commission_usdt: float = 0.0
    is_available: bool = True
    auto_mode: bool = True
    min_deal_amount_rub: float = 100.0
    max_deal_amount_rub: float = 500000.0

# ================== PAYMENT METHODS ==================
# 7 типов оплаты
PAYMENT_METHODS = {
    'sbp': {
        'name': 'SBP',
        'fields': ['phone_number', 'bank_name'],
        'optional_fields': ['holder_name'],
        'description': 'Система быстрых платежей'
    },
    'card': {
        'name': 'Card',
        'fields': ['card_number', 'bank_name'],
        'optional_fields': ['holder_name'],
        'description': 'Банковская карта'
    },
    'sim': {
        'name': 'SIM',
        'fields': ['phone_number', 'operator_name'],
        'optional_fields': [],
        'description': 'Пополнение мобильного'
    },
    'mono_bank': {
        'name': 'Mono Bank',
        'fields': [],  # phone_number OR card_number
        'optional_fields': ['phone_number', 'card_number', 'bank_name', 'holder_name', 'comment'],
        'description': 'Mono Bank (телефон или карта)'
    },
    'sng_sbp': {
        'name': 'SNG-SBP',
        'fields': ['phone_number', 'bank_name'],
        'optional_fields': ['holder_name'],
        'description': 'СНГ - СБП'
    },
    'sng_card': {
        'name': 'SNG-Card',
        'fields': ['card_number', 'bank_name'],
        'optional_fields': ['holder_name'],
        'description': 'СНГ - Карта'
    },
    'qr_code': {
        'name': 'QR-code',
        'fields': ['qr_link'],
        'optional_fields': [],
        'description': 'QR-код (ссылка)'
    }
}

# Обновлённая модель реквизитов - 7 типов оплаты
class PaymentDetailCreate(BaseModel):
    payment_type: str  # sbp, card, sim, mono_bank, sng_sbp, sng_card, qr_code
    card_number: Optional[str] = None  # Для card, sng_card, mono_bank
    phone_number: Optional[str] = None  # Для sbp, sim, sng_sbp, mono_bank
    qr_link: Optional[str] = None  # Для qr_code
    bank_name: Optional[str] = None  # Название банка (вручную)
    operator_name: Optional[str] = None  # Для SIM (вручную)
    holder_name: Optional[str] = None  # ФИО (опционально)
    comment: Optional[str] = None  # Комментарий (для mono_bank)
    min_amount_rub: float = 100.0
    max_amount_rub: float = 500000.0
    daily_limit_rub: float = 1500000.0
    priority: int = 10
    is_active: bool = True

class PaymentDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    trader_id: str
    payment_type: str
    card_number: Optional[str] = None
    phone_number: Optional[str] = None
    qr_link: Optional[str] = None
    qr_data: Optional[str] = None  # Legacy support
    bank_name: Optional[str] = None
    operator_name: Optional[str] = None
    holder_name: Optional[str] = None
    comment: Optional[str] = None
    min_amount_rub: float
    max_amount_rub: float
    daily_limit_rub: float
    used_today_rub: float = 0
    priority: int
    is_active: bool

class OrderCreate(BaseModel):
    amount_rub: float
    payment_method: str = "sbp"  # sbp, card, sim, mono_bank, sng_sbp, sng_card, qr_code
    external_id: Optional[str] = None
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class OrderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    merchant_id: str
    trader_id: Optional[str] = None
    status: str
    amount_rub: float
    amount_usdt: float
    exchange_rate: float
    payment_method: Optional[str] = None  # sbp, card, sim, mono_bank, sng_sbp, sng_card, qr_code
    payment_details: Optional[Dict[str, Any]] = None
    buyer_contact: Optional[str] = None
    created_at: str
    expires_at: str
    external_id: Optional[str] = None
    original_amount_rub: Optional[float] = None
    random_addition_rub: Optional[float] = None
    commission_rub: Optional[float] = None
    cancel_available_at: Optional[str] = None
    dispute_id: Optional[str] = None

# ================== MERCHANT COMMISSION SETTINGS ==================
class CommissionInterval(BaseModel):
    min_amount: float  # Минимальная сумма в рублях
    max_amount: float  # Максимальная сумма в рублях
    percent: float     # Процент комиссии

class MerchantMethodCommission(BaseModel):
    payment_method: str  # sbp, card, sim, mono_bank, sng_sbp, sng_card, qr_code
    intervals: List[CommissionInterval] = []

class MerchantCommissionSettings(BaseModel):
    methods: List[MerchantMethodCommission] = []

# ================== REFERRAL SYSTEM ==================
class ReferralSettings(BaseModel):
    """Настройки реферальной программы"""
    level1_percent: float = 5.0   # % с заработка реферала 1-го уровня
    level2_percent: float = 2.0   # % с заработка реферала 2-го уровня
    level3_percent: float = 1.0   # % с заработка реферала 3-го уровня
    min_withdrawal: float = 100.0  # Минимальная сумма для вывода (₽)
    enabled: bool = True           # Включена ли реф. программа

# ================== MAINTENANCE MODE ==================
class MaintenanceSettings(BaseModel):
    """Настройки режима техобслуживания"""
    enabled: bool = False
    target: str = "all"  # "traders", "merchants", "all"
    duration_minutes: int = 60
    message: str = "Платформа на техническом обслуживании"
    started_at: Optional[str] = None
    ends_at: Optional[str] = None

class WalletResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    address: Optional[str] = None
    available_balance_usdt: float = 0.0
    locked_balance_usdt: float = 0.0
    pending_balance_usdt: float = 0.0
    earned_balance_usdt: float = 0.0
    total_deposited_usdt: float = 0.0
    total_withdrawn_usdt: float = 0.0

class DisputeCreate(BaseModel):
    reason: str

class ChatMessageCreate(BaseModel):
    text: str
    
class TicketCreate(BaseModel):
    subject: str
    message: str
    user_id: Optional[str] = None  # Для админа - кому создать тикет

class TicketReply(BaseModel):
    message: str

class MerchantCreate(BaseModel):
    company_name: str
    website_url: str
    contact_person: Optional[str] = None
    callback_url: Optional[str] = None
    commission_percent: Optional[float] = 25.0  # Комиссия мерчанта (по умолчанию 25%)

class MerchantUpdate(BaseModel):
    company_name: Optional[str] = None
    website_url: Optional[str] = None
    callback_url: Optional[str] = None
    commission_percent: Optional[float] = None  # Комиссия 10-50%

# ================== ФИНАНСОВАЯ МОДЕЛЬ МЕРЧАНТА ==================
class MerchantFeeSettings(BaseModel):
    """Настройки финансовой модели мерчанта"""
    fee_model: str  # "merchant_pays" (Тип 1) или "customer_pays" (Тип 2)
    total_fee_percent: float = 30.0  # Общая накрутка (комиссия трейдера + платформы)

class TraderFeeInterval(BaseModel):
    """Интервал комиссии трейдера"""
    min_amount: float
    max_amount: float
    percent: float

class TraderFeeSettings(BaseModel):
    """Настройки комиссии трейдера с интервалами"""
    intervals: List[TraderFeeInterval] = []
    default_percent: float = 10.0  # Процент по умолчанию если интервалы не настроены

class TelegramLink(BaseModel):
    telegram_id: int

# ================== USDT & MULTI-CURRENCY MODELS ==================

class USDTDeposit(BaseModel):
    amount: float
    tx_hash: str  # TRC20 transaction hash

class USDTWithdraw(BaseModel):
    amount: float
    address: str  # TRC20 wallet address

class CurrencyRateUpdate(BaseModel):
    currency: str  # USD, EUR, USDT
    rate_rub: float  # Курс к рублю
    source: str = "manual"  # manual, coingecko, cbr

# ================== USDT DEPOSIT/WITHDRAW MODELS ==================

class DepositRequestCreate(BaseModel):
    """Создание заявки на депозит с точной суммой"""
    pass  # Автоматически генерируется

class DepositRequestResponse(BaseModel):
    """Ответ заявки на депозит"""
    request_id: str
    exact_amount_usdt: float
    ton_address: str
    expires_at: str
    status: str
    instructions: str

class USDTWithdrawalCreate(BaseModel):
    """Создание запроса на вывод USDT"""
    amount: float  # Сумма в USDT
    ton_address: str  # TON адрес получателя

class WithdrawalAdminConfirm(BaseModel):
    """Подтверждение вывода админом"""
    withdrawal_id: str
    tx_hash: str  # Хэш транзакции после отправки

# ================== AUTO-WITHDRAW MODELS ==================

class AutoWithdrawSetup(BaseModel):
    """Настройка автовывода USDT"""
    wallet_address: str
    seed_phrase: str  # 24 слова
    usdt_contract: str
    toncenter_api_key: str
    encryption_password: str
    max_auto_withdraw: float = 50.0  # Максимальный автовывод
    min_balance_stop: float = 20.0  # Минимальный баланс для остановки

class AutoWithdrawStatus(BaseModel):
    """Статус автовывода"""
    is_running: bool = False
    wallet_address: Optional[str] = None
    balance: float = 0.0
    last_transaction: Optional[str] = None
    last_transaction_time: Optional[str] = None
    pending_withdrawals: int = 0
    total_withdrawn: float = 0.0

class TestWithdrawRequest(BaseModel):
    """Тестовый вывод"""
    to_address: str
    amount: float = 0.001

# Курсы валют (по умолчанию)
CURRENCY_RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "USDT": 92.30
}

# ================== AUTH UTILS ==================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(allowed_roles: List[str]):
    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker

# ================== UTILS ==================

def generate_id(prefix: str) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(3).upper()
    return f"{prefix}_{date_part}_{random_part}"

def generate_ton_address() -> str:
    """Генерация заглушки TON адреса (реальный создаётся при депозите)"""
    return f"UQ{secrets.token_hex(16).upper()}"

async def calculate_usdt_amount(rub_amount: float) -> tuple:
    """Рассчитать сумму USDT по актуальному курсу"""
    usdt_rate = await fetch_usdt_rub_rate()
    usdt_amount = rub_amount / usdt_rate
    return round(usdt_amount, 2), usdt_rate

# ================== TELEGRAM NOTIFICATIONS ==================

# Note: Main send_telegram_notification function is defined earlier in the file (line ~213)

# ================== ADMIN NOTIFICATIONS SYSTEM ==================

async def create_admin_notification(notification_type: str, message: str, data: dict = None):
    """Создать уведомление для админов и отправить в Telegram"""
    notification = {
        "id": generate_id("ntf"),
        "type": notification_type,
        "message": message,
        "data": data or {},
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_notifications.insert_one(notification)
    
    # Уведомляем всех подключённых админов через WebSocket
    admins = await db.users.find({"role": {"$in": ["admin", "support"]}}, {"_id": 0, "id": 1, "telegram_id": 1}).to_list(100)
    for admin in admins:
        await manager.send_to_user(admin["id"], {
            "event": "notification",
            "notification": {
                "id": notification["id"],
                "type": notification_type,
                "message": message,
                "created_at": notification["created_at"]
            }
        })
        
        # Отправляем в Telegram если есть telegram_id
        if admin.get("telegram_id"):
            telegram_msg = f"🔔 <b>Уведомление</b>\n\n{message}"
            await send_telegram_notification(admin["id"], telegram_msg, notification_type)
    
    return notification

# ================== REFERRAL API ==================

@app.get("/api/user/referral")
async def get_user_referral_data(user: dict = Depends(get_current_user)):
    """Получить данные реферальной программы для пользователя"""
    
    # Генерируем реферальный код если его нет
    if not user.get("referral_code"):
        referral_code = secrets.token_hex(4).upper()
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"referral_code": referral_code}}
        )
        user["referral_code"] = referral_code
    
    # Получаем настройки реферальной программы
    settings = await db.platform_settings.find_one({"key": "referral"}, {"_id": 0})
    referral_settings = settings if settings else {}
    
    levels = referral_settings.get("levels", [
        {"level": 1, "percent": 5},
        {"level": 2, "percent": 3},
        {"level": 3, "percent": 1}
    ])
    
    # Считаем рефералов по уровням
    level_stats = []
    total_earned = 0
    
    # Уровень 1 - прямые рефералы
    direct_referrals = await db.users.find(
        {"referrer_id": user["id"]},
        {"_id": 0, "id": 1, "login": 1, "created_at": 1}
    ).to_list(1000)
    
    level_stats.append({
        "level": 1,
        "percent": levels[0]["percent"] if levels else 5,
        "count": len(direct_referrals)
    })
    
    # Уровень 2 и 3 (рефералы рефералов)
    level_2_ids = [r["id"] for r in direct_referrals]
    if level_2_ids:
        level_2_referrals = await db.users.find(
            {"referrer_id": {"$in": level_2_ids}},
            {"_id": 0, "id": 1}
        ).to_list(1000)
        level_stats.append({
            "level": 2,
            "percent": levels[1]["percent"] if len(levels) > 1 else 3,
            "count": len(level_2_referrals)
        })
        
        level_3_ids = [r["id"] for r in level_2_referrals]
        if level_3_ids:
            level_3_referrals = await db.users.find(
                {"referrer_id": {"$in": level_3_ids}},
                {"_id": 0, "id": 1}
            ).to_list(1000)
            level_stats.append({
                "level": 3,
                "percent": levels[2]["percent"] if len(levels) > 2 else 1,
                "count": len(level_3_referrals)
            })
        else:
            level_stats.append({"level": 3, "percent": 1, "count": 0})
    else:
        level_stats.append({"level": 2, "percent": 3, "count": 0})
        level_stats.append({"level": 3, "percent": 1, "count": 0})
    
    # Получаем историю начислений
    referral_earnings = await db.referral_earnings.find(
        {"referrer_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Считаем общий заработок и формируем историю для фронтенда
    history = []
    for earning in referral_earnings:
        total_earned += earning.get("amount_usdt", 0)
        # Получаем никнейм того, от кого пришёл бонус
        from_user = await db.users.find_one(
            {"id": earning.get("from_user_id")}, 
            {"_id": 0, "nickname": 1, "login": 1}
        )
        from_nickname = from_user.get("nickname") or from_user.get("login") if from_user else "Пользователь"
        history.append({
            "level": earning.get("level", 1),
            "from_nickname": from_nickname,
            "percent": earning.get("percent", 0),
            "bonus_usdt": earning.get("amount_usdt", 0),
            "created_at": earning.get("created_at")
        })
    
    # Баланс реферальный в USDT
    referral_balance = user.get("referral_balance", 0)
    
    # Минимум вывода в USDT
    min_withdrawal_usdt = referral_settings.get("min_withdrawal_usdt", 1)
    
    return {
        "referral_code": user.get("referral_code"),
        "referral_balance": referral_balance,  # USDT
        "referral_balance_usdt": referral_balance,  # Явно USDT
        "total_earned": total_earned,  # USDT
        "total_earned_usdt": total_earned,  # Явно USDT
        "level_stats": level_stats,
        "history": history,  # История в USDT
        "settings": {
            "level1_percent": levels[0]["percent"] if levels else 5,
            "level2_percent": levels[1]["percent"] if len(levels) > 1 else 3,
            "level3_percent": levels[2]["percent"] if len(levels) > 2 else 1,
            "min_withdrawal_usdt": min_withdrawal_usdt
        },
        "min_withdrawal_usdt": min_withdrawal_usdt,
        "currency": "USDT",
        "paid_by": "platform"  # Платит площадка
    }

@app.post("/api/user/referral/withdraw")
async def withdraw_referral_balance(user: dict = Depends(get_current_user)):
    """Вывод реферального баланса (USDT) на основной счёт"""
    
    referral_balance = user.get("referral_balance", 0)  # В USDT
    
    settings = await db.platform_settings.find_one({"key": "referral"}, {"_id": 0})
    # Минимум 1 USDT для вывода
    min_withdrawal = settings.get("min_withdrawal_usdt", 1) if settings else 1
    
    if referral_balance < min_withdrawal:
        raise HTTPException(
            status_code=400, 
            detail=f"Минимальная сумма для вывода: {min_withdrawal} USDT"
        )
    
    # Обнуляем реферальный баланс
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"referral_balance": 0}}
    )
    
    # Добавляем USDT в кошелёк (платит площадка)
    await db.wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {"available_balance_usdt": referral_balance}},
        upsert=True
    )
    
    # Записываем транзакцию
    await db.referral_withdrawals.insert_one({
        "id": generate_id("rwd"),
        "user_id": user["id"],
        "amount_usdt": referral_balance,
        "currency": "USDT",
        "source": "platform",  # Платит площадка
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    logger.info(f"Referral withdrawal: {referral_balance} USDT for user {user['id']} (paid by platform)")
    
    return {"success": True, "message": f"Выведено {referral_balance:.4f} USDT на основной счёт"}

# ================== WEBSOCKET MANAGER ==================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
    
    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected users"""
        for user_id, connections in self.active_connections.items():
            for ws in connections:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()


# ================== DISPUTE CHAT WEBSOCKET MANAGER ==================

class DisputeChatManager:
    """WebSocket manager for real-time dispute chat"""
    def __init__(self):
        # dispute_id -> list of (websocket, user_id, is_buyer)
        self.active_connections: Dict[str, List[tuple]] = {}
    
    async def connect(self, websocket: WebSocket, dispute_id: str, user_id: str, is_buyer: bool = False):
        await websocket.accept()
        if dispute_id not in self.active_connections:
            self.active_connections[dispute_id] = []
        self.active_connections[dispute_id].append((websocket, user_id, is_buyer))
        logger.info(f"🔌 WebSocket connected to dispute {dispute_id} by user {user_id} (buyer={is_buyer})")
    
    def disconnect(self, websocket: WebSocket, dispute_id: str):
        if dispute_id in self.active_connections:
            self.active_connections[dispute_id] = [
                conn for conn in self.active_connections[dispute_id] 
                if conn[0] != websocket
            ]
            if not self.active_connections[dispute_id]:
                del self.active_connections[dispute_id]
    
    async def broadcast_to_dispute(self, dispute_id: str, message: dict, exclude_user_id: str = None):
        """Send message to all participants of a dispute"""
        if dispute_id not in self.active_connections:
            return
        
        for ws, user_id, is_buyer in self.active_connections[dispute_id]:
            if exclude_user_id and user_id == exclude_user_id:
                continue
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send WS message to {user_id}: {e}")

dispute_chat_manager = DisputeChatManager()

# ================== INITIALIZE AND INCLUDE MODULAR ROUTERS ==================
# Initialize routers with dependencies
init_notifications(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM
)

init_tickets(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    telegram_func=send_telegram_notification,
    ws_manager=manager,
    site_url=SITE_URL
)

init_disputes(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    telegram_func=send_telegram_notification,
    ws_manager=manager,
    fetch_rate_func=fetch_usdt_rub_rate,
    notify_dispute_message_func=notify_dispute_message,
    notify_dispute_resolved_func=notify_dispute_resolved
)

init_auth(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    telegram_func=send_telegram_notification,
    site_url=SITE_URL
)

init_trader(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    telegram_func=send_telegram_notification,
    fetch_rate_func=fetch_usdt_rub_rate,
    notify_order_completed_func=notify_order_completed
)

init_merchant(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    site_url=SITE_URL
)

# Initialize Invoice API
init_invoice(
    database=db,
    generate_id_func=generate_id,
    calculate_usdt_func=calculate_usdt_amount,
    ws_manager=manager,
    site_url=SITE_URL,
    notify_new_order_func=notify_new_order
)

init_wallet(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM
)

init_admin(
    database=db,
    role_checker=require_role,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    fetch_rate_func=fetch_usdt_rub_rate,
    notify_withdrawal_completed_func=notify_withdrawal_completed,
    send_telegram_func=send_telegram_message
)

init_usdt(
    database=db,
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    fetch_rate_func=fetch_usdt_rub_rate
)

init_shop(
    database=db,
    fetch_rate_func=fetch_usdt_rub_rate,
    ws_manager=manager,
    notify_order_paid_func=notify_order_paid
)

# Initialize optional modules
if CASINO_AVAILABLE:
    init_casino_db(db)

# Include modular routers - these will override duplicate endpoints in api_router
# Create separate modular router to ensure it takes priority
modular_router = APIRouter(prefix="/api")
modular_router.include_router(auth_router)  # ENABLED - modular auth
modular_router.include_router(trader_router)  # ENABLED - modular trader
modular_router.include_router(merchant_router)  # ENABLED - modular merchant
modular_router.include_router(wallet_router)  # ENABLED - modular wallet
modular_router.include_router(rates_router)  # ENABLED - modular rates
modular_router.include_router(admin_router)  # ENABLED - modular admin
modular_router.include_router(usdt_router)  # ENABLED - modular usdt
modular_router.include_router(shop_router)  # ENABLED - modular shop/pay
modular_router.include_router(notifications_router)  # ENABLED - modular notifications
modular_router.include_router(tickets_router)  # ENABLED - modular tickets
modular_router.include_router(disputes_router)  # ENABLED - modular disputes
modular_router.include_router(invoice_router)  # ENABLED - Invoice API v1
if CASINO_AVAILABLE and casino_router:
    modular_router.include_router(casino_router)  # Optional - test casino

# Include modular router FIRST (takes priority over legacy endpoints)
app.include_router(modular_router)

# Legacy router - try to disable and see what breaks
# app.include_router(api_router)

# ================== WEBSOCKET ENDPOINTS ==================

@app.websocket("/api/ws/dispute/{dispute_id}")
async def websocket_dispute_chat(websocket: WebSocket, dispute_id: str, token: str = None):
    """WebSocket endpoint для чата спора"""
    try:
        # Проверяем токен
        if not token:
            logger.warning(f"WebSocket dispute: No token provided")
            await websocket.close(code=4001, reason="No token provided")
            return
        
        # Декодируем JWT
        try:
            from jose import jwt, JWTError
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            user_role = payload.get("role", "user")
        except JWTError as e:
            logger.warning(f"WebSocket dispute: Invalid token - {e}")
            await websocket.close(code=4002, reason="Invalid token")
            return
        
        if not user_id:
            await websocket.close(code=4003, reason="Invalid user")
            return
        
        # Проверяем что спор существует
        dispute = await db.disputes.find_one({"id": dispute_id}, {"_id": 0})
        if not dispute:
            await websocket.close(code=4004, reason="Dispute not found")
            return
        
        # Проверяем доступ к спору
        order = await db.orders.find_one({"id": dispute.get("order_id")}, {"_id": 0})
        
        # Админы и саппорт имеют доступ ко всем спорам
        if user_role not in ["admin", "support"]:
            # Проверяем что пользователь - участник сделки
            has_access = False
            
            # Мерчант
            if order and order.get("merchant_id") == user_id:
                has_access = True
            
            # Трейдер
            if order and order.get("trader_id"):
                trader = await db.traders.find_one({"id": order["trader_id"]}, {"_id": 0, "user_id": 1})
                if trader and trader.get("user_id") == user_id:
                    has_access = True
            
            if not has_access:
                logger.warning(f"WebSocket dispute: User {user_id} has no access to dispute {dispute_id}")
                await websocket.close(code=4005, reason="Access denied")
                return
        
        # Принимаем соединение
        await websocket.accept()
        
        # Определяем роль в споре
        is_buyer = order and order.get("merchant_id") == user_id
        
        # Добавляем в менеджер соединений
        await dispute_chat_manager.connect(websocket, dispute_id, user_id, is_buyer)
        
        logger.info(f"WebSocket dispute: User {user_id} connected to dispute {dispute_id}")
        
        try:
            while True:
                # Ждём сообщения от клиента
                data = await websocket.receive_json()
                
                # Обрабатываем входящие сообщения (например, typing indicator)
                if data.get("type") == "typing":
                    await dispute_chat_manager.broadcast_to_dispute(
                        dispute_id,
                        {"type": "typing", "user_id": user_id},
                        exclude_user_id=user_id
                    )
                    
        except WebSocketDisconnect:
            dispute_chat_manager.disconnect(websocket, dispute_id)
            logger.info(f"WebSocket dispute: User {user_id} disconnected from dispute {dispute_id}")
        except Exception as e:
            logger.error(f"WebSocket dispute error: {e}")
            dispute_chat_manager.disconnect(websocket, dispute_id)
            
    except Exception as e:
        logger.error(f"WebSocket dispute connection error: {e}")
        try:
            await websocket.close(code=4000, reason=str(e))
        except:
            pass

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Добавляем middleware для проверки режима техобслуживания
app.add_middleware(MaintenanceMiddleware)

# ================== BACKGROUND DEPOSIT MONITORING ==================

# Processed transactions cache to avoid duplicates
processed_tx_hashes = set()

async def check_ton_transactions() -> list:
    """
    Проверить входящие USDT (Jetton) транзакции на платформенный кошелёк
    Использует TonAPI для надёжного получения истории Jetton транзакций
    """
    settings = await get_platform_usdt_settings()
    ton_address = settings.get("platform_ton_address", PLATFORM_TON_ADDRESS)
    usdt_contract = settings.get("usdt_contract", USDT_JETTON_CONTRACT) or "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
    
    if not ton_address:
        return []
    
    try:
        # Конвертируем адрес в UQ формат для TonAPI
        from pytoniq_core import Address
        try:
            addr = Address(ton_address)
            api_address = addr.to_str(is_bounceable=False)  # UQ format
        except Exception as e:
            logger.warning(f"Address conversion failed, using as is: {e}")
            api_address = ton_address
        
        logger.debug(f"Checking USDT Jetton history for wallet: {api_address}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Используем TonAPI для получения истории Jetton транзакций
            response = await client.get(
                f"https://tonapi.io/v2/accounts/{api_address}/jettons/{usdt_contract}/history",
                params={"limit": 50}
            )
            
            if response.status_code != 200:
                logger.warning(f"TonAPI Jetton history error: {response.status_code}")
                return []
            
            data = response.json()
            events = data.get("events", [])
            
            logger.debug(f"Found {len(events)} USDT Jetton events")
            
            transactions = []
            
            for event in events:
                event_id = event.get("event_id", "")
                if not event_id:
                    continue
                
                # Используем event_id как tx_hash
                tx_hash = event_id
                
                # Skip already processed
                if tx_hash in processed_tx_hashes:
                    continue
                
                # Check if already in database
                existing = await db.usdt_deposits.find_one({"tx_hash": tx_hash})
                if existing:
                    processed_tx_hashes.add(tx_hash)
                    continue
                
                existing_unident = await db.usdt_unidentified_deposits.find_one({"tx_hash": tx_hash})
                if existing_unident:
                    processed_tx_hashes.add(tx_hash)
                    continue
                
                # Игнорируем scam
                if event.get("is_scam", False):
                    continue
                
                # Обрабатываем actions
                actions = event.get("actions", [])
                
                for action in actions:
                    action_type = action.get("type", "")
                    
                    if action_type == "JettonTransfer":
                        transfer = action.get("JettonTransfer", {})
                        
                        # Проверяем что это ВХОДЯЩИЙ перевод
                        recipient = transfer.get("recipient", {})
                        recipient_address = recipient.get("address", "")
                        
                        # Сравниваем адреса
                        is_incoming = False
                        try:
                            recv_addr = Address(recipient_address)
                            recv_uq = recv_addr.to_str(is_bounceable=False)
                            is_incoming = (recv_uq == api_address or recipient_address == ton_address)
                        except Exception:
                            is_incoming = recipient_address == ton_address
                        
                        if not is_incoming:
                            continue
                        
                        # Сумма USDT (6 decimals)
                        amount_raw = transfer.get("amount", "0")
                        try:
                            amount_usdt = int(amount_raw) / 1_000_000
                        except Exception:
                            amount_usdt = 0
                        
                        if amount_usdt <= 0:
                            continue
                        
                        # Комментарий
                        comment = transfer.get("comment", "") or ""
                        
                        # Отправитель
                        sender = transfer.get("sender", {})
                        sender_address = sender.get("address", "unknown")
                        
                        transactions.append({
                            "tx_hash": tx_hash,
                            "amount_usdt": amount_usdt,
                            "comment": comment.strip().upper(),
                            "sender": sender_address,
                            "timestamp": event.get("timestamp", 0)
                        })
                        
                        logger.info(f"Found USDT transfer: {amount_usdt} USDT, comment: '{comment}', event: {tx_hash[:20]}...")
            
            return transactions
    
    except (httpx.ConnectError, httpx.TimeoutException, OSError, ConnectionError) as e:
        logger.warning(f"Network error fetching TON transactions: {type(e).__name__}")
        return []
    except Exception as e:
        logger.error(f"Error checking TON transactions: {e}")
        return []


# Множество обработанных исходящих tx
processed_outgoing_tx_hashes = set()


async def check_outgoing_transactions() -> list:
    """
    Проверить исходящие USDT транзакции с платформенного кошелька
    Для отслеживания неопознанных выводов (сделанных напрямую с кошелька)
    """
    settings = await get_platform_usdt_settings()
    ton_address = settings.get("platform_ton_address", PLATFORM_TON_ADDRESS)
    usdt_contract = settings.get("usdt_contract", USDT_JETTON_CONTRACT) or "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
    
    if not ton_address:
        return []
    
    try:
        from pytoniq_core import Address
        try:
            addr = Address(ton_address)
            api_address = addr.to_str(is_bounceable=False)
        except:
            api_address = ton_address
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://tonapi.io/v2/accounts/{api_address}/jettons/{usdt_contract}/history",
                params={"limit": 50}
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            events = data.get("events", [])
            
            transactions = []
            
            for event in events:
                event_id = event.get("event_id", "")
                if not event_id:
                    continue
                
                tx_hash = event_id
                
                # Skip already processed
                if tx_hash in processed_outgoing_tx_hashes:
                    continue
                
                # Check database
                existing = await db.usdt_withdrawals.find_one({"tx_hash": tx_hash})
                if existing:
                    processed_outgoing_tx_hashes.add(tx_hash)
                    continue
                
                existing_unident = await db.usdt_unidentified_withdrawals.find_one({"tx_hash": tx_hash})
                if existing_unident:
                    processed_outgoing_tx_hashes.add(tx_hash)
                    continue
                
                if event.get("is_scam", False):
                    continue
                
                for action in event.get("actions", []):
                    if action.get("type") != "JettonTransfer":
                        continue
                    
                    transfer = action.get("JettonTransfer", {})
                    
                    # Check if OUTGOING transfer (sender is our wallet)
                    sender = transfer.get("sender", {})
                    sender_address = sender.get("address", "")
                    
                    is_outgoing = False
                    try:
                        send_addr = Address(sender_address)
                        send_uq = send_addr.to_str(is_bounceable=False)
                        is_outgoing = (send_uq == api_address or sender_address == ton_address)
                    except:
                        is_outgoing = sender_address == ton_address
                    
                    if not is_outgoing:
                        continue
                    
                    # Amount
                    amount_raw = transfer.get("amount", "0")
                    try:
                        amount_usdt = int(amount_raw) / 1_000_000
                    except:
                        amount_usdt = 0
                    
                    if amount_usdt <= 0:
                        continue
                    
                    # Comment
                    comment = transfer.get("comment", "") or ""
                    
                    # Recipient
                    recipient = transfer.get("recipient", {})
                    recipient_address = recipient.get("address", "unknown")
                    
                    transactions.append({
                        "tx_hash": tx_hash,
                        "amount_usdt": amount_usdt,
                        "comment": comment.strip(),
                        "recipient": recipient_address,
                        "timestamp": event.get("timestamp", 0)
                    })
                    
                    logger.info(f"Found OUTGOING USDT: {amount_usdt} USDT to {recipient_address[:20]}..., comment: '{comment}'")
            
            return transactions
            
    except Exception as e:
        logger.error(f"Error checking outgoing transactions: {e}")
        return []


async def process_outgoing_withdrawal(tx: dict) -> dict:
    """
    Обработать исходящую транзакцию с кошелька
    Проверяем есть ли соответствующая заявка на вывод
    """
    tx_hash = tx.get("tx_hash")
    amount_usdt = tx.get("amount_usdt", 0)
    comment = tx.get("comment", "").strip()
    recipient = tx.get("recipient", "")
    
    if tx_hash in processed_outgoing_tx_hashes:
        return {"skipped": True}
    
    # Check if withdrawal exists with this tx_hash
    existing_withdrawal = await db.usdt_withdrawals.find_one({"tx_hash": tx_hash})
    if existing_withdrawal:
        processed_outgoing_tx_hashes.add(tx_hash)
        return {"skipped": True, "reason": "already_processed"}
    
    # Check by recipient address (maybe manual withdrawal)
    withdrawal_by_addr = await db.usdt_withdrawals.find_one({
        "address": {"$regex": recipient[-20:]},  # Match last part of address
        "status": "completed",
        "amount_usdt": amount_usdt
    })
    
    if withdrawal_by_addr:
        processed_outgoing_tx_hashes.add(tx_hash)
        return {"skipped": True, "reason": "matched_by_address"}
    
    # Check if already in unidentified
    existing_unident = await db.usdt_unidentified_withdrawals.find_one({"tx_hash": tx_hash})
    if existing_unident:
        processed_outgoing_tx_hashes.add(tx_hash)
        return {"skipped": True}
    
    # Save as unidentified withdrawal
    unidentified = {
        "id": generate_id("uwd"),
        "tx_hash": tx_hash,
        "amount_usdt": amount_usdt,
        "comment": comment,
        "recipient": recipient,
        "status": "unidentified",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.usdt_unidentified_withdrawals.insert_one(unidentified)
    processed_outgoing_tx_hashes.add(tx_hash)
    
    logger.warning(f"Unidentified withdrawal: {amount_usdt} USDT to {recipient[:30]}..., comment: '{comment}'")
    
    # Уведомляем админов о неопознанном выводе
    asyncio.create_task(notify_unidentified_withdrawal({
        "amount": amount_usdt,
        "comment": comment,
        "to_address": recipient,
        "tx_hash": tx_hash
    }))
    
    return {"unidentified": True, "tx_hash": tx_hash}


async def process_ton_deposit(tx: dict) -> dict:
    """
    Обработать входящую USDT транзакцию
    Ищем заявку на депозит по комментарию
    """
    tx_hash = tx.get("tx_hash")
    amount_usdt = tx.get("amount_usdt", 0)
    comment = tx.get("comment", "").strip()
    
    # Проверяем дубликат перед обработкой
    if tx_hash in processed_tx_hashes:
        return {"skipped": True, "reason": "already_in_memory"}
    
    existing_deposit = await db.usdt_deposits.find_one({"tx_hash": tx_hash})
    if existing_deposit:
        processed_tx_hashes.add(tx_hash)
        return {"skipped": True, "reason": "already_credited"}
    
    existing_unident = await db.usdt_unidentified_deposits.find_one({"tx_hash": tx_hash})
    if existing_unident:
        processed_tx_hashes.add(tx_hash)
        return {"skipped": True, "reason": "already_unidentified"}
    
    if not comment or amount_usdt <= 0:
        # Неопознанный депозит - сохраняем для ручной обработки
        unidentified = {
            "id": generate_id("uid"),
            "tx_hash": tx_hash,
            "amount_usdt": amount_usdt,
            "comment": comment,
            "sender": tx.get("sender"),
            "status": "unidentified",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.usdt_unidentified_deposits.insert_one(unidentified)
        processed_tx_hashes.add(tx_hash)
        logger.warning(f"Unidentified deposit: {amount_usdt} USDT, comment: '{comment}'")
        return {"unidentified": True, "tx_hash": tx_hash}
    
    # Ищем заявку на депозит по комментарию
    deposit_request = await db.deposit_requests.find_one({
        "deposit_comment": comment,
        "status": "pending"
    }, {"_id": 0})
    
    if not deposit_request:
        # Попробуем найти по request_id
        deposit_request = await db.deposit_requests.find_one({
            "request_id": comment,
            "status": "pending"
        }, {"_id": 0})
    
    if deposit_request:
        processed_tx_hashes.add(tx_hash)
        return {
            "deposit_request": deposit_request,
            "amount_usdt": amount_usdt,
            "tx_hash": tx_hash,
            "comment": comment
        }
    
    # Не нашли заявку - сохраняем как неопознанный
    unidentified = {
        "id": generate_id("uid"),
        "tx_hash": tx_hash,
        "amount_usdt": amount_usdt,
        "comment": comment,
        "sender": tx.get("sender"),
        "status": "unidentified",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.usdt_unidentified_deposits.insert_one(unidentified)
    processed_tx_hashes.add(tx_hash)
    logger.warning(f"No matching deposit request for comment: '{comment}', amount: {amount_usdt} USDT")
    
    # Уведомляем админов о неопознанном депозите
    asyncio.create_task(notify_unidentified_deposit({
        "amount": amount_usdt,
        "comment": comment,
        "from_address": tx.get("sender", ""),
        "tx_hash": tx_hash
    }))
    
    return {"unidentified": True, "tx_hash": tx_hash, "comment": comment}


async def send_usdt_withdrawal(to_address: str, amount_usdt: float, withdrawal_id: str) -> dict:
    """
    Отправить USDT на указанный адрес через TON сеть
    Использует TonAPI для получения Jetton wallet и tonutils для отправки
    """
    import secrets
    
    # Получаем конфигурацию из platform_settings
    config = await db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
    
    if not config:
        return {"success": False, "error": "Автовывод не настроен"}
    
    seed_phrase = config.get("seed_phrase")
    wallet_address = config.get("wallet_address")
    usdt_contract = config.get("usdt_contract", "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs")
    toncenter_api_key = config.get("toncenter_api_key", "")
    
    if not seed_phrase:
        return {"success": False, "error": "Seed phrase не настроен"}
    
    if not wallet_address:
        return {"success": False, "error": "Адрес кошелька не настроен"}
    
    if not toncenter_api_key:
        return {"success": False, "error": "Toncenter API ключ не настроен"}
    
    try:
        from tonutils.client import ToncenterV3Client
        from tonutils.wallet import WalletV5R1
        from pytoniq_core import Address, begin_cell
        
        # Создаём клиент Toncenter
        ton_client = ToncenterV3Client(
            api_key=toncenter_api_key,
            is_testnet=False,
            rps=5
        )
        
        # Создаём кошелёк из seed phrase
        mnemonic_list = seed_phrase.strip().split()
        
        if len(mnemonic_list) != 24:
            return {"success": False, "error": f"Неверный seed phrase: ожидается 24 слова, получено {len(mnemonic_list)}"}
        
        # WalletV5R1.from_mnemonic - SYNC function
        wallet, public_key, private_key, _ = WalletV5R1.from_mnemonic(
            client=ton_client,
            mnemonic=mnemonic_list
        )
        
        wallet_addr_str = wallet.address.to_str()
        wallet_addr_uq = wallet.address.to_str(is_bounceable=False)
        logger.info(f"Wallet loaded: {wallet_addr_str} (UQ: {wallet_addr_uq})")
        
        # Получаем Jetton Wallet адрес через TonAPI (надёжнее чем TonCenter)
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"https://tonapi.io/v2/accounts/{wallet_addr_uq}/jettons"
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"TonAPI error: {response.status_code}"}
            
            data = response.json()
            balances = data.get("balances", [])
            
            # Ищем USDT
            sender_jetton_wallet = None
            balance = 0
            for b in balances:
                jetton = b.get("jetton", {})
                symbol = jetton.get("symbol", "").upper()
                name = jetton.get("name", "").upper()
                if symbol == "USD₮" or "USDT" in symbol or "TETHER" in name:
                    wallet_info = b.get("wallet_address", {})
                    sender_jetton_wallet = wallet_info.get("address")
                    balance = int(b.get("balance", "0"))
                    break
            
            if not sender_jetton_wallet:
                return {"success": False, "error": "USDT кошелёк не найден. Убедитесь что на кошельке есть USDT."}
            
            hot_balance = balance / 1_000_000
            logger.info(f"Sender Jetton Wallet: {sender_jetton_wallet}, Balance: {hot_balance} USDT")
            
            # Проверяем баланс
            amount_nano = int(amount_usdt * 1_000_000)
            if balance < amount_nano:
                return {
                    "success": False,
                    "error": f"Недостаточно USDT. Баланс: {hot_balance:.2f}, требуется: {amount_usdt:.2f}",
                    "hot_wallet_balance": hot_balance,
                    "required": amount_usdt
                }
        
        # Формируем Transfer Body по стандарту TEP-74
        destination_addr = Address(to_address)
        sender_jetton_addr = Address(sender_jetton_wallet)
        
        # TEP-74 Jetton Transfer
        query_id = secrets.randbits(64)
        
        transfer_body = (
            begin_cell()
            .store_uint(0xf8a7ea5, 32)   # op::transfer
            .store_uint(query_id, 64)     # query_id
            .store_coins(amount_nano)     # amount
            .store_address(destination_addr)   # destination
            .store_address(wallet.address)     # response_destination
            .store_bit(0)                 # no custom_payload
            .store_coins(1)               # forward_ton_amount (1 nanoton)
            .store_bit(0)                 # no forward_payload
            .end_cell()
        )
        
        # Отправляем на наш Jetton Wallet (не на мастер контракт!)
        tx_hash = await wallet.transfer(
            destination=sender_jetton_addr,
            amount=0.05,  # TON для газа
            body=transfer_body
        )
        
        tx_hash_str = str(tx_hash) if tx_hash else "pending"
        logger.info(f"✅ USDT transfer sent! TX: {tx_hash_str}")
        
        return {
            "success": True,
            "tx_hash": tx_hash_str,
            "amount_usdt": amount_usdt,
            "to_address": to_address,
            "real_transaction": True
        }
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return {"success": False, "error": f"Missing dependency: {str(e)}"}
    except Exception as e:
        logger.error(f"USDT transfer failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_hot_wallet_balance() -> float:
    """Получить баланс USDT на горячем кошельке"""
    try:
        # Try platform_settings first (main config)
        config = await db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
        
        if not config:
            # Fallback to auto_withdraw_config collection
            config = await db.auto_withdraw_config.find_one({"active": True}, {"_id": 0})
        
        if not config:
            return 0.0
        
        wallet_address = config.get("wallet_address")
        # Use correct USDT contract
        usdt_contract = config.get("usdt_contract", "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs")
        api_key = config.get("toncenter_api_key", TONCENTER_API_KEY)
        
        if not wallet_address or not api_key:
            return 0.0
        
        async with httpx.AsyncClient(timeout=15) as client:
            jetton_wallet_url = f"https://toncenter.com/api/v3/jetton/wallets?owner_address={wallet_address}&jetton_address={usdt_contract}&limit=1"
            headers = {"X-API-Key": api_key}
            
            resp = await client.get(jetton_wallet_url, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                wallets = data.get("jetton_wallets", [])
                
                if wallets:
                    balance_raw = int(wallets[0].get("balance", "0"))
                    return balance_raw / 1_000_000
        
        return 0.0
    except Exception as e:
        logger.error(f"Error getting hot wallet balance: {e}")
        return 0.0


# Флаг для остановки фоновой задачи
deposit_monitor_running = False

async def deposit_monitor_task():
    """Фоновая задача для автоматической проверки депозитов каждые 30 секунд"""
    global deposit_monitor_running
    deposit_monitor_running = True
    logger.info("🔄 Deposit monitor started - checking every 30 seconds")
    
    # Увеличенная задержка перед первой проверкой (ждём пока DNS и MongoDB будут готовы)
    await asyncio.sleep(60)
    
    while deposit_monitor_running:
        try:
            # Получаем настройки
            settings = await get_platform_usdt_settings()
            ton_address = settings.get("platform_ton_address", PLATFORM_TON_ADDRESS)
            api_key = settings.get("toncenter_api_key", TONCENTER_API_KEY)
            
            if not ton_address or not api_key:
                logger.warning("TON address or API key not configured, skipping check")
                await asyncio.sleep(30)
                continue
            
            # Проверяем транзакции с обработкой сетевых ошибок
            try:
                transactions = await check_ton_transactions()
            except (httpx.ConnectError, httpx.TimeoutException, httpcore.ConnectError, OSError, ConnectionError) as e:
                logger.warning(f"Network error checking TON transactions (will retry): {type(e).__name__}")
                await asyncio.sleep(30)
                continue
            
            if transactions:
                logger.info(f"Found {len(transactions)} USDT Jetton events, processing...")
                
            processed_count = 0
            for tx in transactions:
                result = await process_ton_deposit(tx)
                if result and result.get("deposit_request"):
                    # Нашли заявку по комментарию - зачисляем
                    dep_req = result["deposit_request"]
                    user_id = dep_req["user_id"]
                    amount = result["amount_usdt"]
                    
                    # Без ограничения минимальной суммы - принимаем любую
                    
                    # Создаём запись депозита
                    deposit = {
                        "id": generate_id("dep"),
                        "user_id": user_id,
                        "tx_hash": result["tx_hash"],
                        "amount_usdt": amount,
                        "request_id": dep_req["request_id"],
                        "deposit_comment": result["comment"],
                        "status": "confirmed",
                        "currency": "USDT",
                        "network": "TON",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.usdt_deposits.insert_one(deposit)
                    
                    # Зачисляем на баланс в usdt_wallets (upsert)
                    await db.usdt_wallets.update_one(
                        {"user_id": user_id},
                        {
                            "$inc": {
                                "balance_usdt": amount,
                                "total_deposited_usdt": amount
                            },
                            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
                            "$setOnInsert": {"user_id": user_id, "created_at": datetime.now(timezone.utc).isoformat()}
                        },
                        upsert=True
                    )
                    
                    # ВАЖНО: Также обновляем wallets (основной баланс трейдера/мерчанта)
                    wallet_result = await db.wallets.update_one(
                        {"user_id": user_id},
                        {
                            "$inc": {
                                "available_balance_usdt": amount,
                                "total_deposited_usdt": amount
                            },
                            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                        }
                    )
                    if wallet_result.modified_count == 0:
                        logger.warning(f"Wallet not found for user {user_id}, creating new wallet")
                        await db.wallets.insert_one({
                            "id": f"wlt_{user_id}",
                            "user_id": user_id,
                            "available_balance_usdt": amount,
                            "locked_balance_usdt": 0,
                            "earned_balance_usdt": 0,
                            "pending_withdrawal_usdt": 0,
                            "total_deposited_usdt": amount,
                            "total_withdrawn_usdt": 0
                        })
                    
                    # Обновляем статус заявки
                    await db.deposit_requests.update_one(
                        {"request_id": dep_req["request_id"]},
                        {"$set": {
                            "status": "credited",
                            "tx_hash": result["tx_hash"],
                            "actual_amount_usdt": amount,
                            "credited_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    
                    processed_count += 1
                    logger.info(f"✅ USDT Deposit credited: {amount} USDT to user {user_id}, comment: {result['comment']}")
                    
                    # Уведомляем пользователя о зачислении
                    asyncio.create_task(notify_deposit_credited(user_id, amount))
                
                elif result and not result.get("deposit_request") and result.get("amount_usdt", 0) > 0:
                    # Неопознанный депозит (без комментария или с неверным)
                    existing = await db.usdt_unidentified_deposits.find_one({"tx_hash": result["tx_hash"]})
                    if not existing:
                        unidentified = {
                            "id": generate_id("uid"),
                            "tx_hash": result["tx_hash"],
                            "amount_usdt": result["amount_usdt"],
                            "comment": result.get("comment"),
                            "sender_address": result.get("sender_address", "unknown"),
                            "reason": "no_matching_comment",
                            "status": "pending",
                            "currency": "USDT",
                            "network": "TON",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.usdt_unidentified_deposits.insert_one(unidentified)
                        
                        # Уведомление админу
                        await create_admin_notification(
                            "new_unidentified_deposit",
                            f"Неопознанный депозит USDT: {result['amount_usdt']:.2f} USDT",
                            {"deposit_id": unidentified["id"], "amount": result["amount_usdt"], "tx_hash": result["tx_hash"]}
                        )
                        
                        logger.warning(f"⚠️ Unidentified USDT deposit: {result['amount_usdt']} USDT, tx: {result['tx_hash']}")
            
            if processed_count > 0:
                logger.info(f"✅ Processed {processed_count} deposits this cycle")
            
            # ========================================
            # ПРОВЕРЯЕМ ИСХОДЯЩИЕ ТРАНЗАКЦИИ (неопознанные выводы)
            # ========================================
            try:
                outgoing_transactions = await check_outgoing_transactions()
                
                for tx in outgoing_transactions:
                    await process_outgoing_withdrawal(tx)
                    
            except Exception as e:
                logger.warning(f"Error checking outgoing transactions: {e}")
                
        except (ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect) as e:
            # MongoDB connection issues - ожидаемо в начале работы или при проблемах с сетью
            logger.warning(f"⚠️ MongoDB connection issue in deposit monitor (will retry): {type(e).__name__}")
        except Exception as e:
            # Другие ошибки - проверяем на MongoDB-related
            error_str = str(e).lower()
            if any(x in error_str for x in ["timed out", "no replica set", "no primary", "connection", "network", "dns", "resolution"]):
                logger.warning(f"⚠️ Network issue in deposit monitor (will retry): {type(e).__name__}")
            else:
                logger.error(f"❌ Error in deposit monitor: {e}")
        
        # Ждём 30 секунд перед следующей проверкой
        await asyncio.sleep(30)

async def cleanup_expired_requests():
    """Фоновая задача для очистки и синхронизации (каждую минуту)"""
    logger.info("🧹 Cleanup & sync task started - running every 60 seconds")
    
    # Задержка перед первым запуском
    await asyncio.sleep(90)
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            
            # ОТКЛЮЧЕНО: sync_all_wallets() вызывал проблемы с балансами
            # wallets collection - единственный источник истины
            
            # ========================================
            # AUTO-CANCEL ORDERS NOT ACCEPTED BY TRADER (10 minutes)
            # ========================================
            ten_minutes_ago = (now - timedelta(minutes=10)).isoformat()
            
            # Find orders with status "new" or "waiting_requisites" older than 10 minutes
            expired_orders = await db.orders.find({
                "status": {"$in": ["new", "waiting_requisites"]},
                "trader_id": {"$in": [None, ""]},  # Not taken by trader
                "created_at": {"$lt": ten_minutes_ago}
            }).to_list(100)
            
            for order in expired_orders:
                try:
                    # Cancel the order
                    await db.orders.update_one(
                        {"id": order["id"], "status": {"$in": ["new", "waiting_requisites"]}},
                        {
                            "$set": {
                                "status": "expired",
                                "cancelled_at": now.isoformat(),
                                "cancel_reason": "auto_expired_no_trader"
                            }
                        }
                    )
                    logger.info(f"⏰ Auto-cancelled order {order['id']} - not accepted within 10 minutes")
                    
                    # Notify merchant about cancellation (optional)
                    try:
                        merchant = await db.merchants.find_one({"id": order.get("merchant_id")})
                        if merchant:
                            await db.notifications.insert_one({
                                "id": generate_id("ntf_"),
                                "user_id": merchant.get("user_id"),
                                "type": "order_expired",
                                "title": "Заказ истёк",
                                "message": f"Заказ #{order['id'][-8:]} автоматически отменён - не принят трейдером в течение 10 минут",
                                "data": {"order_id": order["id"]},
                                "read": False,
                                "created_at": now.isoformat()
                            })
                            
                            # Отправляем webhook мерчанту
                            from routers.invoice_api import send_webhook_notification
                            asyncio.create_task(send_webhook_notification(order["id"], "expired", {
                                "reason": "auto_expired_no_trader"
                            }))
                    except Exception as notify_err:
                        logger.warning(f"Failed to notify merchant about expired order: {notify_err}")
                        
                except Exception as order_err:
                    logger.error(f"Failed to auto-cancel order {order.get('id')}: {order_err}")
            
            if expired_orders:
                logger.info(f"⏰ Auto-cancelled {len(expired_orders)} orders not accepted within 10 minutes")
            
            # ========================================
            # AUTO-CANCEL ORDERS NOT PAID BY BUYER (30 minutes after trader accepted)
            # ========================================
            thirty_minutes_ago = (now - timedelta(minutes=30)).isoformat()
            
            # Find orders accepted by trader but not paid within 30 minutes
            # Включаем также waiting_requisites - трейдер взял, но не выдал реквизиты
            unpaid_orders = await db.orders.find({
                "status": {"$in": ["waiting_buyer_confirmation", "pending", "waiting_payment", "waiting_requisites"]},
                "trader_id": {"$exists": True, "$ne": None},
                "$or": [
                    {"taken_at": {"$lt": thirty_minutes_ago}},
                    {"accepted_at": {"$lt": thirty_minutes_ago}},
                    {"trader_accepted_at": {"$lt": thirty_minutes_ago}}
                ]
            }).to_list(100)
            
            for order in unpaid_orders:
                try:
                    # Возвращаем USDT трейдеру из locked в available
                    trader = await db.traders.find_one({"id": order.get("trader_id")})
                    if trader:
                        amount_usdt = order.get("amount_usdt", 0)
                        await db.wallets.update_one(
                            {"user_id": trader.get("user_id")},
                            {"$inc": {
                                "locked_balance_usdt": -round(amount_usdt, 4),
                                "available_balance_usdt": round(amount_usdt, 4)
                            }}
                        )
                        
                        # Исправляем микро-остатки
                        wallet_check = await db.wallets.find_one(
                            {"user_id": trader.get("user_id")}, 
                            {"_id": 0, "locked_balance_usdt": 1}
                        )
                        if wallet_check:
                            locked_val = wallet_check.get("locked_balance_usdt", 0)
                            if locked_val < 0 or (0 < locked_val < 0.01):
                                await db.wallets.update_one(
                                    {"user_id": trader.get("user_id")},
                                    {"$set": {"locked_balance_usdt": 0}}
                                )
                    
                    # Cancel the order
                    await db.orders.update_one(
                        {"id": order["id"]},
                        {
                            "$set": {
                                "status": "cancelled",
                                "cancelled_at": now.isoformat(),
                                "cancel_reason": "auto_cancelled_not_paid_30min"
                            }
                        }
                    )
                    logger.info(f"⏰ Auto-cancelled order {order['id']} - not paid within 30 minutes after trader accepted")
                    
                    # Отправляем webhook мерчанту
                    from routers.invoice_api import send_webhook_notification
                    asyncio.create_task(send_webhook_notification(order["id"], "expired", {
                        "reason": "auto_cancelled_not_paid_30min"
                    }))
                    
                except Exception as order_err:
                    logger.error(f"Failed to auto-cancel unpaid order {order.get('id')}: {order_err}")
            
            if unpaid_orders:
                logger.info(f"⏰ Auto-cancelled {len(unpaid_orders)} orders not paid within 30 minutes")
            
            # ========================================
            # MONITOR LOCKED BALANCE INCONSISTENCIES (только логирование!)
            # ========================================
            try:
                active_order_statuses = ["pending", "waiting_buyer_confirmation", "waiting_trader_confirmation", "waiting_requisites", "dispute"]
                
                traders_with_locked = await db.wallets.find(
                    {"locked_balance_usdt": {"$gt": 0.01}},
                    {"_id": 0, "user_id": 1, "locked_balance_usdt": 1}
                ).to_list(100)
                
                for wallet in traders_with_locked:
                    user_id = wallet.get("user_id")
                    locked_amount = wallet.get("locked_balance_usdt", 0)
                    
                    trader = await db.traders.find_one({"user_id": user_id}, {"_id": 0, "id": 1})
                    if not trader:
                        continue
                    
                    trader_id = trader.get("id")
                    
                    active_orders = await db.orders.find(
                        {"trader_id": trader_id, "status": {"$in": active_order_statuses}},
                        {"_id": 0, "amount_usdt": 1, "id": 1}
                    ).to_list(50)
                    
                    total_active_usdt = sum(o.get("amount_usdt", 0) for o in active_orders)
                    
                    # Только логируем несоответствие, НЕ исправляем автоматически!
                    if len(active_orders) == 0 and locked_amount > 0.01:
                        logger.warning(f"⚠️ ALERT: Trader {trader_id} has {locked_amount} USDT locked but NO active orders! Manual check required.")
                    elif locked_amount > total_active_usdt + 1:  # допуск 1 USDT на погрешность
                        logger.warning(f"⚠️ ALERT: Trader {trader_id} locked={locked_amount} but active orders need only {total_active_usdt}. Diff: {locked_amount - total_active_usdt}")
            except Exception as monitor_err:
                logger.error(f"Monitor locked balance error: {monitor_err}")
            
            # ========================================
            # CLEANUP DEPOSIT REQUESTS
            # ========================================
            
            # Удаляем просроченные заявки на депозит (старше 24 часов и не зачисленные)
            expired_deposits = await db.deposit_requests.delete_many({
                "status": {"$in": ["pending", "expired", "cancelled"]},
                "created_at": {"$lt": (now - timedelta(hours=24)).isoformat()}
            })
            if expired_deposits.deleted_count > 0:
                logger.info(f"🧹 Deleted {expired_deposits.deleted_count} expired deposit requests")
            
            # Удаляем отменённые/отклонённые выводы старше 7 дней
            expired_withdrawals = await db.usdt_withdrawals.delete_many({
                "status": {"$in": ["rejected", "cancelled"]},
                "created_at": {"$lt": (now - timedelta(days=7)).isoformat()}
            })
            if expired_withdrawals.deleted_count > 0:
                logger.info(f"🧹 Deleted {expired_withdrawals.deleted_count} old rejected/cancelled withdrawals")
            
            # Помечаем как expired заявки старше 2 часов
            await db.deposit_requests.update_many(
                {
                    "status": "pending",
                    "expires_at": {"$lt": now.isoformat()}
                },
                {"$set": {"status": "expired"}}
            )
            
        except (ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect) as e:
            # MongoDB connection issues - ожидаемо при проблемах с сетью
            logger.warning(f"⚠️ MongoDB connection issue in cleanup task (will retry): {type(e).__name__}")
        except Exception as e:
            # Другие ошибки - проверяем на MongoDB-related
            error_str = str(e).lower()
            if any(x in error_str for x in ["timed out", "no replica set", "no primary", "connection", "network", "dns", "resolution"]):
                logger.warning(f"⚠️ Network issue in cleanup task (will retry): {type(e).__name__}")
            else:
                logger.error(f"❌ Error in cleanup task: {e}")
        
        # Ждём 5 минут
        await asyncio.sleep(60)  # Каждую минуту

@app.on_event("startup")
async def startup_event():
    """Запуск фоновых задач при старте сервера"""
    logger.info("🚀 Starting BITARBITR P2P Platform")
    
    # Ждём пока MongoDB будет доступен (для Atlas может потребоваться время)
    max_retries = 5
    for i in range(max_retries):
        try:
            # Проверяем подключение к MongoDB
            await client.admin.command('ping')
            logger.info("✅ MongoDB connection established")
            break
        except Exception as e:
            logger.warning(f"⚠️ Waiting for MongoDB connection (attempt {i+1}/{max_retries}): {type(e).__name__}")
            if i < max_retries - 1:
                await asyncio.sleep(5)
            else:
                logger.error("❌ Could not connect to MongoDB after retries, starting anyway...")
    
    # Запускаем фоновый мониторинг депозитов с задержкой
    asyncio.create_task(deposit_monitor_task())
    
    # Запускаем очистку просроченных заявок
    asyncio.create_task(cleanup_expired_requests())
    
    logger.info("✅ All background tasks started")

@app.on_event("shutdown")
async def shutdown_db_client():
    global deposit_monitor_running
    deposit_monitor_running = False
    logger.info("🛑 Shutting down deposit monitor")
    client.close()
