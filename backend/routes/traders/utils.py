
from core.database import db
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

async def get_trader_stats(trader_id: str):
    """Calculate trader stats"""
    total_trades = await db.trades.count_documents({"trader_id": trader_id})
    completed_trades = await db.trades.count_documents({"trader_id": trader_id, "status": "completed"})
    
    success_rate = (completed_trades / total_trades * 100) if total_trades > 0 else 100.0
    
    # Calculate volume
    pipeline = [
        {"$match": {"trader_id": trader_id, "status": "completed"}},
        {"$group": {"_id": None, "total_volume": {"$sum": "$amount_usdt"}}}
    ]
    volume_result = await db.trades.aggregate(pipeline).to_list(1)
    total_volume = volume_result[0]["total_volume"] if volume_result else 0.0
    
    return {
        "total_trades": total_trades,
        "completed_trades": completed_trades,
        "success_rate": round(success_rate, 1),
        "total_volume_usdt": round(total_volume, 2)
    }
