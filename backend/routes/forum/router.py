
from fastapi import APIRouter
from .public_routes import router as public_router
from .admin_routes import router as admin_router

router = APIRouter()

# Public routes - mounted at /forum
router.include_router(public_router, prefix="/forum", tags=["Forum"])

# Admin routes - mounted at /admin/forum
router.include_router(admin_router, prefix="/admin/forum", tags=["Forum Admin"])
