"""
Rate fetching service - fetches USDT/RUB rate from exchanges
Primary: Rapira (api.rapira.net)
Fallback 1: Binance
Fallback 2: CoinGecko
"""

import httpx
import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Cache for rate
_rate_cache = {
    "rate": None,
    "source": None,
    "updated_at": None,
    "bid": None,
    "ask": None
}

def get_cached_rate():
    """Get the last cached rate"""
    return _rate_cache.copy()

async def fetch_usdt_rub_rate():
    """Fetch USDT/RUB rate from multiple sources with fallback"""
    
    # Source 1: Rapira exchange (primary)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.rapira.net/open/market/rates",
                headers={"Accept": "application/json"}
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("data", [])
                for item in items:
                    if item.get("symbol") == "USDT/RUB":
                        close_price = float(item.get("close", 0))
                        ask_price = float(item.get("askPrice", 0))
                        bid_price = float(item.get("bidPrice", 0))
                        rate = close_price if close_price > 0 else ask_price
                        if rate > 0:
                            _rate_cache["rate"] = round(rate, 2)
                            _rate_cache["source"] = "Rapira"
                            _rate_cache["updated_at"] = datetime.now(timezone.utc).isoformat()
                            _rate_cache["bid"] = round(bid_price, 2) if bid_price > 0 else None
                            _rate_cache["ask"] = round(ask_price, 2) if ask_price > 0 else None
                            logger.info(f"Rapira rate: {rate} RUB/USDT (bid={bid_price}, ask={ask_price})")
                            return rate
    except Exception as e:
        logger.warning(f"Rapira rate fetch failed: {e}")
    
    # Source 2: Binance ticker price (fallback)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB")
            if r.status_code == 200:
                data = r.json()
                rate = float(data["price"])
                if rate > 0:
                    _rate_cache["rate"] = round(rate, 2)
                    _rate_cache["source"] = "Binance"
                    _rate_cache["updated_at"] = datetime.now(timezone.utc).isoformat()
                    return rate
    except Exception as e:
        logger.warning(f"Binance rate fetch failed: {e}")
    
    # Source 3: CoinGecko as last fallback
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub")
            if r.status_code == 200:
                data = r.json()
                rate = float(data.get("tether", {}).get("rub", 0))
                if rate > 0:
                    _rate_cache["rate"] = round(rate, 2)
                    _rate_cache["source"] = "CoinGecko"
                    _rate_cache["updated_at"] = datetime.now(timezone.utc).isoformat()
                    return rate
    except Exception as e:
        logger.warning(f"CoinGecko rate fetch failed: {e}")
    
    # Return cached rate if all sources fail
    if _rate_cache["rate"]:
        return _rate_cache["rate"]
    
    return None


async def update_base_rate_in_db(db):
    """Fetch rate and update base_rate in payout_settings"""
    rate = await fetch_usdt_rub_rate()
    if rate and rate > 0:
        await db.settings.update_one(
            {"type": "payout_settings"},
            {
                "$set": {
                    "base_rate": round(rate, 2),
                    "rate_source": _rate_cache.get("source", "unknown"),
                    "rate_updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        logger.info(f"Base rate updated: {rate} RUB/USDT from {_rate_cache.get('source')}")
        return rate
    return None


async def rate_update_loop(db, interval=300):
    """Background task to update rate every 5 minutes (300 seconds)"""
    # Initial update immediately
    await update_base_rate_in_db(db)
    
    while True:
        await asyncio.sleep(interval)
        try:
            await update_base_rate_in_db(db)
        except Exception as e:
            logger.error(f"Rate update loop error: {e}")
