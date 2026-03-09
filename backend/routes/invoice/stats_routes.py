from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Request
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging

from core.database import db
from .utils import check_rate_limit, get_rate_limit_info

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/transactions")
async def get_merchant_transactions(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    limit: int = 20,
    offset: int = 0
):
    """Получить историю транзакций мерчанта"""
    
    # 1. Verify API key
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # 2. Check rate limit
    if not check_rate_limit(merchant["id"], "transactions"):
        rate_info = get_rate_limit_info(merchant["id"], "transactions")
        raise HTTPException(status_code=429, detail={
            "status": "error",
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Превышен лимит запросов. Повторите через {rate_info['reset_in']} сек."
        })
        
    # 3. Get transactions
    transactions = await db.merchant_invoices.find(
        {"merchant_id": merchant["id"]},
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    # Map fields for API response
    result = []
    for tx in transactions:
        result.append({
            "payment_id": tx["id"],
            "order_id": tx.get("external_order_id"),
            "amount": tx.get("original_amount_rub") or tx.get("amount_rub"),
            "amount_usdt": tx.get("amount_usdt"),
            "currency": tx.get("currency", "RUB"),
            "status": tx["status"],
            "created_at": tx["created_at"],
            "paid_at": tx.get("paid_at")
        })
        
    return {
        "status": "success",
        "transactions": result,
        "count": len(result)
    }


@router.get("/stats")
async def get_merchant_stats(x_api_key: str = Header(..., alias="X-Api-Key")):
    """Получить статистику мерчанта"""
    
    # 1. Verify API key
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
        
    merchant_id = merchant["id"]
    
    # 2. Calculate stats
    pipeline = [
        {"$match": {"merchant_id": merchant_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total_amount": {"$sum": "$amount_rub"},
            "total_usdt": {"$sum": "$amount_usdt"}
        }}
    ]
    
    stats_data = await db.merchant_invoices.aggregate(pipeline).to_list(None)
    
    stats = {
        "total_transactions": 0,
        "successful_transactions": 0,
        "pending_transactions": 0,
        "failed_transactions": 0,
        "total_volume_rub": 0,
        "total_volume_usdt": 0
    }
    
    for item in stats_data:
        status = item["_id"]
        count = item["count"]
        amount = item["total_amount"] or 0
        usdt = item["total_usdt"] or 0
        
        stats["total_transactions"] += count
        
        if status in ["paid", "completed"]:
            stats["successful_transactions"] += count
            stats["total_volume_rub"] += amount
            stats["total_volume_usdt"] += usdt
        elif status in ["pending", "waiting_requisites"]:
            stats["pending_transactions"] += count
        elif status in ["cancelled", "expired", "failed"]:
            stats["failed_transactions"] += count
            
    return {
        "status": "success",
        "stats": stats
    }


@router.get("/docs")
async def get_api_documentation():
    """Получить документацию API"""
    return {
        "version": "1.0",
        "endpoints": {
            "create_invoice": {
                "method": "POST",
                "url": "/api/v1/invoice/create",
                "description": "Создание нового инвойса",
                "params": ["merchant_id", "order_id", "amount", "sign"]
            },
            "check_status": {
                "method": "GET",
                "url": "/api/v1/invoice/status",
                "description": "Проверка статуса инвойса",
                "params": ["merchant_id", "order_id", "sign"]
            },
            "get_transactions": {
                "method": "GET",
                "url": "/api/v1/invoice/transactions",
                "description": "История транзакций",
                "headers": ["X-Api-Key"]
            }
        },
        "webhook_format": {
            "order_id": "string",
            "payment_id": "string",
            "status": "string (paid, cancelled, expired)",
            "amount": "float",
            "sign": "string (HMAC-SHA256)"
        }
    }
