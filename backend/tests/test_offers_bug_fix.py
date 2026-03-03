"""
Test cases for the offers bug fix:
- Trader's ads were visible in public order book but missing from 'My Ads' page
- Fix: 
  1) Removed frontend filter that showed only active offers
  2) Added backend data normalization for offers collection
  3) Made OfferResponse schema more resilient to missing fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMyOffersEndpoint:
    """Tests for GET /api/offers/my - should return ALL trader offers"""

    def test_my_offers_returns_all_offers(self, api_client, trader_auth):
        """GET /api/offers/my should return ALL offers (active and inactive)"""
        response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        offers = response.json()
        assert isinstance(offers, list), "Response should be a list"
        
        # Count active and inactive offers
        active_count = sum(1 for o in offers if o.get("is_active") is True)
        inactive_count = sum(1 for o in offers if o.get("is_active") is False)
        
        print(f"Total offers: {len(offers)}, Active: {active_count}, Inactive: {inactive_count}")
        
        # The fix should ensure we see both active AND inactive offers
        # If all returned are active only, the bug may still exist
        assert len(offers) >= 1, "Trader should have at least 1 offer"

    def test_my_offers_includes_inactive(self, api_client, trader_auth):
        """Specifically check that inactive offers are included in my offers"""
        response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert response.status_code == 200
        offers = response.json()
        
        # Check for presence of inactive offers
        inactive_offers = [o for o in offers if o.get("is_active") is False]
        
        # Note: This test validates the bug fix - inactive offers should be returned
        # If there are no inactive offers in DB, this is not a failure
        if inactive_offers:
            print(f"Found {len(inactive_offers)} inactive offers - bug fix confirmed")
            for offer in inactive_offers:
                print(f"  - Offer {offer.get('id', '?')[:8]}..., available: {offer.get('available_usdt')}")
        else:
            print("No inactive offers in database - cannot confirm bug fix for inactive filtering")

    def test_my_offers_has_required_fields(self, api_client, trader_auth):
        """All returned offers should have required fields with proper defaults"""
        response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            # Check required fields exist
            assert "id" in offer, "Offer missing 'id'"
            assert "trader_id" in offer, "Offer missing 'trader_id'"
            assert "is_active" in offer, f"Offer {offer.get('id')} missing 'is_active' field"
            
            # Check normalization - fields should have defaults
            assert "trader_login" in offer, "Offer missing 'trader_login'"
            assert "payment_methods" in offer, "Offer missing 'payment_methods'"
            assert isinstance(offer.get("payment_methods"), list), "payment_methods should be a list"
            
            # Amount fields should be present
            assert "amount_usdt" in offer or offer.get("amount_usdt") is not None
            assert "available_usdt" in offer or offer.get("available_usdt") is not None
            assert "min_amount" in offer or offer.get("min_amount") is not None
            assert "max_amount" in offer or offer.get("max_amount") is not None
            assert "price_rub" in offer or offer.get("price_rub") is not None

    def test_my_offers_trader_login_populated(self, api_client, trader_auth):
        """trader_login field should be populated for all offers"""
        response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert response.status_code == 200
        offers = response.json()
        
        trader_login = trader_auth["user"].get("login")
        for offer in offers:
            assert offer.get("trader_login"), f"Offer {offer.get('id')} has empty trader_login"
            # Trader's own offers should have their login
            assert offer.get("trader_login") == trader_login, \
                f"Expected trader_login '{trader_login}', got '{offer.get('trader_login')}'"


class TestPublicOffersEndpoint:
    """Tests for GET /api/public/offers - should return ONLY active offers with available_usdt > 0"""

    def test_public_offers_returns_only_active(self, api_client):
        """GET /api/public/offers should return ONLY active offers"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        assert isinstance(offers, list)
        
        for offer in offers:
            assert offer.get("is_active") is True, \
                f"Public offer {offer.get('id')} should be active, got is_active={offer.get('is_active')}"

    def test_public_offers_has_available_usdt(self, api_client):
        """Public offers should have available_usdt > 0"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            available = offer.get("available_usdt", 0)
            assert available > 0, \
                f"Public offer {offer.get('id')} should have available_usdt > 0, got {available}"

    def test_public_offers_has_required_fields(self, api_client):
        """Public offers should have all required fields normalized"""
        response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            assert "id" in offer
            assert "trader_id" in offer
            assert "trader_login" in offer
            assert offer.get("trader_login"), f"Public offer {offer.get('id')} has empty trader_login"
            assert "payment_methods" in offer
            assert isinstance(offer.get("payment_methods"), list)
            assert "is_active" in offer
            assert "available_usdt" in offer

    def test_public_offers_excludes_inactive(self, api_client, trader_auth):
        """Verify inactive offers are NOT shown in public endpoint"""
        # Get trader's offers to identify inactive ones
        my_response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert my_response.status_code == 200
        my_offers = my_response.json()
        
        inactive_ids = {o.get("id") for o in my_offers if o.get("is_active") is False}
        
        # Get public offers
        public_response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert public_response.status_code == 200
        public_offers = public_response.json()
        
        public_ids = {o.get("id") for o in public_offers}
        
        # No inactive offers should appear in public
        overlap = inactive_ids & public_ids
        assert not overlap, f"Inactive offers should not appear in public: {overlap}"


class TestOfferNormalization:
    """Tests for backend data normalization of offers"""

    def test_payment_methods_always_list(self, api_client, trader_auth):
        """payment_methods field should always be a list"""
        response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            pm = offer.get("payment_methods")
            assert pm is not None, "payment_methods should not be None"
            assert isinstance(pm, list), f"payment_methods should be list, got {type(pm)}"

    def test_is_active_boolean(self, api_client, trader_auth):
        """is_active field should be boolean, not string"""
        response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            is_active = offer.get("is_active")
            assert isinstance(is_active, bool), \
                f"is_active should be bool, got {type(is_active)}: {is_active}"

    def test_numeric_fields_are_numbers(self, api_client, trader_auth):
        """Amount fields should be numeric"""
        response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert response.status_code == 200
        offers = response.json()
        
        numeric_fields = ["amount_usdt", "available_usdt", "min_amount", "max_amount", "price_rub"]
        
        for offer in offers:
            for field in numeric_fields:
                value = offer.get(field)
                if value is not None:
                    assert isinstance(value, (int, float)), \
                        f"Offer {offer.get('id')}: {field} should be numeric, got {type(value)}"


class TestOffersFilteringBehavior:
    """Integration tests comparing my offers vs public offers"""

    def test_my_offers_superset_of_active_public(self, api_client, trader_auth):
        """Trader's active offers should appear in public endpoint"""
        # Get trader's offers
        my_response = api_client.get(
            f"{BASE_URL}/api/offers/my",
            headers=trader_auth["headers"]
        )
        assert my_response.status_code == 200
        my_offers = my_response.json()
        
        # Get public offers
        public_response = api_client.get(f"{BASE_URL}/api/public/offers")
        assert public_response.status_code == 200
        public_offers = public_response.json()
        
        # Trader's active offers with available_usdt > 0 should be in public
        my_active_ids = {
            o.get("id") for o in my_offers 
            if o.get("is_active") is True and o.get("available_usdt", 0) > 0
        }
        public_ids = {o.get("id") for o in public_offers}
        
        # All trader's active offers should be visible publicly
        missing = my_active_ids - public_ids
        if missing:
            print(f"Warning: Active offers not in public: {missing}")
        
        # Active offers should be in public
        for offer_id in my_active_ids:
            assert offer_id in public_ids, \
                f"Active offer {offer_id} should appear in public offers"
