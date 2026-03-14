from fastapi import APIRouter

from .trade_routes import router as trade_router
from .action_routes import router as action_router
from .chat_routes import router as chat_router
from .dispute_routes import router as dispute_router

# Create the main router for trades
router = APIRouter()

# Include all sub-routers
# Note: The tags are already defined in server.py when including the main router, 
# but we can add specific tags here if needed.
# For now, we just combine them.

router.include_router(trade_router)
router.include_router(action_router)
router.include_router(chat_router)
router.include_router(dispute_router)
