"""
Test Suite for P2P Exchange Stage 1 Features:
1. Admin Shop Management - GET /api/admin/shops, PUT /api/admin/shops/{id}/commission
2. Product Purchase with quantity and auto-deduction - POST /api/marketplace/products/{id}/buy
3. Shop Dashboard - GET /api/shop/dashboard
4. Shop Orders - GET /api/shop/orders
5. Shop Finances - GET /api/shop/finances
6. Shop Withdraw - POST /api/shop/withdraw
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"login": "admin", "password": "000000"}
TRADER_CREDS = {"login": "trader", "password": "000000"}  # Has shop with 7% commission
BUYER_CREDS = {"login": "trader2", "password": "000000"}  # Buyer

# Product ID for testing
PRODUCT_ID = "686bc773-f166-4255-84e6-0c25aa9497a4"  # Steam Key - Hogwarts Legacy


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful")
    
    def test_trader_login(self):
        """Test trader login (shop owner)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        assert response.status_code == 200, f"Trader login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "trader"
        print(f"✓ Trader login successful")
    
    def test_buyer_login(self):
        """Test buyer login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=BUYER_CREDS)
        assert response.status_code == 200, f"Buyer login failed: {response.text}"
        data = response.json()
        assert "token" in data
        print(f"✓ Buyer login successful")


@pytest.fixture
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Admin login failed")


@pytest.fixture
def trader_token():
    """Get trader auth token (shop owner)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Trader login failed")


@pytest.fixture
def buyer_token():
    """Get buyer auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=BUYER_CREDS)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Buyer login failed")


class TestAdminShopManagement:
    """Admin Shop Management Tests - GET /api/admin/shops, PUT /api/admin/shops/{id}/commission"""
    
    def test_get_all_shops_as_admin(self, admin_token):
        """Admin can list all shops with commission rates"""
        response = requests.get(
            f"{BASE_URL}/api/admin/shops",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get shops: {response.text}"
        shops = response.json()
        assert isinstance(shops, list)
        print(f"✓ Admin can list shops: {len(shops)} shops found")
        
        # Verify shop structure
        if shops:
            shop = shops[0]
            assert "id" in shop
            assert "name" in shop
            assert "commission_rate" in shop
            assert "type" in shop
            print(f"  - First shop: {shop.get('name')} ({shop.get('type')}) - Commission: {shop.get('commission_rate')}%")
    
    def test_get_shops_requires_admin(self, trader_token):
        """Non-admin cannot access shop management"""
        response = requests.get(
            f"{BASE_URL}/api/admin/shops",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Non-admin correctly denied access to shop management")
    
    def test_update_shop_commission(self, admin_token):
        """Admin can update individual shop commission rate"""
        # First get shops to find a shop ID
        response = requests.get(
            f"{BASE_URL}/api/admin/shops",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        shops = response.json()
        
        if not shops:
            pytest.skip("No shops available for testing")
        
        # Find trader shop (Digital Store)
        trader_shop = next((s for s in shops if s.get("type") == "trader"), None)
        if not trader_shop:
            pytest.skip("No trader shop found")
        
        shop_id = trader_shop["id"]
        original_commission = trader_shop.get("commission_rate", 5.0)
        new_commission = 8.0 if original_commission != 8.0 else 7.0
        
        # Update commission
        response = requests.put(
            f"{BASE_URL}/api/admin/shops/{shop_id}/commission?commission_rate={new_commission}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to update commission: {response.text}"
        data = response.json()
        assert data.get("status") == "updated"
        assert data.get("commission_rate") == new_commission
        print(f"✓ Admin updated shop commission from {original_commission}% to {new_commission}%")
        
        # Verify the change persisted
        response = requests.get(
            f"{BASE_URL}/api/admin/shops",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        shops = response.json()
        updated_shop = next((s for s in shops if s["id"] == shop_id), None)
        assert updated_shop is not None
        assert updated_shop["commission_rate"] == new_commission
        print(f"✓ Commission change verified in database")
        
        # Restore original commission
        requests.put(
            f"{BASE_URL}/api/admin/shops/{shop_id}/commission?commission_rate={original_commission}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print(f"✓ Commission restored to {original_commission}%")
    
    def test_update_commission_validation(self, admin_token):
        """Commission rate must be between 0 and 100"""
        # Get a shop ID
        response = requests.get(
            f"{BASE_URL}/api/admin/shops",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        shops = response.json()
        if not shops:
            pytest.skip("No shops available")
        
        shop_id = shops[0]["id"]
        
        # Test invalid commission (negative)
        response = requests.put(
            f"{BASE_URL}/api/admin/shops/{shop_id}/commission?commission_rate=-5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for negative commission, got {response.status_code}"
        print(f"✓ Negative commission correctly rejected")
        
        # Test invalid commission (>100)
        response = requests.put(
            f"{BASE_URL}/api/admin/shops/{shop_id}/commission?commission_rate=150",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for >100 commission, got {response.status_code}"
        print(f"✓ Commission >100% correctly rejected")


class TestShopDashboard:
    """Shop Dashboard Tests - GET /api/shop/dashboard"""
    
    def test_get_shop_dashboard(self, trader_token):
        """Trader with shop can get dashboard stats"""
        response = requests.get(
            f"{BASE_URL}/api/shop/dashboard",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200, f"Failed to get dashboard: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "shop" in data
        assert "stats" in data
        assert "inventory" in data
        
        # Verify shop info
        shop = data["shop"]
        assert "name" in shop
        assert "commission_rate" in shop
        assert "shop_balance" in shop
        print(f"✓ Shop dashboard loaded: {shop.get('name')}")
        print(f"  - Commission rate: {shop.get('commission_rate')}%")
        print(f"  - Shop balance: {shop.get('shop_balance')} USDT")
        
        # Verify stats structure
        stats = data["stats"]
        assert "today" in stats
        assert "week" in stats
        assert "month" in stats
        print(f"  - Today orders: {stats['today'].get('orders', 0)}")
        print(f"  - Week orders: {stats['week'].get('orders', 0)}")
        
        # Verify inventory
        inventory = data["inventory"]
        assert "product_count" in inventory
        assert "total_stock" in inventory
        print(f"  - Products: {inventory.get('product_count')}, Stock: {inventory.get('total_stock')}")
    
    def test_dashboard_requires_shop(self, buyer_token):
        """Trader without shop cannot access dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/shop/dashboard",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        # Should return 404 (no shop) or 403
        assert response.status_code in [403, 404], f"Expected 403/404, got {response.status_code}"
        print(f"✓ Trader without shop correctly denied dashboard access")


