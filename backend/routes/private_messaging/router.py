from fastapi import APIRouter
from .search_routes import router as search_router
from .conversation_routes import router as conversation_router
from .message_routes import router as message_router

router = APIRouter(tags=["private_messaging"])

router.include_router(search_router)
router.include_router(conversation_router)
router.include_router(message_router)
