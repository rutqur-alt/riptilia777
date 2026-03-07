from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Body, Request, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import json

# Import models from schemas
from models.schemas import (
    UserBase, UserCreate, TraderCreate, MerchantCreate, LoginRequest, TokenResponse,
    MerchantResponse, TraderResponse, TradeCreate, TradeResponse,
    PaymentLinkCreate, PaymentLinkResponse, RequisiteCreate, RequisiteResponse,
    OfferCreate, OfferResponse, MessageCreate, MessageResponse,
    CommissionSettings, MerchantApproval, UpdateCommissionSettings, TraderUpdate,
    ChangePasswordRequest, Toggle2FARequest, TicketCreate, TicketMessage, StockItem,
    DirectTradeCreate, ShopApplicationCreate, ShopApplicationResponse, PriceVariant,
    ProductCreate, ProductUpdate, ShopSettings, GuarantorDealCreate, GuarantorDealResponse,
    ForumMessageCreate, ForumMessageResponse, ReviewCreate, ReviewResponse,
    TransferRequest, PrivateMessageCreate, ConversationResponse, PrivateMessageResponse,
    PasswordReset, BalanceFreeze, AdminMessage, MaintenanceToggle, UserRoleUpdate,
    UserBan, BalanceAdjustment, CommissionUpdate, MessageTemplateCreate, MessageTemplateUpdate,
    RequisiteCard, RequisiteSBP, RequisiteQR
)

from routes.rate_service import fetch_usdt_rub_rate, get_cached_rate, rate_update_loop, update_base_rate_in_db

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'p2p-exchange-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Admin role hierarchy
ADMIN_ROLES = {
    "owner": 100,      # Can do everything
    "admin": 80,       # Almost everything except creating admins
    "mod_p2p": 50,     # P2P moderation
    "mod_market": 50,  # Marketplace moderation
    "support": 30      # Support only
}

# Granular permissions for each role
ROLE_PERMISSIONS = {
    "owner": ["*"],  # All permissions
    "admin": ["*"],  # All permissions
    "mod_p2p": [
        # Users
        "view_users", "view_user_stats", "block_users", "block_user_balance",
        # P2P
        "view_p2p_trades", "view_p2p_offers", "resolve_p2p_disputes",
        # Merchants
        "view_merchants", "approve_merchants",
        # Support (limited)
        "view_messages", "send_messages"
    ],
    "mod_market": [
        # Marketplace
        "view_shops", "block_shops", "approve_shops", "block_shop_balance",
        "view_products", "moderate_products",
        # Guarantor
        "act_as_guarantor", "resolve_market_disputes",
        # Support (limited)
        "view_messages", "send_messages"
    ],
    "support": [
        # Messages only
        "view_all_messages", "send_messages", "answer_tickets",
        # Escalation
        "escalate_to_mod_p2p", "escalate_to_mod_market", "escalate_to_admin",
        "invite_to_chat"
    ]
}

def has_permission(user: dict, permission: str) -> bool:
    """Check if user has specific permission"""
    admin_role = user.get("admin_role", user.get("role", ""))
    perms = ROLE_PERMISSIONS.get(admin_role, [])
    return "*" in perms or permission in perms

app = FastAPI(title="P2P Exchange API")
# Patch FastAPI's JSON encoder to handle bson.ObjectId globally
from bson import ObjectId as _BsonObjectId
from fastapi.encoders import ENCODERS_BY_TYPE
ENCODERS_BY_TYPE[_BsonObjectId] = str

