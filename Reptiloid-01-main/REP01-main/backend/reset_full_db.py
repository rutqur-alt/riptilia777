#!/usr/bin/env python3
"""
Full database reset script
Creates:
- Admin staff: owner (admin), mod_p2p, mod_market, support
- 3 merchants with shops
- 3 regular users
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset_database():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['reptiloid']
    
    print("🗑️  Очистка базы данных...")
    
    # Drop all collections
    collections = await db.list_collection_names()
    for col in collections:
        await db.drop_collection(col)
        print(f"   Удалена коллекция: {col}")
    
    print("\n👑 Создание администрации...")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Admin staff
    admins = [
        {
            "id": str(uuid.uuid4()),
            "login": "admin",
            "password": pwd_context.hash("000000"),
            "nickname": "Главный Админ",
            "admin_role": "owner",
            "admin_level": 100,
            "is_active": True,
            "created_at": now,
            "permissions": ["all"]
        },
        {
            "id": str(uuid.uuid4()),
            "login": "mod_p2p",
            "password": pwd_context.hash("000000"),
            "nickname": "Модератор P2P",
            "admin_role": "mod_p2p",
            "admin_level": 50,
            "is_active": True,
            "created_at": now,
            "permissions": ["view_disputes", "resolve_disputes", "view_merchants", "approve_merchants"]
        },
        {
            "id": str(uuid.uuid4()),
            "login": "mod_market",
            "password": pwd_context.hash("000000"),
            "nickname": "Гарант Маркетплейса",
            "admin_role": "mod_market",
            "admin_level": 50,
            "is_active": True,
            "created_at": now,
            "permissions": ["view_shops", "approve_shops", "act_as_guarantor", "resolve_market_disputes"]
        },
        {
            "id": str(uuid.uuid4()),
            "login": "support",
            "password": pwd_context.hash("000000"),
            "nickname": "Служба Поддержки",
            "admin_role": "support",
            "admin_level": 30,
            "is_active": True,
            "created_at": now,
            "permissions": ["view_tickets", "respond_tickets"]
        }
    ]
    
    for admin in admins:
        await db.admins.insert_one(admin)
        print(f"   ✅ {admin['nickname']} ({admin['login']}) - {admin['admin_role']}")
    
    print("\n💼 Создание мерчантов...")
    
    # Merchants (3)
    merchants = [
        {
            "id": str(uuid.uuid4()),
            "login": "merchant1",
            "password": pwd_context.hash("000000"),
            "nickname": "Мерчант Алексей",
            "role": "merchant",
            "is_active": True,
            "is_verified": True,
            "balance_usdt": 5000.0,
            "balance_btc": 0.1,
            "frozen_balance": 0.0,
            "telegram": "@merchant_alex",
            "created_at": now
        },
        {
            "id": str(uuid.uuid4()),
            "login": "merchant2",
            "password": pwd_context.hash("000000"),
            "nickname": "Мерчант Борис",
            "role": "merchant",
            "is_active": True,
            "is_verified": True,
            "balance_usdt": 3000.0,
            "balance_btc": 0.05,
            "frozen_balance": 0.0,
            "telegram": "@merchant_boris",
            "created_at": now
        },
        {
            "id": str(uuid.uuid4()),
            "login": "merchant3",
            "password": pwd_context.hash("000000"),
            "nickname": "Мерчант Виктор",
            "role": "merchant",
            "is_active": True,
            "is_verified": True,
            "balance_usdt": 7000.0,
            "balance_btc": 0.15,
            "frozen_balance": 0.0,
            "telegram": "@merchant_victor",
            "created_at": now
        }
    ]
    
    for merchant in merchants:
        await db.merchants.insert_one(merchant)
        print(f"   ✅ {merchant['nickname']} ({merchant['login']})")
    
    print("\n👤 Создание пользователей...")
    
    # Regular users (3)
    users = [
        {
            "id": str(uuid.uuid4()),
            "login": "user1",
            "password": pwd_context.hash("000000"),
            "nickname": "Пользователь Иван",
            "role": "trader",
            "is_active": True,
            "balance_usdt": 1000.0,
            "balance_btc": 0.01,
            "frozen_balance": 0.0,
            "has_shop": True,
            "shop_settings": {
                "shop_name": "CryptoStore",
                "shop_description": "Магазин цифровых товаров",
                "is_active": True,
                "is_blocked": False
            },
            "created_at": now
        },
        {
            "id": str(uuid.uuid4()),
            "login": "user2",
            "password": pwd_context.hash("000000"),
            "nickname": "Пользователь Мария",
            "role": "trader",
            "is_active": True,
            "balance_usdt": 500.0,
            "balance_btc": 0.005,
            "frozen_balance": 0.0,
            "created_at": now
        },
        {
            "id": str(uuid.uuid4()),
            "login": "user3",
            "password": pwd_context.hash("000000"),
            "nickname": "Пользователь Сергей",
            "role": "trader",
            "is_active": True,
            "balance_usdt": 2000.0,
            "balance_btc": 0.02,
            "frozen_balance": 0.0,
            "created_at": now
        }
    ]
    
    for user in users:
        await db.traders.insert_one(user)
        print(f"   ✅ {user['nickname']} ({user['login']})")
    
    # Get user1 and user2 IDs for requisites and offers
    user1_id = users[0]["id"]
    user2_id = users[1]["id"]
    
    # Create requisites for user1 (seller)
    print("\n💳 Создание реквизитов для user1...")
    requisites = [
        {
            "id": str(uuid.uuid4()),
            "trader_id": user1_id,
            "type": "card",
            "data": {
                "bank_name": "Сбербанк",
                "card_number": "4276 1234 5678 9012",
                "holder_name": "IVAN IVANOV"
            },
            "is_active": True,
            "is_primary": True,
            "created_at": now
        },
        {
            "id": str(uuid.uuid4()),
            "trader_id": user1_id,
            "type": "sbp",
            "data": {
                "bank_name": "Тинькофф",
                "phone": "+7 999 123 45 67",
                "recipient_name": "Иван И."
            },
            "is_active": True,
            "is_primary": False,
            "created_at": now
        },
        {
            "id": str(uuid.uuid4()),
            "trader_id": user1_id,
            "type": "qr",
            "data": {
                "bank_name": "Альфа-Банк",
                "qr_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "description": "Отсканируйте QR-код"
            },
            "is_active": True,
            "is_primary": False,
            "created_at": now
        }
    ]
    for req in requisites:
        await db.requisites.insert_one(req)
    print(f"   ✅ Создано {len(requisites)} реквизитов")
    
    # Create P2P offer from user1
    print("\n📢 Создание P2P оффера от user1...")
    offer_id = str(uuid.uuid4())
    offer = {
        "id": offer_id,
        "trader_id": user1_id,
        "trader_login": "user1",
        "trader_nickname": "Пользователь Иван",
        "amount_usdt": 500.0,
        "available_usdt": 500.0,
        "sold_usdt": 0.0,
        "price_rub": 95.0,
        "min_amount": 10.0,
        "max_amount": 500.0,
        "payment_methods": ["card", "sbp", "qr"],
        "accepted_merchant_types": ["casino", "shop", "stream", "other"],
        "requisites": requisites,
        "conditions": "Оплата в течение 15 минут. Перевод строго без комментариев!",
        "is_active": True,
        "commission_rate": 1.0,
        "reserved_commission": 5.0,
        "created_at": now
    }
    await db.offers.insert_one(offer)
    
    # Update user1 balance (reserve for offer)
    await db.traders.update_one(
        {"id": user1_id},
        {"$inc": {"balance_usdt": -505.0}}  # 500 + 5 commission
    )
    print(f"   ✅ Оффер создан: {offer['amount_usdt']} USDT по {offer['price_rub']} ₽")
    
    # Create indexes
    print("\n📊 Создание индексов...")
    await db.admins.create_index("id", unique=True)
    await db.admins.create_index("login", unique=True)
    await db.merchants.create_index("id", unique=True)
    await db.merchants.create_index("login", unique=True)
    await db.traders.create_index("id", unique=True)
    await db.traders.create_index("login", unique=True)
    await db.unified_conversations.create_index("id", unique=True)
    await db.unified_messages.create_index("conversation_id")
    await db.notifications.create_index("user_id")
    
    # Platform settings
    print("\n⚙️  Создание настроек платформы...")
    await db.platform_settings.insert_one({
        "id": "main",
        "base_rate": 92.0,
        "sell_rate": 95.0,
        "platform_commission": 2.0,
        "updated_at": now
    })
    print("   ✅ Курсы: base_rate=92, sell_rate=95")
    
    # Commission settings
    await db.commission_settings.insert_one({
        "trader_commission": 1.0,
        "minimum_commission": 0.01,
        "casino_commission": 0.5,
        "shop_commission": 0.5,
        "stream_commission": 0.5,
        "other_commission": 0.5,
        "guarantor_commission": 3.0
    })
    print("   ✅ Комиссии: trader=1%, minimum=0.01, guarantor=3%")
    
    # Get IDs for reference
    admin = await db.admins.find_one({"login": "admin"}, {"_id": 0})
    mod_p2p = await db.admins.find_one({"login": "mod_p2p"}, {"_id": 0})
    mod_market = await db.admins.find_one({"login": "mod_market"}, {"_id": 0})
    support_staff = await db.admins.find_one({"login": "support"}, {"_id": 0})
    merchant1 = await db.merchants.find_one({"login": "merchant1"}, {"_id": 0})
    merchant2 = await db.merchants.find_one({"login": "merchant2"}, {"_id": 0})
    user1 = await db.traders.find_one({"login": "user1"}, {"_id": 0})
    user2 = await db.traders.find_one({"login": "user2"}, {"_id": 0})
    user3 = await db.traders.find_one({"login": "user3"}, {"_id": 0})
    
    print("\n💬 Создание ВСЕХ типов чатов...")
    
    # ==================== 1. P2P TRADE (between traders) ====================
    print("\n   📊 1. P2P Trade (трейдер-трейдер)...")
    p2p_trade_id = str(uuid.uuid4())
    p2p_offer_id = str(uuid.uuid4())
    
    # Create P2P offer
    await db.p2p_offers.insert_one({
        "id": p2p_offer_id,
        "seller_id": user1["id"],
        "seller_nickname": user1["nickname"],
        "type": "sell",
        "crypto": "USDT",
        "amount": 500,
        "rate": 93.5,
        "min_limit": 1000,
        "max_limit": 50000,
        "payment_methods": ["card", "sbp"],
        "status": "active",
        "created_at": now
    })
    
    # Create P2P trade (use db.trades - the actual collection used by API)
    await db.trades.insert_one({
        "id": p2p_trade_id,
        "offer_id": p2p_offer_id,
        "trader_id": user1["id"],
        "seller_id": user1["id"],
        "seller_nickname": user1["nickname"],
        "buyer_id": user2["id"],
        "buyer_nickname": user2["nickname"],
        "buyer_type": "trader",
        "crypto": "USDT",
        "amount": 100,
        "rate": 93.5,
        "total_rub": 9350,
        "status": "pending_payment",
        "payment_method": "card",
        "created_at": now
    })
    
    # Create conversation
    p2p_conv_id = str(uuid.uuid4())
    await db.unified_conversations.insert_one({
        "id": p2p_conv_id,
        "type": "p2p_trade",
        "related_id": p2p_trade_id,
        "title": f"P2P: {user1['nickname']} → {user2['nickname']}",
        "status": "active",
        "participants": [
            {"user_id": user1["id"], "role": "seller", "name": user1["nickname"]},
            {"user_id": user2["id"], "role": "buyer", "name": user2["nickname"]}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": p2p_conv_id, "sender_id": user2["id"], "sender_name": user2["nickname"], "sender_type": "buyer", "content": "Привет! Хочу купить 100 USDT", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": p2p_conv_id, "sender_id": user1["id"], "sender_name": user1["nickname"], "sender_type": "seller", "content": "Добро пожаловать! Реквизиты: Сбербанк 4276 1234 5678 9012", "created_at": now}
    ])
    print("      ✅ P2P сделка создана (ожидает оплаты)")
    
    # ==================== 2. P2P DISPUTE ====================
    print("\n   ⚠️  2. P2P Dispute (спор по P2P)...")
    p2p_dispute_trade_id = str(uuid.uuid4())
    p2p_dispute_offer_id = str(uuid.uuid4())
    
    await db.p2p_offers.insert_one({
        "id": p2p_dispute_offer_id,
        "seller_id": user3["id"],
        "seller_nickname": user3["nickname"],
        "type": "sell",
        "crypto": "USDT",
        "amount": 300,
        "rate": 94.0,
        "status": "active",
        "created_at": now
    })
    
    await db.trades.insert_one({
        "id": p2p_dispute_trade_id,
        "offer_id": p2p_dispute_offer_id,
        "trader_id": user3["id"],
        "seller_id": user3["id"],
        "seller_nickname": user3["nickname"],
        "buyer_id": user1["id"],
        "buyer_nickname": user1["nickname"],
        "buyer_type": "trader",
        "crypto": "USDT",
        "amount": 50,
        "rate": 94.0,
        "total_rub": 4700,
        "status": "dispute",
        "dispute_reason": "Покупатель утверждает что оплатил, продавец не подтверждает",
        "payment_method": "sbp",
        "created_at": now
    })
    
    p2p_dispute_conv_id = str(uuid.uuid4())
    await db.unified_conversations.insert_one({
        "id": p2p_dispute_conv_id,
        "type": "p2p_trade",
        "related_id": p2p_dispute_trade_id,
        "title": f"СПОР P2P: {user3['nickname']} vs {user1['nickname']}",
        "status": "dispute",
        "participants": [
            {"user_id": user3["id"], "role": "seller", "name": user3["nickname"]},
            {"user_id": user1["id"], "role": "buyer", "name": user1["nickname"]}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": p2p_dispute_conv_id, "sender_id": user1["id"], "sender_name": user1["nickname"], "sender_type": "buyer", "content": "Я оплатил через СБП, вот чек!", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": p2p_dispute_conv_id, "sender_id": user3["id"], "sender_name": user3["nickname"], "sender_type": "seller", "content": "Деньги не поступили! Проверил 3 раза!", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": p2p_dispute_conv_id, "sender_id": user1["id"], "sender_name": user1["nickname"], "sender_type": "buyer", "content": "Открываю спор! Нужен модератор!", "created_at": now}
    ])
    print("      ✅ Спор P2P создан (требует решения модератора)")
    
    # ==================== 3. MERCHANT APPLICATION ====================
    print("\n   📋 3. Merchant Application (заявка на мерчанта)...")
    
    # Create a NEW pending merchant for this application
    new_merchant_id = str(uuid.uuid4())
    new_merchant = {
        "id": new_merchant_id,
        "login": "casino_new",
        "nickname": "CasinoX Owner",
        "password_hash": pwd_context.hash("000000"),
        "role": "merchant",
        "merchant_name": "CasinoX",
        "merchant_type": "casino",
        "telegram": "@casinox_admin",
        "status": "pending",
        "balance_usdt": 0.0,
        "commission_rate": 0.5,
        "created_at": now
    }
    await db.merchants.insert_one(new_merchant)
    
    merchant_app_id = str(uuid.uuid4())
    await db.merchant_applications.insert_one({
        "id": merchant_app_id,
        "user_id": new_merchant_id,
        "user_nickname": "CasinoX Owner",
        "merchant_type": "casino",
        "merchant_name": "CasinoX",
        "description": "Онлайн-казино с лицензией",
        "website": "https://casinox.example.com",
        "telegram": "@casinox_admin",
        "status": "pending",
        "created_at": now
    })
    
    merchant_app_conv_id = str(uuid.uuid4())
    await db.unified_conversations.insert_one({
        "id": merchant_app_conv_id,
        "type": "merchant_application",
        "related_id": merchant_app_id,
        "title": "CasinoX",
        "status": "pending",
        "merchant_type": "casino",
        "participants": [
            {"user_id": new_merchant_id, "role": "applicant", "name": "CasinoX Owner"}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": merchant_app_conv_id, "sender_id": new_merchant_id, "sender_name": "CasinoX Owner", "sender_type": "user", "content": "Добрый день! Подаю заявку на статус мерчанта для онлайн-казино.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": merchant_app_conv_id, "sender_id": mod_p2p["id"], "sender_name": mod_p2p["nickname"], "sender_type": "admin", "content": "Здравствуйте! Расскажите подробнее о вашем бизнесе и ожидаемых оборотах.", "created_at": now}
    ])
    print("      ✅ Заявка на мерчанта создана (casino_new/000000)")
    
    # ==================== 4. SHOP APPLICATION ====================
    print("\n   🏪 4. Shop Application (заявка на магазин)...")
    shop_app_id = str(uuid.uuid4())
    
    await db.shop_applications.insert_one({
        "id": shop_app_id,
        "user_id": user3["id"],
        "user_nickname": user3["nickname"],
        "shop_name": "TechGadgets",
        "description": "Магазин электроники и гаджетов",
        "category": "electronics",
        "status": "pending",
        "created_at": now
    })
    
    shop_app_conv_id = str(uuid.uuid4())
    await db.unified_conversations.insert_one({
        "id": shop_app_conv_id,
        "type": "shop_application",
        "related_id": shop_app_id,
        "title": f"Заявка на магазин: {user3['nickname']} - TechGadgets",
        "status": "pending",
        "participants": [
            {"user_id": user3["id"], "role": "applicant", "name": user3["nickname"]}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": shop_app_conv_id, "sender_id": user3["id"], "sender_name": user3["nickname"], "sender_type": "user", "content": "Хочу открыть магазин электроники. Планирую продавать смартфоны и аксессуары.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": shop_app_conv_id, "sender_id": mod_market["id"], "sender_name": mod_market["nickname"], "sender_type": "admin", "content": "Приветствую! Укажите источник товаров и примерный ассортимент.", "created_at": now}
    ])
    print("      ✅ Заявка на магазин создана")
    
    # ==================== 5. MARKETPLACE GUARANTOR ====================
    print("\n   🛡️  5. Marketplace Guarantor (сделка с гарантом)...")
    
    # Create shop first
    shop_id = str(uuid.uuid4())
    await db.shops.insert_one({
        "id": shop_id,
        "owner_id": user1["id"],
        "owner_type": "trader",
        "name": "CryptoStore",
        "description": "Магазин цифровых товаров",
        "status": "active",
        "created_at": now
    })
    
    # Create products for marketplace
    product1_id = str(uuid.uuid4())
    await db.shop_products.insert_one({
        "id": product1_id,
        "shop_id": shop_id,
        "seller_id": user1["id"],
        "seller_type": "trader",
        "seller_nickname": user1["nickname"],
        "name": "Premium VPN подписка 1 год",
        "description": "Годовая подписка на VPN сервис. Безлимитный трафик, 50+ стран, отсутствие логов.",
        "price": 50.0,
        "currency": "USDT",
        "category": "software",
        "auto_content": [
            {"text": "VPN-KEY-001-ANNUAL"},
            {"text": "VPN-KEY-002-ANNUAL"},
            {"text": "VPN-KEY-003-ANNUAL"}
        ],
        "reserved_count": 0,
        "sold_count": 0,
        "is_active": True,
        "is_infinite": False,
        "guarantor_commission_percent": 3,
        "created_at": now
    })
    
    product2_id = str(uuid.uuid4())
    await db.shop_products.insert_one({
        "id": product2_id,
        "shop_id": shop_id,
        "seller_id": user1["id"],
        "seller_type": "trader",
        "seller_nickname": user1["nickname"],
        "name": "Steam ключ - CS2 Prime",
        "description": "Лицензионный ключ Counter-Strike 2 Prime Status. Мгновенная доставка.",
        "price": 25.0,
        "currency": "USDT",
        "category": "games",
        "auto_content": [
            {"text": "STEAM-CS2-PRIME-001"},
            {"text": "STEAM-CS2-PRIME-002"}
        ],
        "reserved_count": 0,
        "sold_count": 0,
        "is_active": True,
        "is_infinite": False,
        "guarantor_commission_percent": 3,
        "created_at": now
    })
    
    product3_id = str(uuid.uuid4())
    await db.shop_products.insert_one({
        "id": product3_id,
        "shop_id": shop_id,
        "seller_id": user1["id"],
        "seller_type": "trader",
        "seller_nickname": user1["nickname"],
        "name": "Netflix Premium 1 месяц",
        "description": "Подписка Netflix Premium на 1 месяц. Ultra HD, 4 экрана.",
        "price": 15.0,
        "currency": "USDT",
        "category": "subscriptions",
        "auto_content": [
            {"text": "netflix@example.com:password123"},
            {"text": "netflix2@example.com:password456"}
        ],
        "reserved_count": 0,
        "sold_count": 0,
        "is_active": True,
        "is_infinite": False,
        "guarantor_commission_percent": 3,
        "created_at": now
    })
    
    # Create guarantor order
    guarantor_order_id = str(uuid.uuid4())
    await db.marketplace_orders.insert_one({
        "id": guarantor_order_id,
        "product_id": product1_id,
        "product_title": "Premium VPN подписка 1 год",
        "shop_id": shop_id,
        "seller_id": user1["id"],
        "seller_nickname": user1["nickname"],
        "buyer_id": user2["id"],
        "buyer_nickname": user2["nickname"],
        "quantity": 1,
        "price": 50.0,
        "total": 50.0,
        "purchase_type": "guarantor",
        "status": "pending_delivery",
        "guarantor_id": mod_market["id"],
        "created_at": now
    })
    
    guarantor_conv_id = str(uuid.uuid4())
    await db.unified_conversations.insert_one({
        "id": guarantor_conv_id,
        "type": "marketplace_guarantor",
        "related_id": guarantor_order_id,
        "title": f"Гарант: VPN подписка ({user1['nickname']} → {user2['nickname']})",
        "status": "pending_delivery",
        "purchase_type": "guarantor",
        "participants": [
            {"user_id": user1["id"], "role": "seller", "name": user1["nickname"]},
            {"user_id": user2["id"], "role": "buyer", "name": user2["nickname"]},
            {"user_id": mod_market["id"], "role": "guarantor", "name": mod_market["nickname"]}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": guarantor_conv_id, "sender_id": mod_market["id"], "sender_name": mod_market["nickname"], "sender_type": "admin", "content": "Сделка открыта. Продавец, пожалуйста, предоставьте товар.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": guarantor_conv_id, "sender_id": user1["id"], "sender_name": user1["nickname"], "sender_type": "seller", "content": "Отправляю ключ активации: XXXX-YYYY-ZZZZ-1234", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": guarantor_conv_id, "sender_id": user2["id"], "sender_name": user2["nickname"], "sender_type": "buyer", "content": "Проверяю ключ...", "created_at": now}
    ])
    print("      ✅ Сделка с гарантом создана")
    
    # ==================== 6. SUPPORT TICKET ====================
    print("\n   🎫 6. Support Ticket (тикет поддержки)...")
    support_conv_id = str(uuid.uuid4())
    
    await db.unified_conversations.insert_one({
        "id": support_conv_id,
        "type": "support_ticket",
        "title": f"Тикет: Проблема с выводом средств",
        "status": "open",
        "priority": "high",
        "category": "withdrawal",
        "participants": [
            {"user_id": user1["id"], "role": "user", "name": user1["nickname"]}
        ],
        "assigned_to": support_staff["id"],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": support_conv_id, "sender_id": user1["id"], "sender_name": user1["nickname"], "sender_type": "user", "content": "Здравствуйте! Уже 2 часа не могу вывести USDT на внешний кошелек. Транзакция висит в статусе 'processing'.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": support_conv_id, "sender_id": support_staff["id"], "sender_name": support_staff["nickname"], "sender_type": "admin", "content": "Добрый день! Проверяю вашу транзакцию. Укажите, пожалуйста, ID вывода.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": support_conv_id, "sender_id": user1["id"], "sender_name": user1["nickname"], "sender_type": "user", "content": "ID: WD-123456789", "created_at": now}
    ])
    print("      ✅ Тикет поддержки создан")
    
    # ==================== 7. CRYPTO ORDER (PAYOUT) ====================
    print("\n   💰 7. Crypto Order (выплата/payout)...")
    
    # Create crypto offer
    crypto_offer_id = str(uuid.uuid4())
    await db.crypto_offers.insert_one({
        "id": crypto_offer_id,
        "merchant_id": merchant1["id"],
        "merchant_nickname": merchant1["nickname"],
        "amount_rub": 10000,
        "usdt_from_merchant": 108.7,  # 10000 / 92 base_rate
        "payment_type": "card",
        "card_number": "4276 5555 4444 3333",
        "status": "active",
        "created_at": now
    })
    
    # Create crypto order (someone buying)
    crypto_order_id = str(uuid.uuid4())
    await db.crypto_orders.insert_one({
        "id": crypto_order_id,
        "offer_id": crypto_offer_id,
        "merchant_id": merchant1["id"],
        "merchant_nickname": merchant1["nickname"],
        "buyer_id": user2["id"],
        "buyer_nickname": user2["nickname"],
        "buyer_type": "trader",
        "amount_rub": 10000,
        "amount_usdt": 105.26,  # 10000 / 95 sell_rate
        "rate": 95.0,
        "payment_type": "card",
        "card_number": "4276 5555 4444 3333",
        "status": "pending_payment",
        "created_at": now
    })
    
    crypto_conv_id = str(uuid.uuid4())
    await db.unified_conversations.insert_one({
        "id": crypto_conv_id,
        "type": "crypto_order",
        "related_id": crypto_order_id,
        "title": f"Выплата: {user2['nickname']} покупает 105.26 USDT",
        "status": "pending_payment",
        "participants": [
            {"user_id": merchant1["id"], "role": "merchant", "name": merchant1["nickname"]},
            {"user_id": user2["id"], "role": "buyer", "name": user2["nickname"]}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": crypto_conv_id, "sender_id": "system", "sender_name": "Система", "sender_type": "system", "content": f"Заказ создан. Покупатель {user2['nickname']} хочет купить 105.26 USDT за 10000₽", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": crypto_conv_id, "sender_id": user2["id"], "sender_name": user2["nickname"], "sender_type": "buyer", "content": "Оплачиваю на карту сейчас", "created_at": now}
    ])
    print("      ✅ Выплата (payout) создана")
    
    # ==================== 8. INTERNAL ADMIN CHAT ====================
    print("\n   👥 8. Internal Admin Chat (внутренний чат персонала)...")
    internal_conv_id = str(uuid.uuid4())
    
    await db.unified_conversations.insert_one({
        "id": internal_conv_id,
        "type": "internal_admin",
        "title": "Общий чат персонала",
        "status": "active",
        "participants": [
            {"user_id": admin["id"], "role": "owner", "name": admin["nickname"]},
            {"user_id": mod_p2p["id"], "role": "moderator", "name": mod_p2p["nickname"]},
            {"user_id": mod_market["id"], "role": "moderator", "name": mod_market["nickname"]},
            {"user_id": support_staff["id"], "role": "support", "name": support_staff["nickname"]}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": internal_conv_id, "sender_id": admin["id"], "sender_name": admin["nickname"], "sender_type": "admin", "content": "Всем привет! Сегодня обновили логику выплат. Будьте внимательны к новым заказам.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": internal_conv_id, "sender_id": mod_p2p["id"], "sender_name": mod_p2p["nickname"], "sender_type": "admin", "content": "Понял, слежу за P2P спорами.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": internal_conv_id, "sender_id": mod_market["id"], "sender_name": mod_market["nickname"], "sender_type": "admin", "content": "У меня сейчас 2 сделки с гарантом в работе.", "created_at": now}
    ])
    print("      ✅ Внутренний чат персонала создан")
    
    # ==================== EXTRA: P2P MERCHANT TRADE ====================
    print("\n   🏢 9. P2P Merchant Trade (P2P с мерчантом)...")
    p2p_merchant_trade_id = str(uuid.uuid4())
    
    await db.trades.insert_one({
        "id": p2p_merchant_trade_id,
        "trader_id": merchant2["id"],
        "merchant_id": merchant2["id"],
        "merchant_nickname": merchant2["nickname"],
        "buyer_id": user3["id"],
        "buyer_nickname": user3["nickname"],
        "buyer_type": "trader",
        "crypto": "USDT",
        "amount": 200,
        "rate": 93.0,
        "total_rub": 18600,
        "status": "paid",
        "payment_method": "card",
        "created_at": now
    })
    
    p2p_merchant_conv_id = str(uuid.uuid4())
    await db.unified_conversations.insert_one({
        "id": p2p_merchant_conv_id,
        "type": "p2p_merchant",
        "related_id": p2p_merchant_trade_id,
        "title": f"P2P Мерчант: {merchant2['nickname']} → {user3['nickname']}",
        "status": "paid",
        "participants": [
            {"user_id": merchant2["id"], "role": "merchant", "name": merchant2["nickname"]},
            {"user_id": user3["id"], "role": "buyer", "name": user3["nickname"]}
        ],
        "created_at": now,
        "updated_at": now
    })
    
    await db.unified_messages.insert_many([
        {"id": str(uuid.uuid4()), "conversation_id": p2p_merchant_conv_id, "sender_id": user3["id"], "sender_name": user3["nickname"], "sender_type": "buyer", "content": "Оплатил 18600₽ на карту. Жду подтверждения.", "created_at": now},
        {"id": str(uuid.uuid4()), "conversation_id": p2p_merchant_conv_id, "sender_id": merchant2["id"], "sender_name": merchant2["nickname"], "sender_type": "merchant", "content": "Проверяю поступление...", "created_at": now}
    ])
    print("      ✅ P2P с мерчантом создана (оплачена, ждёт подтверждения)")
    
    print("\n✅ База данных успешно пересоздана!")
    print("\n📋 Учётные записи:")
    print("=" * 50)
    print("АДМИНИСТРАЦИЯ:")
    print("  admin / 000000 - Владелец (полный доступ)")
    print("  mod_p2p / 000000 - Модератор P2P")
    print("  mod_market / 000000 - Гарант Маркетплейса")
    print("  support / 000000 - Служба Поддержки")
    print("\nМЕРЧАНТЫ:")
    print("  merchant1 / 000000 - Мерчант Алексей")
    print("  merchant2 / 000000 - Мерчант Борис")
    print("  merchant3 / 000000 - Мерчант Виктор")
    print("\nПОЛЬЗОВАТЕЛИ:")
    print("  user1 / 000000 - Пользователь Иван")
    print("  user2 / 000000 - Пользователь Мария")
    print("  user3 / 000000 - Пользователь Сергей")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(reset_database())
