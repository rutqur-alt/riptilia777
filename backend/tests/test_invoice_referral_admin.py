"""
Backend API Tests for Invoice API v1, Referral System, and Admin Merchant Fee Settings
Tests for P2P Crypto Exchange REP01-main with BIT-9-DOK-main integrations
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
TEST_TRADER_LOGIN = f"test_trader_{uuid.uuid4().hex[:6]}"
TEST_TRADER_NICKNAME = f"TestTrader{uuid.uuid4().hex[:4]}"
TEST_TRADER_PASSWORD = "testpass123"

TEST_MERCHANT_LOGIN = f"test_merchant_{uuid.uuid4().hex[:6]}"
TEST_MERCHANT_NICKNAME = f"TestMerchant{uuid.uuid4().hex[:4]}"
TEST_MERCHANT_PASSWORD = "testpass123"

TEST_ADMIN_LOGIN = "admin"
TEST_ADMIN_PASSWORD = "admin123"


class TestInvoiceAPIv1:
    """Invoice API v1 endpoint tests - no auth required for docs"""
    
    def test_invoice_docs_endpoint(self):
        """GET /api/v1/invoice/docs - should return API documentation without auth"""
        response = requests.get(f"{BASE_URL}/api/v1/invoice/docs")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("api_version") == "v1"
        assert "endpoints" in data
        assert "authentication" in data
        assert data["authentication"]["header"] == "X-Api-Key"
        assert "statuses" in data
        print(f"✓ Invoice docs endpoint working - API version: {data['api_version']}")
    
    def test_payment_methods_without_api_key(self):
        """GET /api/v1/invoice/payment-methods - should return 401 without X-Api-Key"""
        response = requests.get(f"{BASE_URL}/api/v1/invoice/payment-methods")
        
        assert response.status_code == 422 or response.status_code == 401, \
            f"Expected 422 or 401 without API key, got {response.status_code}"
        print("✓ Payment methods correctly requires X-Api-Key header")
    
    def test_payment_methods_with_invalid_api_key(self):
        """GET /api/v1/invoice/payment-methods - should return 401 with invalid API key"""
        response = requests.get(
            f"{BASE_URL}/api/v1/invoice/payment-methods",
            headers={"X-Api-Key": "invalid-key-12345"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        if isinstance(detail, dict):
            assert detail.get("code") == "INVALID_API_KEY"
        print("✓ Payment methods correctly rejects invalid API key")
    
    def test_invoice_create_without_api_key(self):
        """POST /api/v1/invoice/create - should return 422 without X-Api-Key"""
        response = requests.post(
            f"{BASE_URL}/api/v1/invoice/create",
            json={
                "merchant_id": "test",
                "order_id": "test-order",
                "amount": 1000,
                "callback_url": "https://example.com/callback",
                "sign": "test-sign"
            }
        )
        
        assert response.status_code == 422 or response.status_code == 401, \
            f"Expected 422 or 401 without API key, got {response.status_code}"
        print("✓ Invoice create correctly requires X-Api-Key header")
    
    def test_invoice_status_without_api_key(self):
        """GET /api/v1/invoice/status - should return 422 without X-Api-Key"""
        response = requests.get(
            f"{BASE_URL}/api/v1/invoice/status",
            params={"merchant_id": "test", "order_id": "test-order"}
        )
        
        assert response.status_code == 422 or response.status_code == 401, \
            f"Expected 422 or 401 without API key, got {response.status_code}"
        print("✓ Invoice status correctly requires X-Api-Key header")


class TestReferralSystem:
    """Referral system endpoint tests - requires authentication"""
    
    @pytest.fixture(scope="class")
    def trader_token(self):
        """Register a test trader and get token"""
        # Try to register new trader
        register_response = requests.post(
            f"{BASE_URL}/api/auth/trader/register",
            json={
                "login": TEST_TRADER_LOGIN,
                "nickname": TEST_TRADER_NICKNAME,
                "password": TEST_TRADER_PASSWORD
            }
        )
        
        if register_response.status_code == 200:
            data = register_response.json()
            return data.get("token")
        
        # If registration fails (user exists), try login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "login": TEST_TRADER_LOGIN,
                "password": TEST_TRADER_PASSWORD
            }
        )
        
        if login_response.status_code == 200:
            return login_response.json().get("token")
        
        pytest.skip("Could not register or login test trader")
    
    def test_referral_endpoint_without_auth(self):
        """GET /api/referral - should return 401/403 without auth"""
        response = requests.get(f"{BASE_URL}/api/referral")
        
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403 without auth, got {response.status_code}"
        print("✓ Referral endpoint correctly requires authentication")
    
    def test_referral_endpoint_with_auth(self, trader_token):
        """GET /api/referral - should return referral data with valid token"""
        response = requests.get(
            f"{BASE_URL}/api/referral",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify referral data structure
        assert "referral_code" in data, "Missing referral_code"
        assert "referral_balance_usdt" in data, "Missing referral_balance_usdt"
        assert "total_earned_usdt" in data, "Missing total_earned_usdt"
        assert "level_stats" in data, "Missing level_stats"
        assert "settings" in data, "Missing settings"
        
        # Verify 3-level referral system
        settings = data["settings"]
        assert "levels" in settings, "Missing levels in settings"
        assert len(settings["levels"]) == 3, "Should have 3 referral levels"
        
        # Verify level percentages (5%, 3%, 1%)
        levels = settings["levels"]
        assert levels[0]["percent"] == 5, f"Level 1 should be 5%, got {levels[0]['percent']}"
        assert levels[1]["percent"] == 3, f"Level 2 should be 3%, got {levels[1]['percent']}"
        assert levels[2]["percent"] == 1, f"Level 3 should be 1%, got {levels[2]['percent']}"
        
        print(f"✓ Referral endpoint working - code: {data['referral_code']}, levels: 3")
    
    def test_referral_withdraw_without_auth(self):
        """POST /api/referral/withdraw - should return 401/403 without auth"""
        response = requests.post(f"{BASE_URL}/api/referral/withdraw")
        
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403 without auth, got {response.status_code}"
        print("✓ Referral withdraw correctly requires authentication")
    
    def test_referral_withdraw_with_zero_balance(self, trader_token):
        """POST /api/referral/withdraw - should fail with insufficient balance"""
        response = requests.post(
            f"{BASE_URL}/api/referral/withdraw",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        # Should fail because new trader has 0 referral balance
        assert response.status_code == 400, f"Expected 400 for zero balance, got {response.status_code}"
        print("✓ Referral withdraw correctly rejects zero balance")
    
    def test_trader_referral_info_endpoint(self, trader_token):
        """GET /api/traders/referral - trader-specific referral info"""
        response = requests.get(
            f"{BASE_URL}/api/traders/referral",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "referral_code" in data
        assert "referral_link" in data
        assert "level_stats" in data
        print(f"✓ Trader referral info endpoint working - link: {data.get('referral_link', '')[:50]}...")


class TestTraderRegistrationWithReferral:
    """Test trader registration with referral code"""
    
    def test_register_trader_with_referral_code(self):
        """Register trader with referral code should create referral chain"""
        # First, get a referral code from existing trader
        first_trader_login = f"ref_trader_{uuid.uuid4().hex[:6]}"
        first_trader_nickname = f"RefTrader{uuid.uuid4().hex[:4]}"
        
        # Register first trader
        response1 = requests.post(
            f"{BASE_URL}/api/auth/trader/register",
            json={
                "login": first_trader_login,
                "nickname": first_trader_nickname,
                "password": "testpass123"
            }
        )
        
        if response1.status_code != 200:
            pytest.skip("Could not register first trader")
        
        first_trader_data = response1.json()
        referral_code = first_trader_data["user"].get("referral_code")
        
        if not referral_code:
            pytest.skip("First trader has no referral code")
        
        # Register second trader with referral code
        second_trader_login = f"ref_trader2_{uuid.uuid4().hex[:6]}"
        second_trader_nickname = f"RefTrader2{uuid.uuid4().hex[:4]}"
        
        response2 = requests.post(
            f"{BASE_URL}/api/auth/trader/register",
            json={
                "login": second_trader_login,
                "nickname": second_trader_nickname,
                "password": "testpass123",
                "referral_code": referral_code
            }
        )
        
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}"
        
        second_trader_data = response2.json()
        assert second_trader_data["user"].get("referred_by") == first_trader_data["user"]["id"], \
            "Second trader should have referred_by set to first trader's ID"
        
        print(f"✓ Trader registration with referral code working - referred_by: {second_trader_data['user'].get('referred_by')[:8]}...")


class TestAdminMerchantFeeSettings:
    """Admin API tests for merchant fee settings"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        # Try common admin credentials
        for creds in [
            {"login": "admin", "password": "admin123"},
            {"login": "admin", "password": "admin"},
            {"login": "owner", "password": "owner123"},
        ]:
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json=creds
            )
            if response.status_code == 200:
                data = response.json()
                user = data.get("user", {})
                if user.get("role") in ["admin", "owner"] or user.get("admin_role") in ["admin", "owner"]:
                    return data.get("token")
        
        pytest.skip("Could not login as admin - no valid admin credentials")
    
    @pytest.fixture(scope="class")
    def test_merchant_id(self, admin_token):
        """Get or create a test merchant ID"""
        # List merchants to get an existing one
        response = requests.get(
            f"{BASE_URL}/api/admin/merchants",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            merchants = response.json()
            if isinstance(merchants, list) and len(merchants) > 0:
                return merchants[0].get("id")
        
        # If no merchants, try to register one
        merchant_login = f"test_merch_{uuid.uuid4().hex[:6]}"
        merchant_nickname = f"TestMerch{uuid.uuid4().hex[:4]}"
        
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/merchant/register",
            json={
                "login": merchant_login,
                "nickname": merchant_nickname,
                "password": "testpass123",
                "merchant_name": "Test Merchant",
                "merchant_type": "shop",
                "telegram": "@test_merchant"
            }
        )
        
        if reg_response.status_code == 200:
            return reg_response.json()["user"]["id"]
        
        pytest.skip("Could not get or create test merchant")
    
    def test_get_merchant_fee_settings_without_auth(self):
        """GET /api/admin/merchants/{id}/fee-settings - should require auth"""
        response = requests.get(f"{BASE_URL}/api/admin/merchants/test-id/fee-settings")
        
        assert response.status_code in [401, 403], \
            f"Expected 401 or 403 without auth, got {response.status_code}"
        print("✓ Merchant fee settings correctly requires authentication")
    
    def test_get_merchant_fee_settings(self, admin_token, test_merchant_id):
        """GET /api/admin/merchants/{id}/fee-settings - should return fee settings"""
        response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{test_merchant_id}/fee-settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "merchant_id" in data
        assert "fee_model" in data
        assert "commission_rate" in data
        assert data["fee_model"] in ["customer_pays", "merchant_pays"], \
            f"Invalid fee_model: {data['fee_model']}"
        
        print(f"✓ Merchant fee settings endpoint working - fee_model: {data['fee_model']}")
    
    def test_update_merchant_fee_settings(self, admin_token, test_merchant_id):
        """PUT /api/admin/merchants/{id}/fee-settings - should update fee settings"""
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{test_merchant_id}/fee-settings",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={
                "fee_model": "merchant_pays",
                "commission_rate": 3.5,
                "withdrawal_commission": 2.5
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "success"
        assert data.get("fee_model") == "merchant_pays"
        
        print(f"✓ Merchant fee settings update working - new fee_model: {data.get('fee_model')}")
    
    def test_get_merchant_method_commissions(self, admin_token, test_merchant_id):
        """GET /api/admin/merchants/{id}/method-commissions - should return method commissions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{test_merchant_id}/method-commissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "merchant_id" in data
        assert "methods" in data
        assert isinstance(data["methods"], list)
        
        print(f"✓ Merchant method commissions endpoint working - methods count: {len(data['methods'])}")
    
    def test_update_merchant_method_commissions(self, admin_token, test_merchant_id):
        """PUT /api/admin/merchants/{id}/method-commissions - should update method commissions"""
        test_methods = [
            {
                "payment_method": "card",
                "intervals": [
                    {"min_amount": 100, "max_amount": 999, "percent": 15},
                    {"min_amount": 1000, "max_amount": 4999, "percent": 12},
                    {"min_amount": 5000, "max_amount": 100000, "percent": 10}
                ]
            },
            {
                "payment_method": "sbp",
                "intervals": [
                    {"min_amount": 100, "max_amount": 999, "percent": 12},
                    {"min_amount": 1000, "max_amount": 100000, "percent": 10}
                ]
            }
        ]
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{test_merchant_id}/method-commissions",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={"methods": test_methods}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "success"
        assert data.get("methods_count") == 2
        
        # Verify the update persisted
        verify_response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{test_merchant_id}/method-commissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        verify_data = verify_response.json()
        assert len(verify_data["methods"]) == 2, "Should have 2 payment methods configured"
        
        print(f"✓ Merchant method commissions update working - saved {data.get('methods_count')} methods")


class TestAdminReferralSettings:
    """Admin API tests for referral settings"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        for creds in [
            {"login": "admin", "password": "admin123"},
            {"login": "admin", "password": "admin"},
            {"login": "owner", "password": "owner123"},
        ]:
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json=creds
            )
            if response.status_code == 200:
                data = response.json()
                user = data.get("user", {})
                if user.get("role") in ["admin", "owner"] or user.get("admin_role") in ["admin", "owner"]:
                    return data.get("token")
        
        pytest.skip("Could not login as admin")
    
    def test_get_referral_settings(self, admin_token):
        """GET /api/admin/referral/settings - should return referral settings"""
        response = requests.get(
            f"{BASE_URL}/api/admin/referral/settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "levels" in data
        assert "min_withdrawal_usdt" in data
        
        print(f"✓ Admin referral settings endpoint working - min withdrawal: {data.get('min_withdrawal_usdt')} USDT")
    
    def test_get_referral_stats(self, admin_token):
        """GET /api/admin/referral/stats - should return referral statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/referral/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_referrals" in data
        assert "by_level" in data
        assert "total_bonuses_paid_usdt" in data
        
        print(f"✓ Admin referral stats endpoint working - total referrals: {data.get('total_referrals')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
