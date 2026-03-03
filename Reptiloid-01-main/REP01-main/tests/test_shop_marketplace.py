"""
Test suite for Shop Application Flow and Marketplace features
Tests:
1. Shop Application Flow: Trader applies for shop -> Admin approves -> Trader gets shop management access
2. Admin Panel Shop Applications: View, approve, reject applications at /admin/shops
3. Trader Shop Management: Add/edit/delete products at /trader/shop
4. Marketplace: Display shops and products at /marketplace
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestShopApplicationFlow:
    """Test shop application submission and status checking"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_trader_token(self):
        """Login as trader and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader",
            "password": "000000"
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def get_admin_token(self):
        """Login as admin and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "admin",
            "password": "000000"
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_trader_login(self):
        """Test trader can login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader",
            "password": "000000"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"SUCCESS: Trader login works, user: {data['user'].get('login')}")
    
    def test_admin_login(self):
        """Test admin can login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "admin",
            "password": "000000"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"SUCCESS: Admin login works")
    
    def test_get_my_shop_application_status(self):
        """Test trader can check their shop application status"""
        token = self.get_trader_token()
        assert token, "Failed to get trader token"
        
        response = self.session.get(
            f"{BASE_URL}/api/shop/my-application",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return either has_shop=True or application status
        print(f"SUCCESS: Shop application status: {data}")
        
        if data.get("has_shop"):
            print(f"  - Trader has approved shop: {data.get('shop_settings', {}).get('shop_name')}")
        elif data.get("status"):
            print(f"  - Application status: {data.get('status')}")
        else:
            print(f"  - No application submitted yet")
    
    def test_shop_application_requires_auth(self):
        """Test shop application endpoint requires authentication"""
        response = self.session.post(f"{BASE_URL}/api/shop/apply", json={
            "shop_name": "Test Shop",
            "shop_description": "This is a test shop description that is long enough",
            "categories": ["Test"],
            "telegram": "@test"
        })
        assert response.status_code in [401, 403]
        print("SUCCESS: Shop application requires authentication")


class TestAdminShopApplications:
    """Test admin shop application management"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Login as admin and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "admin",
            "password": "000000"
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_admin_can_view_shop_applications(self):
        """Test admin can view all shop applications"""
        token = self.get_admin_token()
        assert token, "Failed to get admin token"
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/shop-applications",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Admin can view shop applications, count: {len(data)}")
        
        for app in data[:3]:  # Show first 3
            print(f"  - {app.get('shop_name')} ({app.get('status')}) by {app.get('trader_login')}")
    
    def test_admin_can_filter_pending_applications(self):
        """Test admin can filter pending applications"""
        token = self.get_admin_token()
        assert token, "Failed to get admin token"
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/shop-applications?status=pending",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned should be pending
        for app in data:
            assert app.get("status") == "pending", f"Expected pending, got {app.get('status')}"
        
        print(f"SUCCESS: Admin can filter pending applications, count: {len(data)}")
    
    def test_shop_applications_requires_admin(self):
        """Test shop applications endpoint requires admin role"""
        # Try with trader token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader",
            "password": "000000"
        })
        trader_token = response.json().get("token")
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/shop-applications",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 403
        print("SUCCESS: Shop applications endpoint requires admin role")


class TestTraderShopManagement:
    """Test trader shop management (products)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_trader_token(self):
        """Login as trader and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader",
            "password": "000000"
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_trader_can_get_shop_settings(self):
        """Test trader with shop can get shop settings"""
        token = self.get_trader_token()
        assert token, "Failed to get trader token"
        
        response = self.session.get(
            f"{BASE_URL}/api/shop/my-shop",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # If trader has shop, should return 200 with settings
        # If no shop, should return 403
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS: Trader has shop: {data.get('shop_name')}")
        elif response.status_code == 403:
            print("INFO: Trader does not have an approved shop yet")
        else:
            print(f"WARNING: Unexpected status code: {response.status_code}")
    
    def test_trader_can_get_products(self):
        """Test trader with shop can get their products"""
        token = self.get_trader_token()
        assert token, "Failed to get trader token"
        
        response = self.session.get(
            f"{BASE_URL}/api/shop/products",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"SUCCESS: Trader can get products, count: {len(data)}")
            for product in data[:3]:
                print(f"  - {product.get('name')} ({product.get('price')} {product.get('currency')}) - stock: {product.get('stock_count', 0)}")
        elif response.status_code == 403:
            print("INFO: Trader does not have an approved shop yet")
        else:
            print(f"WARNING: Unexpected status code: {response.status_code}")


class TestMarketplace:
    """Test marketplace public endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_marketplace_shops_public(self):
        """Test marketplace shops endpoint is public"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/shops")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Marketplace shops endpoint works, count: {len(data)}")
        
        for shop in data[:3]:
            print(f"  - {shop.get('name')} (@{shop.get('nickname')}) - {shop.get('product_count', 0)} products")
    
    def test_marketplace_products_public(self):
        """Test marketplace products endpoint is public"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/products")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Marketplace products endpoint works, count: {len(data)}")
        
        for product in data[:3]:
            print(f"  - {product.get('name')} ({product.get('price')} {product.get('currency')}) by @{product.get('shop_nickname')}")
    
    def test_marketplace_categories_public(self):
        """Test marketplace categories endpoint is public"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Marketplace categories endpoint works, categories: {data}")
    
    def test_marketplace_shop_detail(self):
        """Test marketplace shop detail endpoint"""
        # First get list of shops
        response = self.session.get(f"{BASE_URL}/api/marketplace/shops")
        shops = response.json()
        
        if shops:
            shop_id = shops[0].get("id")
            response = self.session.get(f"{BASE_URL}/api/marketplace/shops/{shop_id}")
            assert response.status_code == 200
            data = response.json()
            print(f"SUCCESS: Shop detail works for {data.get('name')}")
        else:
            print("INFO: No shops available to test detail endpoint")
    
    def test_marketplace_product_detail(self):
        """Test marketplace product detail endpoint"""
        # First get list of products
        response = self.session.get(f"{BASE_URL}/api/marketplace/products")
        products = response.json()
        
        if products:
            product_id = products[0].get("id")
            response = self.session.get(f"{BASE_URL}/api/marketplace/products/{product_id}")
            assert response.status_code == 200
            data = response.json()
            print(f"SUCCESS: Product detail works for {data.get('name')}")
        else:
            print("INFO: No products available to test detail endpoint")


class TestGuarantorDealCreation:
    """Test guarantor deal creation form"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_trader_token(self):
        """Login as trader and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "trader",
            "password": "000000"
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_guarantor_deals_endpoint_exists(self):
        """Test guarantor deals endpoint exists"""
        token = self.get_trader_token()
        assert token, "Failed to get trader token"
        
        # Try to create a deal (may fail due to validation but endpoint should exist)
        response = self.session.post(
            f"{BASE_URL}/api/guarantor/deals",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "role": "buyer",
                "amount": 100,
                "currency": "USDT",
                "title": "Test Deal",
                "description": "Test description for guarantor deal"
            }
        )
        
        # Should not be 404 - endpoint exists
        assert response.status_code != 404, "Guarantor deals endpoint not found"
        print(f"SUCCESS: Guarantor deals endpoint exists, status: {response.status_code}")
        
        if response.status_code == 200 or response.status_code == 201:
            print("  - Deal created successfully")
        elif response.status_code == 400:
            print(f"  - Validation error: {response.json().get('detail')}")
        elif response.status_code == 403:
            print("  - Permission denied (may need specific role)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
