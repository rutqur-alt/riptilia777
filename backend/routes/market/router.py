from fastapi import APIRouter

from .shop_routes import router as shop_router
from .product_routes import router as product_router
from .admin_routes import router as admin_router
from .public_routes import router as public_router
from .order_routes import router as order_router
from .guarantor_routes import router as guarantor_router
from .shop_api_routes import router as shop_api_router

router = APIRouter()

router.include_router(shop_router)
router.include_router(product_router)
router.include_router(admin_router)
router.include_router(public_router, prefix="/marketplace")
router.include_router(order_router, prefix="/marketplace")
router.include_router(guarantor_router, prefix="/marketplace")
router.include_router(shop_api_router, prefix="/shop")
