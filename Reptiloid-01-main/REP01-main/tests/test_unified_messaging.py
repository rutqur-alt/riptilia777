"""
Test Unified Messaging System - Role Colors and Staff Chat
Tests for:
1. Support role color = BLUE (#3B82F6)
2. Staff chat GET/POST endpoints
3. Role color configuration
4. P2P Disputes API
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com')

# Test credentials
ADMIN_CREDS = {"login": "admin", "password": "000000"}
SUPPORT_CREDS = {"login": "support", "password": "000000"}
TRADER_CREDS = {"login": "trader", "password": "000000"}


class TestRoleColors:
    """Test role color configuration per spec"""
    
    def test_support_color_is_blue(self):
        """Support role must be BLUE (#3B82F6) per spec"""
        # Login as admin
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        
        # Get staff general chat to check role_colors
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check role_colors in response
        role_colors = data.get("role_colors", {})
        assert role_colors.get("support") == "#3B82F6", f"Support color should be #3B82F6 (BLUE), got {role_colors.get('support')}"
        
    def test_admin_color_is_red(self):
        """Admin/Owner role must be RED (#EF4444) per spec"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = resp.json()
        role_colors = data.get("role_colors", {})
        
        assert role_colors.get("admin") == "#EF4444", f"Admin color should be #EF4444 (RED)"
        assert role_colors.get("owner") == "#EF4444", f"Owner color should be #EF4444 (RED)"
        
    def test_moderator_color_is_yellow(self):
        """Moderator roles must be YELLOW (#F59E0B) per spec"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = resp.json()
        role_colors = data.get("role_colors", {})
        
        assert role_colors.get("mod_p2p") == "#F59E0B", f"Mod P2P color should be #F59E0B (YELLOW)"
        assert role_colors.get("mod_market") == "#F59E0B", f"Mod Market color should be #F59E0B (YELLOW)"
        
    def test_user_color_is_white(self):
        """User/Buyer roles must be WHITE (#FFFFFF) per spec"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = resp.json()
        role_colors = data.get("role_colors", {})
        
        assert role_colors.get("user") == "#FFFFFF", f"User color should be #FFFFFF (WHITE)"
        assert role_colors.get("buyer") == "#FFFFFF", f"Buyer color should be #FFFFFF (WHITE)"
        
    def test_merchant_color_is_orange(self):
        """Merchant role must be ORANGE (#F97316) per spec"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = resp.json()
        role_colors = data.get("role_colors", {})
        
        assert role_colors.get("merchant") == "#F97316", f"Merchant color should be #F97316 (ORANGE)"
        
    def test_shop_owner_color_is_purple(self):
        """Shop owner role must be PURPLE (#8B5CF6) per spec"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = resp.json()
        role_colors = data.get("role_colors", {})
        
        assert role_colors.get("shop_owner") == "#8B5CF6", f"Shop owner color should be #8B5CF6 (PURPLE)"


class TestStaffChatAPI:
    """Test staff chat API endpoints"""
    
    def test_get_staff_general_chat_as_admin(self):
        """Admin can access staff general chat"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "conversation" in data
        assert "messages" in data
        assert data["conversation"]["title"] == "Общий чат персонала"
        
    def test_get_staff_general_chat_as_support(self):
        """Support can access staff general chat"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=SUPPORT_CREDS)
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "conversation" in data
        assert "messages" in data
        
    def test_post_message_to_staff_chat_as_admin(self):
        """Admin can send message to staff chat"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.post(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "Test message from admin via pytest"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["sender_role"] == "owner"
        assert data["sender_info"]["color"] == "#EF4444"  # Red for admin
        
    def test_post_message_to_staff_chat_as_support(self):
        """Support can send message to staff chat with BLUE color"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=SUPPORT_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.post(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "Test message from support via pytest"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["sender_role"] == "support"
        assert data["sender_info"]["color"] == "#3B82F6", f"Support message color should be BLUE (#3B82F6)"
        assert data["sender_info"]["role_name"] == "Поддержка"
        
    def test_staff_chat_requires_auth(self):
        """Staff chat requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/msg/staff/general")
        assert resp.status_code in [401, 403]
        
    def test_trader_cannot_access_staff_chat(self):
        """Regular trader cannot access staff chat"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        if login_resp.status_code != 200:
            pytest.skip("Trader user not available")
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/staff/general",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403, "Trader should not access staff chat"


class TestP2PDisputesAPI:
    """Test P2P Disputes API"""
    
    def test_get_disputes_as_admin(self):
        """Admin can view P2P disputes"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/admin/disputes",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should return 200 even if empty
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        
    def test_disputes_requires_admin(self):
        """Disputes endpoint requires admin role"""
        resp = requests.get(f"{BASE_URL}/api/msg/admin/disputes")
        assert resp.status_code in [401, 403]


class TestUserMessagesAPI:
    """Test user messages page API"""
    
    def test_get_conversations_as_trader(self):
        """Trader can get their conversations"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        if login_resp.status_code != 200:
            pytest.skip("Trader user not available")
        token = login_resp.json()["token"]
        
        resp = requests.get(
            f"{BASE_URL}/api/msg/conversations",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
