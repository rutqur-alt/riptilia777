"""
BITARBITR P2P Platform - Rates Router
Handles currency exchange rates - единственный источник: Rapira Exchange
"""
from fastapi import APIRouter
from datetime import datetime, timezone
import httpx
import logging

router = APIRouter(tags=["Rates"])
logger = logging.getLogger(__name__)

# Rate cache - обновляется каждые 20 секунд
_rate_cache = {
    "rate": 94.0,  # Fallback курс
    "updated_at": None,
    "source": "fallback"
}


async def fetch_rate_rapira():
    """Получить курс USDT/RUB через Rapira Exchange API (единственный источник)
    
    API: GET https://api.rapira.net/open/market/rates
    - Публичный, бесплатный, без API-ключа
    - Лимиты: 5 req/sec, 100 req/min
    - Используем mid price = (askPrice + bidPrice) / 2
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://api.rapira.net/open/market/rates",
            headers={"Accept": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            rates_list = data.get("data", [])
            
            # Ищем USDT/RUB пару
            for pair in rates_list:
                symbol = pair.get("symbol", "")
                if symbol == "USDT/RUB":
                    ask_price = pair.get("askPrice")
                    bid_price = pair.get("bidPrice")
                    
                    # Mid price - наиболее справедливый курс
                    if ask_price and bid_price:
                        mid_price = (float(ask_price) + float(bid_price)) / 2
                        return mid_price, "rapira"
                    
                    # Если нет ask/bid - используем close
                    close_price = pair.get("close")
                    if close_price:
                        return float(close_price), "rapira"
            
            logger.warning("USDT/RUB pair not found in Rapira response")
    return None, None


async def fetch_usdt_rub_rate():
    """Get USDT/RUB rate - единственный источник: Rapira Exchange"""
    global _rate_cache
    
    # Проверяем кэш (20 секунд)
    if _rate_cache.get("updated_at"):
        diff = (datetime.now(timezone.utc) - _rate_cache["updated_at"]).total_seconds()
        if diff < 20:
            return _rate_cache["rate"]
    
    # Единственный источник - Rapira
    try:
        rate, source = await fetch_rate_rapira()
        if rate and rate > 0:
            _rate_cache["rate"] = round(rate, 2)
            _rate_cache["updated_at"] = datetime.now(timezone.utc)
            _rate_cache["source"] = source
            logger.info(f"USDT/RUB rate updated: {_rate_cache['rate']} (source: {source})")
            return _rate_cache["rate"]
    except Exception as e:
        logger.warning(f"Rapira rate source error: {e}")
    
    # Fallback только на кэш, НЕ на другие источники
    return _rate_cache.get("rate", 94.0)


@router.get("/rates/usdt")
async def get_usdt_rate():
    """Get current USDT/RUB exchange rate from Rapira"""
    rate = await fetch_usdt_rub_rate()
    return {
        "usdt_rub": rate,
        "source": _rate_cache.get("source", "fallback"),
        "updated_at": _rate_cache.get("updated_at", datetime.now(timezone.utc)).isoformat() if _rate_cache.get("updated_at") else None
    }


@router.get("/currency/rates")
async def get_all_rates():
    """Get all currency rates from Rapira"""
    rate = await fetch_usdt_rub_rate()
    return {
        "rates": {
            "USDT_RUB": rate
        },
        "source": _rate_cache.get("source", "fallback"),
        "updated_at": _rate_cache.get("updated_at", datetime.now(timezone.utc)).isoformat() if _rate_cache.get("updated_at") else None
    }
