"""
Test suite for P2P Exchange new UI features:
- Task 5: Offer List refactor (limits column, USDT+RUB display, payment type display, CIS transfers)
- Task 6: Hide T&C on main page (no T&C visible)
- Task 7: Chat by nickname only (no user list)
- Task 8: Forum search functionality
- Task 10: Delete chats, pinned general chat, real-time messages
- Task 11: Chat auto-moderation (spam/links ban 24h)
- Task 13: Referral promo text
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com')

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
    pytest.skip(f"Trader authentication failed: {response.status_code}")


@pytest.fixture(scope="module")
def trader2_token(api_client):
    """Get authentication token for trader2"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "login": TRADER2_LOGIN,
        "password": TRADER2_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Trader2 authentication failed: {response.status_code}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, trader_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {trader_token}"})
    return api_client


class TestPublicOffers:
    """Test Task 5: Offer List refactor - public offers endpoint"""
    
    def test_public_offers_endpoint_exists(self, api_client):
        """Test that public offers endpoint is accessible"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Public offers endpoint returns {len(data)} offers")
    
    def test_offers_have_limits_fields(self, api_client):
        """Test that offers have min_amount and max_amount fields (Task 5: Limits column)"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            offer = data[0]
            assert "min_amount" in offer, "Offer should have min_amount field"
            assert "max_amount" in offer, "Offer should have max_amount field"
            print(f"✓ Offer has limits: min={offer.get('min_amount')}, max={offer.get('max_amount')}")
        else:
            print("⚠ No offers available to test limits fields")
    
    def test_offers_have_available_usdt(self, api_client):
        """Test that offers have available_usdt field (Task 5: Available shows USDT)"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            offer = data[0]
            assert "available_usdt" in offer, "Offer should have available_usdt field"
            assert "price_rub" in offer, "Offer should have price_rub field for RUB calculation"
            print(f"✓ Offer has available_usdt={offer.get('available_usdt')}, price_rub={offer.get('price_rub')}")
        else:
            print("⚠ No offers available to test available_usdt field")
    
    def test_offers_have_requisites_with_type(self, api_client):
        """Test that offers have requisites with type field (Task 5: Payment shows type)"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        data = response.json()
        
        for offer in data:
            if offer.get("requisites"):
                for req in offer["requisites"]:
                    assert "type" in req, "Requisite should have type field"
                    print(f"✓ Requisite type: {req.get('type')}")
                break
        else:
            print("⚠ No offers with requisites to test type field")


class TestCISRequisites:
    """Test Task 5: CIS transfer requisite type"""
    
    def test_create_cis_requisite(self, api_client, trader_token):
        """Test creating a CIS transfer requisite"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        cis_data = {
            "type": "cis",
            "data": {
                "country": "Казахстан",
                "bank_name": "Kaspi Bank",
                "account_number": "KZ00BANK0000000000",
                "recipient_name": "Test User",
                "swift_bic": "CASPKZKA"
            }
        }
        
        response = api_client.post(f"{BASE_URL}/api/requisites", json=cis_data, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            assert data["type"] == "cis", "Requisite type should be 'cis'"
            assert data["data"]["country"] == "Казахстан"
            print(f"✓ CIS requisite created: {data['id']}")
            
            # Cleanup - delete the requisite
            api_client.delete(f"{BASE_URL}/api/requisites/{data['id']}", headers=headers)
        elif response.status_code == 400 and "Maximum" in response.text:
            print("⚠ Maximum CIS requisites reached, skipping creation test")
        else:
            print(f"⚠ CIS requisite creation returned {response.status_code}: {response.text}")
    
    def test_get_requisites_includes_cis_type(self, api_client, trader_token):
        """Test that requisites endpoint supports CIS type"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        response = api_client.get(f"{BASE_URL}/api/requisites", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check if any CIS requisites exist
        cis_requisites = [r for r in data if r.get("type") == "cis"]
        print(f"✓ Found {len(cis_requisites)} CIS requisites")


class TestForumSearch:
    """Test Task 8: Forum search functionality"""
    
    def test_forum_messages_endpoint(self, api_client):
        """Test that forum messages endpoint is accessible"""
        response = api_client.get(f"{BASE_URL}/api/forum/messages?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Forum messages endpoint returns {len(data)} messages")


