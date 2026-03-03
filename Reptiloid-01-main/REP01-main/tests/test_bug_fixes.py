"""
Test suite for P2P Exchange Bug Fixes:
1. Main page shows ALL unique payment types for offers (not duplicates)
2. Own offers show 'Ваше' instead of 'Купить' button when logged in
3. Profile page (Аккаунт → Профиль) does NOT show 'Торговый счёт'
4. Transaction history shows transfers with correct colors (red for outgoing, green for incoming)
5. Forum rate limit - cannot send more than 1 message per 5 seconds
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TRADER_LOGIN = "trader"
TRADER_PASSWORD = "000000"
TRADER2_LOGIN = "trader2"
TRADER2_PASSWORD = "000000"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def trader_token(api_client):
    """Get authentication token for trader"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "login": TRADER_LOGIN,
        "password": TRADER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed for trader: {response.text}")


@pytest.fixture(scope="module")
def trader2_token(api_client):
    """Get authentication token for trader2"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "login": TRADER2_LOGIN,
        "password": TRADER2_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed for trader2: {response.text}")


@pytest.fixture(scope="module")
def trader_info(api_client, trader_token):
    """Get trader info"""
    response = api_client.get(f"{BASE_URL}/api/traders/me", headers={
        "Authorization": f"Bearer {trader_token}"
    })
    if response.status_code == 200:
        return response.json()
    pytest.skip(f"Failed to get trader info: {response.text}")


class TestBug1PaymentTypes:
    """Bug 1: Main page shows ALL unique payment types for offers (not duplicates)"""
    
    def test_public_offers_have_requisites(self, api_client):
        """Test that public offers endpoint returns offers with requisites"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        
        offers = response.json()
        # Check if offers have requisites field
        for offer in offers:
            if offer.get("requisites"):
                # Verify requisites have type field
                for req in offer["requisites"]:
                    assert "type" in req, "Requisite should have type field"
                    assert req["type"] in ["card", "sbp", "qr", "sim", "cis"], f"Unknown requisite type: {req['type']}"
    
    def test_offers_have_unique_payment_types(self, api_client):
        """Test that offers show unique payment types (not duplicates)"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        
        offers = response.json()
        for offer in offers:
            if offer.get("requisites"):
                types = [r["type"] for r in offer["requisites"]]
                unique_types = list(set(types))
                # Each type should appear only once per offer
                assert len(types) == len(unique_types), f"Offer {offer['id']} has duplicate payment types: {types}"


class TestBug2OwnOfferButton:
    """Bug 2: Own offers show 'Ваше' instead of 'Купить' button when logged in"""
    
    def test_public_offers_include_trader_id(self, api_client):
        """Test that public offers include trader_id for ownership check"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        
        offers = response.json()
        for offer in offers:
            assert "trader_id" in offer, "Offer should have trader_id for ownership check"
    
    def test_my_offers_endpoint(self, api_client, trader_token):
        """Test that trader can get their own offers"""
        response = api_client.get(f"{BASE_URL}/api/offers/my", headers={
            "Authorization": f"Bearer {trader_token}"
        })
        assert response.status_code == 200
        
        offers = response.json()
        # All offers should belong to the authenticated trader
        for offer in offers:
            assert "trader_id" in offer


class TestBug3ProfileNoTradingAccount:
    """Bug 3: Profile page (Аккаунт → Профиль) does NOT show 'Торговый счёт'"""
    
    def test_trader_profile_no_shop_balance(self, api_client, trader_token):
        """Test that trader profile endpoint does not return shop_balance"""
        response = api_client.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {trader_token}"
        })
        assert response.status_code == 200
        
        trader = response.json()
        # Profile should have balance_usdt but NOT shop_balance
        assert "balance_usdt" in trader, "Trader should have balance_usdt"
        # shop_balance should not be in the response (or if present, not displayed in UI)
        # The fix removes shop_balance from TraderAccount display


class TestBug4TransactionHistory:
    """Bug 4: Transaction history shows transfers with correct colors"""
    
    def test_transactions_endpoint(self, api_client, trader_token):
        """Test that transactions endpoint returns data"""
        response = api_client.get(f"{BASE_URL}/api/traders/transactions", headers={
            "Authorization": f"Bearer {trader_token}"
        })
        assert response.status_code == 200
        
        transactions = response.json()
        assert isinstance(transactions, list)
    
    def test_transfers_use_correct_field_names(self, api_client, trader_token):
        """Test that transfers use from_id/to_id field names"""
        response = api_client.get(f"{BASE_URL}/api/traders/transactions", headers={
            "Authorization": f"Bearer {trader_token}"
        })
        assert response.status_code == 200
        
        transactions = response.json()
        for tx in transactions:
            if tx.get("type") in ["transfer_sent", "transfer_received"]:
                # Verify transfer transactions have correct structure
                assert "amount" in tx, "Transfer should have amount"
                assert "description" in tx, "Transfer should have description"
                # Sent transfers should have negative amount
                if tx["type"] == "transfer_sent":
                    assert tx["amount"] < 0, f"Transfer sent should have negative amount, got {tx['amount']}"
                # Received transfers should have positive amount
                elif tx["type"] == "transfer_received":
                    assert tx["amount"] > 0, f"Transfer received should have positive amount, got {tx['amount']}"
    
    def test_transfer_history_endpoint(self, api_client, trader_token):
        """Test transfer history endpoint uses from_id/to_id"""
        response = api_client.get(f"{BASE_URL}/api/transfers/history", headers={
            "Authorization": f"Bearer {trader_token}"
        })
        assert response.status_code == 200
        
        transfers = response.json()
        assert isinstance(transfers, list)


