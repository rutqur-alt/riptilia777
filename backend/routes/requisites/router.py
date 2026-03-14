
from fastapi import APIRouter
from .routes import router as main_router

router = APIRouter()

router.include_router(main_router)
