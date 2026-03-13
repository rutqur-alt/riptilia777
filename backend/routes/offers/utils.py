
from core.database import db
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

async def get_payment_details_for_offer(payment_detail_ids):
    """Helper to fetch payment details by IDs"""
    if not payment_detail_ids:
        return []
    
    details = []
    for pid in payment_detail_ids:
        try:
            pd = await db.payment_details.find_one({"_id": ObjectId(pid)})
            if pd:
                # Convert to legacy format for frontend compatibility if needed
                # or just return as is. The frontend expects {type, data: {...}} or similar
                # Based on previous fixes, we might need to adapt.
                # For now, returning the document with string ID.
                pd["id"] = str(pd["_id"])
                del pd["_id"]
                
                # Ensure legacy format compatibility if frontend expects 'type' and 'data'
                if "payment_type" in pd and "type" not in pd:
                    pd["type"] = pd["payment_type"]
                
                # If data is flattened, we might need to structure it, but let's keep it simple first
                details.append(pd)
        except Exception as e:
            logger.error(f"Error fetching payment detail {pid}: {e}")
            continue
    return details

async def get_trader_nickname(trader_id):
    """Helper to get trader nickname"""
    try:
        trader = await db.traders.find_one({"_id": ObjectId(trader_id)})
        if trader:
            return trader.get("nickname", "Unknown")
    except:
        pass
    return "Unknown"
