"""
BITARBITR SDK - Synchronous Client
"""

import hmac
import hashlib
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import requests

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


class BitarbitrSDK:
    """
    BITARBITR P2P Payment Gateway SDK (Synchronous)
    
    Args:
        api_key: Your API key (X-Api-Key header)
        secret_key: Your secret key for signing requests
        merchant_id: Your merchant ID
        base_url: API base URL (default: https://bitarbitr.org)
        timeout: Request timeout in seconds (default: 30)
    
    Example:
        >>> sdk = BitarbitrSDK(
        ...     api_key='sk_live_xxx',
        ...     secret_key='your_secret',
        ...     merchant_id='merch_xxx'
        ... )
        >>> methods = sdk.get_payment_methods()
        >>> invoice = sdk.create_invoice(
        ...     order_id='ORDER_123',
        ...     amount=1500,
        ...     callback_url='https://yoursite.com/webhook'
        ... )
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
        
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        })
    
    def _api_url(self, endpoint: str) -> str:
        """Build full API URL"""
        return f"{self.base_url}/api/v1/invoice{endpoint}"
    
    def generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC-SHA256 signature for request
        
        Args:
            params: Request parameters (without 'sign')
        
        Returns:
            Hex-encoded signature
        """
        # Filter out None values and 'sign' key
        sign_data = {}
        for key, value in params.items():
            if key != 'sign' and value is not None:
                # Normalize floats
                if isinstance(value, float) and value == int(value):
                    value = int(value)
                sign_data[key] = value
        
        # Sort by keys and build string
        sorted_params = sorted(sign_data.items())
        sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
        sign_string += self.secret_key
        
        # HMAC-SHA256
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_webhook(self, payload: Dict[str, Any], provided_sign: str) -> bool:
        """
        Verify webhook signature
        
        Args:
            payload: Webhook payload (without 'sign')
            provided_sign: Signature from webhook
        
        Returns:
            True if signature is valid
        
        Example:
            >>> @app.route('/webhook', methods=['POST'])
            ... def webhook():
            ...     data = request.json
            ...     sign = data.pop('sign', '')
            ...     if not sdk.verify_webhook(data, sign):
            ...         return {'status': 'error'}, 401
            ...     # Process webhook...
            ...     return {'status': 'ok'}
        """
        expected_sign = self.generate_signature(payload)
        return hmac.compare_digest(expected_sign.lower(), provided_sign.lower())
    
    def _handle_error(self, response: requests.Response) -> None:
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
    
    def get_payment_methods(self) -> List[Dict[str, str]]:
        """
        Get available payment methods
        
        Returns:
            List of payment methods with id, name, description
        
        Example:
            >>> methods = sdk.get_payment_methods()
            >>> for m in methods:
            ...     print(f"{m['id']}: {m['name']}")
        """
        response = self.session.get(
            self._api_url('/payment-methods'),
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        return response.json().get('payment_methods', [])
    
    def create_invoice(
        self,
        order_id: str,
        amount: float,
        callback_url: str,
        payment_method: Optional[str] = None,
        user_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new payment invoice
        
        Args:
            order_id: Unique order ID in your system
            amount: Amount in RUB
            callback_url: URL for webhook notifications
            payment_method: Payment method ID (card, sbp, etc.)
            user_id: User ID in your system (optional)
            description: Payment description (optional)
        
        Returns:
            Invoice data with payment_url
        
        Example:
            >>> invoice = sdk.create_invoice(
            ...     order_id='ORDER_123',
            ...     amount=1500,
            ...     callback_url='https://yoursite.com/webhook',
            ...     payment_method='card'
            ... )
            >>> print(invoice['payment_url'])
            >>> # Open in browser: webbrowser.open(invoice['payment_url'])
        """
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
        
        response = self.session.post(
            self._api_url('/create'),
            json=params,
            timeout=self.timeout
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
    
    def get_status(
        self,
        order_id: Optional[str] = None,
        payment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check payment status
        
        Args:
            order_id: Order ID in your system
            payment_id: Payment ID from BITARBITR
        
        Returns:
            Payment status data
        
        Example:
            >>> status = sdk.get_status(order_id='ORDER_123')
            >>> if status['status'] == 'paid':
            ...     print(f"Payment received: {status['amount']} RUB")
        """
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
        
        response = self.session.get(
            self._api_url('/status'),
            params=params,
            timeout=self.timeout
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
    
    def get_transactions(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get list of transactions
        
        Args:
            status: Filter by status (active, completed, dispute)
            limit: Max results (default: 50)
            offset: Offset for pagination
        
        Returns:
            Transactions list with pagination info
        """
        params = {'limit': limit, 'offset': offset}
        if status:
            params['status'] = status
        
        response = self.session.get(
            self._api_url('/transactions'),
            params=params,
            timeout=self.timeout
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
    
    def get_stats(self, period: str = 'today') -> Dict[str, Any]:
        """
        Get merchant statistics
        
        Args:
            period: Time period (today, week, month, all)
        
        Returns:
            Statistics data
        """
        response = self.session.get(
            self._api_url('/stats'),
            params={'period': period},
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        return response.json().get('data', {})
    
    def get_analytics(self, period: str = 'month') -> Dict[str, Any]:
        """
        Get extended analytics (markers, conversion by payment method, etc.)
        
        Args:
            period: Time period (today, week, month, all)
        
        Returns:
            Analytics data including:
            - conversion_funnel
            - markers statistics
            - payment_methods breakdown
            - amount_distribution
            - peak_hours
        """
        response = self.session.get(
            self._api_url('/analytics'),
            params={'period': period},
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            self._handle_error(response)
        
        return response.json().get('data', {})
