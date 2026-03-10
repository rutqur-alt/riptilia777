
from fastapi import APIRouter
from .routes import router as routes_router

router = APIRouter(prefix="/event-notifications", tags=["event-notifications"])

router.include_router(routes_router)