api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Import modular routes
from routes.auth import router as auth_router
from routes.traders import router as traders_router
from routes.merchants import router as merchants_router
from routes.requisites import router as requisites_router
from routes.offers import router as offers_router
from routes.trades import router as trades_router
from routes.payment_links import router as payment_links_router
from routes.admin import router as admin_router
from routes.super_admin import router as super_admin_router
from routes.support import router as support_router
from routes.shop import router as shop_router
from routes.marketplace import router as marketplace_router
from routes.guarantor import router as guarantor_router
from routes.merchant import router as merchant_router
from routes.forum import router as forum_router
from routes.reviews import router as reviews_router
from routes.notifications import router as notifications_router
from routes.transfers import router as transfers_router
from routes.private_messaging import router as private_messaging_router
from routes.crypto_payouts import router as crypto_payouts_router
from routes.unified_messaging import router as unified_messaging_router
from routes.trade_chats import router as trade_chats_router
from routes.staff_admin import router as staff_admin_router
from routes.admin_chats import router as admin_chats_router
from routes.user_chats import router as user_chats_router
from routes.admin_users import router as admin_users_router
from routes.broadcast import router as broadcast_router
from routes.staff_templates import router as staff_templates_router
from routes.admin_dashboard import router as admin_dashboard_router
from routes.merchant_messages import router as merchant_messages_router
from routes.chat_management import router as chat_management_router
from routes.admin_management import router as admin_management_router
from routes.invoice_api import router as invoice_api_router
from routes.referral import router as referral_router
from routes.merchant_api import router as merchant_api_router
from routes.event_notifications import router as event_notifications_router
from routes.wallet_api import router as wallet_api_router
api_router.include_router(auth_router)
api_router.include_router(traders_router)
api_router.include_router(merchants_router)
api_router.include_router(requisites_router)
api_router.include_router(offers_router)
api_router.include_router(trades_router)
api_router.include_router(payment_links_router)
api_router.include_router(admin_router)
api_router.include_router(super_admin_router)
api_router.include_router(support_router)
api_router.include_router(shop_router)
api_router.include_router(marketplace_router)
api_router.include_router(guarantor_router)
api_router.include_router(merchant_router)
api_router.include_router(forum_router)
api_router.include_router(reviews_router)
api_router.include_router(notifications_router)
api_router.include_router(transfers_router)
api_router.include_router(private_messaging_router)
api_router.include_router(crypto_payouts_router)
api_router.include_router(unified_messaging_router)
api_router.include_router(trade_chats_router)
api_router.include_router(staff_admin_router)
api_router.include_router(admin_chats_router)
api_router.include_router(user_chats_router)
api_router.include_router(admin_users_router)
api_router.include_router(broadcast_router)
api_router.include_router(staff_templates_router)
api_router.include_router(admin_dashboard_router)
api_router.include_router(merchant_messages_router)
api_router.include_router(chat_management_router)
api_router.include_router(admin_management_router)
api_router.include_router(invoice_api_router)
api_router.include_router(referral_router)
api_router.include_router(merchant_api_router)
api_router.include_router(event_notifications_router)
api_router.include_router(wallet_api_router)
from routes.shop_api import router as shop_api_router
api_router.include_router(shop_api_router)
from routes.qr_aggregator import router as qr_aggregator_router
api_router.include_router(qr_aggregator_router)

# Import shared WebSocket manager
from core.websocket import manager



# ==================== WEBSOCKET REAL-TIME MESSAGING ====================
from fastapi import WebSocket, WebSocketDisconnect
from routes.ws_routes import ws_manager

@app.websocket("/ws/trade/{trade_id}")
async def ws_trade(websocket: WebSocket, trade_id: str):
    channel = f"trade_{trade_id}"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)

@app.websocket("/ws/conversation/{conv_id}")
async def ws_conversation(websocket: WebSocket, conv_id: str):
    channel = f"conv_{conv_id}"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)

@app.websocket("/ws/staff-chat")
async def ws_staff_chat(websocket: WebSocket):
    channel = "staff_chat"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)

@app.websocket("/ws/user/{user_id}")
async def ws_user(websocket: WebSocket, user_id: str):
    channel = f"user_{user_id}"
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception:
        ws_manager.disconnect(websocket, channel)


# ==================== MAINTENANCE MODE MIDDLEWARE ====================
@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    """Block all non-admin requests when maintenance mode is enabled"""
    # Skip for specific paths - auth must always be accessible
    skip_paths = ["/ws/", "/api/auth/login", "/api/auth/register", "/api/system/status", "/api/admin/", "/api/super-admin/", "/health", "/api/maintenance-status"]
    
    if any(request.url.path.startswith(p) for p in skip_paths):
        return await call_next(request)
    
    # Check maintenance mode
    settings = await db.system_settings.find_one({"key": "maintenance_mode"})
    if settings and settings.get("enabled"):
        # Check if user is admin (from token)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                role = payload.get("role")
                if role in ["admin", "owner", "mod_p2p", "mod_market", "support"]:
                    return await call_next(request)
            except:
                pass
        
        # Return maintenance response
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Ведутся технические работы. Пожалуйста, попробуйте позже.",
                "maintenance": True,
                "message": settings.get("message", "Сайт временно недоступен")
            }
        )
    
    return await call_next(request)

