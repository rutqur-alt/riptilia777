from fastapi import APIRouter
from .offer_routes import router as offer_router
from .order_routes import router as order_router
from .merchant_routes import router as merchant_router
from .admin_routes import router as admin_router
from .dispute_routes import router as dispute_router
from .settings_routes import router as settings_router

router = APIRouter()

router.include_router(offer_router)
router.include_router(order_router)
router.include_router(merchant_router)
router.include_router(admin_router)
router.include_router(dispute_router)
router.include_router(settings_router)
