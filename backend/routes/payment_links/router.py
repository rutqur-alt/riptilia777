
from fastapi import APIRouter
from .dashboard_routes import router as dashboard_router
from .public_routes import router as public_router
from .api_routes import router as api_router

router = APIRouter()

# Dashboard routes (require auth) - mounted at /payment-links
router.include_router(dashboard_router, prefix="/payment-links", tags=["Payment Links"])

# Public routes (no auth or client auth) - mounted at /payment-links
router.include_router(public_router, prefix="/payment-links", tags=["Payment Links Public"])

# API routes (API Key auth) - mounted at /v1
router.include_router(api_router, prefix="/v1", tags=["Merchant API"])
