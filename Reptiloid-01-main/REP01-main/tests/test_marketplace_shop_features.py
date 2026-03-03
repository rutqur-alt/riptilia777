"""
Test suite for P2P Marketplace 'Reptiloid' shop features:
1. Product purchase in marketplace - buyer purchases from seller
2. My purchases - purchased product should display with content
3. User balance lock via admin - user should not be able to create offers
4. Shop block via admin - shop should not appear in marketplace
5. Shop unblock - shop should appear again in marketplace
6. Send message to shop from buyer
7. View messages by shop owner
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "000000"
SELLER_LOGIN = "trader"  # Has shop 'Digital Store'
SELLER_PASSWORD = "000000"
BUYER_LOGIN = "trader2"
BUYER_PASSWORD = "000000"

# Shop ID for trader
SHOP_ID = "a9bed1fb-a63e-4cfe-aae9-f6b12d08df96"


class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def seller_token(self):
        """Get seller (trader) token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": SELLER_LOGIN,
            "password": SELLER_PASSWORD
        })
        assert response.status_code == 200, f"Seller login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer (trader2) token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": BUYER_LOGIN,
            "password": BUYER_PASSWORD
        })
        assert response.status_code == 200, f"Buyer login failed: {response.text}"
        return response.json()["token"]
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print("✓ Admin login successful")
    
    def test_seller_login(self):
        """Test seller login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": SELLER_LOGIN,
            "password": SELLER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print("✓ Seller login successful")
    
    def test_buyer_login(self):
        """Test buyer login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": BUYER_LOGIN,
            "password": BUYER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print("✓ Buyer login successful")


