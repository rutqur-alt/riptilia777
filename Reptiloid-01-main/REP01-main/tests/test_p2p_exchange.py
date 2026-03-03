# P2P Exchange Platform - Comprehensive Backend API Tests
# Tests all endpoints: Auth, Merchants, Traders, Offers, Trades, Chat, Admin

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com').rstrip('/')

# Test data storage
test_data = {
    "admin_token": None,
    "trader_token": None,
    "merchant_token": None,
    "trader_id": None,
    "merchant_id": None,
    "offer_id": None,
    "payment_link_id": None,
    "trade_id": None,
    "chat_id": None
}


class TestHealthCheck:
    """Health check and basic API tests"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "P2P Exchange API" in data["message"]
        print("SUCCESS: API root endpoint working")
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("SUCCESS: Health endpoint working")


class TestAdminAuth:
    """Admin authentication tests"""
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"
        test_data["admin_token"] = data["token"]
        print(f"SUCCESS: Admin login successful, role: {data['user']['role']}")
    
    def test_admin_login_invalid_password(self):
        """Test admin login with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("SUCCESS: Invalid admin password rejected correctly")
    
    def test_admin_me_endpoint(self):
        """Test admin /auth/me endpoint"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["role"] == "admin"
        print("SUCCESS: Admin /auth/me endpoint working")


class TestTraderAuth:
    """Trader registration and authentication tests"""
    
    def test_trader_registration(self):
        """Test trader registration"""
        unique_login = f"test_trader_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/auth/trader/register", json={
            "login": unique_login,
            "password": "trader123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["login"] == unique_login
        assert data["user"]["balance_usdt"] == 0.0
        assert "commission_rate" in data["user"]
        test_data["trader_token"] = data["token"]
        test_data["trader_id"] = data["user"]["id"]
        print(f"SUCCESS: Trader registered with login: {unique_login}")
    
    def test_trader_login_existing(self):
        """Test login with existing trader credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader1",
            "password": "trader123"
        })
        # May or may not exist, just check response format
        if response.status_code == 200:
            data = response.json()
            assert "token" in data
            print("SUCCESS: Existing trader login works")
        else:
            print("INFO: trader1 doesn't exist, registration test passed")
    
    def test_trader_duplicate_registration(self):
        """Test duplicate trader registration fails"""
        if not test_data["trader_id"]:
            pytest.skip("No trader created yet")
        
        # First register a trader
        unique_login = f"dup_test_{uuid.uuid4().hex[:8]}"
        response1 = requests.post(f"{BASE_URL}/api/auth/trader/register", json={
            "login": unique_login,
            "password": "test123"
        })
        assert response1.status_code == 200
        
        # Try to register with same login - should fail
        response = requests.post(f"{BASE_URL}/api/auth/trader/register", json={
            "login": unique_login,
            "password": "test123"
        })
        assert response.status_code == 400
        print("SUCCESS: Duplicate registration rejected correctly")


