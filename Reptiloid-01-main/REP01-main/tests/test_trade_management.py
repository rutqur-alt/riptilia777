# P2P Exchange - Trade Management Tests
# Tests for trade confirm, cancel, dispute, and chat functionality

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com').rstrip('/')

# Test data storage
test_data = {
    "trader_token": None,
    "trader_id": None,
    "admin_token": None,
    "trade_id": None
}


class TestTraderLogin:
    """Test trader login with provided credentials"""
    
    def test_trader_login(self):
        """Test trader login with credentials: trader/000000"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader",
            "password": "000000"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "trader"
        test_data["trader_token"] = data["token"]
        test_data["trader_id"] = data["user"]["id"]
        print(f"SUCCESS: Trader login successful, balance: {data['user']['balance_usdt']} USDT")


class TestTraderProfile:
    """Test trader profile endpoint"""
    
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
        print(f"SUCCESS: Trader profile retrieved - balance: {data['balance_usdt']} USDT")


class TestTradesList:
    """Test trades list endpoint"""
    
    def test_get_trades_list(self):
        """Test getting trader's trades list"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.get(f"{BASE_URL}/api/trades", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Check trade statuses
        statuses = set(t["status"] for t in data)
        print(f"SUCCESS: Got {len(data)} trades with statuses: {statuses}")
        
        # Store a pending/paid trade for further tests
        for trade in data:
            if trade["status"] in ["pending", "paid"]:
                test_data["trade_id"] = trade["id"]
                print(f"Found active trade: {trade['id']} with status: {trade['status']}")
                break


class TestTradeDetail:
    """Test trade detail endpoint"""
    
    def test_get_trade_detail(self):
        """Test getting trade detail"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # First get trades list to find a trade
        response = requests.get(f"{BASE_URL}/api/trades", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        trades = response.json()
        if not trades:
            pytest.skip("No trades available")
        
        trade_id = trades[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/trades/{trade_id}", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "amount_usdt" in data
        assert "status" in data
        assert "price_rub" in data
        assert "amount_rub" in data
        print(f"SUCCESS: Trade detail retrieved - {data['amount_usdt']} USDT, status: {data['status']}")


class TestTradeMessages:
    """Test trade chat/messages functionality"""
    
    def test_get_trade_messages(self):
        """Test getting trade messages"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Get a trade
        response = requests.get(f"{BASE_URL}/api/trades", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        trades = response.json()
        if not trades:
            pytest.skip("No trades available")
        
        trade_id = trades[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/trades/{trade_id}/messages", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Got {len(data)} messages for trade {trade_id}")
    
    def test_send_trade_message(self):
        """Test sending a message in trade chat"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Get a pending/paid trade
        response = requests.get(f"{BASE_URL}/api/trades", headers={
            "Authorization": f"Bearer {test_data['trader_token']}"
        })
        trades = response.json()
        active_trade = None
        for trade in trades:
            if trade["status"] in ["pending", "paid"]:
                active_trade = trade
                break
        
        if not active_trade:
            pytest.skip("No active trade available")
        
        response = requests.post(
            f"{BASE_URL}/api/trades/{active_trade['id']}/messages",
            json={"content": "Test message from pytest"},
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test message from pytest"
        assert data["sender_type"] == "trader"
        print(f"SUCCESS: Message sent to trade {active_trade['id']}")


class TestTradeConfirm:
    """Test trade confirm endpoint"""
    
    def test_confirm_trade_creates_new_and_confirms(self):
        """Test creating a trade and confirming it"""
        if not test_data["trader_token"] or not test_data["trader_id"]:
            pytest.skip("Trader token not available")
        
        # First deposit some USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=50",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create trade: {response.text}")
        
        trade = response.json()
        trade_id = trade["id"]
        print(f"Created trade: {trade_id}")
        
        # Confirm the trade
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/confirm",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        print(f"SUCCESS: Trade {trade_id} confirmed")


class TestTradeCancel:
    """Test trade cancel endpoint"""
    
    def test_cancel_trade_creates_new_and_cancels(self):
        """Test creating a trade and cancelling it"""
        if not test_data["trader_token"] or not test_data["trader_id"]:
            pytest.skip("Trader token not available")
        
        # First deposit some USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=50",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create trade: {response.text}")
        
        trade = response.json()
        trade_id = trade["id"]
        print(f"Created trade: {trade_id}")
        
        # Cancel the trade
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/cancel",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        print(f"SUCCESS: Trade {trade_id} cancelled")


class TestTradeDispute:
    """Test trade dispute endpoint"""
    
    def test_dispute_trade_creates_new_and_disputes(self):
        """Test creating a trade and opening a dispute"""
        if not test_data["trader_token"] or not test_data["trader_id"]:
            pytest.skip("Trader token not available")
        
        # First deposit some USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=50",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create trade: {response.text}")
        
        trade = response.json()
        trade_id = trade["id"]
        print(f"Created trade: {trade_id}")
        
        # Open dispute (no auth required for customer)
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/dispute?reason=Test%20dispute%20from%20pytest"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disputed"
        print(f"SUCCESS: Trade {trade_id} disputed")


class TestMarkPaid:
    """Test mark-paid endpoint"""
    
    def test_mark_trade_paid(self):
        """Test marking a trade as paid"""
        if not test_data["trader_token"] or not test_data["trader_id"]:
            pytest.skip("Trader token not available")
        
        # First deposit some USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=50",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create trade: {response.text}")
        
        trade = response.json()
        trade_id = trade["id"]
        print(f"Created trade: {trade_id}")
        
        # Mark as paid (no auth required for customer)
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        print(f"SUCCESS: Trade {trade_id} marked as paid")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
