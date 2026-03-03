"""Custom exceptions for BITARBITR SDK"""


class BitarbitrError(Exception):
    """Base exception for BITARBITR SDK"""
    def __init__(self, message: str, code: str = None, status_code: int = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class InvalidAPIKeyError(BitarbitrError):
    """Raised when API key is invalid"""
    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message, code="INVALID_API_KEY", status_code=401)


class InvalidSignatureError(BitarbitrError):
    """Raised when request signature is invalid"""
    def __init__(self, message: str = "Invalid signature"):
        super().__init__(message, code="INVALID_SIGNATURE", status_code=400)


class RateLimitError(BitarbitrError):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str = "Rate limit exceeded", reset_in: int = None):
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", status_code=429)
        self.reset_in = reset_in


class OrderNotFoundError(BitarbitrError):
    """Raised when order/payment is not found"""
    def __init__(self, message: str = "Order not found"):
        super().__init__(message, code="NOT_FOUND", status_code=404)


class DuplicateOrderError(BitarbitrError):
    """Raised when order_id already exists"""
    def __init__(self, message: str = "Duplicate order ID"):
        super().__init__(message, code="DUPLICATE_ORDER_ID", status_code=400)


class InvalidAmountError(BitarbitrError):
    """Raised when amount is invalid"""
    def __init__(self, message: str = "Invalid amount"):
        super().__init__(message, code="INVALID_AMOUNT", status_code=400)


class PaymentMethodNotAvailableError(BitarbitrError):
    """Raised when payment method is not available"""
    def __init__(self, message: str = "Payment method not available"):
        super().__init__(message, code="PAYMENT_METHOD_NOT_AVAILABLE", status_code=400)
