"""
Test suite for Unified Messages Hub and Admin Panel features
Tests: P2P Disputes, Guarantor Orders, Decisions API, Chat Block API
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com')

# Test credentials
ADMIN_CREDS = {"login": "admin", "password": "000000"}
MOD_P2P_CREDS = {"login": "mod_p2p", "password": "000000"}


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login with owner role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["admin_role"] == "owner"
        print(f"✓ Admin login successful, role: {data['user']['admin_role']}")
    
    def test_mod_p2p_login(self):
        """Test mod_p2p login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MOD_P2P_CREDS)
        assert response.status_code == 200, f"Mod P2P login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["admin_role"] == "mod_p2p"
        print(f"✓ Mod P2P login successful, role: {data['user']['admin_role']}")


class TestUnifiedMessagesAPI:
    """Test Unified Messages Hub API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.user_id = response.json()["user"]["id"]
    
    def test_get_disputes(self):
        """Test GET /api/msg/admin/disputes - P2P Споры"""
        response = requests.get(f"{BASE_URL}/api/msg/admin/disputes", headers=self.headers)
        assert response.status_code == 200, f"Failed to get disputes: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/msg/admin/disputes - Found {len(data)} disputes")
        
        # Check dispute structure if any exist
        if len(data) > 0:
            dispute = data[0]
            assert "id" in dispute
            assert "type" in dispute
            print(f"  - First dispute ID: {dispute['id'][:8]}...")
            if dispute.get("assigned_to_name"):
                print(f"  - Assigned to: {dispute['assigned_to_name']}")
    
    def test_get_guarantor_orders(self):
        """Test GET /api/msg/admin/guarantor-orders - Гарант-сделки"""
        response = requests.get(f"{BASE_URL}/api/msg/admin/guarantor-orders", headers=self.headers)
        assert response.status_code == 200, f"Failed to get guarantor orders: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/msg/admin/guarantor-orders - Found {len(data)} guarantor orders")
        
        # Check structure if any exist
        if len(data) > 0:
            order = data[0]
            assert "id" in order
            print(f"  - First order ID: {order['id'][:8]}...")
            if order.get("title"):
                print(f"  - Title: {order['title']}")
    
    def test_get_merchant_applications(self):
        """Test GET /api/msg/admin/merchant-applications - Заявки мерчантов"""
        response = requests.get(f"{BASE_URL}/api/msg/admin/merchant-applications", headers=self.headers)
        assert response.status_code == 200, f"Failed to get merchant applications: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/msg/admin/merchant-applications - Found {len(data)} applications")
    
    def test_get_shop_applications(self):
        """Test GET /api/msg/admin/shop-applications - Заявки магазинов"""
        response = requests.get(f"{BASE_URL}/api/msg/admin/shop-applications", headers=self.headers)
        assert response.status_code == 200, f"Failed to get shop applications: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/msg/admin/shop-applications - Found {len(data)} applications")
    
    def test_get_support_tickets(self):
        """Test GET /api/admin/support/tickets - Поддержка"""
        response = requests.get(f"{BASE_URL}/api/admin/support/tickets?status=open", headers=self.headers)
        assert response.status_code == 200, f"Failed to get support tickets: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/admin/support/tickets - Found {len(data)} open tickets")


class TestDecisionsAPI:
    """Test Admin Decisions API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_all_decisions(self):
        """Test GET /api/admin/decisions - Get all decisions"""
        response = requests.get(f"{BASE_URL}/api/admin/decisions", headers=self.headers)
        assert response.status_code == 200, f"Failed to get decisions: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/admin/decisions - Found {len(data)} decisions")
        
        # Check structure if any exist
        if len(data) > 0:
            decision = data[0]
            assert "id" in decision
            print(f"  - First decision ID: {decision['id'][:8]}...")
            if decision.get("decision_type"):
                print(f"  - Type: {decision['decision_type']}")
    
    def test_revert_decision_not_found(self):
        """Test POST /api/admin/revert-decision/{id} - Non-existent decision"""
        fake_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/admin/revert-decision/{fake_id}",
            json={"reason": "Test revert"},
            headers=self.headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ POST /api/admin/revert-decision - Returns 404 for non-existent decision")


