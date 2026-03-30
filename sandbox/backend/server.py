from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Body, Request, File, UploadFile
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
import jwt
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
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

# Core imports - single source of truth
from core.database import db, client
from core.config import (
    JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS,
    ADMIN_ROLES, ROLE_PERMISSIONS, has_permission
)
from utils.rate_service import fetch_usdt_rub_rate, get_cached_rate, rate_update_loop, update_base_rate_in_db

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')


# Allowed MIME types for file uploads
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
}
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

def validate_upload(file: UploadFile) -> None:
    """Validate uploaded file MIME type and extension"""
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Недопустимый тип файла: {file.content_type}")
    if file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Недопустимое расширение файла: {ext}")

app = FastAPI(title="P2P Exchange API")
# Global exception handler - hide stack traces from clients
from starlette.responses import JSONResponse as _SafeJSONResponse
import traceback as _tb

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    _tb.print_exc()  # Log full traceback to server logs
    return _SafeJSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Hide Pydantic version info from validation error responses
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []
    for err in exc.errors():
        # Remove url field that exposes Pydantic version
        clean_err = {k: v for k, v in err.items() if k != "url"}
        errors.append(clean_err)
    return _SafeJSONResponse(
        status_code=422,
        content={"detail": errors}
    )


# Patch FastAPI's JSON encoder to handle bson.ObjectId globally
from bson import ObjectId as _BsonObjectId
from fastapi.encoders import ENCODERS_BY_TYPE
ENCODERS_BY_TYPE[_BsonObjectId] = str

api_router = APIRouter(prefix="/api")

# Import modular routes from modules/
# Auth
from modules.auth.routes import router as auth_router
from modules.auth.two_factor import router as two_factor_router
from modules.auth.captcha import router as captcha_router
# Users
from modules.users.traders import router as traders_router
from modules.users.admin_users import router as admin_users_router
# Admin
from modules.admin.routes import router as admin_router
from modules.admin.dashboard import router as admin_dashboard_router
from modules.admin.management import router as admin_management_router
from modules.admin.super_admin import router as super_admin_router
# Staff
from modules.staff.routes import router as staff_admin_router
from modules.staff.payroll import router as staff_payroll_router
from modules.staff.templates import router as staff_templates_router
# P2P
from modules.p2p.trades import router as trades_router
from modules.p2p.trade_chats import router as trade_chats_router
from modules.p2p.offers import router as offers_router
from modules.p2p.requisites import router as requisites_router
# Merchants
from modules.merchants.routes import router as merchants_router
from modules.merchants.merchant import router as merchant_router
from modules.merchants.api import router as merchant_api_router
from modules.merchants.messages import router as merchant_messages_router
# Shop
from modules.shop.routes import router as shop_router
from modules.shop.api import router as shop_api_router
# Marketplace
from modules.marketplace.routes import router as marketplace_router
from modules.marketplace.guarantor import router as guarantor_router
# Messaging
from modules.messaging.unified import router as unified_messaging_router
from modules.messaging.private import router as private_messaging_router
from modules.messaging.admin_chats import router as admin_chats_router
from modules.messaging.user_chats import router as user_chats_router
from modules.messaging.chat_management import router as chat_management_router
# Finance
from modules.finance.wallet import router as wallet_api_router
from modules.finance.crypto_payouts import router as crypto_payouts_router
from modules.finance.accounting import router as accounting_router
from modules.finance.transfers import router as transfers_router
# Payments
from modules.payments.invoice import router as invoice_api_router
from modules.payments.links import router as payment_links_router
# Notifications
from modules.notifications.routes import router as notifications_router
from modules.notifications.events import router as event_notifications_router
from modules.notifications.broadcast import router as broadcast_router
# Social
from modules.social.forum import router as forum_router
from modules.social.reviews import router as reviews_router
from modules.social.referral import router as referral_router
# Support
from modules.support.routes import router as support_router
# QR Aggregator
from modules.qr_aggregator.routes import router as qr_aggregator_router
from modules.qr_aggregator.webhook import router as qr_webhook_router
from modules.qr_aggregator.provider_routes import router as qr_provider_router
from modules.qr_aggregator.admin_routes import router as qr_admin_router
from modules.agents.routes import router as agents_router

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(two_factor_router)
api_router.include_router(captcha_router)
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
app.include_router(staff_payroll_router)
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
api_router.include_router(shop_api_router)
api_router.include_router(accounting_router)
# QR Aggregator routers
api_router.include_router(qr_aggregator_router)
api_router.include_router(qr_webhook_router)
api_router.include_router(qr_provider_router)
api_router.include_router(qr_admin_router)
api_router.include_router(agents_router)

# Import shared WebSocket manager
from core.websocket import manager



# ==================== WEBSOCKET REAL-TIME MESSAGING ====================
from fastapi import WebSocket, WebSocketDisconnect
from modules.messaging.ws_routes import ws_manager
import jwt as _jwt
from core.config import JWT_SECRET, JWT_ALGORITHM

