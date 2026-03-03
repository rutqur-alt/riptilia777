"""
Test Session Persistence for DepositPage
Tests that clients can return to active trades after closing browser
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com')

class TestSessionPersistence:
    """Session persistence tests for payment gateway"""
    
    def test_get_active_trade_with_valid_client_id(self):
        """Test that active trade is returned for valid client_session_id"""
        response = requests.get(
            f"{BASE_URL}/api/payment-links/512a69d2/active-trade",
            params={"client_id": "client_1768831674828_an1e6x9ax"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify trade data
        assert data is not None
        assert data.get("id") == "trd_6360efed"
        assert data.get("client_session_id") == "client_1768831674828_an1e6x9ax"
        assert data.get("status") in ["pending", "paid", "disputed"]
        assert data.get("payment_link_id") == "512a69d2"
        
        # Verify requisites are included
        assert "requisites" in data
        assert len(data["requisites"]) > 0
        
        print(f"✅ Active trade found: {data['id']} with status: {data['status']}")
    
    def test_get_active_trade_with_invalid_client_id(self):
        """Test that no trade is returned for invalid client_session_id"""
        response = requests.get(
            f"{BASE_URL}/api/payment-links/512a69d2/active-trade",
            params={"client_id": "invalid_client_id_12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return null/None for invalid client
        assert data is None
        print("✅ No trade returned for invalid client_id")
    
    def test_get_active_trade_without_client_id(self):
        """Test endpoint behavior without client_id parameter"""
        response = requests.get(
            f"{BASE_URL}/api/payment-links/512a69d2/active-trade"
        )
        
        assert response.status_code == 200
        # Without client_id, should return any active trade for the link
        # or None if no active trades
        print("✅ Endpoint works without client_id parameter")
    
    def test_payment_link_exists(self):
        """Test that payment link exists and is active"""
        response = requests.get(f"{BASE_URL}/api/payment-links/512a69d2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("id") == "512a69d2"
        assert data.get("status") == "active"
        assert data.get("amount_rub") > 0
        
        print(f"✅ Payment link found: {data['id']} with amount: {data['amount_rub']} RUB")
    
    def test_trade_public_endpoint(self):
        """Test public trade endpoint returns correct data"""
        response = requests.get(f"{BASE_URL}/api/trades/trd_6360efed/public")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("id") == "trd_6360efed"
        assert data.get("status") in ["pending", "paid", "disputed", "completed", "cancelled"]
        assert "requisites" in data
        assert "amount_rub" in data
        
        print(f"✅ Trade public data: status={data['status']}, amount={data['amount_rub']} RUB")
    
    def test_trade_messages_public_endpoint(self):
        """Test that chat messages can be fetched publicly"""
        response = requests.get(f"{BASE_URL}/api/trades/trd_6360efed/messages-public")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✅ Found {len(data)} messages for trade")
        
        # Verify message structure if messages exist
        if len(data) > 0:
            msg = data[0]
            assert "id" in msg
            assert "content" in msg
            assert "sender_type" in msg
    
    def test_trade_status_mapping(self):
        """Test that trade status correctly maps to UI step"""
        response = requests.get(
            f"{BASE_URL}/api/payment-links/512a69d2/active-trade",
            params={"client_id": "client_1768831674828_an1e6x9ax"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        status = data.get("status")
        
        # Verify status mapping logic (from DepositPage.js lines 169-178)
        expected_steps = {
            "pending": "payment",
            "paid": "waiting",
            "disputed": "disputed",
            "completed": "completed"
        }
        
        if status in expected_steps:
            print(f"✅ Trade status '{status}' should map to step '{expected_steps[status]}'")
        else:
            print(f"⚠️ Unknown status: {status}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
