"""
Authentication utilities - password hashing, JWT, dependencies
"""
import bcrypt
import hashlib
import jwt
import uuid
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

from core.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS, ADMIN_ROLES
from core.database import db

security = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    # Try bcrypt first
    try:
        if hashed.startswith("$2"):
            return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        pass
    
    # Try SHA256 (legacy)
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
            # Update last_seen
            if user:
                await db.traders.update_one(
                    {"id": user_id},
                    {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
                )
        elif role == "merchant":
            user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
        elif role == "qr_provider":
            user = await db.qr_providers.find_one({"id": user_id}, {"_id": 0})
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
        if role in ADMIN_ROLES:
            if ADMIN_ROLES[role] >= min_level:
                return user
        if role == "admin":
            admin = await db.admins.find_one({"id": user["id"]}, {"_id": 0})
            if admin:
                admin_role = admin.get("admin_role", "admin")
                if ADMIN_ROLES.get(admin_role, 0) >= min_level:
                    return user
        raise HTTPException(status_code=403, detail="Insufficient admin permissions")
    return admin_checker


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
