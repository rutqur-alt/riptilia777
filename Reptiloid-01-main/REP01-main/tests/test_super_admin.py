"""
Super Admin Panel API Tests
Tests for the new Super Admin Panel functionality including:
- Admin authentication
- Platform overview
- User management (ban/unban, balance adjustment)
- Staff management
- Financial overview
- Moderation (chats)
- Commission settings
- Activity logs
- Maintenance mode
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "000000"
TRADER_LOGIN = "trader"
TRADER_PASSWORD = "000000"


class TestAdminAuthentication:
    """Test admin login and authentication"""
    
    def test_admin_login_success(self):
        """Test admin can login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["role"] == "admin", f"Expected admin role, got {data['user']['role']}"
        print(f"✓ Admin login successful, role: {data['user']['role']}")
    
    def test_admin_login_wrong_password(self):
        """Test admin login fails with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Admin login correctly rejected with wrong password")


class TestSuperAdminOverview:
    """Test /api/super-admin/overview endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_overview(self):
        """Test getting platform overview"""
        response = requests.get(f"{BASE_URL}/api/super-admin/overview", headers=self.headers)
        assert response.status_code == 200, f"Overview failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "users" in data, "Missing users in overview"
        assert "trades" in data, "Missing trades in overview"
        assert "volumes" in data, "Missing volumes in overview"
        assert "marketplace" in data, "Missing marketplace in overview"
        
        # Check users structure
        assert "total_traders" in data["users"], "Missing total_traders"
        assert "total_merchants" in data["users"], "Missing total_merchants"
        
        # Check trades structure
        assert "total" in data["trades"], "Missing total trades"
        assert "completed" in data["trades"], "Missing completed trades"
        
        # Check volumes structure
        assert "total_usdt" in data["volumes"], "Missing total_usdt"
        assert "total_commission" in data["volumes"], "Missing total_commission"
        
        print(f"✓ Overview: {data['users']['total_traders']} traders, {data['trades']['completed']} completed trades, {data['volumes']['total_usdt']} USDT volume")
    
    def test_overview_requires_auth(self):
        """Test overview requires authentication"""
        response = requests.get(f"{BASE_URL}/api/super-admin/overview")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Overview correctly requires authentication")


class TestSuperAdminUsers:
    """Test /api/super-admin/users endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_all_users(self):
        """Test getting all users"""
        response = requests.get(f"{BASE_URL}/api/super-admin/users?user_type=all&limit=200", headers=self.headers)
        assert response.status_code == 200, f"Get users failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of users"
        assert len(data) > 0, "Expected at least one user"
        
        # Check user structure
        user = data[0]
        assert "id" in user, "Missing id in user"
        assert "user_type" in user, "Missing user_type in user"
        
        print(f"✓ Got {len(data)} users")
    
    def test_get_traders_only(self):
        """Test filtering by traders"""
        response = requests.get(f"{BASE_URL}/api/super-admin/users?user_type=traders&limit=100", headers=self.headers)
        assert response.status_code == 200, f"Get traders failed: {response.text}"
        data = response.json()
        
        for user in data:
            assert user["user_type"] == "trader", f"Expected trader, got {user['user_type']}"
        
        print(f"✓ Got {len(data)} traders")
    
    def test_get_merchants_only(self):
        """Test filtering by merchants"""
        response = requests.get(f"{BASE_URL}/api/super-admin/users?user_type=merchants&limit=100", headers=self.headers)
        assert response.status_code == 200, f"Get merchants failed: {response.text}"
        data = response.json()
        
        for user in data:
            assert user["user_type"] == "merchant", f"Expected merchant, got {user['user_type']}"
        
        print(f"✓ Got {len(data)} merchants")
    
    def test_search_users(self):
        """Test searching users"""
        response = requests.get(f"{BASE_URL}/api/super-admin/users?search=trader&limit=50", headers=self.headers)
        assert response.status_code == 200, f"Search users failed: {response.text}"
        data = response.json()
        
        print(f"✓ Search returned {len(data)} users matching 'trader'")


class TestSuperAdminStaff:
    """Test /api/super-admin/staff endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_staff_list(self):
        """Test getting staff list"""
        response = requests.get(f"{BASE_URL}/api/super-admin/staff", headers=self.headers)
        assert response.status_code == 200, f"Get staff failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of staff"
        assert len(data) >= 1, "Expected at least one staff member (admin)"
        
        # Check staff structure
        staff = data[0]
        assert "id" in staff, "Missing id in staff"
        assert "login" in staff, "Missing login in staff"
        
        print(f"✓ Got {len(data)} staff members")


