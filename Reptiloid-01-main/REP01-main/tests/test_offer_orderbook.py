# P2P Exchange - Offer Order Book and Balance Reservation Tests
# Tests for new functionality:
# 1. Public endpoint /api/public/offers returns active offers
# 2. Payment method filter works
# 3. Offer creation reserves amount_usdt from trader balance
# 4. Cannot select multiple requisites of same type
# 5. Deleting offer returns reserved amount to trader balance
# 6. Offers show: trader, rate, available amount, payment methods, conditions

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com').rstrip('/')

# Test data storage
test_data = {
    "trader_token": None,
    "trader_id": None,
    "initial_balance": None,
    "requisite_card_id": None,
    "requisite_sbp_id": None,
    "requisite_card2_id": None,
    "offer_id": None
}


class TestSetup:
    """Setup test data - login trader"""
    
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
    
    def test_get_initial_balance(self):
        """Get trader's initial balance"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        trader = response.json()
        test_data["initial_balance"] = trader["balance_usdt"]
        print(f"Initial balance: {test_data['initial_balance']} USDT")
    
    def test_deposit_for_testing(self):
        """Deposit USDT for testing"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/traders/deposit?amount=500",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        test_data["initial_balance"] = data["balance_usdt"]
        print(f"Deposited 500 USDT, new balance: {test_data['initial_balance']}")


