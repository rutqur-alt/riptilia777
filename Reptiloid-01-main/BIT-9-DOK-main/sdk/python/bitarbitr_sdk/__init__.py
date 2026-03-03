"""
BITARBITR SDK - Official Python SDK
P2P Payment Gateway Integration

Usage:
    from bitarbitr_sdk import BitarbitrSDK
    
    sdk = BitarbitrSDK(
        api_key='sk_live_xxx',
        secret_key='your_secret',
        merchant_id='merch_xxx'
    )
    
    # Get payment methods
    methods = sdk.get_payment_methods()
    
    # Create invoice
    invoice = sdk.create_invoice(
        order_id='ORDER_123',
        amount=1500,
        callback_url='https://yoursite.com/webhook',
        payment_method='card'
    )
    
    # Open payment URL in new tab
    print(invoice['payment_url'])
"""

from .client import BitarbitrSDK
from .async_client import AsyncBitarbitrSDK
from .exceptions import (
    BitarbitrError,
    InvalidAPIKeyError,
    InvalidSignatureError,
    RateLimitError,
    OrderNotFoundError
)

__version__ = "1.0.0"
__all__ = [
    "BitarbitrSDK",
    "AsyncBitarbitrSDK",
    "BitarbitrError",
    "InvalidAPIKeyError",
    "InvalidSignatureError",
    "RateLimitError",
    "OrderNotFoundError"
]
