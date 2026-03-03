"""
Test suite for User Dashboard and Private Messaging features
- User Dashboard /user with P2P, Market, Chat sections
- Private messaging API: /api/conversations, /api/conversations/{user_id}, /api/conversations/{conv_id}/messages
- Admin Chat Moderation: /api/admin/conversations, /api/admin/private-messages
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"login": "admin", "password": "000000"}
TRADER_CREDS = {"login": "trader", "password": "000000"}
TRADER2_CREDS = {"login": "trader2", "password": "000000"}


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Admin can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful")
    
    def test_trader_login(self):
        """Trader can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "trader"
        print(f"✓ Trader login successful, nickname: {data['user'].get('nickname')}")
    
    def test_trader2_login(self):
        """Trader2 can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER2_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"✓ Trader2 login successful, nickname: {data['user'].get('nickname')}")


class TestUserDashboardAPIs:
    """Test APIs used by User Dashboard"""
    
    @pytest.fixture
    def trader_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        return response.json()["token"]
    
    @pytest.fixture
    def trader_user(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        return response.json()["user"]
    
    def test_get_trader_profile(self, trader_token):
        """GET /api/traders/me - Get trader profile for dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "balance_usdt" in data
        assert "nickname" in data
        print(f"✓ Trader profile: balance={data['balance_usdt']} USDT, has_shop={data.get('has_shop')}")
    
    def test_get_trader_stats(self, trader_token):
        """GET /api/traders/stats - Get P2P stats for dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/traders/stats",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "salesCount" in data
        assert "purchasesCount" in data
        assert "salesVolume" in data
        assert "purchasesVolume" in data
        print(f"✓ Trader stats: sales={data['salesCount']}, purchases={data['purchasesCount']}")
    
    def test_get_active_sales(self, trader_token):
        """GET /api/trades/sales/active - Get active sales for P2P section"""
        response = requests.get(
            f"{BASE_URL}/api/trades/sales/active",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Active sales: {len(data)} trades")
    
    def test_get_active_purchases(self, trader_token):
        """GET /api/trades/purchases/active - Get active purchases for P2P section"""
        response = requests.get(
            f"{BASE_URL}/api/trades/purchases/active",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Active purchases: {len(data)} trades")
    
    def test_get_marketplace_purchases(self, trader_token):
        """GET /api/marketplace/my-purchases - Get marketplace purchases for Market section"""
        response = requests.get(
            f"{BASE_URL}/api/marketplace/my-purchases",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Marketplace purchases: {len(data)} orders")


class TestPrivateMessaging:
    """Test Private Messaging APIs"""
    
    @pytest.fixture
    def trader_auth(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        data = response.json()
        return {"token": data["token"], "user": data["user"]}
    
    @pytest.fixture
    def trader2_auth(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER2_CREDS)
        data = response.json()
        return {"token": data["token"], "user": data["user"]}
    
    def test_search_users(self, trader_auth):
        """GET /api/users/search - Search users by nickname"""
        response = requests.get(
            f"{BASE_URL}/api/users/search?query=trader",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ User search: found {len(data)} users matching 'trader'")
    
    def test_get_online_users(self, trader_auth):
        """GET /api/users/online - Get all users for messaging"""
        response = requests.get(
            f"{BASE_URL}/api/users/online",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Online users: {len(data)} users available")
    
    def test_get_conversations(self, trader_auth):
        """GET /api/conversations - Get user's conversations"""
        response = requests.get(
            f"{BASE_URL}/api/conversations",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Conversations: {len(data)} conversations found")
        return data
    
    def test_create_conversation(self, trader_auth, trader2_auth):
        """POST /api/conversations/{user_id} - Create or get conversation"""
        trader2_id = trader2_auth["user"]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/conversations/{trader2_id}",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "participants" in data
        assert trader2_id in data["participants"]
        print(f"✓ Conversation created/retrieved: {data['id']}")
        return data
    
    def test_send_message(self, trader_auth, trader2_auth):
        """POST /api/conversations/{conv_id}/messages - Send a message"""
        # First create/get conversation
        trader2_id = trader2_auth["user"]["id"]
        conv_response = requests.post(
            f"{BASE_URL}/api/conversations/{trader2_id}",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        conv_id = conv_response.json()["id"]
        
        # Send message
        import time
        test_message = f"Test message from pytest at {time.time()}"
        response = requests.post(
            f"{BASE_URL}/api/conversations/{conv_id}/messages",
            json={"content": test_message},
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == test_message
        assert data["sender_id"] == trader_auth["user"]["id"]
        print(f"✓ Message sent: {data['id']}")
        return data
    
    def test_get_conversation_messages(self, trader_auth, trader2_auth):
        """GET /api/conversations/{conv_id}/messages - Get messages in conversation"""
        # First create/get conversation
        trader2_id = trader2_auth["user"]["id"]
        conv_response = requests.post(
            f"{BASE_URL}/api/conversations/{trader2_id}",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        conv_id = conv_response.json()["id"]
        
        # Get messages
        response = requests.get(
            f"{BASE_URL}/api/conversations/{conv_id}/messages",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Messages retrieved: {len(data)} messages in conversation")
    
    def test_cannot_message_self(self, trader_auth):
        """POST /api/conversations/{user_id} - Cannot create conversation with self"""
        my_id = trader_auth["user"]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/conversations/{my_id}",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 400
        print(f"✓ Correctly rejected self-messaging")
    
    def test_empty_message_rejected(self, trader_auth, trader2_auth):
        """POST /api/conversations/{conv_id}/messages - Empty message rejected"""
        trader2_id = trader2_auth["user"]["id"]
        conv_response = requests.post(
            f"{BASE_URL}/api/conversations/{trader2_id}",
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        conv_id = conv_response.json()["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/conversations/{conv_id}/messages",
            json={"content": "   "},
            headers={"Authorization": f"Bearer {trader_auth['token']}"}
        )
        assert response.status_code == 400
        print(f"✓ Empty message correctly rejected")


class TestAdminChatModeration:
    """Test Admin Chat Moderation APIs"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        return response.json()["token"]
    
    @pytest.fixture
    def trader_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        return response.json()["token"]
    
    def test_admin_get_conversations(self, admin_token):
        """GET /api/admin/conversations - Admin can view all conversations"""
        response = requests.get(
            f"{BASE_URL}/api/admin/conversations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin conversations: {len(data)} total conversations")
        
        # Check enriched data
        if data:
            conv = data[0]
            assert "participant_names" in conv
            assert "message_count" in conv
            print(f"  First conversation: {conv.get('participant_names')}, {conv.get('message_count')} messages")
        return data
    
    def test_admin_get_private_messages(self, admin_token):
        """GET /api/admin/private-messages - Admin can view all private messages"""
        response = requests.get(
            f"{BASE_URL}/api/admin/private-messages",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin private messages: {len(data)} total messages")
        
        if data:
            msg = data[0]
            assert "sender_nickname" in msg
            assert "content" in msg
            assert "conversation_id" in msg
            print(f"  Latest message from @{msg.get('sender_nickname')}: {msg.get('content')[:50]}...")
        return data
    
    def test_admin_cannot_access_without_auth(self):
        """Admin endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/conversations")
        assert response.status_code in [401, 403]
        print(f"✓ Admin endpoints protected")
    
    def test_trader_cannot_access_admin_endpoints(self, trader_token):
        """Traders cannot access admin chat moderation"""
        response = requests.get(
            f"{BASE_URL}/api/admin/conversations",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 403
        print(f"✓ Traders correctly blocked from admin endpoints")


class TestAdminPanelAPIs:
    """Test Admin Panel APIs for P2P section"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        return response.json()["token"]
    
    def test_admin_get_traders(self, admin_token):
        """GET /api/admin/traders - Admin can view all users (renamed from traders)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/traders",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin traders (users): {len(data)} users")
    
    def test_admin_get_merchants(self, admin_token):
        """GET /api/admin/merchants - Admin can view merchants"""
        response = requests.get(
            f"{BASE_URL}/api/admin/merchants",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin merchants: {len(data)} merchants")
    
    def test_admin_get_trades(self, admin_token):
        """GET /api/admin/trades - Admin can view all trades"""
        response = requests.get(
            f"{BASE_URL}/api/admin/trades",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin trades: {len(data)} trades")
    
    def test_admin_get_shops(self, admin_token):
        """GET /api/admin/shops - Admin can view marketplace shops"""
        response = requests.get(
            f"{BASE_URL}/api/admin/shops",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin shops: {len(data)} shops")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