class TestSuperAdminFinances:
    """Test /api/super-admin/finances endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_finances_7d(self):
        """Test getting 7-day financial overview"""
        response = requests.get(f"{BASE_URL}/api/super-admin/finances?period=7d", headers=self.headers)
        assert response.status_code == 200, f"Get finances failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "period" in data, "Missing period"
        assert "p2p" in data, "Missing p2p data"
        assert "marketplace" in data, "Missing marketplace data"
        assert "pending_withdrawals" in data, "Missing pending_withdrawals"
        assert "daily_trades" in data, "Missing daily_trades"
        
        # Check p2p structure
        assert "total_commission" in data["p2p"], "Missing total_commission in p2p"
        assert "total_volume_usdt" in data["p2p"], "Missing total_volume_usdt in p2p"
        assert "trade_count" in data["p2p"], "Missing trade_count in p2p"
        
        print(f"✓ Finances: P2P volume {data['p2p']['total_volume_usdt']} USDT, commission {data['p2p']['total_commission']} USDT")
    
    def test_get_finances_different_periods(self):
        """Test different period filters"""
        for period in ["1d", "7d", "30d", "90d"]:
            response = requests.get(f"{BASE_URL}/api/super-admin/finances?period={period}", headers=self.headers)
            assert response.status_code == 200, f"Get finances for {period} failed: {response.text}"
            data = response.json()
            assert data["period"] == period, f"Expected period {period}, got {data['period']}"
        
        print("✓ All period filters work correctly")


class TestSuperAdminMaintenance:
    """Test /api/super-admin/maintenance endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_maintenance_status(self):
        """Test getting maintenance status"""
        response = requests.get(f"{BASE_URL}/api/super-admin/maintenance", headers=self.headers)
        assert response.status_code == 200, f"Get maintenance failed: {response.text}"
        data = response.json()
        
        # Should have enabled field
        assert "enabled" in data or data == {}, f"Unexpected response: {data}"
        
        print(f"✓ Maintenance status: {data.get('enabled', False)}")
    
    def test_toggle_maintenance_mode(self):
        """Test toggling maintenance mode"""
        # Enable maintenance
        response = requests.post(
            f"{BASE_URL}/api/super-admin/maintenance",
            json={"enabled": True, "message": "Test maintenance"},
            headers=self.headers
        )
        assert response.status_code == 200, f"Enable maintenance failed: {response.text}"
        
        # Verify enabled
        response = requests.get(f"{BASE_URL}/api/super-admin/maintenance", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("enabled") == True, "Maintenance should be enabled"
        
        # Disable maintenance
        response = requests.post(
            f"{BASE_URL}/api/super-admin/maintenance",
            json={"enabled": False, "message": ""},
            headers=self.headers
        )
        assert response.status_code == 200, f"Disable maintenance failed: {response.text}"
        
        # Verify disabled
        response = requests.get(f"{BASE_URL}/api/super-admin/maintenance", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("enabled") == False, "Maintenance should be disabled"
        
        print("✓ Maintenance mode toggle works correctly")


class TestSuperAdminActivityLog:
    """Test /api/super-admin/activity-log endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_activity_log(self):
        """Test getting activity log"""
        response = requests.get(f"{BASE_URL}/api/super-admin/activity-log?limit=50", headers=self.headers)
        assert response.status_code == 200, f"Get activity log failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of logs"
        
        if len(data) > 0:
            log = data[0]
            assert "action" in log, "Missing action in log"
            assert "admin_id" in log, "Missing admin_id in log"
            assert "created_at" in log, "Missing created_at in log"
        
        print(f"✓ Got {len(data)} activity log entries")


class TestSuperAdminModerationChats:
    """Test /api/super-admin/moderation/chats endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_chats_for_moderation(self):
        """Test getting chats for moderation"""
        response = requests.get(f"{BASE_URL}/api/super-admin/moderation/chats?limit=50", headers=self.headers)
        assert response.status_code == 200, f"Get chats failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of chats"
        
        print(f"✓ Got {len(data)} chats for moderation")


class TestSuperAdminCommissions:
    """Test /api/super-admin/commissions endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_all_commissions(self):
        """Test getting all commission settings"""
        response = requests.get(f"{BASE_URL}/api/super-admin/commissions/all", headers=self.headers)
        assert response.status_code == 200, f"Get commissions failed: {response.text}"
        data = response.json()
        
        # Check expected fields
        expected_fields = ["trader_commission", "casino_commission", "shop_commission"]
        for field in expected_fields:
            assert field in data, f"Missing {field} in commissions"
        
        print(f"✓ Commission settings: trader={data.get('trader_commission')}%, casino={data.get('casino_commission')}%")


class TestUserBanUnban:
    """Test user ban/unban functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token and find a test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get a trader to test with
        response = requests.get(f"{BASE_URL}/api/super-admin/users?user_type=traders&limit=10", headers=self.headers)
        assert response.status_code == 200
        traders = response.json()
        # Find a trader that's not the main test trader
        self.test_trader = None
        for t in traders:
            if t.get("login") != "trader":
                self.test_trader = t
                break
        if not self.test_trader and len(traders) > 0:
            self.test_trader = traders[0]
    
    def test_ban_user(self):
        """Test banning a user"""
        if not self.test_trader:
            pytest.skip("No test trader available")
        
        user_id = self.test_trader["id"]
        
        # Ban user
        response = requests.post(
            f"{BASE_URL}/api/super-admin/users/{user_id}/ban",
            json={"banned": True, "reason": "Test ban", "duration_hours": None},
            headers=self.headers
        )
        assert response.status_code == 200, f"Ban user failed: {response.text}"
        
        # Verify banned
        response = requests.get(f"{BASE_URL}/api/super-admin/users?user_type=traders&status=blocked", headers=self.headers)
        assert response.status_code == 200
        blocked_users = response.json()
        blocked_ids = [u["id"] for u in blocked_users]
        assert user_id in blocked_ids, "User should be in blocked list"
        
        # Unban user
        response = requests.post(
            f"{BASE_URL}/api/super-admin/users/{user_id}/ban",
            json={"banned": False, "reason": "Test unban", "duration_hours": None},
            headers=self.headers
        )
        assert response.status_code == 200, f"Unban user failed: {response.text}"
        
        print(f"✓ Ban/unban user {self.test_trader.get('login', user_id)} works correctly")


class TestBalanceAdjustment:
    """Test balance adjustment functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token and find a test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, "Admin login failed"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get a trader to test with
        response = requests.get(f"{BASE_URL}/api/super-admin/users?user_type=traders&limit=10", headers=self.headers)
        assert response.status_code == 200
        traders = response.json()
        self.test_trader = traders[0] if traders else None
    
    def test_adjust_balance(self):
        """Test adjusting user balance"""
        if not self.test_trader:
            pytest.skip("No test trader available")
        
        user_id = self.test_trader["id"]
        original_balance = self.test_trader.get("balance_usdt", 0)
        
        # Add balance
        response = requests.post(
            f"{BASE_URL}/api/super-admin/users/{user_id}/balance",
            json={"amount": 10.0, "reason": "Test adjustment"},
            headers=self.headers
        )
        assert response.status_code == 200, f"Add balance failed: {response.text}"
        data = response.json()
        assert data.get("new_balance") == original_balance + 10.0, "Balance not updated correctly"
        
        # Remove balance (restore original)
        response = requests.post(
            f"{BASE_URL}/api/super-admin/users/{user_id}/balance",
            json={"amount": -10.0, "reason": "Test adjustment reversal"},
            headers=self.headers
        )
        assert response.status_code == 200, f"Remove balance failed: {response.text}"
        data = response.json()
        assert data.get("new_balance") == original_balance, "Balance not restored correctly"
        
        print(f"✓ Balance adjustment for {self.test_trader.get('login', user_id)} works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
