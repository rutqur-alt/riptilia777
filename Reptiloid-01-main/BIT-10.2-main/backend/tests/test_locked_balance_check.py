"""
Tests for Trader Locked Balance Check and Manual Unfreeze Feature
- GET /api/admin/traders/{trader_id}/locked-check
- POST /api/admin/traders/{trader_id}/unfreeze
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLockedBalanceCheck:
    """Tests for locked balance check and unfreeze endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin and get trader ID"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "admin", "password": "000000"}
        )
        assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"
        self.admin_token = login_response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get traders list
        traders_response = requests.get(
            f"{BASE_URL}/api/admin/traders",
            headers=self.headers
        )
        assert traders_response.status_code == 200, f"Failed to get traders: {traders_response.text}"
        traders = traders_response.json().get("traders", [])
        
        if traders:
            self.trader_id = traders[0]["id"]
            self.trader_user_id = traders[0]["user_id"]
        else:
            pytest.skip("No traders available for testing")
    
    def test_locked_check_endpoint_returns_correct_structure(self):
        """Test that locked-check endpoint returns all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/locked-check",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify all required fields are present
        required_fields = [
            "trader_id", "user_id", "locked_balance_usdt", "available_balance_usdt",
            "active_orders_count", "active_orders_total_usdt", "active_orders",
            "has_mismatch", "mismatch_type", "difference"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify data types
        assert isinstance(data["locked_balance_usdt"], (int, float))
        assert isinstance(data["available_balance_usdt"], (int, float))
        assert isinstance(data["active_orders_count"], int)
        assert isinstance(data["active_orders"], list)
        assert isinstance(data["has_mismatch"], bool)
        
        print(f"✓ Locked check returned correct structure for trader {self.trader_id}")
        print(f"  - Locked: {data['locked_balance_usdt']} USDT")
        print(f"  - Available: {data['available_balance_usdt']} USDT")
        print(f"  - Active orders: {data['active_orders_count']}")
        print(f"  - Has mismatch: {data['has_mismatch']}")
    
    def test_locked_check_nonexistent_trader(self):
        """Test that locked-check returns 404 for non-existent trader"""
        response = requests.get(
            f"{BASE_URL}/api/admin/traders/trd_nonexistent_12345/locked-check",
            headers=self.headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        assert "не найден" in response.json().get("detail", "").lower() or "not found" in response.json().get("detail", "").lower()
        print("✓ Non-existent trader returns 404")
    
    def test_locked_check_requires_auth(self):
        """Test that locked-check requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/locked-check"
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Locked check requires authentication")
    
    def test_unfreeze_requires_admin_role(self):
        """Test that unfreeze endpoint requires admin role (not support)"""
        # Login as trader (non-admin)
        trader_login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "111", "password": "000000"}
        )
        
        if trader_login.status_code == 200:
            trader_token = trader_login.json()["token"]
            trader_headers = {"Authorization": f"Bearer {trader_token}"}
            
            response = requests.post(
                f"{BASE_URL}/api/admin/traders/{self.trader_id}/unfreeze?amount=0.01&reason=Test",
                headers=trader_headers
            )
            
            assert response.status_code in [401, 403], f"Expected 401/403 for non-admin, got {response.status_code}"
            print("✓ Unfreeze requires admin role")
        else:
            print("⚠ Skipped: Could not login as trader")
    
    def test_unfreeze_validates_amount_exceeds_locked(self):
        """Test that unfreeze rejects amount exceeding locked balance"""
        response = requests.post(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/unfreeze?amount=999999&reason=Test",
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        detail = response.json().get("detail", "")
        assert "нельзя" in detail.lower() or "cannot" in detail.lower() or "заморожен" in detail.lower()
        print("✓ Unfreeze rejects amount exceeding locked balance")
    
    def test_unfreeze_validates_negative_amount(self):
        """Test that unfreeze rejects negative amount"""
        response = requests.post(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/unfreeze?amount=-5&reason=Test",
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        detail = response.json().get("detail", "")
        assert "положительн" in detail.lower() or "positive" in detail.lower()
        print("✓ Unfreeze rejects negative amount")
    
    def test_unfreeze_requires_reason(self):
        """Test that unfreeze requires reason parameter"""
        response = requests.post(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/unfreeze?amount=0.01",
            headers=self.headers
        )
        
        # Should fail due to missing required 'reason' parameter
        assert response.status_code == 422, f"Expected 422 for missing reason, got {response.status_code}"
        print("✓ Unfreeze requires reason parameter")
    
    def test_unfreeze_success_updates_balance(self):
        """Test that successful unfreeze updates locked and available balances"""
        # Get initial balances
        initial_check = requests.get(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/locked-check",
            headers=self.headers
        )
        assert initial_check.status_code == 200
        initial_data = initial_check.json()
        
        initial_locked = initial_data["locked_balance_usdt"]
        initial_available = initial_data["available_balance_usdt"]
        
        if initial_locked < 0.01:
            pytest.skip("Not enough locked balance to test unfreeze")
        
        # Perform unfreeze
        unfreeze_amount = 0.01
        response = requests.post(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/unfreeze?amount={unfreeze_amount}&reason=Automated%20test%20unfreeze",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Unfreeze failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert data["unfrozen_amount"] == unfreeze_amount
        
        # Verify balances changed
        final_check = requests.get(
            f"{BASE_URL}/api/admin/traders/{self.trader_id}/locked-check",
            headers=self.headers
        )
        assert final_check.status_code == 200
        final_data = final_check.json()
        
        # Locked should decrease, available should increase
        assert abs(final_data["locked_balance_usdt"] - (initial_locked - unfreeze_amount)) < 0.001, \
            f"Locked balance not updated correctly: {final_data['locked_balance_usdt']} vs expected {initial_locked - unfreeze_amount}"
        assert abs(final_data["available_balance_usdt"] - (initial_available + unfreeze_amount)) < 0.001, \
            f"Available balance not updated correctly: {final_data['available_balance_usdt']} vs expected {initial_available + unfreeze_amount}"
        
        print(f"✓ Unfreeze successfully updated balances")
        print(f"  - Locked: {initial_locked} → {final_data['locked_balance_usdt']}")
        print(f"  - Available: {initial_available} → {final_data['available_balance_usdt']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