# Models imported from models/schemas.py

# Requisite type models for validation (not in schemas yet)
class RequisiteSIM(BaseModel):
    phone: str
    operator: str
    is_primary: bool = False

class RequisiteCIS(BaseModel):
    country: str
    bank_name: str
    account_number: str
    recipient_name: str
    swift_bic: Optional[str] = None
    is_primary: bool = False

# ==================== AUTH HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    import hashlib
    # Try bcrypt first
    try:
        if hashed.startswith("$2"):  # bcrypt hash
            return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        pass
    
    # Try SHA256
    sha_hash = hashlib.sha256(password.encode()).hexdigest()
    if sha_hash == hashed:
        return True
    
    return False

def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role")
        
        if role == "trader":
            user = await db.traders.find_one({"id": user_id}, {"_id": 0})
        elif role == "merchant":
            user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
        elif role == "admin":
            user = await db.admins.find_one({"id": user_id}, {"_id": 0})
        else:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user["role"] = role
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(allowed_roles: List[str]):
    async def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker

def require_admin_level(min_level: int = 30):
    """Require minimum admin level: owner=100, admin=80, mod=50, support=30"""
    async def admin_checker(user: dict = Depends(get_current_user)):
        role = user.get("role", "")
        # Check if user is staff member
        if role in ADMIN_ROLES:
            if ADMIN_ROLES[role] >= min_level:
                return user
        # Check if regular admin
        if role == "admin":
            admin = await db.admins.find_one({"id": user["id"]}, {"_id": 0})
            if admin:
                admin_role = admin.get("admin_role", "admin")
                if ADMIN_ROLES.get(admin_role, 0) >= min_level:
                    return user
        raise HTTPException(status_code=403, detail="Insufficient admin permissions")
    return admin_checker

async def log_admin_action(admin_id: str, action: str, target_type: str, target_id: str, details: dict = None):
    """Log admin actions for audit trail"""
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": admin_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

