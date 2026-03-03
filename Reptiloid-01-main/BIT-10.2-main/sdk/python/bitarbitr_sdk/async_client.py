"""
BITARBITR SDK - Asynchronous Client
"""

import hmac
import hashlib
from typing import Optional, Dict, Any, List

import httpx

from .exceptions import (
    BitarbitrError,
    InvalidAPIKeyError,
    InvalidSignatureError,
    RateLimitError,
    OrderNotFoundError,
    DuplicateOrderError,
    InvalidAmountError,
    PaymentMethodNotAvailableError
)


class AsyncBitarbitrSDK:
    """
    BITARBITR P2P Payment Gateway SDK (Asynchronous)
    
    Args:
        api_key: Your API key (X-Api-Key header)
        secret_key: Your secret key for signing requests
        merchant_id: Your merchant ID
        base_url: API base URL (default: https://bitarbitr.org)
        timeout: Request timeout in seconds (default: 30)
    
    Example:
        >>> sdk = AsyncBitarbitrSDK(
        ...     api_key='sk_live_xxx',
        ...     secret_key='your_secret',
        ...     merchant_id='merch_xxx'
        ... )
        >>> async with sdk:
        ...     methods = await sdk.get_payment_methods()
        ...     invoice = await sdk.create_invoice(...)
    """
    
    # Payment statuses
    STATUS_WAITING_REQUISITES = 'waiting_requisites'
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'
    STATUS_DISPUTE = 'dispute'
    
    # Payment methods
    METHOD_CARD = 'card'
    METHOD_SBP = 'sbp'
    METHOD_SIM = 'sim'
    METHOD_MONO_BANK = 'mono_bank'
    METHOD_SNG_SBP = 'sng_sbp'
    METHOD_SNG_CARD = 'sng_card'
    METHOD_QR_CODE = 'qr_code'
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        merchant_id: str,
        base_url: str = "https://bitarbitr.org",
        timeout: int = 30
    ):
        if not api_key:
            raise ValueError("api_key is required")
        if not secret_key:
            raise ValueError("secret_key is required")
        if not merchant_id:
            raise ValueError("merchant_id is required")
        
        self.api_key = api_key
        self.secret_key = secret_key
        self.merchant_id = merchant_id
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                'X-Api-Key': self.api_key,
                'Content-Type': 'application/json'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _api_url(self, endpoint: str) -> str:
        """Build full API URL"""
        return f"{self.base_url}/api/v1/invoice{endpoint}"
    
    def generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature"""
        sign_data = {}
        for key, value in params.items():
            if key != 'sign' and value is not None:
                if isinstance(value, float) and value == int(value):
                    value = int(value)
                sign_data[key] = value
        
        sorted_params = sorted(sign_data.items())
        sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
        sign_string += self.secret_key
        
        return hmac.new(
            self.secret_key.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_webhook(self, payload: Dict[str, Any], provided_sign: str) -> bool:
        """Verify webhook signature"""
        expected_sign = self.generate_signature(payload)
        return hmac.compare_digest(expected_sign.lower(), provided_sign.lower())
    
    def _handle_error(self, response: httpx.Response) -> None:
        """Handle API error responses"""
        try:
            data = response.json()
            detail = data.get('detail', {})
            
            if isinstance(detail, dict):
                code = detail.get('code', '')
                message = detail.get('message', str(detail))
            else:
                code = ''
                message = str(detail)
            
            error_map = {
                'INVALID_API_KEY': InvalidAPIKeyError,
                'INVALID_SIGNATURE': InvalidSignatureError,
                'RATE_LIMIT_EXCEEDED': RateLimitError,
                'NOT_FOUND': OrderNotFoundError,
                'DUPLICATE_ORDER_ID': DuplicateOrderError,
                'INVALID_AMOUNT': InvalidAmountError,
                'PAYMENT_METHOD_NOT_AVAILABLE': PaymentMethodNotAvailableError
            }
            
            error_class = error_map.get(code, BitarbitrError)
            raise error_class(message)
            
        except (ValueError, KeyError):
            raise BitarbitrError(
                f"API error: {response.status_code} {response.text}",
                status_code=response.status_code
            )
    
    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("SDK must be used as async context manager: async with sdk:")
        return self._client
    
    async def get_payment_methods(self) -> List[Dict[str, str]]:
        """Get available payment methods"""
        response = await self.client.get(self._api_url('/payment-methods'))
        
        if response.status_code != 200:
            self._handle_error(response)
        
        return response.json().get('payment_methods', [])
    
    async def create_invoice(
        self,
        order_id: str,
        amount: float,
        callback_url: str,
        payment_method: Optional[str] = None,
        user_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new payment invoice"""
        params = {
            'merchant_id': self.merchant_id,
            'order_id': order_id,
            'amount': amount,
            'currency': 'RUB',
            'callback_url': callback_url,
            'payment_method': payment_method,
            'user_id': user_id,
            'description': description
        }
        
        params['sign'] = self.generate_signature(params)
        
        response = await self.client.post(
            self._api_url('/create'),
            json=params
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        data = response.json()
        return {
            'status': data.get('status'),
            'payment_id': data.get('payment_id'),
            'payment_url': data.get('payment_url'),
            'details': data.get('details', {})
        }
    
    async def get_status(
        self,
        order_id: Optional[str] = None,
        payment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check payment status"""
        if not order_id and not payment_id:
            raise ValueError("Either order_id or payment_id is required")
        
        sign_data = {'merchant_id': self.merchant_id}
        if order_id:
            sign_data['order_id'] = order_id
        if payment_id:
            sign_data['payment_id'] = payment_id
        
        sign = self.generate_signature(sign_data)
        
        params = {'merchant_id': self.merchant_id, 'sign': sign}
        if order_id:
            params['order_id'] = order_id
        if payment_id:
            params['payment_id'] = payment_id
        
        response = await self.client.get(
            self._api_url('/status'),
            params=params
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        data = response.json().get('data', {})
        return {
            'order_id': data.get('order_id'),
            'payment_id': data.get('payment_id'),
            'status': data.get('status'),
            'amount': data.get('amount'),
            'amount_usdt': data.get('amount_usdt'),
            'created_at': data.get('created_at'),
            'paid_at': data.get('paid_at'),
            'dispute_url': data.get('dispute_url')
        }
    
    async def get_transactions(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get list of transactions"""
        params = {'limit': limit, 'offset': offset}
        if status:
            params['status'] = status
        
        response = await self.client.get(
            self._api_url('/transactions'),
            params=params
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        data = response.json().get('data', {})
        return {
            'transactions': data.get('transactions', []),
            'total': data.get('total', 0),
            'limit': data.get('limit', limit),
            'offset': data.get('offset', offset)
        }
    
    async def get_stats(self, period: str = 'today') -> Dict[str, Any]:
        """Get merchant statistics"""
        response = await self.client.get(
            self._api_url('/stats'),
            params={'period': period}
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        return response.json().get('data', {})
    
    async def get_analytics(self, period: str = 'month') -> Dict[str, Any]:
        """Get extended analytics"""
        response = await self.client.get(
            self._api_url('/analytics'),
            params={'period': period}
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        return response.json().get('data', {})
