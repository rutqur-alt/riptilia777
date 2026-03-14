
from fastapi import APIRouter
from .notification_routes import router as notification_router
from .badge_routes import router as badge_router
from .status_routes import router as status_router
from .security_routes import router as security_router

router = APIRouter()

# Notification routes - mounted at root level because they have specific paths
router.include_router(notification_router, tags=["Notifications"])

# Badge routes
router.include_router(badge_router, tags=["Badges"])

# Status routes
router.include_router(status_router, tags=["User Status"])

# Security routes
router.include_router(security_router, tags=["Security"])
