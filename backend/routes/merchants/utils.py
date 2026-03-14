
from core.database import db
from bson import ObjectId
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

async def get_merchant_stats(merchant_id: str):
    """Calculate merchant stats"""
    # Total stats
    total_tx = await db.merchant_transactions.count_documents({"merchant_id": merchant_id, "status": "completed"})
    
    pipeline = [
        {"$match": {"merchant_id": merchant_id, "status": "completed"}},
        {"$group": {"_id": None, "total_volume": {"$sum": "$amount_usdt"}}}
    ]
    volume_result = await db.merchant_transactions.aggregate(pipeline).to_list(1)
    total_volume = volume_result[0]["total_volume"] if volume_result else 0.0
    
    # Today stats
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_tx = await db.merchant_transactions.count_documents({
        "merchant_id": merchant_id, 
        "status": "completed",
        "created_at": {"$gte": today_start.isoformat()}
    })
    
    pipeline_today = [
        {"$match": {
            "merchant_id": merchant_id, 
            "status": "completed",
            "created_at": {"$gte": today_start.isoformat()}
        }},
        {"$group": {"_id": None, "total_volume": {"$sum": "$amount_usdt"}}}
    ]
    today_volume_result = await db.merchant_transactions.aggregate(pipeline_today).to_list(1)
    today_volume = today_volume_result[0]["total_volume"] if today_volume_result else 0.0
    
    return {
        "total_transactions": total_tx,
        "total_turnover": round(total_volume, 2),
        "today_transactions": today_tx,
        "today_turnover": round(today_volume, 2)
    }