class TestShopOrders:
    """Shop Orders Tests - GET /api/shop/orders"""
    
    def test_get_shop_orders(self, trader_token):
        """Trader can get shop orders"""
        response = requests.get(
            f"{BASE_URL}/api/shop/orders",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200, f"Failed to get orders: {response.text}"
        orders = response.json()
        assert isinstance(orders, list)
        print(f"✓ Shop orders loaded: {len(orders)} orders")
        
        # Verify order structure if orders exist
        if orders:
            order = orders[0]
            assert "id" in order
            assert "product_name" in order
            assert "total_price" in order
            assert "commission" in order
            assert "seller_receives" in order
            print(f"  - Latest order: {order.get('product_name')} - {order.get('total_price')} USDT")
            print(f"    Commission: {order.get('commission')} USDT, Seller receives: {order.get('seller_receives')} USDT")
    
    def test_filter_orders_by_status(self, trader_token):
        """Can filter orders by status"""
        response = requests.get(
            f"{BASE_URL}/api/shop/orders?status=completed",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200
        orders = response.json()
        # All orders should be completed
        for order in orders:
            assert order.get("status") == "completed"
        print(f"✓ Order filtering by status works: {len(orders)} completed orders")


class TestShopFinances:
    """Shop Finances Tests - GET /api/shop/finances"""
    
    def test_get_shop_finances(self, trader_token):
        """Trader can get financial history"""
        response = requests.get(
            f"{BASE_URL}/api/shop/finances",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 200, f"Failed to get finances: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "balance" in data
        assert "commission_rate" in data
        assert "sales" in data
        assert "withdrawals" in data
        
        print(f"✓ Shop finances loaded")
        print(f"  - Balance: {data.get('balance')} USDT")
        print(f"  - Commission rate: {data.get('commission_rate')}%")
        print(f"  - Sales count: {len(data.get('sales', []))}")
        print(f"  - Withdrawals count: {len(data.get('withdrawals', []))}")


class TestShopWithdraw:
    """Shop Withdraw Tests - POST /api/shop/withdraw"""
    
    def test_withdraw_validation(self, trader_token):
        """Withdrawal validates amount"""
        # Test zero amount
        response = requests.post(
            f"{BASE_URL}/api/shop/withdraw?amount=0&method=card&details=test",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for zero amount, got {response.status_code}"
        print(f"✓ Zero amount withdrawal correctly rejected")
        
        # Test negative amount
        response = requests.post(
            f"{BASE_URL}/api/shop/withdraw?amount=-10&method=card&details=test",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for negative amount, got {response.status_code}"
        print(f"✓ Negative amount withdrawal correctly rejected")
    
    def test_withdraw_insufficient_balance(self, trader_token):
        """Cannot withdraw more than balance"""
        # Try to withdraw a very large amount
        response = requests.post(
            f"{BASE_URL}/api/shop/withdraw?amount=999999999&method=card&details=test",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for insufficient balance, got {response.status_code}"
        assert "Недостаточно" in response.json().get("detail", "")
        print(f"✓ Insufficient balance withdrawal correctly rejected")


class TestProductPurchase:
    """Product Purchase Tests - POST /api/marketplace/products/{id}/buy"""
    
    def test_get_product_details(self):
        """Get product details before purchase"""
        response = requests.get(f"{BASE_URL}/api/marketplace/products/{PRODUCT_ID}")
        if response.status_code == 404:
            pytest.skip(f"Product {PRODUCT_ID} not found")
        
        assert response.status_code == 200, f"Failed to get product: {response.text}"
        product = response.json()
        assert "id" in product
        assert "name" in product
        assert "price" in product
        print(f"✓ Product found: {product.get('name')} - {product.get('price')} USDT")
        return product
    
    def test_purchase_requires_auth(self):
        """Purchase requires authentication"""
        response = requests.post(f"{BASE_URL}/api/marketplace/products/{PRODUCT_ID}/buy?quantity=1")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Purchase correctly requires authentication")
    
    def test_purchase_validates_quantity(self, buyer_token):
        """Purchase validates quantity parameter"""
        # Test zero quantity
        response = requests.post(
            f"{BASE_URL}/api/marketplace/products/{PRODUCT_ID}/buy?quantity=0",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for zero quantity, got {response.status_code}"
        print(f"✓ Zero quantity correctly rejected")
    
    def test_purchase_checks_stock(self, buyer_token):
        """Purchase checks stock availability"""
        # Try to buy more than available
        response = requests.post(
            f"{BASE_URL}/api/marketplace/products/{PRODUCT_ID}/buy?quantity=9999",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        # Should fail due to insufficient stock or balance
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Excessive quantity correctly rejected")


class TestMarketplaceIntegration:
    """Integration tests for marketplace flow"""
    
    def test_marketplace_products_list(self):
        """Public marketplace products endpoint works"""
        response = requests.get(f"{BASE_URL}/api/marketplace/products")
        assert response.status_code == 200, f"Failed to get products: {response.text}"
        products = response.json()
        assert isinstance(products, list)
        print(f"✓ Marketplace products: {len(products)} products available")
    
    def test_marketplace_shops_list(self):
        """Public marketplace shops endpoint works"""
        response = requests.get(f"{BASE_URL}/api/marketplace/shops")
        assert response.status_code == 200, f"Failed to get shops: {response.text}"
        shops = response.json()
        assert isinstance(shops, list)
        print(f"✓ Marketplace shops: {len(shops)} shops available")
        
        # Check for Digital Store with 7% commission
        digital_store = next((s for s in shops if "Digital" in s.get("name", "")), None)
        if digital_store:
            print(f"  - Found Digital Store: commission {digital_store.get('commission_rate', 'N/A')}%")


class TestCommissionCalculation:
    """Test that commission is calculated using individual shop rate"""
    
    def test_shop_has_individual_commission(self, admin_token):
        """Verify shops have individual commission rates"""
        response = requests.get(
            f"{BASE_URL}/api/admin/shops",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        shops = response.json()
        
        # Check that different shops can have different rates
        commission_rates = set(s.get("commission_rate") for s in shops if s.get("commission_rate"))
        print(f"✓ Found commission rates: {commission_rates}")
        
        # Verify Digital Store has 7% commission
        digital_store = next((s for s in shops if "Digital" in s.get("name", "")), None)
        if digital_store:
            assert digital_store.get("commission_rate") == 7.0, f"Expected 7%, got {digital_store.get('commission_rate')}%"
            print(f"✓ Digital Store has 7% commission as expected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