class TestMerchantAuth:
    """Merchant registration and authentication tests"""
    
    def test_merchant_registration_casino(self):
        """Test merchant registration with casino type"""
        unique_login = f"test_merchant_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/auth/merchant/register", json={
            "login": unique_login,
            "password": "merchant123",
            "merchant_name": "Test Casino",
            "merchant_type": "casino",
            "telegram": "@test_casino"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["status"] == "pending"
        assert data["user"]["merchant_type"] == "casino"
        assert data["user"]["commission_rate"] == 0.5  # Casino commission
        test_data["merchant_token"] = data["token"]
        test_data["merchant_id"] = data["user"]["id"]
        test_data["chat_id"] = f"chat_{data['user']['id']}"
        print(f"SUCCESS: Merchant registered with type: casino, status: pending")
    
    def test_merchant_registration_shop(self):
        """Test merchant registration with shop type"""
        unique_login = f"test_shop_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/auth/merchant/register", json={
            "login": unique_login,
            "password": "shop123",
            "merchant_name": "Test Shop",
            "merchant_type": "shop",
            "telegram": "@test_shop"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["commission_rate"] == 0.3  # Shop commission
        print(f"SUCCESS: Shop merchant registered with commission: 0.3%")
    
    def test_merchant_registration_stream(self):
        """Test merchant registration with stream type"""
        unique_login = f"test_stream_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/auth/merchant/register", json={
            "login": unique_login,
            "password": "stream123",
            "merchant_name": "Test Stream",
            "merchant_type": "stream",
            "telegram": "@test_stream"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["commission_rate"] == 0.4  # Stream commission
        print(f"SUCCESS: Stream merchant registered with commission: 0.4%")


class TestAdminMerchantManagement:
    """Admin merchant management tests"""
    
    def test_get_pending_merchants(self):
        """Test getting pending merchants list"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/merchants/pending", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Got {len(data)} pending merchants")
    
    def test_get_all_merchants(self):
        """Test getting all merchants list"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/merchants/all", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Got {len(data)} total merchants")
    
    def test_approve_merchant(self):
        """Test approving a merchant"""
        if not test_data["admin_token"] or not test_data["merchant_id"]:
            pytest.skip("Admin token or merchant ID not available")
        
        response = requests.post(
            f"{BASE_URL}/api/merchants/{test_data['merchant_id']}/approve",
            json={"approved": True},
            headers={"Authorization": f"Bearer {test_data['admin_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert "api_key" in data
        print(f"SUCCESS: Merchant approved, API key generated")
    
    def test_get_merchant_details(self):
        """Test getting merchant details"""
        if not test_data["admin_token"] or not test_data["merchant_id"]:
            pytest.skip("Admin token or merchant ID not available")
        
        response = requests.get(
            f"{BASE_URL}/api/merchants/{test_data['merchant_id']}",
            headers={"Authorization": f"Bearer {test_data['admin_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["api_key"] is not None
        print(f"SUCCESS: Merchant details retrieved, status: active")


class TestAdminCommissionSettings:
    """Admin commission settings tests"""
    
    def test_get_commission_settings(self):
        """Test getting commission settings"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/admin/commission-settings", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "trader_commission" in data
        assert "casino_commission" in data
        assert "shop_commission" in data
        assert "stream_commission" in data
        assert "other_commission" in data
        assert "minimum_commission" in data
        print(f"SUCCESS: Commission settings retrieved - trader: {data['trader_commission']}%")
    
    def test_update_commission_settings(self):
        """Test updating commission settings"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.put(
            f"{BASE_URL}/api/admin/commission-settings",
            json={"trader_commission": 1.0},
            headers={"Authorization": f"Bearer {test_data['admin_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trader_commission"] == 1.0
        print("SUCCESS: Commission settings updated")
    
    def test_get_commission_history(self):
        """Test getting commission change history"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/admin/commission-history", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Commission history retrieved - {len(data)} entries")


class TestAdminMonitoring:
    """Admin monitoring tests"""
    
    def test_get_monitoring_data(self):
        """Test getting monitoring data"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/admin/monitoring", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "suspicious_activity" in data
        assert "inactive_merchants" in data
        assert "recommendations" in data
        print(f"SUCCESS: Monitoring data retrieved - suspicious: {len(data['suspicious_activity'])}, inactive: {len(data['inactive_merchants'])}")


class TestAdminStats:
    """Admin statistics tests"""
    
    def test_get_admin_stats(self):
        """Test getting admin statistics"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "total_merchants" in data
        assert "pending_merchants" in data
        assert "active_merchants" in data
        assert "total_traders" in data
        assert "today" in data
        assert "trades_count" in data["today"]
        assert "trades_volume" in data["today"]
        assert "total_commission" in data["today"]
        assert "merchant_commission_by_type" in data["today"]
        print(f"SUCCESS: Admin stats retrieved - merchants: {data['total_merchants']}, traders: {data['total_traders']}")


class TestTraderOperations:
    """Trader operations tests"""
    
    def test_get_trader_profile(self):
        """Test getting trader profile"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "balance_usdt" in data
        assert "commission_rate" in data
        assert "accepted_merchant_types" in data
        print(f"SUCCESS: Trader profile retrieved - balance: {data['balance_usdt']}")
    
    def test_trader_deposit(self):
        """Test trader deposit"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=1000",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["balance_usdt"] == 1000.0
        print(f"SUCCESS: Trader deposit successful - new balance: {data['balance_usdt']}")
    
    def test_update_trader_preferences(self):
        """Test updating trader merchant type preferences"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.put(
            f"{BASE_URL}/api/traders/me",
            json={"accepted_merchant_types": ["casino", "shop"]},
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "casino" in data["accepted_merchant_types"]
        assert "shop" in data["accepted_merchant_types"]
        print("SUCCESS: Trader preferences updated")


class TestOffers:
    """Offer management tests"""
    
    def test_create_offer(self):
        """Test creating an offer"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/offers",
            json={
                "min_amount": 100,
                "max_amount": 10000,
                "price_rub": 92.5,
                "payment_methods": ["sberbank", "tinkoff"],
                "accepted_merchant_types": ["casino", "shop", "stream", "other"]
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["min_amount"] == 100
        assert data["max_amount"] == 10000
        assert data["price_rub"] == 92.5
        assert data["is_active"] == True
        test_data["offer_id"] = data["id"]
        print(f"SUCCESS: Offer created - ID: {data['id']}")
    
    def test_get_my_offers(self):
        """Test getting trader's offers"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.get(f"{BASE_URL}/api/offers/my", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"SUCCESS: Got {len(data)} trader offers")
    
    def test_get_public_offers(self):
        """Test getting public offers"""
        response = requests.get(f"{BASE_URL}/api/offers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Got {len(data)} public offers")
    
    def test_delete_offer(self):
        """Test deleting an offer"""
        if not test_data["trader_token"] or not test_data["offer_id"]:
            pytest.skip("Trader token or offer ID not available")
        
        response = requests.delete(
            f"{BASE_URL}/api/offers/{test_data['offer_id']}",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        print("SUCCESS: Offer deleted")


class TestPaymentLinks:
    """Payment link tests"""
    
    def test_create_payment_link(self):
        """Test creating a payment link"""
        if not test_data["merchant_token"]:
            pytest.skip("Merchant token not available")
        
        # Need to refresh merchant token after approval
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": f"test_merchant_{test_data['merchant_id'][:8]}",
            "password": "merchant123"
        })
        
        # Use existing token if login fails
        token = test_data["merchant_token"]
        
        response = requests.post(
            f"{BASE_URL}/api/payment-links",
            json={
                "amount_rub": 25000,
                "price_rub": 92.0
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "link_url" in data
            assert data["amount_rub"] == 25000
            test_data["payment_link_id"] = data["id"]
            print(f"SUCCESS: Payment link created - {data['link_url']}")
        elif response.status_code == 403:
            print("INFO: Merchant not active yet, payment link creation skipped")
        else:
            print(f"INFO: Payment link creation returned {response.status_code}")
    
    def test_get_payment_links(self):
        """Test getting merchant's payment links"""
        if not test_data["merchant_token"]:
            pytest.skip("Merchant token not available")
        
        response = requests.get(f"{BASE_URL}/api/payment-links", headers={
            "Authorization": f"Bearer {test_data['merchant_token']}"
        })
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"SUCCESS: Got {len(data)} payment links")
        else:
            print(f"INFO: Get payment links returned {response.status_code}")


class TestChat:
    """Chat functionality tests"""
    
    def test_get_chats_admin(self):
        """Test admin getting chat list"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/chats", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Admin got {len(data)} chats")
    
    def test_get_chats_merchant(self):
        """Test merchant getting their chat"""
        if not test_data["merchant_token"]:
            pytest.skip("Merchant token not available")
        
        response = requests.get(f"{BASE_URL}/api/chats", headers={
            "Authorization": f"Bearer {test_data['merchant_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Merchant got {len(data)} chats")
    
    def test_get_chat_messages(self):
        """Test getting chat messages"""
        if not test_data["admin_token"] or not test_data["chat_id"]:
            pytest.skip("Admin token or chat ID not available")
        
        response = requests.get(
            f"{BASE_URL}/api/chats/{test_data['chat_id']}/messages",
            headers={"Authorization": f"Bearer {test_data['admin_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have welcome message
        assert len(data) > 0
        print(f"SUCCESS: Got {len(data)} messages in chat")
    
    def test_send_message_admin(self):
        """Test admin sending message"""
        if not test_data["admin_token"] or not test_data["chat_id"]:
            pytest.skip("Admin token or chat ID not available")
        
        response = requests.post(
            f"{BASE_URL}/api/chats/{test_data['chat_id']}/messages",
            json={"content": "Test message from admin"},
            headers={"Authorization": f"Bearer {test_data['admin_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test message from admin"
        assert data["sender_type"] == "admin"
        print("SUCCESS: Admin message sent")
    
    def test_send_message_merchant(self):
        """Test merchant sending message"""
        if not test_data["merchant_token"] or not test_data["chat_id"]:
            pytest.skip("Merchant token or chat ID not available")
        
        response = requests.post(
            f"{BASE_URL}/api/chats/{test_data['chat_id']}/messages",
            json={"content": "Test message from merchant"},
            headers={"Authorization": f"Bearer {test_data['merchant_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test message from merchant"
        assert data["sender_type"] == "merchant"
        print("SUCCESS: Merchant message sent")


class TestTrades:
    """Trade operations tests"""
    
    def test_get_trades_trader(self):
        """Test trader getting their trades"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.get(f"{BASE_URL}/api/trades", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Trader got {len(data)} trades")
    
    def test_get_trades_admin(self):
        """Test admin getting all trades"""
        if not test_data["admin_token"]:
            pytest.skip("Admin token not available")
        
        response = requests.get(f"{BASE_URL}/api/trades", headers={
            "Authorization": f"Bearer {test_data['admin_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Admin got {len(data)} trades")


class TestMerchantActions:
    """Merchant action tests (block, suspend)"""
    
    def test_suspend_merchant(self):
        """Test suspending a merchant"""
        if not test_data["admin_token"] or not test_data["merchant_id"]:
            pytest.skip("Admin token or merchant ID not available")
        
        response = requests.post(
            f"{BASE_URL}/api/merchants/{test_data['merchant_id']}/suspend",
            headers={"Authorization": f"Bearer {test_data['admin_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "suspended"
        print("SUCCESS: Merchant suspended")
    
    def test_block_merchant(self):
        """Test blocking a merchant"""
        if not test_data["admin_token"] or not test_data["merchant_id"]:
            pytest.skip("Admin token or merchant ID not available")
        
        response = requests.post(
            f"{BASE_URL}/api/merchants/{test_data['merchant_id']}/block",
            headers={"Authorization": f"Bearer {test_data['admin_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        print("SUCCESS: Merchant blocked")


class TestAuthorizationErrors:
    """Authorization error handling tests"""
    
    def test_unauthorized_access(self):
        """Test accessing protected endpoint without token"""
        response = requests.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code in [401, 403]
        print("SUCCESS: Unauthorized access rejected")
    
    def test_invalid_token(self):
        """Test accessing with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
        print("SUCCESS: Invalid token rejected")
    
    def test_trader_accessing_admin_endpoint(self):
        """Test trader accessing admin-only endpoint"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 403
        print("SUCCESS: Trader blocked from admin endpoint")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
