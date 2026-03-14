from fastapi import APIRouter

from .chat_routes import router as chat_router
from .admin_routes import router as admin_router
from .support_routes import router as support_router
from .user_routes import router as user_router
from .merchant_routes import router as merchant_router
from .trade_routes import router as trade_router
from .chat_management_routes import router as management_router

router = APIRouter()

router.include_router(chat_router)
router.include_router(admin_router)
router.include_router(support_router)
router.include_router(user_router)
router.include_router(merchant_router)
router.include_router(trade_router)
router.include_router(management_router)