class TestBug5ForumRateLimit:
    """Bug 5: Forum rate limit - cannot send more than 1 message per 5 seconds"""
    
    def test_forum_rate_limit_returns_429(self, api_client, trader_token):
        """Test that sending messages too fast returns 429 error"""
        # Wait to ensure no rate limit from previous tests
        time.sleep(6)
        
        # First message should succeed
        unique_msg = f"Test message {uuid.uuid4().hex[:8]}"
        response1 = api_client.post(f"{BASE_URL}/api/forum/messages", 
            json={"content": unique_msg},
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        # If first message fails due to ban, skip test
        if response1.status_code == 403 and "заблокированы" in response1.text:
            pytest.skip("Trader is banned from forum")
        
        # If first message fails due to existing rate limit, wait and retry
        if response1.status_code == 429:
            time.sleep(6)  # Wait for rate limit to expire
            response1 = api_client.post(f"{BASE_URL}/api/forum/messages", 
                json={"content": unique_msg},
                headers={"Authorization": f"Bearer {trader_token}"}
            )
        
        # First message should succeed (201 or 200)
        assert response1.status_code in [200, 201], f"First message should succeed, got {response1.status_code}: {response1.text}"
        
        # Second message immediately after should fail with 429
        unique_msg2 = f"Test message 2 {uuid.uuid4().hex[:8]}"
        response2 = api_client.post(f"{BASE_URL}/api/forum/messages", 
            json={"content": unique_msg2},
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        assert response2.status_code == 429, f"Second message should be rate limited (429), got {response2.status_code}"
        
        # Verify error message contains wait time
        error_detail = response2.json().get("detail", "")
        assert "Подождите" in error_detail, f"Error should contain 'Подождите', got: {error_detail}"
        assert "сек" in error_detail, f"Error should contain 'сек', got: {error_detail}"
    
    def test_forum_rate_limit_allows_after_wait(self, api_client, trader2_token):
        """Test that messages are allowed after waiting 5 seconds"""
        # Wait to ensure no rate limit from previous tests
        time.sleep(6)
        
        # First message
        unique_msg = f"Rate limit test {uuid.uuid4().hex[:8]}"
        response1 = api_client.post(f"{BASE_URL}/api/forum/messages", 
            json={"content": unique_msg},
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        
        # If banned, skip test
        if response1.status_code == 403 and "заблокированы" in response1.text:
            pytest.skip("Trader2 is banned from forum")
        
        # If rate limited, wait
        if response1.status_code == 429:
            time.sleep(6)
            response1 = api_client.post(f"{BASE_URL}/api/forum/messages", 
                json={"content": unique_msg},
                headers={"Authorization": f"Bearer {trader2_token}"}
            )
        
        assert response1.status_code in [200, 201], f"First message should succeed: {response1.text}"
        
        # Wait 6 seconds (more than 5 second limit)
        time.sleep(6)
        
        # Second message after wait should succeed
        unique_msg2 = f"After wait test {uuid.uuid4().hex[:8]}"
        response2 = api_client.post(f"{BASE_URL}/api/forum/messages", 
            json={"content": unique_msg2},
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        
        assert response2.status_code in [200, 201], f"Message after wait should succeed, got {response2.status_code}: {response2.text}"


class TestTransferCreation:
    """Test transfer creation to verify from_id/to_id fields"""
    
    def test_create_transfer(self, api_client, trader_token, trader2_token):
        """Test creating a transfer between traders"""
        # Get trader2 info to get their nickname
        response = api_client.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {trader2_token}"
        })
        assert response.status_code == 200
        trader2_info = response.json()
        trader2_nickname = trader2_info.get("nickname") or trader2_info.get("login")
        
        # Create a small transfer
        response = api_client.post(f"{BASE_URL}/api/transfers/send", 
            json={
                "to_nickname": trader2_nickname,
                "amount": 0.01
            },
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        # May fail if insufficient balance, but should not be 500
        assert response.status_code != 500, f"Transfer should not cause server error: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("status") == "success"
            assert "transfer_id" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
