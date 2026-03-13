from fastapi import APIRouter

from .user_routes import router as user_router
from .withdrawal_routes import router as withdrawal_router
from .admin_routes import router as admin_router
from .management_routes import router as management_router
from .transfer_routes import router as transfer_router
from .analytics_routes import router as analytics_router
from .adjustment_routes import router as adjustment_router

router = APIRouter(tags=["TON Wallet"])

router.include_router(user_router)
router.include_router(withdrawal_router)
router.include_router(admin_router)
router.include_router(management_router)
router.include_router(transfer_router)
router.include_router(analytics_router)
router.include_router(adjustment_router)
