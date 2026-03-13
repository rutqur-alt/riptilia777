import hmac
import hashlib
import json
from core.database import db

def generate_signature(api_secret: str, data: dict) -> str:
    """Generate HMAC-SHA256 signature"""
    sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hmac.new(
        api_secret.encode('utf-8'),
        sorted_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def verify_signature(api_secret: str, data: dict, provided_signature: str) -> bool:
    """Verify HMAC signature"""
    expected = generate_signature(api_secret, data)
    return hmac.compare_digest(expected, provided_signature)

async def verify_merchant(api_key: str, api_secret: str, merchant_id: str):
    """Verify all 3 credentials and return merchant"""
    merchant = await db.merchants.find_one({"api_key": api_key}, {"_id": 0})
    
    if not merchant:
        return None, "INVALID_API_KEY"
    
    if merchant.get("api_secret") != api_secret:
        return None, "INVALID_API_SECRET"
    
    if merchant.get("id") != merchant_id:
        return None, "INVALID_MERCHANT_ID"
    
    if merchant.get("status") != "active":
        return None, "MERCHANT_NOT_ACTIVE"
    
    return merchant, None
