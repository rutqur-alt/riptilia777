from fastapi import APIRouter
from .auth_routes import router as auth_router
from .invoice_routes import router as invoice_router
from .status_routes import router as status_router
from .balance_routes import router as balance_router
from .transaction_routes import router as transaction_router
from .operator_routes import router as operator_router
from .requisite_routes import router as requisite_router
from .payment_routes import router as payment_router
from .dispute_routes import router as dispute_router

router = APIRouter(prefix="/merchant/v1", tags=["Merchant API"])

router.include_router(auth_router)
router.include_router(invoice_router)
router.include_router(status_router)
router.include_router(balance_router)
router.include_router(transaction_router)
router.include_router(operator_router)
router.include_router(requisite_router)
router.include_router(payment_router)
router.include_router(dispute_router)
