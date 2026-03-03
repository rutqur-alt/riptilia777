# P2P Exchange - New Trade Logic Tests
# Tests for the new trade management rules:
# 1. Trader confirm ONLY after client marks as paid (status = "paid" or "disputed")
# 2. Trader cancel ONLY if pending AND 30 minutes passed
# 3. Dispute ONLY 10 minutes after payment
# 4. Client chat via messages-public endpoint
# 5. Trade requisites populated from offer
# 6. Public trade endpoint returns requisites

import pytest
import requests
import os
import time
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com').rstrip('/')

# Test data storage
test_data = {
    "trader_token": None,
    "trader_id": None,
    "merchant_token": None,
    "merchant_id": None,
    "admin_token": None,
    "offer_id": None,
    "requisite_id": None,
    "payment_link_id": None
}


class TestSetup:
    """Setup test data - login trader, merchant, admin"""
    
    def test_trader_login(self):
        """Login as trader"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader",
            "password": "000000"
        })
        assert response.status_code == 200, f"Trader login failed: {response.text}"
        data = response.json()
        test_data["trader_token"] = data["token"]
        test_data["trader_id"] = data["user"]["id"]
        print(f"SUCCESS: Trader logged in, ID: {test_data['trader_id']}")
    
    def test_merchant_login(self):
        """Login as merchant"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": "merchant",
            "password": "000000"
        })
        assert response.status_code == 200, f"Merchant login failed: {response.text}"
        data = response.json()
        test_data["merchant_token"] = data["token"]
        test_data["merchant_id"] = data["user"]["id"]
        print(f"SUCCESS: Merchant logged in, ID: {test_data['merchant_id']}")
    
    def test_admin_login(self):
        """Login as admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": "admin",
            "password": "000000"
        })
        # Admin might have different password
        if response.status_code != 200:
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "login": "admin",
                "password": "admin123"
            })
        if response.status_code == 200:
            data = response.json()
            test_data["admin_token"] = data["token"]
            print(f"SUCCESS: Admin logged in")
        else:
            print(f"WARNING: Admin login failed, some tests may be skipped")


class TestTraderConfirmLogic:
    """Test: Trader can confirm trade ONLY after client marks as paid"""
    
    def test_confirm_fails_when_status_pending(self):
        """Trader confirm should FAIL if status is 'pending'"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT first
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade (status will be 'pending')
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        assert response.status_code == 200, f"Trade creation failed: {response.text}"
        trade = response.json()
        trade_id = trade["id"]
        assert trade["status"] == "pending", f"Expected pending status, got {trade['status']}"
        print(f"Created trade {trade_id} with status: pending")
        
        # Try to confirm - should FAIL
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/confirm",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        assert "оплат" in error_detail.lower() or "paid" in error_detail.lower(), f"Unexpected error: {error_detail}"
        print(f"SUCCESS: Confirm correctly rejected for pending trade - {error_detail}")
        
        # Cleanup - cancel the trade (need to wait 30 min or use admin)
        # For now, just leave it
    
    def test_confirm_succeeds_when_status_paid(self):
        """Trader confirm should SUCCEED if status is 'paid'"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        assert response.status_code == 200
        trade = response.json()
        trade_id = trade["id"]
        print(f"Created trade {trade_id}")
        
        # Mark as paid (client action - no auth)
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        assert response.status_code == 200, f"Mark paid failed: {response.text}"
        assert response.json()["status"] == "paid"
        print(f"Trade marked as paid")
        
        # Now confirm - should SUCCEED
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/confirm",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200, f"Confirm failed: {response.text}"
        assert response.json()["status"] == "completed"
        print(f"SUCCESS: Trade {trade_id} confirmed after payment")
    
    def test_confirm_succeeds_when_status_disputed(self):
        """Trader confirm should SUCCEED if status is 'disputed'"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        assert response.status_code == 200
        trade = response.json()
        trade_id = trade["id"]
        print(f"Created trade {trade_id}")
        
        # Mark as paid first
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        assert response.status_code == 200
        
        # We need to wait 10 minutes for dispute to be allowed
        # For testing, we'll directly update the database or skip this test
        # Let's try to open dispute anyway to see the error
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/dispute-public?reason=Test")
        if response.status_code == 400:
            # Expected - 10 min wait required
            print(f"Dispute requires 10 min wait (expected behavior)")
            pytest.skip("Cannot test disputed confirm without waiting 10 minutes")
        
        if response.status_code == 200:
            assert response.json()["status"] == "disputed"
            
            # Now confirm - should SUCCEED
            response = requests.post(
                f"{BASE_URL}/api/trades/{trade_id}/confirm",
                headers={"Authorization": f"Bearer {test_data['trader_token']}"}
            )
            assert response.status_code == 200, f"Confirm failed: {response.text}"
            assert response.json()["status"] == "completed"
            print(f"SUCCESS: Trade {trade_id} confirmed from disputed status")