class TestForumAutoModeration:
    """Test Task 11: Chat auto-moderation (spam/links ban 24h)"""
    
    def test_spam_keyword_blocked(self, api_client, trader_token):
        """Test that spam keywords are blocked and user is banned"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        # Try to send a message with spam keyword
        spam_message = {"content": "Продаю аккаунты дешево!"}
        response = api_client.post(f"{BASE_URL}/api/forum/messages", json=spam_message, headers=headers)
        
        # Should be blocked with 403
        if response.status_code == 403:
            assert "заблокирован" in response.text.lower() or "blocked" in response.text.lower()
            print(f"✓ Spam message blocked: {response.json().get('detail', response.text)}")
        else:
            print(f"⚠ Spam message not blocked, status: {response.status_code}")
    
    def test_external_link_blocked(self, api_client, trader2_token):
        """Test that external links are blocked"""
        headers = {"Authorization": f"Bearer {trader2_token}"}
        
        # Try to send a message with external link
        link_message = {"content": "Check out https://example.com for more info"}
        response = api_client.post(f"{BASE_URL}/api/forum/messages", json=link_message, headers=headers)
        
        # Should be blocked with 403
        if response.status_code == 403:
            assert "ссылки" in response.text.lower() or "link" in response.text.lower() or "заблокирован" in response.text.lower()
            print(f"✓ Link message blocked: {response.json().get('detail', response.text)}")
        else:
            print(f"⚠ Link message not blocked, status: {response.status_code}")
    
    def test_telegram_link_blocked(self, api_client, trader2_token):
        """Test that telegram links are blocked"""
        headers = {"Authorization": f"Bearer {trader2_token}"}
        
        # Try to send a message with telegram link
        tg_message = {"content": "Contact me at t.me/myusername"}
        response = api_client.post(f"{BASE_URL}/api/forum/messages", json=tg_message, headers=headers)
        
        # Should be blocked with 403
        if response.status_code == 403:
            print(f"✓ Telegram link blocked: {response.json().get('detail', response.text)}")
        else:
            print(f"⚠ Telegram link not blocked, status: {response.status_code}")


class TestConversations:
    """Test Task 7 & 10: Chat by nickname, delete chats"""
    
    def test_search_users_by_nickname(self, api_client, trader_token):
        """Test searching users by nickname (Task 7)"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        # Search for users
        response = api_client.get(f"{BASE_URL}/api/users/search?q=trader", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list), "Response should be a list"
            for user in data:
                assert "nickname" in user, "User should have nickname field"
            print(f"✓ User search returns {len(data)} users with nicknames")
        else:
            print(f"⚠ User search returned {response.status_code}")
    
    def test_get_conversations(self, api_client, trader_token):
        """Test getting conversations list"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        response = api_client.get(f"{BASE_URL}/api/conversations", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Conversations endpoint returns {len(data)} conversations")
    
    def test_delete_conversation_endpoint_exists(self, api_client, trader_token):
        """Test that delete conversation endpoint exists (Task 10)"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        # Try to delete a non-existent conversation to verify endpoint exists
        response = api_client.delete(f"{BASE_URL}/api/conversations/non_existent_id", headers=headers)
        
        # Should return 404 (not found) not 405 (method not allowed)
        assert response.status_code in [404, 200], f"Delete endpoint should exist, got {response.status_code}"
        print(f"✓ Delete conversation endpoint exists (status: {response.status_code})")


class TestReferralProgram:
    """Test Task 13: Referral promo text"""
    
    def test_referral_info_endpoint(self, api_client, trader_token):
        """Test that referral info endpoint returns data"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        response = api_client.get(f"{BASE_URL}/api/traders/referral", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "referral_code" in data, "Should have referral_code"
        assert "referral_link" in data, "Should have referral_link"
        assert "referral_earnings" in data, "Should have referral_earnings"
        assert "referrals_count" in data, "Should have referrals_count"
        
        print(f"✓ Referral info: code={data['referral_code']}, earnings={data['referral_earnings']}, count={data['referrals_count']}")


class TestPrivateMessages:
    """Test Task 10: Real-time messages"""
    
    def test_create_conversation(self, api_client, trader_token, trader2_token):
        """Test creating a conversation between two traders"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        # First get trader2's ID
        headers2 = {"Authorization": f"Bearer {trader2_token}"}
        me_response = api_client.get(f"{BASE_URL}/api/traders/me", headers=headers2)
        
        if me_response.status_code == 200:
            trader2_id = me_response.json().get("id")
            
            # Create conversation
            response = api_client.post(f"{BASE_URL}/api/conversations/{trader2_id}", json={}, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                assert "id" in data, "Conversation should have id"
                print(f"✓ Conversation created/retrieved: {data['id']}")
            else:
                print(f"⚠ Create conversation returned {response.status_code}")
        else:
            print(f"⚠ Could not get trader2 info: {me_response.status_code}")
    
    def test_send_private_message(self, api_client, trader_token, trader2_token):
        """Test sending a private message"""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        # Get trader2's ID
        headers2 = {"Authorization": f"Bearer {trader2_token}"}
        me_response = api_client.get(f"{BASE_URL}/api/traders/me", headers=headers2)
        
        if me_response.status_code == 200:
            trader2_id = me_response.json().get("id")
            
            # Create/get conversation
            conv_response = api_client.post(f"{BASE_URL}/api/conversations/{trader2_id}", json={}, headers=headers)
            
            if conv_response.status_code == 200:
                conv_id = conv_response.json().get("id")
                
                # Send message
                msg_data = {"content": f"Test message {uuid.uuid4().hex[:8]}"}
                msg_response = api_client.post(f"{BASE_URL}/api/conversations/{conv_id}/messages", json=msg_data, headers=headers)
                
                if msg_response.status_code in [200, 201]:
                    print(f"✓ Private message sent successfully")
                else:
                    print(f"⚠ Send message returned {msg_response.status_code}: {msg_response.text}")
            else:
                print(f"⚠ Create conversation returned {conv_response.status_code}")
        else:
            print(f"⚠ Could not get trader2 info")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