async def _verify_ws_token(websocket: WebSocket) -> dict:
    """Verify JWT token from WebSocket query params. Returns user payload or None."""
    try:
        token = websocket.query_params.get("token")
        if not token:
            return None
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role")
        if user_id and role:
            return {"user_id": user_id, "role": role}
        return None
    except Exception:
        return None

@app.websocket("/ws/trade/{trade_id}")
async def ws_trade(websocket: WebSocket, trade_id: str):
    user = await _verify_ws_token(websocket)
    if not user:
        await websocket.close(code=4401, reason="Unauthorized")
        return
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
    user = await _verify_ws_token(websocket)
    if not user:
        await websocket.close(code=4401, reason="Unauthorized")
        return
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
    user = await _verify_ws_token(websocket)
    if not user or user.get("role") != "admin":
        await websocket.close(code=4401, reason="Unauthorized")
        return
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
    user = await _verify_ws_token(websocket)
    if not user or user.get("user_id") != user_id:
        await websocket.close(code=4401, reason="Unauthorized")
        return
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

@app.websocket("/ws/global")
async def ws_global(websocket: WebSocket):
    """Global channel for orderbook/offer updates - no auth required"""
    channel = "global"
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

@app.websocket("/ws/admin")
async def ws_admin(websocket: WebSocket):
    """Admin channel for real-time admin panel updates"""
    user = await _verify_ws_token(websocket)
    if not user or user.get("role") != "admin":
        await websocket.close(code=4401, reason="Unauthorized")
        return
    channel = "admin"
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



# ==================== ONION ACCESS MIDDLEWARE ====================
@app.middleware("http")
async def onion_access_middleware(request: Request, call_next):
    """Block admin API routes for non-onion requests.
    Admin roles (owner, admin, mod_p2p, mod_market, support) can only
    access admin endpoints through the .onion hidden service.
    Regular users (trader, merchant, qr_provider) are not affected.
    """
    path = request.url.path
    
    # Admin-only API paths that require onion access
    admin_paths = ["/api/admin/", "/api/super-admin/"]
    
    is_admin_path = any(path.startswith(p) for p in admin_paths)
    
    if not is_admin_path:
        return await call_next(request)
    
    # Check if request comes through onion (nginx sets this header)
    is_onion = request.headers.get("x-onion-access") == "true"
    
    if is_onion:
        # Onion access — allow everything, IP already masked by nginx
        return await call_next(request)
    
    # Non-onion request to admin path — check if user has admin role
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            role = payload.get("role", "")
            admin_role = payload.get("admin_role", "")
            
            # If user has an admin role, block access on non-onion
            if role in ["admin"] or admin_role in ["owner", "admin", "mod_p2p", "mod_market", "support"]:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access denied. Admin panel is only available through the secure channel."}
                )
        except Exception:
            pass
    
    # No valid token or not admin — let it through (will get 401 from endpoint itself)
    return await call_next(request)


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


# ==================== SECURITY HEADERS MIDDLEWARE ====================
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response



@app.middleware("http")
async def deprecated_api_middleware(request: Request, call_next):
    """Add deprecation warning headers to old merchant API v1 responses"""
    response = await call_next(request)
    if request.url.path.startswith("/api/merchant/v1"):
        response.headers["X-API-Deprecated"] = "true"
        response.headers["X-API-Deprecation-Notice"] = "This API version is deprecated. Please migrate to /api/v1/invoice/. See https://reptiloid.vg/api-docs"
        response.headers["X-API-Sunset"] = "2025-09-01"
    return response

# ==================== IDEMPOTENCY MIDDLEWARE ====================
from core.idempotency import should_protect, check_idempotency, complete_idempotency, fail_idempotency, ensure_idempotency_index
import json as _json_mod