class TestTraderCancelLogic:
    """Test: Trader can cancel ONLY if pending AND 30 minutes passed"""
    
    def test_cancel_fails_when_status_not_pending(self):
        """Trader cancel should FAIL if status is not 'pending'"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        assert response.status_code == 200
        trade = response.json()
        trade_id = trade["id"]
        
        # Mark as paid
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        assert response.status_code == 200
        print(f"Trade {trade_id} marked as paid")
        
        # Try to cancel - should FAIL (status is 'paid', not 'pending')
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/cancel",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        print(f"SUCCESS: Cancel correctly rejected for paid trade - {error_detail}")
    
    def test_cancel_fails_when_pending_but_less_than_30_min(self):
        """Trader cancel should FAIL if pending but less than 30 min passed"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade (just created, so less than 30 min)
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        assert response.status_code == 200
        trade = response.json()
        trade_id = trade["id"]
        print(f"Created trade {trade_id} (just now)")
        
        # Try to cancel immediately - should FAIL (30 min not passed)
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/cancel",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        assert "мин" in error_detail.lower() or "30" in error_detail, f"Expected time-related error: {error_detail}"
        print(f"SUCCESS: Cancel correctly rejected (30 min not passed) - {error_detail}")


class TestClientMarkPaid:
    """Test: Client can mark trade as paid"""
    
    def test_client_mark_paid(self):
        """Client can mark trade as paid (POST /api/trades/{id}/mark-paid)"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        assert response.status_code == 200
        trade = response.json()
        trade_id = trade["id"]
        assert trade["status"] == "pending"
        
        # Mark as paid (no auth - client action)
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        assert response.status_code == 200, f"Mark paid failed: {response.text}"
        data = response.json()
        assert data["status"] == "paid"
        print(f"SUCCESS: Client marked trade {trade_id} as paid")
    
    def test_mark_paid_fails_when_not_pending(self):
        """Mark paid should fail if trade is not pending"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create and mark as paid
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        trade = response.json()
        trade_id = trade["id"]
        
        # Mark as paid first time
        requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        
        # Try to mark as paid again - should fail
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"SUCCESS: Mark paid correctly rejected for non-pending trade")


class TestClientCancelTrade:
    """Test: Client can cancel trade at any time"""
    
    def test_client_cancel_pending_trade(self):
        """Client can cancel trade when pending"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        assert response.status_code == 200
        trade = response.json()
        trade_id = trade["id"]
        
        # Client cancel (no auth)
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/cancel-client")
        assert response.status_code == 200, f"Client cancel failed: {response.text}"
        data = response.json()
        assert data["status"] == "cancelled"
        print(f"SUCCESS: Client cancelled pending trade {trade_id}")
    
    def test_client_cancel_paid_trade(self):
        """Client can cancel trade when paid"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        trade = response.json()
        trade_id = trade["id"]
        
        # Mark as paid
        requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        
        # Client cancel (no auth)
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/cancel-client")
        assert response.status_code == 200, f"Client cancel failed: {response.text}"
        data = response.json()
        assert data["status"] == "cancelled"
        print(f"SUCCESS: Client cancelled paid trade {trade_id}")


class TestClientChat:
    """Test: Client can send message via messages-public endpoint"""
    
    def test_client_send_message(self):
        """Client can send message (POST /api/trades/{id}/messages-public)"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        trade = response.json()
        trade_id = trade["id"]
        
        # Client sends message (no auth)
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/messages-public",
            json={"content": "Hello from client test"}
        )
        assert response.status_code == 200, f"Send message failed: {response.text}"
        data = response.json()
        assert data["content"] == "Hello from client test"
        assert data["sender_type"] == "client"
        print(f"SUCCESS: Client sent message to trade {trade_id}")
    
    def test_client_get_messages(self):
        """Client can get messages (GET /api/trades/{id}/messages-public)"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        trade = response.json()
        trade_id = trade["id"]
        
        # Get messages (no auth)
        response = requests.get(f"{BASE_URL}/api/trades/{trade_id}/messages-public")
        assert response.status_code == 200, f"Get messages failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Client got {len(data)} messages from trade {trade_id}")


class TestDisputeLogic:
    """Test: Dispute can be opened ONLY 10 minutes after payment"""
    
    def test_dispute_fails_before_10_min(self):
        """Dispute should fail if less than 10 min since payment"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        trade = response.json()
        trade_id = trade["id"]
        
        # Mark as paid
        requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        
        # Try to open dispute immediately - should FAIL
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/dispute-public?reason=Test")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        assert "мин" in error_detail.lower() or "10" in error_detail, f"Expected time-related error: {error_detail}"
        print(f"SUCCESS: Dispute correctly rejected (10 min not passed) - {error_detail}")
    
    def test_dispute_fails_when_not_paid(self):
        """Dispute should fail if trade is not paid"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create a new trade (pending)
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        trade = response.json()
        trade_id = trade["id"]
        
        # Try to open dispute on pending trade - should FAIL
        response = requests.post(f"{BASE_URL}/api/trades/{trade_id}/dispute-public?reason=Test")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        assert "оплат" in error_detail.lower() or "paid" in error_detail.lower(), f"Expected payment-related error: {error_detail}"
        print(f"SUCCESS: Dispute correctly rejected for non-paid trade - {error_detail}")


