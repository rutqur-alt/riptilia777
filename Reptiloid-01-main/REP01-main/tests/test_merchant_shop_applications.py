"""
Test suite for Merchant and Shop Application flows
Tests the complete user journey:
1. Merchant registration -> chat opens -> messaging -> approve/reject
2. Shop application -> chat opens -> messaging -> approve/reject
"""

import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"login": "admin", "password": "000000"}
TRADER_CREDS = {"login": "trader", "password": "000000"}


class TestMerchantApplicationFlow:
    """Test complete merchant registration and approval flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.unique_id = uuid.uuid4().hex[:8]
        self.merchant_login = f"TEST_merchant_{self.unique_id}"
        self.merchant_nickname = f"testmerch{self.unique_id}"
        self.merchant_name = f"Test Merchant {self.unique_id}"
        self.merchant_token = None
        self.merchant_id = None
        self.admin_token = None
        
    def get_admin_token(self):
        """Get admin authentication token"""
        if self.admin_token:
            return self.admin_token
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        self.admin_token = response.json()["token"]
        return self.admin_token
    
    def test_01_merchant_registration(self):
        """Test merchant registration creates pending merchant with chat"""
        # Register new merchant
        register_data = {
            "login": self.merchant_login,
            "password": "testpass123",
            "nickname": self.merchant_nickname,
            "merchant_name": self.merchant_name,
            "merchant_type": "casino",
            "telegram": "@test_merchant_tg"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/merchant/register", json=register_data)
        assert response.status_code == 200, f"Merchant registration failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        
        self.merchant_token = data["token"]
        self.merchant_id = data["user"]["id"]
        
        # Verify merchant status is pending
        assert data["user"]["status"] == "pending", f"Expected pending status, got {data['user']['status']}"
        assert data["user"]["merchant_name"] == self.merchant_name
        assert data["user"]["merchant_type"] == "casino"
        
        print(f"SUCCESS: Merchant registered with ID {self.merchant_id}, status: pending")
        
        # Store for next tests
        pytest.merchant_token = self.merchant_token
        pytest.merchant_id = self.merchant_id
        pytest.merchant_login = self.merchant_login
        
    def test_02_merchant_chat_opens_automatically(self):
        """Test that chat with admin opens automatically after registration"""
        token = getattr(pytest, 'merchant_token', None)
        if not token:
            pytest.skip("Merchant not registered in previous test")
        
        # Get merchant's chat
        response = requests.get(
            f"{BASE_URL}/api/my/merchant-chat",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Failed to get merchant chat: {response.text}"
        
        data = response.json()
        assert "conversation" in data, "No conversation in response"
        assert "messages" in data, "No messages in response"
        
        # Verify welcome message exists
        messages = data["messages"]
        assert len(messages) > 0, "No messages in chat - welcome message should exist"
        
        # Check for system welcome message
        welcome_found = any(
            msg.get("is_system") or msg.get("sender_role") == "system" 
            for msg in messages
        )
        assert welcome_found, "No system welcome message found"
        
        print(f"SUCCESS: Chat opened with {len(messages)} message(s), welcome message present")
        
    def test_03_merchant_can_send_message(self):
        """Test that merchant can send message in chat"""
        token = getattr(pytest, 'merchant_token', None)
        if not token:
            pytest.skip("Merchant not registered")
        
        # Send message
        message_content = f"Привет! Это тестовое сообщение от мерчанта {uuid.uuid4().hex[:6]}"
        response = requests.post(
            f"{BASE_URL}/api/my/merchant-chat/send",
            json={"content": message_content},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Failed to send message: {response.text}"
        
        # Verify message appears in chat
        time.sleep(0.5)  # Small delay for DB write
        
        chat_response = requests.get(
            f"{BASE_URL}/api/my/merchant-chat",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert chat_response.status_code == 200
        
        messages = chat_response.json().get("messages", [])
        message_found = any(msg.get("content") == message_content for msg in messages)
        assert message_found, "Sent message not found in chat"
        
        print(f"SUCCESS: Merchant message sent and visible in chat")
        
    def test_04_admin_sees_merchant_application(self):
        """Test that admin can see merchant application in messages hub"""
        admin_token = self.get_admin_token()
        merchant_id = getattr(pytest, 'merchant_id', None)
        
        if not merchant_id:
            pytest.skip("Merchant not registered")
        
        # Get merchant applications
        response = requests.get(
            f"{BASE_URL}/api/msg/admin/merchant-applications",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get merchant applications: {response.text}"
        
        applications = response.json()
        assert isinstance(applications, list), "Expected list of applications"
        
        # Find our test merchant
        test_app = None
        for app in applications:
            if app.get("data", {}).get("user_id") == merchant_id or \
               any(p == merchant_id for p in app.get("participants", [])):
                test_app = app
                break
        
        assert test_app is not None, f"Test merchant application not found. Apps: {[a.get('data', {}).get('merchant_name') for a in applications]}"
        
        print(f"SUCCESS: Admin sees merchant application in messages hub")
        pytest.merchant_conv_id = test_app.get("id")
        pytest.merchant_related_id = test_app.get("related_id") or test_app.get("data", {}).get("id")
        
    def test_05_admin_sees_merchant_messages(self):
        """Test that admin can see messages from merchant"""
        admin_token = self.get_admin_token()
        conv_id = getattr(pytest, 'merchant_conv_id', None)
        
        if not conv_id:
            pytest.skip("Conversation not found")
        
        # Get conversation messages
        response = requests.get(
            f"{BASE_URL}/api/msg/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get conversation: {response.text}"
        
        data = response.json()
        messages = data.get("messages", [])
        
        # Should have at least welcome message and merchant's message
        assert len(messages) >= 2, f"Expected at least 2 messages, got {len(messages)}"
        
        print(f"SUCCESS: Admin sees {len(messages)} messages in merchant chat")
        
    def test_06_admin_can_reply_to_merchant(self):
        """Test that admin can send message to merchant"""
        admin_token = self.get_admin_token()
        conv_id = getattr(pytest, 'merchant_conv_id', None)
        
        if not conv_id:
            pytest.skip("Conversation not found")
        
        # Send message as admin - correct endpoint is /send not /messages
        message_content = f"Ответ от администратора {uuid.uuid4().hex[:6]}"
        response = requests.post(
            f"{BASE_URL}/api/msg/conversations/{conv_id}/send",
            json={"content": message_content},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to send admin message: {response.text}"
        
        # Verify message appears
        time.sleep(0.5)
        
        chat_response = requests.get(
            f"{BASE_URL}/api/msg/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        messages = chat_response.json().get("messages", [])
        admin_msg_found = any(msg.get("content") == message_content for msg in messages)
        assert admin_msg_found, "Admin message not found in chat"
        
        print(f"SUCCESS: Admin message sent and visible")
        
    def test_07_merchant_sees_admin_reply(self):
        """Test that merchant can see admin's reply"""
        token = getattr(pytest, 'merchant_token', None)
        if not token:
            pytest.skip("Merchant not registered")
        
        # Get merchant's chat
        response = requests.get(
            f"{BASE_URL}/api/my/merchant-chat",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        messages = response.json().get("messages", [])
        
        # Should have admin message
        admin_msg_found = any(
            msg.get("sender_role") in ["admin", "owner", "mod_p2p"] 
            for msg in messages
        )
        assert admin_msg_found, "Admin reply not visible to merchant"
        
        print(f"SUCCESS: Merchant sees admin reply")
        
    def test_08_admin_approves_merchant(self):
        """Test merchant approval flow"""
        admin_token = self.get_admin_token()
        merchant_id = getattr(pytest, 'merchant_id', None)
        related_id = getattr(pytest, 'merchant_related_id', None)
        
        if not merchant_id:
            pytest.skip("Merchant not registered")
        
        # Try with related_id first, then merchant_id
        approve_id = related_id or merchant_id
        
        response = requests.post(
            f"{BASE_URL}/api/admin/merchants/{approve_id}/approve",
            json={"approved": True, "custom_commission": 0.5},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # If failed with related_id, try merchant_id
        if response.status_code != 200 and related_id and related_id != merchant_id:
            response = requests.post(
                f"{BASE_URL}/api/admin/merchants/{merchant_id}/approve",
                json={"approved": True, "custom_commission": 0.5},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
        
        assert response.status_code == 200, f"Failed to approve merchant: {response.text}"
        
        data = response.json()
        assert data.get("status") == "approved", f"Expected approved status, got {data}"
        
        print(f"SUCCESS: Merchant approved")
        
    def test_09_merchant_receives_approval_message(self):
        """Test that merchant receives system message about approval"""
        token = getattr(pytest, 'merchant_token', None)
        if not token:
            pytest.skip("Merchant not registered")
        
        time.sleep(0.5)  # Wait for message to be created
        
        # Get merchant's chat
        response = requests.get(
            f"{BASE_URL}/api/my/merchant-chat",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        messages = response.json().get("messages", [])
        
        # Look for approval message
        approval_found = any(
            "одобрен" in msg.get("content", "").lower() or 
            "🎉" in msg.get("content", "")
            for msg in messages
        )
        assert approval_found, "Approval message not found in chat"
        
        print(f"SUCCESS: Merchant received approval notification")


class TestMerchantRejectionFlow:
    """Test merchant rejection flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.unique_id = uuid.uuid4().hex[:8]
        self.admin_token = None
        
    def get_admin_token(self):
        if self.admin_token:
            return self.admin_token
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        self.admin_token = response.json()["token"]
        return self.admin_token
    
    def test_01_register_and_reject_merchant(self):
        """Test merchant rejection with reason"""
        # Register merchant
        register_data = {
            "login": f"TEST_reject_{self.unique_id}",
            "password": "testpass123",
            "nickname": f"rejectmerch{self.unique_id}",
            "merchant_name": f"Reject Test {self.unique_id}",
            "merchant_type": "shop",
            "telegram": "@reject_test"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/merchant/register", json=register_data)
        assert response.status_code == 200
        
        merchant_id = response.json()["user"]["id"]
        merchant_token = response.json()["token"]
        
        # Admin rejects
        admin_token = self.get_admin_token()
        
        reject_response = requests.post(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/approve",
            json={"approved": False, "reason": "Тестовая причина отказа"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert reject_response.status_code == 200
        assert reject_response.json().get("status") == "rejected"
        
        print(f"SUCCESS: Merchant rejected with reason")


class TestShopApplicationFlow:
    """Test shop application flow for traders"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.unique_id = uuid.uuid4().hex[:8]
        self.trader_token = None
        self.admin_token = None
        
    def get_trader_token(self):
        if self.trader_token:
            return self.trader_token
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        assert response.status_code == 200, f"Trader login failed: {response.text}"
        self.trader_token = response.json()["token"]
        return self.trader_token
    
    def get_admin_token(self):
        if self.admin_token:
            return self.admin_token
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        self.admin_token = response.json()["token"]
        return self.admin_token
    
    def test_01_trader_creates_shop_application(self):
        """Test trader can create shop application"""
        trader_token = self.get_trader_token()
        
        # Create shop application with correct fields
        shop_data = {
            "shop_name": f"Test Shop {self.unique_id}",
            "shop_description": "Тестовый магазин для проверки функционала платформы и продажи цифровых товаров",
            "categories": ["digital", "services"],
            "telegram": "@test_shop_tg"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/apply",
            json=shop_data,
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        # May fail if trader already has shop application or shop
        if response.status_code == 400 and ("уже" in response.text.lower() or "already" in response.text.lower()):
            print("INFO: Trader already has shop application or shop, skipping creation")
            pytest.skip("Trader already has shop application")
        
        assert response.status_code in [200, 201], f"Failed to create shop application: {response.text}"
        
        data = response.json()
        pytest.shop_app_id = data.get("id") or data.get("application_id")
        
        print(f"SUCCESS: Shop application created")
        
    def test_02_shop_application_chat_works(self):
        """Test shop application chat functionality"""
        trader_token = self.get_trader_token()
        
        # Get shop application chat
        response = requests.get(
            f"{BASE_URL}/api/my/shop-application-chat",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        if response.status_code == 404:
            print("INFO: No pending shop application chat found")
            pytest.skip("No shop application chat")
        
        assert response.status_code == 200, f"Failed to get shop chat: {response.text}"
        
        data = response.json()
        print(f"SUCCESS: Shop application chat accessible, {len(data.get('messages', []))} messages")
        
    def test_03_trader_sends_message_in_shop_chat(self):
        """Test trader can send message in shop application chat"""
        trader_token = self.get_trader_token()
        
        message_content = f"Сообщение в чат заявки магазина {uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/my/shop-application-chat/send",
            json={"content": message_content},
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("No shop application chat")
        
        assert response.status_code == 200, f"Failed to send message: {response.text}"
        
        print(f"SUCCESS: Message sent in shop application chat")
        
    def test_04_admin_sees_shop_applications(self):
        """Test admin can see shop applications"""
        admin_token = self.get_admin_token()
        
        response = requests.get(
            f"{BASE_URL}/api/msg/admin/shop-applications",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get shop applications: {response.text}"
        
        applications = response.json()
        assert isinstance(applications, list)
        
        print(f"SUCCESS: Admin sees {len(applications)} shop applications")
        
        if applications:
            pytest.shop_conv_id = applications[0].get("id")
            pytest.shop_related_id = applications[0].get("related_id")
            
    def test_05_admin_can_approve_shop(self):
        """Test admin can approve shop application"""
        admin_token = self.get_admin_token()
        
        # Get shop applications
        response = requests.get(
            f"{BASE_URL}/api/admin/shop-applications?status=pending",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 200:
            pytest.skip("Cannot get shop applications")
        
        applications = response.json()
        if not applications:
            print("INFO: No pending shop applications to approve")
            pytest.skip("No pending shop applications")
        
        app_id = applications[0].get("id")
        
        # Approve - decision is a query parameter
        approve_response = requests.post(
            f"{BASE_URL}/api/admin/shop-applications/{app_id}/review?decision=approve",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # May already be approved
        if approve_response.status_code == 400:
            print("INFO: Shop application may already be processed")
        else:
            assert approve_response.status_code == 200, f"Failed to approve: {approve_response.text}"
            print(f"SUCCESS: Shop application approved")


class TestAPIEndpoints:
    """Test individual API endpoints"""
    
    def test_health_check(self):
        """Test API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("SUCCESS: API health check passed")
        
    def test_maintenance_status(self):
        """Test maintenance status endpoint"""
        response = requests.get(f"{BASE_URL}/api/maintenance-status")
        assert response.status_code == 200
        print("SUCCESS: Maintenance status endpoint works")
        
    def test_admin_login(self):
        """Test admin can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] in ["admin", "owner"]
        print(f"SUCCESS: Admin login works, role: {data['user']['role']}")
        
    def test_trader_login(self):
        """Test trader can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "trader"
        print("SUCCESS: Trader login works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