@app.middleware("http")
async def idempotency_middleware(request: Request, call_next):
    """Prevent duplicate requests for mutation endpoints"""
    path = request.url.path
    method = request.method
    
    if not should_protect(path, method):
        return await call_next(request)
    
    # Read body for fingerprinting
    body = await request.body()
    
    # Check for duplicate
    dup_result = await check_idempotency(request, body)
    if dup_result and dup_result.get("duplicate"):
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=dup_result.get("status_code", 409),
            content=dup_result.get("body", {"detail": "Duplicate request", "duplicate": True})
        )
    
    # Process the request
    try:
        response = await call_next(request)
        
        # Cache successful responses
        if 200 <= response.status_code < 300:
            resp_body_bytes = b""
            async for chunk in response.body_iterator:
                resp_body_bytes += chunk
            
            try:
                resp_json = _json_mod.loads(resp_body_bytes)
            except Exception:
                resp_json = {"status": "ok"}
            
            await complete_idempotency(request, body, response.status_code, resp_json)
            
            from starlette.responses import Response
            return Response(
                content=resp_body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        else:
            await fail_idempotency(request, body)
        
        return response
    except Exception as e:
        await fail_idempotency(request, body)
        raise


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
# All auth functions imported from core/auth.py (single source of truth)
from core.auth import (
    hash_password, verify_password, password_needs_rehash,
    create_token, get_current_user, require_role, require_admin_level,
    log_admin_action, get_merchant_by_api_key, security, api_key_header
)

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
    # Use update_one with upsert to prevent race condition duplicates
    # when multiple workers start simultaneously
    await db.admins.create_index("login", unique=True)
    existing = await db.admins.find_one({"admin_role": "owner"})
    if not existing:
        try:
            await db.admins.update_one(
                {"login": "admin"},
                {"$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "login": "admin",
                    "nickname": "NIKTO",
                    "display_name": "NIKTO",
                    "password_hash": hash_password("admin123"),
                    "role": "admin",
                    "admin_role": "owner",
                    "level": 100,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
        except Exception:
            pass  # Another worker already created it

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



async def _process_webhook_queue():
    """Background task: process pending webhook retries from webhook_queue collection"""
    import httpx
    from datetime import datetime, timezone, timedelta
    
    WEBHOOK_RETRY_INTERVALS = [60, 300, 900, 3600, 7200, 14400, 43200, 86400]
    
    while True:
        try:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            now = datetime.now(timezone.utc).isoformat()
            
            # Find pending webhooks that are scheduled to be sent
            pending = await db.webhook_queue.find({
                "status": "pending",
                "scheduled_at": {"$lte": now}
            }).limit(10).to_list(10)
            
            for webhook in pending:
                try:
                    # Mark as processing to prevent double-send
                    result = await db.webhook_queue.update_one(
                        {"_id": webhook["_id"], "status": "pending"},
                        {"$set": {"status": "processing"}}
                    )
                    if result.modified_count == 0:
                        continue
                    
                    callback_url = webhook.get("callback_url")
                    payload = webhook.get("payload", {})
                    retry_count = webhook.get("retry_count", 0)
                    
                    success = False
                    try:
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(
                                callback_url,
                                json=payload,
                                headers={"Content-Type": "application/json"}
                            )
                            if response.status_code == 200:
                                try:
                                    resp_data = response.json()
                                    if resp_data.get("status") == "ok":
                                        success = True
                                except:
                                    pass
                    except Exception as e:
                        logging.warning(f"Webhook retry error: {e}")
                    
                    if success:
                        await db.webhook_queue.update_one(
                            {"_id": webhook["_id"]},
                            {"$set": {"status": "delivered", "delivered_at": now}}
                        )
                        logging.info(f"Webhook delivered on retry #{retry_count}: {callback_url}")
                    else:
                        if retry_count < len(WEBHOOK_RETRY_INTERVALS):
                            delay = WEBHOOK_RETRY_INTERVALS[retry_count]
                            next_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
                            await db.webhook_queue.update_one(
                                {"_id": webhook["_id"]},
                                {"$set": {
                                    "status": "pending",
                                    "retry_count": retry_count + 1,
                                    "scheduled_at": next_at,
                                    "last_error": f"Failed attempt #{retry_count + 1}"
                                }}
                            )
                        else:
                            await db.webhook_queue.update_one(
                                {"_id": webhook["_id"]},
                                {"$set": {"status": "failed", "failed_at": now}}
                            )
                            logging.warning(f"Webhook permanently failed after {retry_count} retries: {callback_url}")
                
                except Exception as e:
                    logging.error(f"Error processing webhook queue item: {e}")
                    await db.webhook_queue.update_one(
                        {"_id": webhook["_id"]},
                        {"$set": {"status": "pending"}}
                    )
        except Exception as e:
            logging.error(f"Webhook queue processor error: {e}")
            await asyncio.sleep(60)


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
    
    # Start QR aggregator background sync task
    from modules.qr_aggregator.background_sync import start_background_sync
    start_background_sync()
    logging.info("Started QR aggregator background sync task (every 60 sec)")

    asyncio.create_task(_process_webhook_queue())
    logging.info("Started webhook retry queue processor (every 30 sec)")

    # Start auto-confirm background task for trader 111
    from modules.p2p.auto_confirm import auto_confirm_loop
    asyncio.create_task(auto_confirm_loop())
    logging.info("Started auto-confirm background task for trader 111")


async def auto_cancel_expired_trades():
    """Background task to auto-cancel trades and invoices that have expired"""
    # Import webhook senders
    from modules.merchants.api import send_merchant_webhook
    from modules.payments.invoice import send_webhook_notification
    
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

# ==================== STATIC FILES FOR FORUM UPLOADS ====================
from fastapi.responses import FileResponse

@api_router.get("/uploads/forum/{filename}")
async def get_forum_image(filename: str):
    """Serve forum uploaded images"""
    filepath = Path(__file__).parent / "uploads" / "forum" / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(filepath)

# Include router
app.include_router(api_router)

# WAF (Web Application Firewall)
from core.waf import WAFMiddleware
app.add_middleware(WAFMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Requested-With", "Accept"],
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
    # Stop QR aggregator background sync
    from modules.qr_aggregator.background_sync import stop_background_sync
    stop_background_sync()
    
    client.close()
