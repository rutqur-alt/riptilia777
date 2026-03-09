from fastapi import APIRouter
from .invoice_routes import router as invoice_router
from .operator_routes import router as operator_router
from .payment_routes import router as payment_router
from .stats_routes import router as stats_router
from .dispute_routes import router as dispute_router
from .webhook_routes import test_webhook_receiver, get_test_webhooks, clear_test_webhooks

router = APIRouter(prefix="/v1/invoice", tags=["Invoice API v1"])

# Include sub-routers
router.include_router(invoice_router)
router.include_router(operator_router)
router.include_router(payment_router)
router.include_router(stats_router)
router.include_router(dispute_router)

# Webhook testing endpoints (were at the end of invoice_api.py)
# We need to add them to the router manually or create a separate router for them
# Let's check where they are. They were in invoice_api.py but I didn't see them in the extracted files list in my thought process.
# Ah, I see them in the partial view of invoice_api.py at the end of the file outline:
# decorated_definition test_webhook_receiver (1535:1566)
# decorated_definition get_test_webhooks (1569:1586)
# decorated_definition clear_test_webhooks (1589:1600)

# I need to check if I extracted them.
# I read webhook_routes.py and it only had send_webhook and send_webhook_notification.
# I might have missed extracting the test webhook endpoints.

# Let me check webhook_routes.py again.
