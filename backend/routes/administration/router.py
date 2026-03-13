from fastapi import APIRouter

from .dashboard_routes import router as dashboard_router
from .users_routes import router as users_router
from .staff_routes import router as staff_router
from .settings_routes import router as settings_router
from .logs_routes import router as logs_router
from .templates_routes import router as templates_router
from .trade_routes import router as trade_router
from .dispute_routes import router as dispute_router
from .offer_routes import router as offer_router
from .finance_routes import router as finance_router

router = APIRouter()

router.include_router(dashboard_router)
router.include_router(users_router)
router.include_router(staff_router)
router.include_router(settings_router)
router.include_router(logs_router)
router.include_router(templates_router)
router.include_router(trade_router)
router.include_router(dispute_router)
router.include_router(offer_router)
router.include_router(finance_router)