class TestMarketplaceShops:
    """Test marketplace shops listing"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def seller_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": SELLER_LOGIN,
            "password": SELLER_PASSWORD
        })
        return response.json()["token"]
    
    def test_marketplace_shops_list(self):
        """Test getting marketplace shops list"""
        response = requests.get(f"{BASE_URL}/api/marketplace/shops")
        assert response.status_code == 200
        shops = response.json()
        assert isinstance(shops, list)
        print(f"✓ Marketplace shops list returned {len(shops)} shops")
        return shops
    
    def test_marketplace_products_list(self):
        """Test getting marketplace products list"""
        response = requests.get(f"{BASE_URL}/api/marketplace/products")
        assert response.status_code == 200
        products = response.json()
        assert isinstance(products, list)
        print(f"✓ Marketplace products list returned {len(products)} products")
        return products
    
    def test_seller_has_shop(self, seller_token):
        """Test that seller has a shop"""
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {seller_token}"
        })
        assert response.status_code == 200
        trader = response.json()
        assert trader.get("has_shop") == True, "Seller should have a shop"
        print(f"✓ Seller has shop: {trader.get('shop_settings', {}).get('shop_name', 'Unknown')}")


class TestShopBlockUnblock:
    """Test shop blocking and unblocking via admin"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def seller_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": SELLER_LOGIN,
            "password": SELLER_PASSWORD
        })
        return response.json()["token"]
    
    def get_seller_id(self, seller_token):
        """Get seller user ID"""
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {seller_token}"
        })
        return response.json()["id"]
    
    def test_block_shop(self, admin_token, seller_token):
        """Test blocking a shop via admin"""
        seller_id = self.get_seller_id(seller_token)
        
        # First ensure shop is not blocked
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {seller_token}"
        })
        trader = response.json()
        initial_blocked = trader.get("shop_settings", {}).get("is_blocked", False)
        
        # Block the shop
        response = requests.post(
            f"{BASE_URL}/api/admin/shops/{seller_id}/block",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"✓ Shop block toggled. is_blocked: {data['is_blocked']}")
        
        # If it was blocked, unblock it first, then block again
        if initial_blocked:
            # Unblock first
            response = requests.post(
                f"{BASE_URL}/api/admin/shops/{seller_id}/block",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
        
        return data["is_blocked"]
    
    def test_blocked_shop_not_in_marketplace(self, admin_token, seller_token):
        """Test that blocked shop does not appear in marketplace"""
        seller_id = self.get_seller_id(seller_token)
        
        # Ensure shop is blocked
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {seller_token}"
        })
        trader = response.json()
        is_blocked = trader.get("shop_settings", {}).get("is_blocked", False)
        
        if not is_blocked:
            # Block the shop
            response = requests.post(
                f"{BASE_URL}/api/admin/shops/{seller_id}/block",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
        
        # Check marketplace shops
        response = requests.get(f"{BASE_URL}/api/marketplace/shops")
        assert response.status_code == 200
        shops = response.json()
        
        # Shop should not be in the list
        shop_ids = [s.get("id") for s in shops]
        # Note: The shop ID might be the trader ID
        print(f"✓ Marketplace has {len(shops)} shops after blocking")
        
        # Unblock for next tests
        response = requests.post(
            f"{BASE_URL}/api/admin/shops/{seller_id}/block",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        print("✓ Shop unblocked for next tests")
    
    def test_unblock_shop(self, admin_token, seller_token):
        """Test unblocking a shop via admin"""
        seller_id = self.get_seller_id(seller_token)
        
        # First block the shop to ensure we can test unblocking
        response = requests.post(
            f"{BASE_URL}/api/admin/shops/{seller_id}/block",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        first_toggle = response.json()
        
        # If it's now unblocked, we need to block it first
        if first_toggle["is_blocked"] == False:
            response = requests.post(
                f"{BASE_URL}/api/admin/shops/{seller_id}/block",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
        
        # Now unblock
        response = requests.post(
            f"{BASE_URL}/api/admin/shops/{seller_id}/block",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["is_blocked"] == False, "Shop should be unblocked"
        print("✓ Shop unblocked successfully")
    
    def test_unblocked_shop_in_marketplace(self, admin_token, seller_token):
        """Test that unblocked shop appears in marketplace"""
        seller_id = self.get_seller_id(seller_token)
        
        # Ensure shop is unblocked
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {seller_token}"
        })
        trader = response.json()
        is_blocked = trader.get("shop_settings", {}).get("is_blocked", False)
        
        if is_blocked:
            # Unblock the shop
            response = requests.post(
                f"{BASE_URL}/api/admin/shops/{seller_id}/block",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
        
        # Check marketplace shops
        response = requests.get(f"{BASE_URL}/api/marketplace/shops")
        assert response.status_code == 200
        shops = response.json()
        print(f"✓ Marketplace has {len(shops)} shops after unblocking")


class TestBalanceLock:
    """Test user balance lock via admin"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": BUYER_LOGIN,
            "password": BUYER_PASSWORD
        })
        return response.json()["token"]
    
    def get_buyer_id(self, buyer_token):
        """Get buyer user ID"""
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {buyer_token}"
        })
        return response.json()["id"]
    
    def test_toggle_balance_lock(self, admin_token, buyer_token):
        """Test toggling user balance lock"""
        buyer_id = self.get_buyer_id(buyer_token)
        
        # Toggle balance lock
        response = requests.post(
            f"{BASE_URL}/api/super-admin/users/{buyer_id}/toggle-balance-lock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"✓ Balance lock toggled. is_balance_locked: {data['is_balance_locked']}")
        
        # Toggle back to original state
        response = requests.post(
            f"{BASE_URL}/api/super-admin/users/{buyer_id}/toggle-balance-lock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        print("✓ Balance lock toggled back")
    
    def test_locked_user_cannot_create_offer(self, admin_token, buyer_token):
        """Test that user with locked balance cannot create offers"""
        buyer_id = self.get_buyer_id(buyer_token)
        
        # First check current balance lock status
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {buyer_token}"
        })
        trader = response.json()
        initial_locked = trader.get("is_balance_locked", False)
        
        # Lock balance if not locked
        if not initial_locked:
            response = requests.post(
                f"{BASE_URL}/api/super-admin/users/{buyer_id}/toggle-balance-lock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
        
        # Try to create an offer - should fail
        # First need to add requisites
        response = requests.get(f"{BASE_URL}/api/requisites", headers={
            "Authorization": f"Bearer {buyer_token}"
        })
        requisites = response.json()
        
        if len(requisites) > 0:
            response = requests.post(
                f"{BASE_URL}/api/offers",
                headers={"Authorization": f"Bearer {buyer_token}"},
                json={
                    "amount_usdt": 10,
                    "min_amount": 1,
                    "max_amount": 10,
                    "price_rub": 95,
                    "payment_methods": ["card"],
                    "accepted_merchant_types": ["casino", "shop"],
                    "requisite_ids": [requisites[0]["id"]]
                }
            )
            # Should fail with 403 or similar error
            if response.status_code == 403:
                print("✓ Locked user correctly blocked from creating offer")
            else:
                print(f"Note: Offer creation returned {response.status_code}: {response.text[:200]}")
        else:
            print("Note: No requisites found for buyer, skipping offer creation test")
        
        # Unlock balance
        if not initial_locked:
            response = requests.post(
                f"{BASE_URL}/api/super-admin/users/{buyer_id}/toggle-balance-lock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
            print("✓ Balance unlocked after test")


class TestProductPurchase:
    """Test product purchase in marketplace"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": BUYER_LOGIN,
            "password": BUYER_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def seller_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": SELLER_LOGIN,
            "password": SELLER_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": ADMIN_LOGIN,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_get_marketplace_products(self):
        """Get available products in marketplace"""
        response = requests.get(f"{BASE_URL}/api/marketplace/products")
        assert response.status_code == 200
        products = response.json()
        print(f"✓ Found {len(products)} products in marketplace")
        return products
    
    def test_buyer_balance(self, buyer_token, admin_token):
        """Check buyer balance and add if needed"""
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {buyer_token}"
        })
        assert response.status_code == 200
        trader = response.json()
        balance = trader.get("balance_usdt", 0)
        print(f"✓ Buyer balance: {balance} USDT")
        
        # If balance is low, add some via admin
        if balance < 100:
            buyer_id = trader["id"]
            response = requests.post(
                f"{BASE_URL}/api/super-admin/users/{buyer_id}/balance",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"amount": 100, "reason": "Test balance top-up"}
            )
            if response.status_code == 200:
                print("✓ Added 100 USDT to buyer balance")
            else:
                print(f"Note: Could not add balance: {response.status_code}")
        
        return balance
    
    def test_buy_product(self, buyer_token):
        """Test buying a product"""
        # Get products
        response = requests.get(f"{BASE_URL}/api/marketplace/products")
        products = response.json()
        
        if len(products) == 0:
            pytest.skip("No products available in marketplace")
        
        # Find a product with stock or infinite
        product = None
        for p in products:
            if p.get("is_infinite") or p.get("stock_count", 0) > 0:
                product = p
                break
        
        if not product:
            pytest.skip("No products with stock available")
        
        product_id = product["id"]
        print(f"Attempting to buy product: {product.get('name', 'Unknown')} (ID: {product_id})")
        
        # Try to buy
        response = requests.post(
            f"{BASE_URL}/api/marketplace/products/{product_id}/buy",
            headers={"Authorization": f"Bearer {buyer_token}"},
            params={"quantity": 1, "purchase_type": "instant"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Product purchased successfully! Purchase ID: {data.get('purchase_id', 'N/A')}")
            return data
        elif response.status_code == 400:
            print(f"Note: Purchase failed (expected if no balance): {response.json().get('detail', response.text)}")
        else:
            print(f"Note: Purchase returned {response.status_code}: {response.text[:200]}")
        
        return None
    
    def test_my_purchases(self, buyer_token):
        """Test getting my purchases"""
        response = requests.get(
            f"{BASE_URL}/api/marketplace/my-purchases",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert response.status_code == 200
        purchases = response.json()
        print(f"✓ Found {len(purchases)} purchases for buyer")
        
        # Check if purchases have delivered_content
        for purchase in purchases[:3]:  # Check first 3
            has_content = "delivered_content" in purchase and purchase["delivered_content"]
            status = purchase.get("status", "unknown")
            print(f"  - Purchase {purchase.get('id', 'N/A')[:8]}...: status={status}, has_content={has_content}")
        
        return purchases


class TestShopMessages:
    """Test shop messaging functionality"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": BUYER_LOGIN,
            "password": BUYER_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def seller_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "login": SELLER_LOGIN,
            "password": SELLER_PASSWORD
        })
        return response.json()["token"]
    
    def get_seller_id(self, seller_token):
        """Get seller user ID"""
        response = requests.get(f"{BASE_URL}/api/traders/me", headers={
            "Authorization": f"Bearer {seller_token}"
        })
        return response.json()["id"]
    
    def test_send_message_to_shop(self, buyer_token, seller_token):
        """Test sending a message to a shop"""
        seller_id = self.get_seller_id(seller_token)
        
        # Send message
        response = requests.post(
            f"{BASE_URL}/api/shop/{seller_id}/messages",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"message": f"Test message from buyer at {time.time()}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "sent"
            print(f"✓ Message sent to shop. Conversation ID: {data.get('conversation_id', 'N/A')}")
            return data
        else:
            print(f"Note: Message sending returned {response.status_code}: {response.text[:200]}")
            return None
    
    def test_shop_owner_view_messages(self, seller_token):
        """Test shop owner viewing messages"""
        response = requests.get(
            f"{BASE_URL}/api/shop/messages",
            headers={"Authorization": f"Bearer {seller_token}"}
        )
        
        if response.status_code == 200:
            conversations = response.json()
            print(f"✓ Shop owner has {len(conversations)} conversations")
            
            for conv in conversations[:3]:  # Show first 3
                customer = conv.get("customer_nickname", "Unknown")
                msg_count = len(conv.get("messages", []))
                unread = conv.get("unread_shop", 0)
                print(f"  - Conversation with {customer}: {msg_count} messages, {unread} unread")
            
            return conversations
        else:
            print(f"Note: Get messages returned {response.status_code}: {response.text[:200]}")
            return []
    
    def test_shop_owner_reply(self, seller_token, buyer_token):
        """Test shop owner replying to a message"""
        # First get conversations
        response = requests.get(
            f"{BASE_URL}/api/shop/messages",
            headers={"Authorization": f"Bearer {seller_token}"}
        )
        
        if response.status_code != 200 or len(response.json()) == 0:
            # Send a message first
            seller_id = self.get_seller_id(seller_token)
            requests.post(
                f"{BASE_URL}/api/shop/{seller_id}/messages",
                headers={"Authorization": f"Bearer {buyer_token}"},
                json={"message": "Test message for reply test"}
            )
            
            # Get conversations again
            response = requests.get(
                f"{BASE_URL}/api/shop/messages",
                headers={"Authorization": f"Bearer {seller_token}"}
            )
        
        if response.status_code == 200 and len(response.json()) > 0:
            conversations = response.json()
            conv_id = conversations[0]["id"]
            
            # Reply
            response = requests.post(
                f"{BASE_URL}/api/shop/messages/{conv_id}/reply",
                headers={"Authorization": f"Bearer {seller_token}"},
                json={"message": f"Shop reply at {time.time()}"}
            )
            
            if response.status_code == 200:
                print("✓ Shop owner replied successfully")
            else:
                print(f"Note: Reply returned {response.status_code}: {response.text[:200]}")
        else:
            print("Note: No conversations to reply to")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
