from fastapi import APIRouter
from .deal_routes import router as deal_router
from .action_routes import router as action_router
from .dispute_routes import router as dispute_router

router = APIRouter(prefix="/guarantor", tags=["guarantor"])

router.include_router(deal_router)
router.include_router(action_router)
router.include_router(dispute_router)
