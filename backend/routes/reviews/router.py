
from fastapi import APIRouter
from .review_routes import router as review_router
from .category_routes import router as category_router
from .favorite_routes import router as favorite_router

router = APIRouter()

# Review routes - mounted at root level because they have specific paths
router.include_router(review_router, tags=["Reviews"])

# Category routes
router.include_router(category_router, tags=["Categories"])

# Favorite routes
router.include_router(favorite_router, tags=["Favorites"])