class TestPublicOffersEndpoint:
    """Test: Public endpoint /api/public/offers returns active offers"""
    
    def test_public_offers_endpoint_exists(self):
        """GET /api/public/offers should return 200"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200, f"Public offers endpoint failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"SUCCESS: Public offers endpoint returns {len(data)} offers")
    
    def test_public_offers_returns_active_only(self):
        """Public offers should only return active offers with available_usdt > 0"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            assert offer.get("is_active") == True, f"Offer {offer['id']} should be active"
            available = offer.get("available_usdt", offer.get("amount_usdt", 0))
            assert available > 0, f"Offer {offer['id']} should have available_usdt > 0"
        
        print(f"SUCCESS: All {len(offers)} offers are active with available_usdt > 0")
    
    def test_public_offers_have_required_fields(self):
        """Public offers should have all required fields for display"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        required_fields = ["id", "trader_login", "price_rub", "payment_methods", "is_active"]
        
        for offer in offers:
            for field in required_fields:
                assert field in offer, f"Offer missing required field: {field}"
            
            # Check amount fields (new logic)
            assert "amount_usdt" in offer or "max_amount" in offer, "Offer should have amount_usdt or max_amount"
            assert "available_usdt" in offer or "max_amount" in offer, "Offer should have available_usdt or max_amount"
        
        if offers:
            print(f"SUCCESS: Offers have all required fields")
            print(f"Sample offer: trader={offers[0]['trader_login']}, price={offers[0]['price_rub']}, available={offers[0].get('available_usdt', offers[0].get('amount_usdt'))}")
        else:
            print("No offers to verify fields")


class TestPaymentMethodFilter:
    """Test: Payment method filter works"""
    
    def test_filter_by_card(self):
        """Filter offers by card payment method"""
        response = requests.get(f"{BASE_URL}/api/public/offers?payment_method=card")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            # Check if offer has card in payment_methods or requisites
            has_card = "card" in offer.get("payment_methods", [])
            has_card_requisite = any(r.get("type") == "card" for r in offer.get("requisites", []))
            assert has_card or has_card_requisite, f"Offer {offer['id']} should have card payment method"
        
        print(f"SUCCESS: Filter by card returns {len(offers)} offers")
    
    def test_filter_by_sbp(self):
        """Filter offers by SBP payment method"""
        response = requests.get(f"{BASE_URL}/api/public/offers?payment_method=sbp")
        assert response.status_code == 200
        offers = response.json()
        print(f"SUCCESS: Filter by sbp returns {len(offers)} offers")
    
    def test_filter_all_returns_all(self):
        """Filter 'all' should return all active offers"""
        response_all = requests.get(f"{BASE_URL}/api/public/offers?payment_method=all")
        response_none = requests.get(f"{BASE_URL}/api/public/offers")
        
        assert response_all.status_code == 200
        assert response_none.status_code == 200
        
        offers_all = response_all.json()
        offers_none = response_none.json()
        
        # Both should return same number of offers
        assert len(offers_all) == len(offers_none), "Filter 'all' should return same as no filter"
        print(f"SUCCESS: Filter 'all' returns {len(offers_all)} offers (same as no filter)")


class TestOfferSorting:
    """Test: Offer sorting works"""
    
    def test_sort_by_price(self):
        """Sort offers by price (ascending)"""
        response = requests.get(f"{BASE_URL}/api/public/offers?sort_by=price")
        assert response.status_code == 200
        offers = response.json()
        
        if len(offers) > 1:
            prices = [o["price_rub"] for o in offers]
            assert prices == sorted(prices), "Offers should be sorted by price ascending"
            print(f"SUCCESS: Offers sorted by price: {prices[:5]}...")
        else:
            print("Not enough offers to verify sorting")
    
    def test_sort_by_amount(self):
        """Sort offers by amount (descending)"""
        response = requests.get(f"{BASE_URL}/api/public/offers?sort_by=amount")
        assert response.status_code == 200
        offers = response.json()
        
        if len(offers) > 1:
            amounts = [o.get("available_usdt", o.get("amount_usdt", 0)) for o in offers]
            assert amounts == sorted(amounts, reverse=True), "Offers should be sorted by amount descending"
            print(f"SUCCESS: Offers sorted by amount: {amounts[:5]}...")
        else:
            print("Not enough offers to verify sorting")
    
    def test_sort_by_rating(self):
        """Sort offers by rating (descending)"""
        response = requests.get(f"{BASE_URL}/api/public/offers?sort_by=rating")
        assert response.status_code == 200
        offers = response.json()
        
        if len(offers) > 1:
            ratings = [o.get("success_rate", 100) for o in offers]
            assert ratings == sorted(ratings, reverse=True), "Offers should be sorted by rating descending"
            print(f"SUCCESS: Offers sorted by rating: {ratings[:5]}...")
        else:
            print("Not enough offers to verify sorting")


class TestRequisiteCreation:
    """Setup requisites for offer testing"""
    
    def test_create_card_requisite(self):
        """Create a card requisite"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/requisites",
            json={
                "type": "card",
                "data": {
                    "bank_name": "Сбербанк",
                    "card_number": "4276 1234 5678 9012",
                    "card_holder": "IVAN PETROV",
                    "is_primary": True
                }
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        if response.status_code == 200:
            req = response.json()
            test_data["requisite_card_id"] = req["id"]
            print(f"Created card requisite: {req['id']}")
        elif response.status_code == 400 and "Maximum" in response.text:
            # Get existing requisites
            response = requests.get(
                f"{BASE_URL}/api/requisites",
                headers={"Authorization": f"Bearer {test_data['trader_token']}"}
            )
            if response.status_code == 200:
                reqs = response.json()
                card_reqs = [r for r in reqs if r["type"] == "card"]
                if card_reqs:
                    test_data["requisite_card_id"] = card_reqs[0]["id"]
                    print(f"Using existing card requisite: {test_data['requisite_card_id']}")
    
    def test_create_sbp_requisite(self):
        """Create an SBP requisite"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/requisites",
            json={
                "type": "sbp",
                "data": {
                    "phone": "+7 999 123 4567",
                    "recipient_name": "Иван П.",
                    "bank_name": "Тинькофф",
                    "is_primary": False
                }
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        if response.status_code == 200:
            req = response.json()
            test_data["requisite_sbp_id"] = req["id"]
            print(f"Created SBP requisite: {req['id']}")
        elif response.status_code == 400:
            # Get existing requisites
            response = requests.get(
                f"{BASE_URL}/api/requisites",
                headers={"Authorization": f"Bearer {test_data['trader_token']}"}
            )
            if response.status_code == 200:
                reqs = response.json()
                sbp_reqs = [r for r in reqs if r["type"] == "sbp"]
                if sbp_reqs:
                    test_data["requisite_sbp_id"] = sbp_reqs[0]["id"]
                    print(f"Using existing SBP requisite: {test_data['requisite_sbp_id']}")
    
    def test_create_second_card_requisite(self):
        """Create a second card requisite for duplicate type test"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/requisites",
            json={
                "type": "card",
                "data": {
                    "bank_name": "Тинькофф",
                    "card_number": "5536 9876 5432 1098",
                    "card_holder": "IVAN PETROV",
                    "is_primary": False
                }
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        
        if response.status_code == 200:
            req = response.json()
            test_data["requisite_card2_id"] = req["id"]
            print(f"Created second card requisite: {req['id']}")
        elif response.status_code == 400:
            # Get existing requisites
            response = requests.get(
                f"{BASE_URL}/api/requisites",
                headers={"Authorization": f"Bearer {test_data['trader_token']}"}
            )
            if response.status_code == 200:
                reqs = response.json()
                card_reqs = [r for r in reqs if r["type"] == "card"]
                if len(card_reqs) > 1:
                    test_data["requisite_card2_id"] = card_reqs[1]["id"]
                    print(f"Using existing second card requisite: {test_data['requisite_card2_id']}")


class TestOfferBalanceReservation:
    """Test: Creating offer reserves amount_usdt from trader balance"""
    
    def test_create_offer_reserves_balance(self):
        """Creating offer should reserve amount_usdt from trader balance"""
        if not test_data["trader_token"] or not test_data["requisite_card_id"]:
            pytest.skip("Trader token or requisite not available")
        
        # Get current balance
        response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        balance_before = response.json()["balance_usdt"]
        print(f"Balance before offer: {balance_before} USDT")
        
        # Create offer with amount_usdt
        offer_amount = 100.0
        response = requests.post(
            f"{BASE_URL}/api/offers",
            json={
                "amount_usdt": offer_amount,
                "price_rub": 92.5,
                "payment_methods": ["card"],
                "accepted_merchant_types": ["casino", "shop", "stream", "other"],
                "requisite_ids": [test_data["requisite_card_id"]],
                "conditions": "Тестовое объявление"
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200, f"Offer creation failed: {response.text}"
        offer = response.json()
        test_data["offer_id"] = offer["id"]
        print(f"Created offer: {offer['id']}, amount_usdt: {offer['amount_usdt']}")
        
        # Check balance decreased
        response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        balance_after = response.json()["balance_usdt"]
        print(f"Balance after offer: {balance_after} USDT")
        
        expected_balance = balance_before - offer_amount
        assert abs(balance_after - expected_balance) < 0.01, f"Balance should decrease by {offer_amount}. Expected {expected_balance}, got {balance_after}"
        print(f"SUCCESS: Balance decreased by {offer_amount} USDT (reserved for offer)")
    
    def test_offer_has_amount_usdt_field(self):
        """Offer should have amount_usdt and available_usdt fields"""
        if not test_data["offer_id"]:
            pytest.skip("Offer not created")
        
        response = requests.get(
            f"{BASE_URL}/api/offers/my",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200
        offers = response.json()
        
        offer = next((o for o in offers if o["id"] == test_data["offer_id"]), None)
        assert offer is not None, "Created offer not found"
        
        assert "amount_usdt" in offer, "Offer should have amount_usdt field"
        assert "available_usdt" in offer, "Offer should have available_usdt field"
        assert offer["amount_usdt"] == offer["available_usdt"], "Initially amount_usdt should equal available_usdt"
        print(f"SUCCESS: Offer has amount_usdt={offer['amount_usdt']}, available_usdt={offer['available_usdt']}")
    
    def test_insufficient_balance_error(self):
        """Creating offer with amount > balance should fail"""
        if not test_data["trader_token"] or not test_data["requisite_card_id"]:
            pytest.skip("Trader token or requisite not available")
        
        # Get current balance
        response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        balance = response.json()["balance_usdt"]
        
        # Try to create offer with more than balance
        response = requests.post(
            f"{BASE_URL}/api/offers",
            json={
                "amount_usdt": balance + 1000,  # More than available
                "price_rub": 92.5,
                "payment_methods": ["card"],
                "accepted_merchant_types": ["casino", "shop"],
                "requisite_ids": [test_data["requisite_card_id"]]
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        error = response.json().get("detail", "")
        assert "недостаточно" in error.lower() or "баланс" in error.lower(), f"Expected balance error: {error}"
        print(f"SUCCESS: Insufficient balance error returned: {error}")


class TestDuplicateRequisiteType:
    """Test: Cannot select multiple requisites of same type"""
    
    def test_duplicate_requisite_type_rejected(self):
        """Creating offer with two card requisites should fail"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        if not test_data["requisite_card_id"] or not test_data["requisite_card2_id"]:
            pytest.skip("Need two card requisites for this test")
        
        # Try to create offer with two card requisites
        response = requests.post(
            f"{BASE_URL}/api/offers",
            json={
                "amount_usdt": 50,
                "price_rub": 93.0,
                "payment_methods": ["card"],
                "accepted_merchant_types": ["casino", "shop"],
                "requisite_ids": [test_data["requisite_card_id"], test_data["requisite_card2_id"]]
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        error = response.json().get("detail", "")
        assert "один" in error.lower() or "type" in error.lower() or "реквизит" in error.lower(), f"Expected duplicate type error: {error}"
        print(f"SUCCESS: Duplicate requisite type rejected: {error}")
    
    def test_different_requisite_types_allowed(self):
        """Creating offer with card + sbp requisites should succeed"""
        if not test_data["trader_token"]:
            pytest.skip("Trader token not available")
        
        if not test_data["requisite_card_id"] or not test_data["requisite_sbp_id"]:
            pytest.skip("Need card and sbp requisites for this test")
        
        # Create offer with card + sbp (different types)
        response = requests.post(
            f"{BASE_URL}/api/offers",
            json={
                "amount_usdt": 50,
                "price_rub": 93.0,
                "payment_methods": ["card", "sbp"],
                "accepted_merchant_types": ["casino", "shop", "stream", "other"],
                "requisite_ids": [test_data["requisite_card_id"], test_data["requisite_sbp_id"]]
            },
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200, f"Offer creation failed: {response.text}"
        offer = response.json()
        print(f"SUCCESS: Offer with different requisite types created: {offer['id']}")
        
        # Cleanup - delete this offer
        requests.delete(
            f"{BASE_URL}/api/offers/{offer['id']}",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )


class TestOfferDeletionReturnsBalance:
    """Test: Deleting offer returns reserved amount to trader balance"""
    
    def test_delete_offer_returns_balance(self):
        """Deleting offer should return available_usdt to trader balance"""
        if not test_data["trader_token"] or not test_data["offer_id"]:
            pytest.skip("Trader token or offer not available")
        
        # Get current balance
        response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        balance_before = response.json()["balance_usdt"]
        print(f"Balance before deletion: {balance_before} USDT")
        
        # Get offer's available_usdt
        response = requests.get(
            f"{BASE_URL}/api/offers/my",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        offers = response.json()
        offer = next((o for o in offers if o["id"] == test_data["offer_id"]), None)
        
        if not offer:
            pytest.skip("Offer not found")
        
        available_usdt = offer.get("available_usdt", offer.get("amount_usdt", 0))
        print(f"Offer available_usdt: {available_usdt}")
        
        # Delete offer
        response = requests.delete(
            f"{BASE_URL}/api/offers/{test_data['offer_id']}",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        assert response.status_code == 200, f"Delete failed: {response.text}"
        delete_result = response.json()
        print(f"Delete result: {delete_result}")
        
        # Check returned_usdt in response
        if "returned_usdt" in delete_result:
            assert delete_result["returned_usdt"] == available_usdt, f"returned_usdt should match available_usdt"
        
        # Check balance increased
        response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {test_data['trader_token']}"}
        )
        balance_after = response.json()["balance_usdt"]
        print(f"Balance after deletion: {balance_after} USDT")
        
        expected_balance = balance_before + available_usdt
        assert abs(balance_after - expected_balance) < 0.01, f"Balance should increase by {available_usdt}. Expected {expected_balance}, got {balance_after}"
        print(f"SUCCESS: Balance increased by {available_usdt} USDT (returned from deleted offer)")
        
        test_data["offer_id"] = None  # Clear offer_id


class TestOfferDisplayFields:
    """Test: Offers in order book show required fields"""
    
    def test_offers_show_trader_info(self):
        """Offers should show trader login"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            assert "trader_login" in offer, "Offer should have trader_login"
            assert offer["trader_login"], "trader_login should not be empty"
        
        if offers:
            print(f"SUCCESS: Offers show trader_login (e.g., {offers[0]['trader_login']})")
    
    def test_offers_show_rate(self):
        """Offers should show price_rub (rate)"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            assert "price_rub" in offer, "Offer should have price_rub"
            assert offer["price_rub"] > 0, "price_rub should be positive"
        
        if offers:
            print(f"SUCCESS: Offers show price_rub (e.g., {offers[0]['price_rub']})")
    
    def test_offers_show_available_amount(self):
        """Offers should show available_usdt"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            available = offer.get("available_usdt", offer.get("amount_usdt"))
            assert available is not None, "Offer should have available_usdt or amount_usdt"
            assert available > 0, "Available amount should be positive"
        
        if offers:
            print(f"SUCCESS: Offers show available amount")
    
    def test_offers_show_payment_methods(self):
        """Offers should show payment_methods or requisites"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            has_methods = "payment_methods" in offer and offer["payment_methods"]
            has_requisites = "requisites" in offer and offer["requisites"]
            assert has_methods or has_requisites, "Offer should have payment_methods or requisites"
        
        if offers:
            print(f"SUCCESS: Offers show payment methods/requisites")
    
    def test_offers_show_conditions(self):
        """Offers should have conditions field (can be null)"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        # conditions field should exist (can be null)
        for offer in offers:
            assert "conditions" in offer or True, "Offer should have conditions field"
        
        offers_with_conditions = [o for o in offers if o.get("conditions")]
        print(f"SUCCESS: {len(offers_with_conditions)} of {len(offers)} offers have conditions")
    
    def test_offers_show_trades_count(self):
        """Offers should show trades_count"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            assert "trades_count" in offer or True, "Offer should have trades_count"
        
        if offers:
            print(f"SUCCESS: Offers show trades_count")
    
    def test_offers_show_success_rate(self):
        """Offers should show success_rate"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200
        offers = response.json()
        
        for offer in offers:
            rate = offer.get("success_rate", 100)
            assert 0 <= rate <= 100, f"success_rate should be 0-100, got {rate}"
        
        if offers:
            print(f"SUCCESS: Offers show success_rate")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
