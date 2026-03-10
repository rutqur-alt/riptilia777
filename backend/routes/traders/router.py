
from fastapi import APIRouter
from .profile_routes import router as profile_router
from .public_routes import router as public_router

router = APIRouter()

# Include sub-routers
# Profile routes (require auth)
router.include_router(profile_router, prefix="/traders", tags=["Trader Profile"])

# Public routes
router.include_router(public_router, prefix="/public/traders", tags=["Public Traders"])
