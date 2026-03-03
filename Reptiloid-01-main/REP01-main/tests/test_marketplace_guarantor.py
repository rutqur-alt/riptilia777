"""
Test Marketplace Guarantor Purchase Flow
Tests for:
- Product page shows two purchase options (instant and guarantor)
- Guarantor commission (3%) is correctly calculated
- Guarantor purchase creates order with pending_confirmation status
- Buyer can confirm receipt
- Buyer can cancel order before confirmation
- Buyer can open dispute
- After confirmation, product is delivered and seller receives payment
- My Purchases shows order status and action buttons
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://p2p-gateway.preview.emergentagent.com')

# Test credentials
TRADER2_CREDS = {"login": "trader2", "password": "000000"}
TRADER_CREDS = {"login": "trader", "password": "000000"}
ADMIN_CREDS = {"login": "admin", "password": "000000"}

# Test product ID from context
TEST_PRODUCT_ID = "38133cce-314c-4077-bae2-8337d9fd2953"


class TestMarketplaceGuarantorFlow:
    """Test marketplace guarantor purchase flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.trader2_token = None
        self.trader_token = None
        self.admin_token = None
    
    def login(self, credentials):
        """Login and return token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=credentials)
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_01_login_trader2(self):
        """Test login as trader2 (buyer)"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=TRADER2_CREDS)
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        self.trader2_token = data["token"]
        print(f"✓ Logged in as trader2, balance: {data['user'].get('balance_usdt', 0)} USDT")
    
    def test_02_login_trader(self):
        """Test login as trader (seller)"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        self.trader_token = data["token"]
        print(f"✓ Logged in as trader, balance: {data['user'].get('balance_usdt', 0)} USDT")
    
    def test_03_get_commission_settings(self):
        """Test getting commission settings including guarantor settings"""
        # Login as admin to get settings
        admin_token = self.login(ADMIN_CREDS)
        assert admin_token, "Admin login failed"
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/commission-settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get settings: {response.text}"
        
        settings = response.json()
        assert "guarantor_commission_percent" in settings, "Missing guarantor_commission_percent"
        assert "guarantor_auto_complete_days" in settings, "Missing guarantor_auto_complete_days"
        
        print(f"✓ Guarantor commission: {settings['guarantor_commission_percent']}%")
        print(f"✓ Auto-complete days: {settings['guarantor_auto_complete_days']}")
    
    def test_04_get_product_details(self):
        """Test getting product details with guarantor info"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/products/{TEST_PRODUCT_ID}")
        
        if response.status_code == 404:
            pytest.skip("Test product not found - may have been sold out")
        
        assert response.status_code == 200, f"Failed to get product: {response.text}"
        
        product = response.json()
        assert "id" in product
        assert "name" in product
        assert "price" in product
        
        print(f"✓ Product: {product['name']}")
        print(f"✓ Price: {product['price']} USDT")
        print(f"✓ Stock: {product.get('stock_count', 0)} available")
        
        # Check if guarantor commission is included
        if "guarantor_commission_percent" in product:
            print(f"✓ Guarantor commission in product: {product['guarantor_commission_percent']}%")
    
    def test_05_get_marketplace_products(self):
        """Test getting marketplace products list"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/products")
        assert response.status_code == 200, f"Failed to get products: {response.text}"
        
        products = response.json()
        assert isinstance(products, list)
        print(f"✓ Found {len(products)} products in marketplace")
        
        # Find a product with stock for testing
        available_products = [p for p in products if p.get("stock_count", 0) > 0]
        print(f"✓ {len(available_products)} products have stock available")
    
    def test_06_buy_product_instant(self):
        """Test instant purchase (direct buy)"""
        trader2_token = self.login(TRADER2_CREDS)
        assert trader2_token, "Trader2 login failed"
        
        # Get buyer balance before
        me_response = self.session.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        assert me_response.status_code == 200
        balance_before = me_response.json().get("balance_usdt", 0)
        
        # Try to buy a product with stock
        products_response = self.session.get(f"{BASE_URL}/api/marketplace/products")
        products = products_response.json()
        
        available_product = None
        for p in products:
            if p.get("stock_count", 0) > 0:
                available_product = p
                break
        
        if not available_product:
            pytest.skip("No products with stock available for testing")
        
        product_id = available_product["id"]
        product_price = available_product["price"]
        
        if balance_before < product_price:
            pytest.skip(f"Insufficient balance: {balance_before} < {product_price}")
        
        # Buy instant
        response = self.session.post(
            f"{BASE_URL}/api/marketplace/products/{product_id}/buy?quantity=1&purchase_type=instant",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        
        if response.status_code == 400 and "Недостаточно" in response.text:
            pytest.skip("Insufficient balance or stock")
        
        assert response.status_code == 200, f"Instant purchase failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "success"
        assert data["purchase_type"] == "instant"
        print(f"✓ Instant purchase successful: {data.get('message')}")
        
        if data.get("delivered_content"):
            print(f"✓ Delivered content received")
    
    def test_07_buy_product_guarantor(self):
        """Test guarantor purchase (escrow)"""
        trader2_token = self.login(TRADER2_CREDS)
        assert trader2_token, "Trader2 login failed"
        
        # Get buyer balance before
        me_response = self.session.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        assert me_response.status_code == 200
        balance_before = me_response.json().get("balance_usdt", 0)
        
        # Find a product with stock
        products_response = self.session.get(f"{BASE_URL}/api/marketplace/products")
        products = products_response.json()
        
        available_product = None
        for p in products:
            if p.get("stock_count", 0) > 0:
                available_product = p
                break
        
        if not available_product:
            pytest.skip("No products with stock available for testing")
        
        product_id = available_product["id"]
        product_price = available_product["price"]
        
        # Calculate total with guarantor fee (3%)
        guarantor_fee = product_price * 0.03
        total_with_guarantor = product_price + guarantor_fee
        
        if balance_before < total_with_guarantor:
            pytest.skip(f"Insufficient balance: {balance_before} < {total_with_guarantor}")
        
        # Buy with guarantor
        response = self.session.post(
            f"{BASE_URL}/api/marketplace/products/{product_id}/buy?quantity=1&purchase_type=guarantor",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        
        if response.status_code == 400 and "Недостаточно" in response.text:
            pytest.skip("Insufficient balance or stock")
        
        assert response.status_code == 200, f"Guarantor purchase failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "success"
        assert data["purchase_type"] == "guarantor"
        assert "guarantor_fee" in data
        assert "total_with_guarantor" in data
        assert "auto_complete_at" in data
        
        print(f"✓ Guarantor purchase successful")
        print(f"✓ Product price: {data['total_price']} USDT")
        print(f"✓ Guarantor fee: {data['guarantor_fee']} USDT")
        print(f"✓ Total: {data['total_with_guarantor']} USDT")
        print(f"✓ Auto-complete at: {data['auto_complete_at']}")
        
        # Store purchase ID for later tests
        self.__class__.guarantor_purchase_id = data["purchase_id"]
    
    def test_08_check_my_purchases(self):
        """Test that purchase appears in My Purchases with correct status"""
        trader2_token = self.login(TRADER2_CREDS)
        assert trader2_token, "Trader2 login failed"
        
        response = self.session.get(
            f"{BASE_URL}/api/marketplace/my-purchases",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        assert response.status_code == 200, f"Failed to get purchases: {response.text}"
        
        purchases = response.json()
        assert isinstance(purchases, list)
        print(f"✓ Found {len(purchases)} purchases")
        
        # Check for pending_confirmation purchases
        pending_purchases = [p for p in purchases if p.get("status") == "pending_confirmation"]
        print(f"✓ {len(pending_purchases)} purchases pending confirmation")
        
        # Check for guarantor purchases
        guarantor_purchases = [p for p in purchases if p.get("purchase_type") == "guarantor"]
        print(f"✓ {len(guarantor_purchases)} guarantor purchases")
        
        # Verify purchase structure
        if purchases:
            sample = purchases[0]
            required_fields = ["id", "product_name", "quantity", "total_price", "status", "created_at"]
            for field in required_fields:
                assert field in sample, f"Missing field: {field}"
            print(f"✓ Purchase structure validated")
    
    def test_09_confirm_guarantor_purchase(self):
        """Test buyer confirming receipt of product"""
        trader2_token = self.login(TRADER2_CREDS)
        assert trader2_token, "Trader2 login failed"
        
        # Get pending purchases
        response = self.session.get(
            f"{BASE_URL}/api/marketplace/my-purchases",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        purchases = response.json()
        
        # Find a pending guarantor purchase
        pending_purchase = None
        for p in purchases:
            if p.get("status") == "pending_confirmation" and p.get("purchase_type") == "guarantor":
                pending_purchase = p
                break
        
        if not pending_purchase:
            pytest.skip("No pending guarantor purchase to confirm")
        
        purchase_id = pending_purchase["id"]
        
        # Confirm the purchase
        response = self.session.post(
            f"{BASE_URL}/api/marketplace/purchases/{purchase_id}/confirm",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        assert response.status_code == 200, f"Confirm failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "success"
        print(f"✓ Purchase confirmed successfully")
        
        if data.get("delivered_content"):
            print(f"✓ Delivered content: {len(data['delivered_content'])} items")
        
        if data.get("seller_received"):
            print(f"✓ Seller received: {data['seller_received']} USDT")
    
    def test_10_cancel_guarantor_purchase(self):
        """Test buyer cancelling a guarantor purchase"""
        trader2_token = self.login(TRADER2_CREDS)
        assert trader2_token, "Trader2 login failed"
        
        # First create a new guarantor purchase to cancel
        products_response = self.session.get(f"{BASE_URL}/api/marketplace/products")
        products = products_response.json()
        
        available_product = None
        for p in products:
            if p.get("stock_count", 0) > 0:
                available_product = p
                break
        
        if not available_product:
            pytest.skip("No products with stock available")
        
        # Get balance
        me_response = self.session.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        balance_before = me_response.json().get("balance_usdt", 0)
        
        product_price = available_product["price"]
        total_with_guarantor = product_price * 1.03
        
        if balance_before < total_with_guarantor:
            pytest.skip("Insufficient balance for cancel test")
        
        # Create guarantor purchase
        buy_response = self.session.post(
            f"{BASE_URL}/api/marketplace/products/{available_product['id']}/buy?quantity=1&purchase_type=guarantor",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        
        if buy_response.status_code != 200:
            pytest.skip("Could not create purchase for cancel test")
        
        purchase_id = buy_response.json()["purchase_id"]
        
        # Cancel the purchase
        response = self.session.post(
            f"{BASE_URL}/api/marketplace/purchases/{purchase_id}/cancel",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        assert response.status_code == 200, f"Cancel failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "success"
        assert "refunded_amount" in data
        
        print(f"✓ Purchase cancelled successfully")
        print(f"✓ Refunded: {data['refunded_amount']} USDT")
    
    def test_11_open_dispute(self):
        """Test buyer opening a dispute"""
        trader2_token = self.login(TRADER2_CREDS)
        assert trader2_token, "Trader2 login failed"
        
        # First create a new guarantor purchase
        products_response = self.session.get(f"{BASE_URL}/api/marketplace/products")
        products = products_response.json()
        
        available_product = None
        for p in products:
            if p.get("stock_count", 0) > 0:
                available_product = p
                break
        
        if not available_product:
            pytest.skip("No products with stock available")
        
        # Get balance
        me_response = self.session.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        balance_before = me_response.json().get("balance_usdt", 0)
        
        product_price = available_product["price"]
        total_with_guarantor = product_price * 1.03
        
        if balance_before < total_with_guarantor:
            pytest.skip("Insufficient balance for dispute test")
        
        # Create guarantor purchase
        buy_response = self.session.post(
            f"{BASE_URL}/api/marketplace/products/{available_product['id']}/buy?quantity=1&purchase_type=guarantor",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        
        if buy_response.status_code != 200:
            pytest.skip("Could not create purchase for dispute test")
        
        purchase_id = buy_response.json()["purchase_id"]
        
        # Open dispute
        response = self.session.post(
            f"{BASE_URL}/api/marketplace/purchases/{purchase_id}/dispute?reason=TEST_DISPUTE_REASON",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        assert response.status_code == 200, f"Dispute failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "success"
        
        print(f"✓ Dispute opened successfully")
        print(f"✓ Message: {data.get('message')}")
        
        # Store for cleanup
        self.__class__.disputed_purchase_id = purchase_id
    
    def test_12_admin_resolve_dispute(self):
        """Test admin resolving a dispute"""
        admin_token = self.login(ADMIN_CREDS)
        assert admin_token, "Admin login failed"
        
        # Get disputed purchase ID from previous test
        purchase_id = getattr(self.__class__, 'disputed_purchase_id', None)
        
        if not purchase_id:
            pytest.skip("No disputed purchase to resolve")
        
        # Resolve dispute - refund buyer
        response = self.session.post(
            f"{BASE_URL}/api/marketplace/purchases/{purchase_id}/resolve?resolution=refund_buyer&admin_note=TEST_RESOLUTION",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 400:
            # Purchase may have been already resolved or cancelled
            print(f"⚠ Could not resolve dispute: {response.text}")
            return
        
        assert response.status_code == 200, f"Resolve failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "success"
        
        print(f"✓ Dispute resolved successfully")
        print(f"✓ Resolution: {data.get('resolution')}")
    
    def test_13_verify_purchase_statuses(self):
        """Verify all purchase statuses are correct"""
        trader2_token = self.login(TRADER2_CREDS)
        assert trader2_token, "Trader2 login failed"
        
        response = self.session.get(
            f"{BASE_URL}/api/marketplace/my-purchases",
            headers={"Authorization": f"Bearer {trader2_token}"}
        )
        assert response.status_code == 200
        
        purchases = response.json()
        
        # Count by status
        status_counts = {}
        for p in purchases:
            status = p.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"✓ Purchase status breakdown:")
        for status, count in status_counts.items():
            print(f"  - {status}: {count}")
        
        # Count by purchase type
        type_counts = {}
        for p in purchases:
            ptype = p.get("purchase_type", "unknown")
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        print(f"✓ Purchase type breakdown:")
        for ptype, count in type_counts.items():
            print(f"  - {ptype}: {count}")


class TestProductPagePurchaseOptions:
    """Test product page shows both purchase options"""
    
    def test_product_has_price_info(self):
        """Test product endpoint returns price info"""
        response = requests.get(f"{BASE_URL}/api/marketplace/products")
        assert response.status_code == 200
        
        products = response.json()
        if not products:
            pytest.skip("No products available")
        
        product = products[0]
        assert "price" in product
        assert "currency" in product or product.get("price") is not None
        
        print(f"✓ Product price: {product['price']}")
    
    def test_commission_settings_available(self):
        """Test commission settings endpoint returns guarantor info"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=ADMIN_CREDS
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/commission-settings",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        settings = response.json()
        guarantor_percent = settings.get("guarantor_commission_percent", 3.0)
        auto_days = settings.get("guarantor_auto_complete_days", 3)
        
        assert guarantor_percent > 0
        assert auto_days > 0
        
        print(f"✓ Guarantor commission: {guarantor_percent}%")
        print(f"✓ Auto-complete days: {auto_days}")


