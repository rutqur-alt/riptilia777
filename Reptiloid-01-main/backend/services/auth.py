from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import os
from functools import wraps
from typing import List

from services.database import db

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'p2p-exchange-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# ==================== PASSWORD HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ==================== JWT HELPERS ====================

def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate JWT token, return user data"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role")
        
        if not user_id or not role:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Get user from appropriate collection
        if role == "admin":
            user = await db.admins.find_one({"id": user_id}, {"_id": 0})
        elif role == "trader":
            user = await db.traders.find_one({"id": user_id}, {"_id": 0})
            # Update last_seen
            if user:
                await db.traders.update_one(
                    {"id": user_id},
                    {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
                )
        elif role == "merchant":
            user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
        else:
            raise HTTPException(status_code=401, detail="Invalid role")
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(allowed_roles: List[str]):
    """Dependency to require specific roles"""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {allowed_roles}"
            )
        return user
    return role_checker

async def get_merchant_by_api_key(api_key: str = Depends(api_key_header)):
    """Authenticate merchant by API key for external API access"""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Pass X-API-Key header."
        )
    
    merchant = await db.merchants.find_one({"api_key": api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    if merchant.get("status") != "approved":
        raise HTTPException(
            status_code=403,
            detail="Merchant account not approved"
        )
    
    return merchant

__all__ = [
    'hash_password', 'verify_password', 'create_token',
    'get_current_user', 'require_role', 'get_merchant_by_api_key',
    'security', 'api_key_header', 'JWT_SECRET', 'JWT_ALGORITHM'
]
