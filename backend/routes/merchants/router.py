
from fastapi import APIRouter
from .profile_routes import router as profile_router
from .public_routes import router as public_router

router = APIRouter()

# Include sub-routers
# Profile routes (require auth)
router.include_router(profile_router, prefix="/merchants", tags=["Merchant Profile"])

# Public routes
router.include_router(public_router, prefix="/public/merchants", tags=["Public Merchants"])
