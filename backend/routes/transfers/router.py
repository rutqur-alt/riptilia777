
from fastapi import APIRouter
from .transfer_routes import router as transfer_router

router = APIRouter()

# Transfer routes - mounted at /transfers
router.include_router(transfer_router, prefix="/transfers", tags=["Transfers"])
