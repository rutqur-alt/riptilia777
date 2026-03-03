#!/usr/bin/env python3
"""
Полная очистка и создание чистых тестовых данных
"""
import asyncio
import secrets
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
import bcrypt

import os
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "bitarbitr")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def generate_id(prefix: str) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(3).upper()
    return f"{prefix}_{date_part}_{random_part}"

async def reset_database():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🗑️ ОЧИСТКА БАЗЫ ДАННЫХ...")
    
    # Удаляем все данные
    await db.users.delete_many({})
    await db.merchants.delete_many({})
    await db.traders.delete_many({})
    await db.wallets.delete_many({})
    await db.payment_details.delete_many({})
    await db.orders.delete_many({})
    await db.disputes.delete_many({})
    await db.dispute_messages.delete_many({})
    await db.merchant_invoices.delete_many({})
    await db.callback_queue.delete_many({})
    await db.notifications.delete_many({})
    
    print("✅ База очищена\n")
    
    # ============ АДМИН ============
    admin_id = generate_id("usr")
    admin = {
        "id": admin_id,
        "login": "admin",
        "nickname": "Администратор",
        "password_hash": hash_password("000000"),
        "role": "admin",
        "is_active": True,
        "is_verified": True,
        "approval_status": "approved",
        "two_factor_enabled": False,
        "telegram_id": None,
        "referral_code": secrets.token_hex(4).upper(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(admin)
    print("✅ АДМИН создан: login=admin, password=000000")
    
    # ============ ТРЕЙДЕР ============
    trader_user_id = generate_id("usr")
    trader_id = generate_id("trd")
    wallet_id = generate_id("wal")
    
    trader_user = {
        "id": trader_user_id,
        "login": "111",
        "nickname": "Трейдер",
        "password_hash": hash_password("000000"),
        "role": "trader",
        "is_active": True,
        "is_verified": True,
        "approval_status": "approved",
        "two_factor_enabled": False,
        "telegram_id": None,
        "referral_code": secrets.token_hex(4).upper(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(trader_user)
    
    trader = {
        "id": trader_id,
        "user_id": trader_user_id,
        "rating": 5.0,
        "total_deals": 0,
        "successful_deals": 0,
        "disputed_deals": 0,
        "total_volume_rub": 0.0,
        "total_commission_usdt": 0.0,
        "is_available": True,
        "auto_mode": True,
        "auto_accept": True,
        "min_deal_amount_rub": 100.0,
        "max_deal_amount_rub": 500000.0,
        "fee_percent": 10.0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.traders.insert_one(trader)
    
    wallet = {
        "id": wallet_id,
        "user_id": trader_user_id,
        "address": f"UQ{secrets.token_hex(16).upper()}",
        "available_balance_usdt": 50000.0,
        "locked_balance_usdt": 0.0,
        "pending_balance_usdt": 0.0,
        "total_deposited_usdt": 50000.0,
        "total_withdrawn_usdt": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.wallets.insert_one(wallet)
    
    # Реквизиты трейдера - Карта Сбербанк
    payment_card = {
        "id": generate_id("pay"),
        "trader_id": trader_id,
        "payment_type": "card",
        "card_number": "2200700111112222",
        "phone_number": None,
        "bank_name": "Сбербанк",
        "holder_name": "ИВАНОВ ИВАН",
        "min_amount_rub": 100.0,
        "max_amount_rub": 300000.0,
        "daily_limit_rub": 1000000.0,
        "used_today_rub": 0.0,
        "priority": 10,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payment_details.insert_one(payment_card)
    
    # Реквизиты трейдера - СБП Тинькофф
    payment_sbp = {
        "id": generate_id("pay"),
        "trader_id": trader_id,
        "payment_type": "sbp",
        "card_number": None,
        "phone_number": "+79001234567",
        "bank_name": "Тинькофф",
        "holder_name": "ИВАНОВ ИВАН",
        "min_amount_rub": 100.0,
        "max_amount_rub": 100000.0,
        "daily_limit_rub": 500000.0,
        "used_today_rub": 0.0,
        "priority": 5,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payment_details.insert_one(payment_sbp)
    
    print(f"✅ ТРЕЙДЕР создан: login=111, password=000000")
    print(f"   ID: {trader_id}")
    print(f"   Баланс: 50000 USDT")
    print(f"   Карта: 2200 7001 1111 2222 (Сбербанк)")
    print(f"   СБП: +7 900 123-45-67 (Тинькофф)")
    
    # ============ МЕРЧАНТ ============
    merchant_user_id = generate_id("usr")
    merchant_id = generate_id("mrc")
    merchant_wallet_id = generate_id("wal")
    api_key = f"sk_live_{secrets.token_hex(24)}"
    secret_key = secrets.token_hex(32)
    
    merchant_user = {
        "id": merchant_user_id,
        "login": "222",
        "nickname": "Мерчант",
        "password_hash": hash_password("000000"),
        "role": "merchant",
        "is_active": True,
        "is_verified": True,
        "approval_status": "approved",
        "two_factor_enabled": False,
        "telegram_id": None,
        "referral_code": secrets.token_hex(4).upper(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(merchant_user)
    
    merchant = {
        "id": merchant_id,
        "user_id": merchant_user_id,
        "company_name": "Test Shop",
        "website_url": "https://shop.example.com",
        "api_key": api_key,
        "api_secret": secret_key,
        "secret_key": secret_key,
        "is_approved": True,
        "daily_limit_rub": 10000000.0,
        "total_processed_rub": 0.0,
        "total_processed_usdt": 0.0,
        "commission_percent": 5.0,
        "fee_model": "merchant_pays",
        "total_fee_percent": 5.0,
        "trader_fee_percent": 3.0,
        "marker_amount": 12.0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.merchants.insert_one(merchant)
    
    merchant_wallet = {
        "id": merchant_wallet_id,
        "user_id": merchant_user_id,
        "address": f"UQ{secrets.token_hex(16).upper()}",
        "available_balance_usdt": 10000.0,
        "locked_balance_usdt": 0.0,
        "pending_balance_usdt": 0.0,
        "total_deposited_usdt": 10000.0,
        "total_withdrawn_usdt": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.wallets.insert_one(merchant_wallet)
    
    print(f"\n✅ МЕРЧАНТ создан: login=222, password=000000")
    print(f"   ID: {merchant_id}")
    print(f"   API Key: {api_key}")
    print(f"   Secret: {secret_key}")
    
    # ============ СОЗДАЁМ 5 СДЕЛОК (3 со спорами) ============
    print("\n📦 СОЗДАНИЕ ТЕСТОВЫХ СДЕЛОК...\n")
    
    now = datetime.now(timezone.utc)
    
    # Сделка 1 - Ожидает оплаты
    order1_id = "ORD-0001"
    order1 = {
        "id": order1_id,
        "merchant_id": merchant_id,
        "trader_id": trader_id,
        "external_id": "SHOP-0001",
        "amount_rub": 1500.0,
        "amount_usdt": 20.0,
        "exchange_rate": 75.0,
        "payment_method": "card",
        "payment_details": {
            "type": "card",
            "bank_name": "Сбербанк",
            "card_number": "2200700111112222",
            "holder_name": "ИВАНОВ ИВАН",
            "comment": "ORD-0001"
        },
        "status": "waiting_buyer_confirmation",
        "callback_url": "https://shop.example.com/callback",
        "dispute_token": secrets.token_urlsafe(32),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat()
    }
    await db.orders.insert_one(order1)
    print(f"✅ Сделка {order1_id}: 1500₽ - Ожидает оплаты")
    
    # Сделка 2 - Завершена
    order2_id = "ORD-0002"
    order2 = {
        "id": order2_id,
        "merchant_id": merchant_id,
        "trader_id": trader_id,
        "external_id": "SHOP-0002",
        "amount_rub": 3000.0,
        "amount_usdt": 40.0,
        "exchange_rate": 75.0,
        "payment_method": "sbp",
        "payment_details": {
            "type": "sbp",
            "bank_name": "Тинькофф",
            "phone_number": "+79001234567",
            "holder_name": "ИВАНОВ ИВАН",
            "comment": "ORD-0002"
        },
        "status": "completed",
        "callback_url": "https://shop.example.com/callback",
        "dispute_token": secrets.token_urlsafe(32),
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "completed_at": (now - timedelta(hours=1)).isoformat()
    }
    await db.orders.insert_one(order2)
    print(f"✅ Сделка {order2_id}: 3000₽ - Завершена")
    
    # Сделки 3, 4, 5 - Споры
    dispute_orders = [
        {"id": "ORD-0003", "amount": 2500, "reason": "Клиент оплатил, но деньги не пришли на карту"},
        {"id": "ORD-0004", "amount": 5000, "reason": "Перевод завис, требуется проверка"},
        {"id": "ORD-0005", "amount": 7500, "reason": "СБП перевод не дошёл до получателя"},
    ]
    
    for i, data in enumerate(dispute_orders, 3):
        order_id = data["id"]
        dispute_token = secrets.token_urlsafe(32)
        dispute_id = f"DSP-{i:04d}"
        
        order = {
            "id": order_id,
            "merchant_id": merchant_id,
            "trader_id": trader_id,
            "external_id": f"SHOP-{i:04d}",
            "original_amount_rub": float(data["amount"]) - 10,  # Original amount without marker
            "amount_rub": float(data["amount"]),
            "amount_usdt": round(data["amount"] / 75.0, 2),
            "exchange_rate": 75.0,
            "marker": 10.0,
            "marker_rub": 10.0,
            "fee_model": "merchant_pays",
            "payment_method": "card" if i % 2 == 1 else "sbp",
            "payment_details": {
                "type": "card" if i % 2 == 1 else "sbp",
                "bank_name": "Сбербанк" if i % 2 == 1 else "Тинькофф",
                "card_number": "2200700111112222" if i % 2 == 1 else None,
                "phone_number": None if i % 2 == 1 else "+79001234567",
                "holder_name": "ИВАНОВ ИВАН",
                "comment": order_id
            },
            "status": "disputed",
            "callback_url": "https://shop.example.com/callback",
            "dispute_token": dispute_token,
            "dispute_id": dispute_id,
            "dispute_url": f"https://p2p-gateway.preview.emergentagent.com/dispute/{dispute_token}",
            "created_at": (now - timedelta(hours=i)).isoformat()
        }
        await db.orders.insert_one(order)
        
        dispute = {
            "id": dispute_id,
            "order_id": order_id,
            "merchant_id": merchant_id,
            "trader_id": trader_id,
            "dispute_token": dispute_token,
            "public_token": dispute_token,
            "reason": data["reason"],
            "status": "open",
            "initiated_by": "buyer",
            "created_at": (now - timedelta(hours=i) + timedelta(minutes=10)).isoformat(),
            "updated_at": now.isoformat()
        }
        await db.disputes.insert_one(dispute)
        
        # Добавляем сообщения в чат спора
        messages = [
            {"role": "buyer", "name": "Покупатель", "text": f"Здравствуйте! Я оплатил {data['amount']}₽, но статус не обновился. Прикрепляю скриншот чека."},
            {"role": "trader", "name": "Трейдер", "text": "Добрый день! Проверяю поступление на счёт..."},
            {"role": "moderator", "name": "Модератор", "text": "Подключился к рассмотрению. Ожидаю подтверждения от обеих сторон."},
        ]
        
        for j, msg in enumerate(messages):
            await db.dispute_messages.insert_one({
                "id": generate_id("msg"),
                "dispute_id": dispute_id,
                "sender_id": msg["role"],
                "sender_role": msg["role"],
                "sender_name": msg["name"],
                "text": msg["text"],
                "created_at": (now - timedelta(hours=i) + timedelta(minutes=15+j*2)).isoformat()
            })
        
        print(f"⚠️ Сделка {order_id}: {data['amount']}₽ - СПОР ({dispute_id})")
        print(f"   Ссылка: https://p2p-gateway.preview.emergentagent.com/dispute/{dispute_token}")
    
    # Итог
    print("\n" + "="*60)
    print("✅ ВСЕ ДАННЫЕ СОЗДАНЫ!")
    print("="*60)
    print("""
╔════════════════════════════════════════════════════════════╗
║                    УЧЁТНЫЕ ДАННЫЕ                           ║
╠═════════════╦═══════════════╦═══════════════════════════════╣
║ Роль        ║ Логин         ║ Пароль                        ║
╠═════════════╬═══════════════╬═══════════════════════════════╣
║ Админ       ║ admin         ║ 000000                        ║
║ Трейдер     ║ 111           ║ 000000                        ║
║ Мерчант     ║ 222           ║ 000000                        ║
╚═════════════╩═══════════════╩═══════════════════════════════╝

📦 СДЕЛКИ:
  • ORD-0001: 1500₽ - Ожидает оплаты
  • ORD-0002: 3000₽ - Завершена
  • ORD-0003: 2500₽ - СПОР (DSP-0003)
  • ORD-0004: 5000₽ - СПОР (DSP-0004)
  • ORD-0005: 7500₽ - СПОР (DSP-0005)
""")
    print(f"🔑 API мерчанта:")
    print(f"   Merchant ID: {merchant_id}")
    print(f"   API Key: {api_key}")
    print(f"   Secret: {secret_key}")
    print("="*60)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(reset_database())