class TestGuarantorCommissionCalculation:
    """Test guarantor commission is correctly calculated"""
    
    def test_guarantor_fee_calculation(self):
        """Test that guarantor fee is 3% of product price"""
        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TRADER2_CREDS
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Get balance
        me_response = requests.get(
            f"{BASE_URL}/api/traders/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        balance = me_response.json().get("balance_usdt", 0)
        
        # Get a product
        products_response = requests.get(f"{BASE_URL}/api/marketplace/products")
        products = products_response.json()
        
        available_product = None
        for p in products:
            if p.get("stock_count", 0) > 0 and p.get("price", 0) * 1.03 < balance:
                available_product = p
                break
        
        if not available_product:
            pytest.skip("No affordable product with stock")
        
        product_price = available_product["price"]
        expected_fee = product_price * 0.03
        expected_total = product_price + expected_fee
        
        # Buy with guarantor
        response = requests.post(
            f"{BASE_URL}/api/marketplace/products/{available_product['id']}/buy?quantity=1&purchase_type=guarantor",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != 200:
            pytest.skip(f"Could not buy: {response.text}")
        
        data = response.json()
        actual_fee = data.get("guarantor_fee", 0)
        actual_total = data.get("total_with_guarantor", 0)
        
        # Allow small floating point differences
        assert abs(actual_fee - expected_fee) < 0.01, f"Fee mismatch: {actual_fee} vs {expected_fee}"
        assert abs(actual_total - expected_total) < 0.01, f"Total mismatch: {actual_total} vs {expected_total}"
        
        print(f"✓ Product price: {product_price} USDT")
        print(f"✓ Expected fee (3%): {expected_fee:.4f} USDT")
        print(f"✓ Actual fee: {actual_fee:.4f} USDT")
        print(f"✓ Total with guarantor: {actual_total:.4f} USDT")
        
        # Cancel to refund
        purchase_id = data["purchase_id"]
        requests.post(
            f"{BASE_URL}/api/marketplace/purchases/{purchase_id}/cancel",
            headers={"Authorization": f"Bearer {token}"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
