from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta, timezone
import asyncio

from core.database import db as mongodb
from routes.ton_finance import (
    get_hot_wallet_balance
)
from .dependencies import require_roles

router = APIRouter()

# Simple in-memory cache for analytics
_analytics_cache = {}

@router.get("/admin/analytics/full")
async def get_full_analytics(
    period: str = "7d",
    user: dict = Depends(require_roles(["admin"]))
):
    """Get comprehensive financial analytics - OPTIMIZED with parallel queries and caching"""
    
    # Check cache (30 second TTL)
    cache_key = f"analytics_{period}"
    cache_ttl = 30
    now_ts = datetime.now(timezone.utc).timestamp()
    
    if cache_key in _analytics_cache:
        cached = _analytics_cache[cache_key]
        if now_ts - cached['time'] < cache_ttl:
            return cached['data']
    
    days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    period_days = days.get(period, 7)
    start_date = datetime.now(timezone.utc) - timedelta(days=period_days)
    
    try:
        # Define all queries as async functions
        async def get_traders_stats():
            pipeline = [{"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$balance_usdt", 0]}}, "count": {"$sum": 1}}}]
            result = await mongodb.traders.aggregate(pipeline).to_list(1)
            return result[0] if result else {"total": 0, "count": 0}
        
        async def get_merchants_stats():
            pipeline = [{"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$balance_usdt", 0]}}, "count": {"$sum": 1}}}]
            result = await mongodb.merchants.aggregate(pipeline).to_list(1)
            return result[0] if result else {"total": 0, "count": 0}
        
        async def get_hw_balance():
            try:
                hw_data = await get_hot_wallet_balance()
                return hw_data.get('balance', 0)
            except:
                return 0
        
        async def get_trades_stats():
            # Use MongoDB aggregation for daily stats instead of Python filtering
            pipeline = [
                {"$match": {"status": "completed", "created_at": {"$gte": start_date.isoformat()}}},
                {"$group": {
                    "_id": {"$substr": ["$created_at", 0, 10]},
                    "volume": {"$sum": {"$ifNull": ["$amount_usdt", 0]}},
                    "fees_rub": {"$sum": {"$ifNull": ["$platform_fee_rub", 0]}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            return await mongodb.trades.aggregate(pipeline).to_list(100)
        
        async def get_pending_stats():
            pipeline = [
                {"$match": {"status": "pending"}},
                {"$group": {"_id": None, "count": {"$sum": 1}, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}}
            ]
            result = await mongodb.withdrawal_requests.aggregate(pipeline).to_list(1)
            return result[0] if result else {"count": 0, "total": 0}
        
        async def get_rate():
            settings = await mongodb.settings.find_one({"type": "payout_settings"}, {"_id": 0, "base_rate": 1})
            return settings.get("base_rate", 78) if settings else 78
        
        # Execute ALL queries in parallel
        traders_stats, merchants_stats, hot_wallet_balance, trades_by_day, pending_stats, base_rate = await asyncio.gather(
            get_traders_stats(),
            get_merchants_stats(),
            get_hw_balance(),
            get_trades_stats(),
            get_pending_stats(),
            get_rate()
        )
        
        # Process results
        traders_balance = traders_stats.get("total", 0) or 0
        traders_count = traders_stats.get("count", 0) or 0
        merchants_balance = merchants_stats.get("total", 0) or 0
        merchants_count = merchants_stats.get("count", 0) or 0
        total_user_balance = traders_balance + merchants_balance
        
        # Calculate platform metrics
        platform_profit = hot_wallet_balance - total_user_balance
        reserve_ratio = (hot_wallet_balance / total_user_balance * 100) if total_user_balance > 0 else 100
        
        # Process trades stats
        total_volume = sum(d.get("volume", 0) for d in trades_by_day)
        total_fees_rub = sum(d.get("fees_rub", 0) for d in trades_by_day)
        total_trades = sum(d.get("count", 0) for d in trades_by_day)
        total_fees_usdt = total_fees_rub / base_rate if base_rate > 0 else 0
        
        # Build daily stats from aggregation results
        daily_map = {d["_id"]: d for d in trades_by_day}
        daily_stats = []
        for i in range(min(period_days, 30)):
            day = datetime.now(timezone.utc) - timedelta(days=i)
            date_key = day.strftime("%Y-%m-%d")
            day_data = daily_map.get(date_key, {})
            daily_stats.append({
                "date": date_key,
                "trades": day_data.get("count", 0),
                "volume": day_data.get("volume", 0),
                "fees": day_data.get("fees_rub", 0) / base_rate if base_rate > 0 else 0
            })
        daily_stats.reverse()
        
        result = {
            "success": True,
            "analytics": {
                "overview": {
                    "hot_wallet_balance": hot_wallet_balance,
                    "traders_balance": traders_balance,
                    "merchants_balance": merchants_balance,
                    "total_user_balance": total_user_balance,
                    "platform_profit": platform_profit,
                    "reserve_ratio": round(reserve_ratio, 2),
                    "is_healthy": reserve_ratio >= 100 or total_user_balance == 0
                },
                "users": {
                    "traders_count": traders_count,
                    "merchants_count": merchants_count,
                    "total_users": traders_count + merchants_count
                },
                "period_stats": {
                    "period": period,
                    "total_volume": round(total_volume, 2),
                    "total_trades": total_trades,
                    "total_fees_usdt": round(total_fees_usdt, 4),
                    "avg_trade_size": round(total_volume / total_trades, 2) if total_trades > 0 else 0
                },
                "pending": {
                    "withdrawals_count": pending_stats.get("count", 0),
                    "withdrawals_amount": round(pending_stats.get("total", 0), 2)
                },
                "daily_stats": daily_stats
            }
        }
        
        # Save to cache
        _analytics_cache[cache_key] = {
            'time': now_ts,
            'data': result
        }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/analytics/top-traders")
async def get_top_traders(
    limit: int = 10,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """Get top traders by volume"""
    try:
        # Get traders with trade stats
        traders = await mongodb.traders.find(
            {"is_deleted": {"$ne": True}},
            {"_id": 0, "id": 1, "login": 1, "nickname": 1, "balance_usdt": 1, 
             "salesCount": 1, "purchasesCount": 1, "created_at": 1}
        ).sort("balance_usdt", -1).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "traders": traders
        }
    except Exception as e:
        return {"success": True, "traders": []}


@router.get("/admin/analytics/top-merchants")
async def get_top_merchants(
    limit: int = 10,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """Get top merchants by volume"""
    try:
        merchants = await mongodb.merchants.find(
            {"is_deleted": {"$ne": True}},
            {"_id": 0, "id": 1, "login": 1, "nickname": 1, "merchant_name": 1,
             "balance_usdt": 1, "merchant_type": 1, "created_at": 1}
        ).sort("balance_usdt", -1).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "merchants": merchants
        }
    except Exception as e:
        return {"success": True, "merchants": []}


@router.get("/admin/users/search")
async def search_users(
    query: str = "",
    role: str = "all",
    user: dict = Depends(require_roles(["admin", "mod", "support"]))
):
    """Search users by ID, login, or nickname"""
    try:
        results = []
        
        search_filter = {}
        if query:
            search_filter["$or"] = [
                {"id": {"$regex": query, "$options": "i"}},
                {"login": {"$regex": query, "$options": "i"}},
                {"nickname": {"$regex": query, "$options": "i"}}
            ]
        
        # Search traders
        if role in ["all", "trader"]:
            traders = await mongodb.traders.find(
                search_filter,
                {"_id": 0, "id": 1, "login": 1, "nickname": 1, "balance_usdt": 1, "created_at": 1}
            ).limit(20).to_list(20)
            
            for t in traders:
                t["role"] = "trader"
                results.append(t)
        
        # Search merchants
        if role in ["all", "merchant"]:
            merchants = await mongodb.merchants.find(
                search_filter,
                {"_id": 0, "id": 1, "login": 1, "nickname": 1, "merchant_name": 1, 
                 "balance_usdt": 1, "created_at": 1}
            ).limit(20).to_list(20)
            
            for m in merchants:
                m["role"] = "merchant"
                results.append(m)
        
        return {
            "success": True,
            "count": len(results),
            "users": results
        }
    except Exception as e:
        return {"success": True, "count": 0, "users": []}


@router.get("/admin/users/{user_id}/details")
async def get_user_full_details(
    user_id: str,
    user: dict = Depends(require_roles(["admin", "mod", "support"]))
):
    """Get full user details including balance and transactions"""
    try:
        # Try to find in traders
        found_user = await mongodb.traders.find_one({"id": user_id}, {"_id": 0})
        role = "trader"
        
        if not found_user:
            # Try merchants
            found_user = await mongodb.merchants.find_one({"id": user_id}, {"_id": 0})
            role = "merchant"
        
        if not found_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Get recent trades
        trades = await mongodb.trades.find(
            {"$or": [{"trader_id": user_id}, {"merchant_id": user_id}]},
            {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        
        # Get withdrawal requests
        withdrawals = await mongodb.withdrawal_requests.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        return {
            "success": True,
            "user": {
                **found_user,
                "role": role
            },
            "recent_trades": trades,
            "withdrawal_requests": withdrawals
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
