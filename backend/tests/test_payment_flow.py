"""
Payment Flow Tests - P2P Crypto Exchange Payment Gateway
Tests the complete payment flow for external customers from merchant sites.
"""
import pytest
import requests
import hashlib
import hmac
import time
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://merchant-api-preview.preview.emergentagent.com')
if not BASE_URL.endswith('/api'):
    BASE_URL = BASE_URL.rstrip('/') + '/api'

# Test credentials
MERCHANT_API_KEY = 'pk_live_2104acf7fcd048c89f3ef31dcf0be172'
MERCHANT_SECRET_KEY = 'sk_live_7be965cae79a406e863791c6ce35768d'
MERCHANT_ID = 'c15086fa-7de6-42b1-a321-f7cb127eeb90'
TRADER_LOGIN = 'trader1'
TRADER_PASSWORD = '000000'


def generate_signature(data, secret_key):
    """Generate HMAC-SHA256 signature like the backend does"""
    sign_data = {}
    for k, v in data.items():
        if k == 'sign' or v is None:
            continue
        if isinstance(v, float) and v == int(v):
            v = int(v)
        sign_data[k] = v
    
    sorted_params = sorted(sign_data.items())
    sign_string = '&'.join(f'{k}={v}' for k, v in sorted_params)
    sign_string += secret_key
    
    signature = hmac.new(
        secret_key.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


class TestMerchantAPI:
    """Test merchant API endpoints"""
    
    def test_merchant_info_valid_key(self):
        """GET /shop/merchant-info/{api_key} - should return merchant info"""
        response = requests.get(f"{BASE_URL}/shop/merchant-info/{MERCHANT_API_KEY}")
        assert response.status_code == 200
        
        data = response.json()
        assert "merchant_id" in data
        assert "company_name" in data
        assert data["status"] == "active"
    
    def test_merchant_info_invalid_key(self):
        """GET /shop/merchant-info/{api_key} - should return 401 for invalid key"""
        response = requests.get(f"{BASE_URL}/shop/merchant-info/invalid_key_123")
        assert response.status_code == 401
    
    def test_payment_methods(self):
        """GET /v1/invoice/payment-methods - should return payment methods"""
        response = requests.get(
            f"{BASE_URL}/v1/invoice/payment-methods",
            headers={"X-Api-Key": MERCHANT_API_KEY}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "payment_methods" in data
        assert len(data["payment_methods"]) > 0
        
        # Check for expected payment methods
        method_ids = [m["id"] for m in data["payment_methods"]]
        assert "card" in method_ids
        assert "sbp" in method_ids
    
    def test_payment_methods_no_auth(self):
        """GET /v1/invoice/payment-methods - should return 422 without X-Api-Key"""
        response = requests.get(f"{BASE_URL}/v1/invoice/payment-methods")
        assert response.status_code == 422


class TestInvoiceCreation:
    """Test invoice creation flow"""
    
    def test_create_invoice_success(self):
        """POST /v1/invoice/create - should create invoice successfully"""
        order_id = f'TEST_{int(time.time())}'
        request_data = {
            'merchant_id': MERCHANT_ID,
            'order_id': order_id,
            'amount': 5000,
            'currency': 'RUB',
            'user_id': 'test_user_123',
            'callback_url': 'https://example.com/callback',
            'payment_method': 'card'
        }
        
        sign = generate_signature(request_data, MERCHANT_SECRET_KEY)
        request_data['sign'] = sign
        
        response = requests.post(
            f"{BASE_URL}/v1/invoice/create",
            json=request_data,
            headers={"X-Api-Key": MERCHANT_API_KEY, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "payment_id" in data
        assert "payment_url" in data
        assert data["payment_id"].startswith("inv_")
    
    def test_create_invoice_invalid_signature(self):
        """POST /v1/invoice/create - should return 400 for invalid signature"""
        order_id = f'TEST_{int(time.time())}'
        request_data = {
            'merchant_id': MERCHANT_ID,
            'order_id': order_id,
            'amount': 5000,
            'currency': 'RUB',
            'user_id': 'test_user_123',
            'callback_url': 'https://example.com/callback',
            'payment_method': 'card',
            'sign': 'invalid_signature'
        }
        
        response = requests.post(
            f"{BASE_URL}/v1/invoice/create",
            json=request_data,
            headers={"X-Api-Key": MERCHANT_API_KEY, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] == "INVALID_SIGNATURE"
    
    def test_create_invoice_minimum_amount(self):
        """POST /v1/invoice/create - should reject amount below minimum"""
        order_id = f'TEST_{int(time.time())}'
        request_data = {
            'merchant_id': MERCHANT_ID,
            'order_id': order_id,
            'amount': 50,  # Below minimum of 100
            'currency': 'RUB',
            'user_id': 'test_user_123',
            'callback_url': 'https://example.com/callback',
            'payment_method': 'card'
        }
        
        sign = generate_signature(request_data, MERCHANT_SECRET_KEY)
        request_data['sign'] = sign
        
        response = requests.post(
            f"{BASE_URL}/v1/invoice/create",
            json=request_data,
            headers={"X-Api-Key": MERCHANT_API_KEY, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] == "INVALID_AMOUNT"


class TestPublicOperators:
    """Test public operators endpoint"""
    
    def test_get_operators(self):
        """GET /public/operators - should return available operators"""
        response = requests.get(f"{BASE_URL}/public/operators?amount_rub=5000")
        assert response.status_code == 200
        
        data = response.json()
        assert "operators" in data
        # Operators list may be empty if no active offers
    
    def test_get_operators_with_usdt_amount(self):
        """GET /public/operators - should work with amount_usdt parameter"""
        response = requests.get(f"{BASE_URL}/public/operators?amount_usdt=50")
        assert response.status_code == 200
        
        data = response.json()
        assert "operators" in data


class TestPaymentPage:
    """Test payment page endpoints"""
    
    def test_get_payment_info_valid_order(self):
        """GET /shop/pay/{order_id} - should return order info"""
        # First create an invoice
        order_id = f'TEST_PAY_{int(time.time())}'
        request_data = {
            'merchant_id': MERCHANT_ID,
            'order_id': order_id,
            'amount': 1000,
            'currency': 'RUB',
            'user_id': 'test_user_pay',
            'callback_url': 'https://example.com/callback',
            'payment_method': 'card'
        }
        
        sign = generate_signature(request_data, MERCHANT_SECRET_KEY)
        request_data['sign'] = sign
        
        create_response = requests.post(
            f"{BASE_URL}/v1/invoice/create",
            json=request_data,
            headers={"X-Api-Key": MERCHANT_API_KEY, "Content-Type": "application/json"}
        )
        
        if create_response.status_code != 200:
            pytest.skip("Could not create invoice for test")
        
        invoice_id = create_response.json()["payment_id"]
        
        # Now get payment info
        response = requests.get(f"{BASE_URL}/shop/pay/{invoice_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "order" in data
        assert data["order"]["id"] == invoice_id
    
    def test_get_payment_info_invalid_order(self):
        """GET /shop/pay/{order_id} - should return 404 for invalid order"""
        response = requests.get(f"{BASE_URL}/shop/pay/invalid_order_123")
        assert response.status_code == 404


class TestTraderAuth:
    """Test trader authentication"""
    
    def test_trader_login_success(self):
        """POST /auth/login - should login trader successfully"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"login": TRADER_LOGIN, "password": TRADER_PASSWORD}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["login"] == TRADER_LOGIN
    
    def test_trader_login_invalid_credentials(self):
        """POST /auth/login - should return 401 for invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"login": "invalid_user", "password": "wrong_password"}
        )
        assert response.status_code == 401


class TestTraderSales:
    """Test trader sales endpoints"""
    
    @pytest.fixture
    def trader_token(self):
        """Get trader authentication token"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"login": TRADER_LOGIN, "password": TRADER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Could not authenticate trader")
    
    def test_get_active_sales(self, trader_token):
        """GET /trades/sales/active - should return active sales"""
        response = requests.get(
            f"{BASE_URL}/trades/sales/active",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_trader_info(self, trader_token):
        """GET /traders/me - should return trader info"""
        response = requests.get(
            f"{BASE_URL}/traders/me",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "balance_usdt" in data
        assert "login" in data


class TestTradeConfirmation:
    """Test trade confirmation flow"""
    
    @pytest.fixture
    def trader_token(self):
        """Get trader authentication token"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"login": TRADER_LOGIN, "password": TRADER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Could not authenticate trader")
    
    def test_confirm_trade_requires_auth(self):
        """POST /trades/{trade_id}/confirm - should require authentication"""
        response = requests.post(f"{BASE_URL}/trades/fake_trade_id/confirm")
        assert response.status_code in [401, 403, 422]
    
    def test_confirm_nonexistent_trade(self, trader_token):
        """POST /trades/{trade_id}/confirm - should return 404 for nonexistent trade"""
        response = requests.post(
            f"{BASE_URL}/trades/nonexistent_trade_123/confirm",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
