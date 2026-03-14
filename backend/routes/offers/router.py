
from fastapi import APIRouter
from .private_routes import router as private_router
from .public_routes import router as public_router

router = APIRouter()

# Include sub-routers
router.include_router(private_router, prefix="/trader/offers", tags=["Trader Offers"])
router.include_router(public_router, prefix="/public", tags=["Public Offers"])
