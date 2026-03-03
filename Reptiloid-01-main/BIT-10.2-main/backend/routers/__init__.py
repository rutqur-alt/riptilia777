"""
BITARBITR P2P Platform - Routers

Modular router components for the API.
All endpoints are now in modular routers.
"""

from .auth import router as auth_router
from .trader import router as trader_router
from .merchant import router as merchant_router
from .notifications import router as notifications_router
from .tickets import router as tickets_router
from .disputes import router as disputes_router
from .invoice_api import router as invoice_router
from .wallet import router as wallet_router
from .rates import router as rates_router
from .admin import router as admin_router
from .usdt import router as usdt_router
from .shop import router as shop_router

__all__ = [
    "auth_router",
    "trader_router", 
    "merchant_router",
    "notifications_router",
    "tickets_router",
    "disputes_router",
    "invoice_router",
    "wallet_router",
    "rates_router",
    "admin_router",
    "usdt_router",
    "shop_router",
]
