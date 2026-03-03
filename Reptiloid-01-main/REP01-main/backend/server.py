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

# Import shared WebSocket manager
from core.websocket import manager

# ==================== MAINTENANCE MODE MIDDLEWARE ====================
@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    """Block all non-admin requests when maintenance mode is enabled"""
    # Skip for specific paths - auth must always be accessible
    skip_paths = ["/api/auth/login", "/api/auth/register", "/api/system/status", "/api/admin/", "/api/super-admin/", "/health", "/api/maintenance-status"]
    
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

async def auto_cancel_expired_trades():
    """Background task to auto-cancel trades that have been pending for 30+ minutes"""
    while True:
        try:
            # Get system settings for timeout
            settings = await db.system_settings.find_one({"key": "system_settings"}, {"_id": 0})
            timeout_minutes = settings.get("trade_timeout_minutes", 30) if settings else 30
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            
            # Find expired pending trades (ONLY if buyer hasn't marked as paid)
            # Status "pending" means buyer hasn't clicked "paid" yet
            # Status "paid" means buyer clicked paid, waiting for seller - don't auto-cancel
            expired_trades = await db.trades.find({
                "status": "pending",  # Only pending, not "paid"
                "created_at": {"$lt": cutoff_time.isoformat()}
            }).to_list(100)
            
            for trade in expired_trades:
                # Cancel the trade
                await db.trades.update_one(
                    {"id": trade["id"]},
                    {"$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.now(timezone.utc).isoformat(),
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
                
                print(f"[AUTO-CANCEL] Trade {trade['id']} cancelled - buyer didn't pay in {timeout_minutes} minutes")
            
            # Also check merchant payment requests
            expired_requests = await db.payment_requests.find({
                "status": "pending",
                "created_at": {"$lt": cutoff_time.isoformat()}
            }).to_list(100)
            
            for request in expired_requests:
                await db.payment_requests.update_one(
                    {"id": request["id"]},
                    {"$set": {
                        "status": "expired",
                        "expired_at": datetime.now(timezone.utc).isoformat()
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
                            filepath = f"/app/backend/uploads/{filename}"
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
                            filepath = f"/app/backend/uploads/{filename}"
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
