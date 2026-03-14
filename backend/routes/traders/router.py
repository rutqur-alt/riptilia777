
from fastapi import APIRouter
from .profile_routes import router as profile_router
from .public_routes import router as public_router
from .payment_details_routes import router as payment_details_router

router = APIRouter()

# Include sub-routers
# Profile routes (require auth)
router.include_router(profile_router, prefix="/traders", tags=["Trader Profile"])

# Public routes
router.include_router(public_router, prefix="/public/traders", tags=["Public Traders"])

# Payment details routes (require auth)
router.include_router(payment_details_router, tags=["Trader Payment Details"])
