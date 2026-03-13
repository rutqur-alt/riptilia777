from fastapi import APIRouter, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter()

@router.get("/users/search")
async def search_users(query: str, user: dict = Depends(get_current_user)):
    """Search users by nickname or login for messaging"""
    if len(query) < 2:
        return []
    
    traders = await db.traders.find({
        "$or": [
            {"nickname": {"$regex": query, "$options": "i"}},
            {"login": {"$regex": query, "$options": "i"}},
            {"display_name": {"$regex": query, "$options": "i"}}
        ],
        "id": {"$ne": user["id"]}
    }, {"_id": 0, "id": 1, "nickname": 1, "login": 1, "display_name": 1}).to_list(10)
    
    merchants = await db.merchants.find({
        "$or": [
            {"nickname": {"$regex": query, "$options": "i"}},
            {"login": {"$regex": query, "$options": "i"}},
            {"merchant_name": {"$regex": query, "$options": "i"}}
        ],
        "id": {"$ne": user["id"]}
    }, {"_id": 0, "id": 1, "nickname": 1, "login": 1, "merchant_name": 1}).to_list(10)
    
    results = []
    for t in traders:
        nick = t.get("nickname") or t.get("display_name") or t.get("login", "Unknown")
        results.append({"id": t["id"], "nickname": nick, "login": t.get("login"), "type": "user"})
    for m in merchants:
        nick = m.get("nickname") or m.get("merchant_name") or m.get("login", "Unknown")
        results.append({"id": m["id"], "nickname": nick, "login": m.get("login"), "type": "merchant", "name": m.get("merchant_name")})
    
    return results


@router.get("/users/online")
async def get_online_users(user: dict = Depends(get_current_user)):
    """Get list of all users for messaging"""
    traders = await db.traders.find(
        {"id": {"$ne": user["id"]}},
        {"_id": 0, "id": 1, "nickname": 1}
    ).to_list(100)
    
    return [{"id": t["id"], "nickname": t["nickname"], "type": "user"} for t in traders]