# API Key authentication for merchants
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_merchant_by_api_key(api_key: str = Depends(api_key_header)):
    """Authenticate merchant by API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    merchant = await db.merchants.find_one({"api_key": api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if merchant.get("status") != "approved":
        raise HTTPException(status_code=403, detail="Merchant not approved")
    
    merchant["role"] = "merchant"
    return merchant

# ==================== WEBSOCKET MANAGER ====================
# WebSocket manager is now imported from core/websocket.py

# ==================== INITIALIZATION ====================

async def init_commission_settings():
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    if not settings:
        default_settings = CommissionSettings().model_dump()
        default_settings["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.commission_settings.insert_one(default_settings)

async def init_admin():
    admin = await db.admins.find_one({"login": "admin"}, {"_id": 0})
    if not admin:
        admin_doc = {
            "id": str(uuid.uuid4()),
            "login": "admin",
            "password_hash": hash_password("admin123"),
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.admins.insert_one(admin_doc)

async def auto_complete_guarantor_orders():
    """Background task to auto-complete guarantor orders after deadline"""
    while True:
        try:
            now = datetime.now(timezone.utc)
            pending_orders = await db.marketplace_purchases.find({
                "status": "pending_confirmation",
                "purchase_type": "guarantor",
                "auto_complete_at": {"$lte": now.isoformat()}
            }, {"_id": 0}).to_list(100)
            
            for order in pending_orders:
                try:
                    purchase_id = order["id"]
                    product_id = order["product_id"]
                    seller_id = order["seller_id"]
                    quantity = order["quantity"]
                    total_with_guarantor = order.get("total_with_guarantor", order["total_price"])
                    seller_receives = order["seller_receives"]
                    platform_commission = order["commission"]
                    reserved_content = order.get("reserved_content", [])
                    
                    # Release stock from reserved
                    product = await db.shop_products.find_one({"id": product_id})
                    if product:
                        auto_content = product.get("auto_content", [])
                        new_content = [c for c in auto_content if c not in reserved_content]
                        await db.shop_products.update_one(
                            {"id": product_id},
                            {
                                "$set": {"auto_content": new_content},
                                "$inc": {"reserved_count": -quantity, "sold_count": quantity}
                            }
                        )
                    
                    # Release escrow from buyer
                    await db.traders.update_one(
                        {"id": order["buyer_id"]},
                        {"$inc": {"balance_escrow": -total_with_guarantor}}
                    )
                    
                    # Pay seller
                    await db.traders.update_one(
                        {"id": seller_id},
                        {"$inc": {"shop_balance": seller_receives}}
                    )
                    
                    # Update order status
                    await db.marketplace_purchases.update_one(
                        {"id": purchase_id},
                        {"$set": {
                            "status": "completed",
                            "delivered_content": reserved_content,
                            "completed_at": now.isoformat(),
                            "confirmed_by": "auto_complete"
                        }}
                    )
                    
                    # Record commission
                    await db.commission_payments.insert_one({
                        "id": str(uuid.uuid4()),
                        "purchase_id": purchase_id,
                        "buyer_id": order["buyer_id"],
                        "seller_id": seller_id,
                        "seller_type": "trader",
                        "amount": platform_commission,
                        "commission_rate": order.get("commission_rate", 5.0),
                        "type": "marketplace_guarantor_auto",
                        "created_at": now.isoformat()
                    })
                    
                    # Notify both parties
                    for party_id in [order["buyer_id"], seller_id]:
                        await db.notifications.insert_one({
                            "id": str(uuid.uuid4()),
                            "user_id": party_id,
                            "type": "order_auto_completed",
                            "title": "Заказ автозавершён",
                            "message": f"Заказ #{purchase_id[:8]} автоматически завершён (истёк срок подтверждения)",
                            "data": {"purchase_id": purchase_id},
                            "read": False,
                            "created_at": now.isoformat()
                        })
                    
                    # Update seller stats
                    await db.traders.update_one(
                        {"id": seller_id},
                        {"$inc": {
                            "shop_stats.total_sales": order["total_price"],
                            "shop_stats.total_orders": 1,
                            "shop_stats.total_commission_paid": platform_commission
                        }}
                    )
                    
                    print(f"[AUTO-COMPLETE] Order {purchase_id[:8]} auto-completed")
                except Exception as e:
                    print(f"[AUTO-COMPLETE] Error processing order {order.get('id', '?')}: {e}")
        except Exception as e:
            print(f"[AUTO-COMPLETE] Task error: {e}")
        
        await asyncio.sleep(60)  # Check every minute


@app.on_event("startup")
async def startup():
    await init_commission_settings()
    await init_admin()
    
    # Migrate: Add nickname to existing users who don't have it
    await db.traders.update_many(
        {"nickname": {"$exists": False}},
        [{"$set": {"nickname": "$login"}}]
    )
    await db.merchants.update_many(
        {"nickname": {"$exists": False}},
        [{"$set": {"nickname": "$login"}}]
    )
    
    # Start background task for auto-canceling expired trades
    asyncio.create_task(auto_cancel_expired_trades())
    
    # Start background task for cleaning up old files from delivered purchases
    asyncio.create_task(cleanup_old_purchase_files())
    
    # Start background task for updating USDT/RUB exchange rate from Binance
    asyncio.create_task(rate_update_loop(db, interval=300))
    logging.info("Started USDT/RUB rate update background task (every 5 min)")
    
    # Start background task for auto-completing guarantor marketplace orders
    asyncio.create_task(auto_complete_guarantor_orders())
    logging.info("Started guarantor auto-complete background task")

async def auto_cancel_expired_trades():
    """Background task to auto-cancel trades and invoices that have expired"""
    # Import webhook senders
    from routes.merchant_api import send_merchant_webhook
    from routes.invoice_api import send_webhook_notification
    
    while True:
        try:
            # Get system settings for timeout
            settings = await db.system_settings.find_one({"key": "system_settings"}, {"_id": 0})
            timeout_minutes = settings.get("trade_timeout_minutes", 30) if settings else 30
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            cancelled_at = datetime.now(timezone.utc).isoformat()
            
            # ========== 1. CANCEL EXPIRED TRADES ==========
            # Find expired pending trades (ONLY if buyer hasn't marked as paid)
            expired_trades = await db.trades.find({
                "status": "pending",
                "created_at": {"$lt": cutoff_time.isoformat()}
            }).to_list(100)
            
            for trade in expired_trades:
                # Cancel the trade
                await db.trades.update_one(
                    {"id": trade["id"]},
                    {"$set": {
                        "status": "cancelled",
                        "cancelled_at": cancelled_at,
                        "cancel_reason": "auto_timeout_no_payment",
                        "cancelled_by": "system"
                    }}
                )
                
                # Return reserved USDT to seller's offer
                if trade.get("offer_id"):
                    await db.offers.update_one(
                        {"id": trade["offer_id"]},
                        {"$inc": {"available_usdt": trade["amount_usdt"]}}
                    )
                
                # Update linked invoice status
                if trade.get("invoice_id"):
                    await db.merchant_invoices.update_one(
                        {"id": trade["invoice_id"]},
                        {"$set": {"status": "cancelled", "cancelled_at": cancelled_at}}
                    )
                
                # Send webhook (prefer Invoice API, fallback to old merchant_api)
                try:
                    if trade.get("invoice_id"):
                        await send_webhook_notification(
                            trade["invoice_id"],
                            "cancelled",
                            {
                                "trade_id": trade["id"],
                                "reason": "auto_timeout",
                                "cancel_reason": f"Клиент не оплатил в течение {timeout_minutes} минут",
                                "cancelled_at": cancelled_at,
                                "cancelled_by": "system"
                            }
                        )
                    elif trade.get("merchant_id"):
                        await send_merchant_webhook(
                            merchant_id=trade["merchant_id"],
                            payment_id=trade["id"],
                            status="cancelled",
                            extra_data={
                                "trade_id": trade["id"],
                                "amount_rub": trade.get("amount_rub", 0),
                                "reason": "auto_timeout",
                                "cancel_reason": f"Клиент не оплатил в течение {timeout_minutes} минут",
                                "cancelled_at": cancelled_at,
                                "cancelled_by": "system"
                            }
                        )
                except Exception as webhook_err:
                    print(f"[AUTO-CANCEL] Webhook error for trade {trade['id']}: {webhook_err}")
                
                print(f"[AUTO-CANCEL] Trade {trade['id']} cancelled - buyer didn't pay in {timeout_minutes} minutes")
            
            # ========== 2. EXPIRE INVOICES WITHOUT TRADE ==========
            # Invoices where client never selected an operator
            expired_invoices = await db.merchant_invoices.find({
                "status": "waiting_requisites",
                "trade_id": {"$exists": False},
                "expires_at": {"$lt": datetime.now(timezone.utc).isoformat()}
            }).to_list(100)
            
            for invoice in expired_invoices:
                await db.merchant_invoices.update_one(
                    {"id": invoice["id"]},
                    {"$set": {"status": "expired", "expired_at": cancelled_at}}
                )
                
                # Send expired webhook
                try:
                    await send_webhook_notification(
                        invoice["id"],
                        "expired",
                        {
                            "reason": "Клиент не выбрал оператора",
                            "expired_at": cancelled_at
                        }
                    )
                except Exception as webhook_err:
                    print(f"[AUTO-EXPIRE] Webhook error for invoice {invoice['id']}: {webhook_err}")
                
                print(f"[AUTO-EXPIRE] Invoice {invoice['id']} expired - client didn't select operator")
            
            # ========== 3. EXPIRE OLD PAYMENT REQUESTS ==========
            expired_requests = await db.payment_requests.find({
                "status": "pending",
                "created_at": {"$lt": cutoff_time.isoformat()}
            }).to_list(100)
            
            for request in expired_requests:
                await db.payment_requests.update_one(
                    {"id": request["id"]},
                    {"$set": {
                        "status": "expired",
                        "expired_at": cancelled_at
                    }}
                )
                print(f"[AUTO-EXPIRE] Payment request {request['id']} expired")
            
        except Exception as e:
            print(f"[AUTO-CANCEL ERROR] {e}")
        
        # Run every minute
        await asyncio.sleep(60)

async def cleanup_old_purchase_files():
    """Background task to delete files from delivered purchases after 7 days"""
    import os
    
    while True:
        try:
            # Find completed marketplace purchases older than 7 days
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
            
            old_purchases = await db.marketplace_purchases.find({
                "status": "completed",
                "completed_at": {"$lt": cutoff_time.isoformat()},
                "files_cleaned": {"$ne": True}  # Not already cleaned
            }).to_list(100)
            
            files_deleted = 0
            
            for purchase in old_purchases:
                delivered_content = purchase.get("delivered_content", [])
                
                for item in delivered_content:
                    if isinstance(item, dict):
                        # Delete photo file
                        photo_url = item.get("photo_url")
                        if photo_url and photo_url.startswith("/api/uploads/"):
                            filename = photo_url.replace("/api/uploads/", "")
                            filepath = os.path.join(str(Path(__file__).parent / "uploads"), filename)
                            if os.path.exists(filepath):
                                try:
                                    os.remove(filepath)
                                    files_deleted += 1
                                except Exception as e:
                                    print(f"[CLEANUP] Failed to delete {filepath}: {e}")
                        
                        # Delete attached file
                        file_url = item.get("file_url")
                        if file_url and file_url.startswith("/api/uploads/"):
                            filename = file_url.replace("/api/uploads/", "")
                            filepath = os.path.join(str(Path(__file__).parent / "uploads"), filename)
                            if os.path.exists(filepath):
                                try:
                                    os.remove(filepath)
                                    files_deleted += 1
                                except Exception as e:
                                    print(f"[CLEANUP] Failed to delete {filepath}: {e}")
                
                # Mark purchase as cleaned but keep text data
                # Replace file URLs with expiration notice
                cleaned_content = []
                for item in delivered_content:
                    if isinstance(item, dict):
                        cleaned_content.append({
                            "text": item.get("text", ""),
                            "photo_url": "[Фото удалено]" if item.get("photo_url") else None,
                            "file_url": "[Файл удалён]" if item.get("file_url") else None
                        })
                    else:
                        cleaned_content.append(item)
                
                await db.marketplace_purchases.update_one(
                    {"id": purchase["id"]},
                    {"$set": {
                        "files_cleaned": True, 
                        "files_cleaned_at": datetime.now(timezone.utc).isoformat(),
                        "delivered_content": cleaned_content
                    }}
                )
            
            if files_deleted > 0:
                print(f"[CLEANUP] Deleted {files_deleted} old files from {len(old_purchases)} purchases")
            
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")
        
        # Run every hour
        await asyncio.sleep(3600)

# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "P2P Exchange API", "status": "running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============ EXCHANGE RATE ENDPOINTS ============

@app.get("/api/exchange-rate")
async def get_exchange_rate():
    """Get current USDT/RUB exchange rate from Binance"""
    cached = get_cached_rate()
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = settings.get("base_rate", 0) if settings else 0
    sell_rate = settings.get("sell_rate", 0) if settings else 0
    rate_source = settings.get("rate_source", "manual") if settings else "manual"
    rate_updated = settings.get("rate_updated_at", None) if settings else None
    
    return {
        "base_rate": base_rate,
        "sell_rate": sell_rate,
        "rate_source": rate_source,
        "rate_updated_at": rate_updated,
        "cached": cached
    }

@app.post("/api/exchange-rate/refresh")
async def refresh_exchange_rate(user: dict = Depends(get_current_user)):
    """Force refresh the exchange rate (admin only)"""
    if user.get("role") not in ["admin", "owner", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    rate = await update_base_rate_in_db(db)
    if rate:
        return {"success": True, "rate": rate, "cached": get_cached_rate()}
    raise HTTPException(status_code=500, detail="Failed to fetch rate from all sources")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