class TestTradeRequisites:
    """Test: Trade requisites are populated from offer"""
    
    def test_create_requisite_and_offer(self):
        """Create requisite and offer for testing"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Create a requisite
        response = requests.post(
            f"{BASE_URL}/api/requisites",
            json={
                "type": "card",
                "data": {
                    "bank_name": "Test Bank",
                    "card_number": "4111 1111 1111 1111",
                    "card_holder": "TEST HOLDER",
                    "is_primary": True
                }
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        if response.status_code == 200:
            requisite = response.json()
            test_data["requisite_id"] = requisite["id"]
            print(f"Created requisite: {requisite['id']}")
        else:
            # Might already exist, get existing
            response = requests.get(
                f"{BASE_URL}/api/requisites",
                headers={"Authorization": f"Bearer {test_data['trader_token']}"}
            )
            if response.status_code == 200:
                requisites = response.json()
                if requisites:
                    test_data["requisite_id"] = requisites[0]["id"]
                    print(f"Using existing requisite: {test_data['requisite_id']}")
        
        # Create an offer with requisite
        if test_data["requisite_id"]:
            response = requests.post(
                f"{BASE_URL}/api/offers",
                json={
                    "min_amount": 1,
                    "max_amount": 1000,
                    "price_rub": 95.0,
                    "payment_methods": ["sberbank", "tinkoff"],
                    "accepted_merchant_types": ["casino", "shop", "stream", "other"],
                    "requisite_ids": [test_data["requisite_id"]],
                    "conditions": "Test conditions"
                },
                headers={"Authorization": f"Bearer {test_data['trader_token']}"}
            )
            if response.status_code == 200:
                offer = response.json()
                test_data["offer_id"] = offer["id"]
                print(f"Created offer: {offer['id']} with requisites: {offer.get('requisite_ids')}")
    
    def test_trade_has_requisites_from_offer(self):
        """Trade should have requisites populated from offer (via get_trade endpoint)"""
        if not test_data["trader_token"] or not test_data["requisite_id"]:
            pytest.skip("Trader token or requisite not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create trade with requisite_ids
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 10,
            "price_rub": 95.0,
            "trader_id": test_data["trader_id"],
            "requisite_ids": [test_data["requisite_id"]]
        })
        assert response.status_code == 200, f"Trade creation failed: {response.text}"
        trade_create = response.json()
        trade_id = trade_create["id"]
        print(f"Created trade: {trade_id}")
        
        # Get trade detail (this endpoint returns requisites)
        response = requests.get(
            f"{BASE_URL}/api/trades/{trade_id}",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200, f"Get trade failed: {response.text}"
        trade = response.json()
        
        # Check requisites are populated
        assert "requisites" in trade, "Trade should have requisites field"
        assert len(trade["requisites"]) > 0, "Trade should have at least one requisite"
        print(f"SUCCESS: Trade {trade['id']} has {len(trade['requisites'])} requisites")
        
        # Verify requisite data
        req = trade["requisites"][0]
        assert "type" in req
        assert "data" in req
        print(f"Requisite type: {req['type']}, data: {req['data']}")


class TestPublicTradeEndpoint:
    """Test: Public trade endpoint returns requisites"""
    
    def test_public_trade_returns_requisites(self):
        """GET /api/trades/{id}/public should return requisites"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create trade with requisites
        requisite_ids = [test_data["requisite_id"]] if test_data.get("requisite_id") else []
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 10,
            "price_rub": 95.0,
            "trader_id": test_data["trader_id"],
            "requisite_ids": requisite_ids
        })
        assert response.status_code == 200
        trade = response.json()
        trade_id = trade["id"]
        
        # Get public trade info (no auth)
        response = requests.get(f"{BASE_URL}/api/trades/{trade_id}/public")
        assert response.status_code == 200, f"Public trade failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "id" in data
        assert "amount_usdt" in data
        assert "amount_rub" in data
        assert "status" in data
        assert "requisites" in data
        assert "trader_login" in data
        print(f"SUCCESS: Public trade endpoint returns all required fields including requisites")
        print(f"Public trade data: id={data['id']}, status={data['status']}, requisites={len(data['requisites'])}")


class TestChatClosedAfterCompletion:
    """Test: Chat is closed after trade completion"""
    
    def test_chat_closed_after_completion(self):
        """Client cannot send message after trade is completed"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        # Deposit USDT
        requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=100",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Create trade
        response = requests.post(f"{BASE_URL}/api/trades", json={
            "amount_usdt": 5,
            "price_rub": 92.5,
            "trader_id": test_data["trader_id"]
        })
        trade = response.json()
        trade_id = trade["id"]
        
        # Mark as paid
        requests.post(f"{BASE_URL}/api/trades/{trade_id}/mark-paid")
        
        # Confirm trade
        requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/confirm",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        # Try to send message - should fail
        response = requests.post(
            f"{BASE_URL}/api/trades/{trade_id}/messages-public",
            json={"content": "Test after completion"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"SUCCESS: Chat correctly closed after trade completion")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
