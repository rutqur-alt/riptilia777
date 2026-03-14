
from fastapi import APIRouter
from .user_routes import router as user_router
from .admin_routes import router as admin_router

router = APIRouter()

# User routes
router.include_router(user_router)

# Admin routes
router.include_router(admin_router)