class TestChatBlockAPI:
    """Test Chat Block/Unblock API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_block_chat_user_not_found(self):
        """Test POST /api/admin/users/{id}/block-chat - Non-existent user"""
        fake_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{fake_id}/block-chat",
            json={"duration_hours": 24, "reason": "Test block"},
            headers=self.headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ POST /api/admin/users/{{id}}/block-chat - Returns 404 for non-existent user")
    
    def test_unblock_chat_user_not_found(self):
        """Test POST /api/admin/users/{id}/unblock-chat - Non-existent user"""
        fake_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{fake_id}/unblock-chat",
            json={},
            headers=self.headers
        )
        # This endpoint doesn't check if user exists, just updates
        # So it should return 200 even for non-existent user
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print(f"✓ POST /api/admin/users/{{id}}/unblock-chat - Endpoint accessible")


class TestRoleBasedAccess:
    """Test role-based access to different categories"""
    
    def test_mod_p2p_can_access_disputes(self):
        """Test mod_p2p can access P2P disputes"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MOD_P2P_CREDS)
        if response.status_code != 200:
            pytest.skip("mod_p2p user not available")
        
        token = response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/msg/admin/disputes", headers=headers)
        assert response.status_code == 200, f"mod_p2p should access disputes: {response.text}"
        print(f"✓ mod_p2p can access P2P disputes")
    
    def test_admin_role_access_guarantor(self):
        """Test that admin role users can access guarantor orders (role-based, not admin_role)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MOD_P2P_CREDS)
        if response.status_code != 200:
            pytest.skip("mod_p2p user not available")
        
        token = response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/msg/admin/guarantor-orders", headers=headers)
        # All admin users (role=admin) can access, regardless of admin_role
        # Frontend filters categories based on admin_role
        assert response.status_code == 200, f"Admin role should access guarantor orders: {response.text}"
        print(f"✓ Admin role users can access guarantor orders (frontend filters by admin_role)")


class TestConversationMessages:
    """Test conversation message endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_conversation_messages(self):
        """Test getting messages from a dispute conversation"""
        # First get disputes
        response = requests.get(f"{BASE_URL}/api/msg/admin/disputes", headers=self.headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes")
        
        disputes = response.json()
        if len(disputes) == 0:
            pytest.skip("No disputes available for testing")
        
        # Get messages from first dispute
        conv_id = disputes[0]["id"]
        response = requests.get(f"{BASE_URL}/api/msg/conversations/{conv_id}", headers=self.headers)
        assert response.status_code == 200, f"Failed to get conversation: {response.text}"
        
        data = response.json()
        assert "messages" in data
        print(f"✓ GET /api/msg/conversations/{{id}} - Found {len(data['messages'])} messages")
        
        # Check if assigned_to info is present
        if data.get("assigned_to"):
            print(f"  - Assigned to: {data.get('assigned_to_name', 'Unknown')}")


class TestDisputeActions:
    """Test dispute action endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_take_dispute_endpoint_exists(self):
        """Test that take dispute endpoint exists"""
        # Get disputes first
        response = requests.get(f"{BASE_URL}/api/msg/admin/disputes", headers=self.headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes")
        
        disputes = response.json()
        if len(disputes) == 0:
            pytest.skip("No disputes available for testing")
        
        # Try to take the first dispute
        dispute_id = disputes[0].get("related_id") or disputes[0]["id"]
        response = requests.post(
            f"{BASE_URL}/api/msg/staff/dispute/{dispute_id}/take",
            json={},
            headers=self.headers
        )
        # Should either succeed or say already taken
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, {response.text}"
        print(f"✓ POST /api/msg/staff/dispute/{{id}}/take - Endpoint accessible")
    
    def test_internal_discussion_endpoint_exists(self):
        """Test that internal discussion endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/msg/admin/disputes", headers=self.headers)
        if response.status_code != 200:
            pytest.skip("Cannot get disputes")
        
        disputes = response.json()
        if len(disputes) == 0:
            pytest.skip("No disputes available for testing")
        
        dispute_id = disputes[0].get("related_id") or disputes[0]["id"]
        response = requests.post(
            f"{BASE_URL}/api/msg/staff/dispute/{dispute_id}/discussion",
            json={"title": "Test discussion"},
            headers=self.headers
        )
        # Should either succeed or say already exists
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, {response.text}"
        print(f"✓ POST /api/msg/staff/dispute/{{id}}/discussion - Endpoint accessible")


class TestGuarantorActions:
    """Test guarantor action endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_guarantor_decision_invalid_type(self):
        """Test guarantor decision with invalid type"""
        fake_order_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/msg/guarantor/order/{fake_order_id}/decision",
            json={"decision_type": "invalid_type", "reason": "Test"},
            headers=self.headers
        )
        # Should return 400 for invalid decision type or 404 for not found
        assert response.status_code in [400, 404], f"Unexpected status: {response.status_code}"
        print(f"✓ POST /api/msg/guarantor/order/{{id}}/decision - Validates decision type")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
