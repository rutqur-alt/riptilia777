from datetime import datetime, timezone
import secrets
import time
import hmac
import hashlib
from collections import defaultdict
from typing import Dict, Any

# Rate limits per merchant per minute
RATE_LIMITS = {
    "create": 60,
    "status": 120,
    "transactions": 30
}

# In-memory rate limit storage
_rate_limit_storage = defaultdict(lambda: defaultdict(list))


def generate_id(prefix: str = "inv") -> str:
    """Генерация уникального ID"""
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}_{date_part}_{secrets.token_hex(4).upper()}"


def check_rate_limit(merchant_id: str, endpoint: str) -> bool:
    """Проверка rate limit"""
    limit = RATE_LIMITS.get(endpoint, 60)
    now = time.time()
    window = 60
    
    _rate_limit_storage[merchant_id][endpoint] = [
        t for t in _rate_limit_storage[merchant_id][endpoint]
        if now - t < window
    ]
    
    if len(_rate_limit_storage[merchant_id][endpoint]) >= limit:
        return False
    
    _rate_limit_storage[merchant_id][endpoint].append(now)
    return True


def get_rate_limit_info(merchant_id: str, endpoint: str) -> dict:
    """Получить информацию о rate limit"""
    limit = RATE_LIMITS.get(endpoint, 60)
    now = time.time()
    window = 60
    
    current = len([
        t for t in _rate_limit_storage[merchant_id][endpoint]
        if now - t < window
    ])
    
    return {
        "limit": limit,
        "remaining": max(0, limit - current),
        "reset_in": int(window - (now % window))
    }


def generate_signature(data: Dict[str, Any], secret_key: str) -> str:
    """Генерация HMAC-SHA256 подписи"""
    sign_data = {}
    for k, v in data.items():
        if k == 'sign' or v is None:
            continue
        if isinstance(v, float) and v == int(v):
            v = int(v)
        sign_data[k] = v
    
    sorted_params = sorted(sign_data.items())
    sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
    sign_string += secret_key
    
    signature = hmac.new(
        secret_key.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_signature(data: Dict[str, Any], provided_sign: str, secret_key: str) -> bool:
    """Проверка подписи"""
    expected_sign = generate_signature(data, secret_key)
    return hmac.compare_digest(expected_sign.lower(), provided_sign.lower())
