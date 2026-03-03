#!/usr/bin/env python3
"""
Script to reset database and create test users.
Keeps only admin account and creates:
- 3 traders (user1, user2, user3)  
- 3 merchants (merchant1 - casino, merchant2 - shop, merchant3 - stream)
- Staff members (mod_p2p, mod_market, support)
"""

import asyncio
import os
import bcrypt
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

async def reset_database():
    print("=" * 50)
    print("🗑️  CLEANING DATABASE")
    print("=" * 50)
    
    # Collections to clean completely
    collections_to_clear = [
        'trades', 'trade_messages', 'offers',  # P2P
        'marketplace_orders', 'products', 'product_categories',  # Marketplace  
        'merchant_applications', 'shop_applications',  # Applications
        'unified_conversations', 'unified_messages',  # Messages
        'internal_discussions', 'broadcasts',  # Staff comms
        'decisions', 'decision_actions', 'admin_logs',  # Logs
        'notifications', 'chats', 'messages',  # Legacy
        'admin_online',  # Online status
    ]
    
    for coll in collections_to_clear:
        result = await db[coll].delete_many({})
        print(f"  ✓ {coll}: удалено {result.deleted_count} документов")
    
    # Clear traders (keep none)
    result = await db.traders.delete_many({})
    print(f"  ✓ traders: удалено {result.deleted_count} документов")
    
    # Clear merchants (keep none)
    result = await db.merchants.delete_many({})
    print(f"  ✓ merchants: удалено {result.deleted_count} документов")
    
    # Clear staff except admin
    result = await db.admins.delete_many({"login": {"$ne": "admin"}})
    print(f"  ✓ admins: удалено {result.deleted_count} документов (admin сохранён)")
    
    print("\n" + "=" * 50)
    print("✨ CREATING TEST USERS")
    print("=" * 50)
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Create 3 traders
    traders = [
        {"name": "user1", "nickname": "Пользователь Один"},
        {"name": "user2", "nickname": "Пользователь Два"},
        {"name": "user3", "nickname": "Пользователь Три"},
    ]
    
    for t in traders:
        trader_id = str(uuid.uuid4())
        ref_code = uuid.uuid4().hex[:8].upper()
        trader = {
            "id": trader_id,
            "login": t["name"],
            "nickname": t["nickname"],
            "password_hash": hash_password("000000"),
            "role": "trader",
            "balance_usdt": 1000.0,  # Starting balance
            "balance_rub": 0.0,
            "total_traded": 0.0,
            "successful_trades": 0,
            "rating": 5.0,
            "is_blocked": False,
            "referral_code": ref_code,
            "referred_by": None,
            "created_at": now
        }
        await db.traders.insert_one(trader)
        print(f"  ✓ Создан trader: {t['name']} ({t['nickname']})")
    
    # Create 3 merchants with different types
    merchants_data = [
        {"name": "merchant1", "merchant_name": "Мерчант Казино", "type": "casino"},
        {"name": "merchant2", "merchant_name": "Мерчант Магазин", "type": "shop"},
        {"name": "merchant3", "merchant_name": "Мерчант Стрим", "type": "stream"},
    ]
    
    # Get commission settings
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    
    for m in merchants_data:
        merchant_id = str(uuid.uuid4())
        api_key = f"merch_sk_{uuid.uuid4().hex[:32]}"
        commission_key = f"{m['type']}_commission"
        commission_rate = settings.get(commission_key, 0.5) if settings else 0.5
        
        merchant = {
            "id": merchant_id,
            "login": m["name"],
            "nickname": m["name"],
            "merchant_name": m["merchant_name"],
            "merchant_type": m["type"],
            "password_hash": hash_password("000000"),
            "role": "merchant",
            "status": "active",  # Already approved
            "balance_usdt": 500.0,
            "api_key": api_key,
            "commission_rate": commission_rate,
            "total_commission_paid": 0.0,
            "approved_at": now,
            "approved_by": "admin",
            "created_at": now
        }
        await db.merchants.insert_one(merchant)
        print(f"  ✓ Создан merchant: {m['name']} ({m['merchant_name']}) - тип: {m['type']}, комиссия: {commission_rate}%")
    
    # Create staff members
    staff_data = [
        {"login": "mod_p2p", "nickname": "P2P Модератор", "role": "mod_p2p"},
        {"login": "mod_market", "nickname": "Маркет Модератор", "role": "mod_market"},
        {"login": "support", "nickname": "Поддержка", "role": "support"},
    ]
    
    for s in staff_data:
        staff_id = str(uuid.uuid4())
        staff = {
            "id": staff_id,
            "login": s["login"],
            "nickname": s["nickname"],
            "password_hash": hash_password("000000"),
            "role": "admin",
            "admin_role": s["role"],
            "is_active": True,
            "created_at": now
        }
        await db.admins.insert_one(staff)
        print(f"  ✓ Создан staff: {s['login']} ({s['nickname']}) - роль: {s['role']}")
    
    # Update admin to be active
    await db.admins.update_one(
        {"login": "admin"},
        {"$set": {"is_active": True, "nickname": "Super Admin"}}
    )
    print(f"  ✓ Обновлён admin: is_active=True")
    
    print("\n" + "=" * 50)
    print("✅ БАЗА ДАННЫХ ГОТОВА!")
    print("=" * 50)
    print("\nТестовые аккаунты (пароль для всех: 000000):")
    print("\n📦 Пользователи:")
    print("  • user1 - Пользователь Один")
    print("  • user2 - Пользователь Два")
    print("  • user3 - Пользователь Три")
    print("\n💼 Мерчанты:")
    print("  • merchant1 - Мерчант Казино (тип: casino)")
    print("  • merchant2 - Мерчант Магазин (тип: shop)")
    print("  • merchant3 - Мерчант Стрим (тип: stream)")
    print("\n👥 Персонал:")
    print("  • admin - Владелец (owner)")
    print("  • mod_p2p - P2P Модератор")
    print("  • mod_market - Маркет Модератор")
    print("  • support - Поддержка")

if __name__ == "__main__":
    asyncio.run(reset_database())
