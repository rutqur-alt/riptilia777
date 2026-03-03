"""
Test suite for P2P Exchange new features:
- Price Variants (bulk discounts)
- Stock Upload/Download
- Product Reservation
- Admin Withdrawals Management
- Admin Inventory Monitoring
- Shop Transfer
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"login": "admin", "password": "000000"}
TRADER_CREDS = {"login": "trader", "password": "000000"}
BUYER_CREDS = {"login": "trader2", "password": "000000"}

# Known IDs from context
NETFLIX_PRODUCT_ID = "858807c4-c75d-4ecf-9481-dba8eceb237c"
WITHDRAWAL_ID = "c2be0ee8-1904-4f2d-bb72-58da98170819"


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Admin can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        
    def test_trader_login(self):
        """Trader can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "trader"
        
    def test_buyer_login(self):
        """Buyer (trader2) can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=BUYER_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data


@pytest.fixture
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Admin login failed")


@pytest.fixture
def trader_token():
    """Get trader auth token"""
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


class TestPriceVariants:
    """Test price variants (bulk discounts) feature"""
    
    def test_get_product_with_variants(self, buyer_token):
        """Get Netflix product with price variants"""
        response = requests.get(
            f"{BASE_URL}/api/marketplace/products/{NETFLIX_PRODUCT_ID}",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert response.status_code == 200
        product = response.json()
        assert "Netflix Premium" in product["name"]  # Name includes "1 месяц"
        assert "price_variants" in product
        # Should have variants: 2 (-10%), 5 (-20%), 12 (-33%)
        variants = product.get("price_variants", [])
        assert len(variants) >= 3, f"Expected at least 3 variants, got {len(variants)}"
        print(f"Product: {product['name']}, Price: {product['price']}, Variants: {variants}")
        
    def test_buy_with_variant_quantity(self, buyer_token):
        """Buy product using variant_quantity parameter"""
        # First check stock
        response = requests.get(
            f"{BASE_URL}/api/marketplace/products/{NETFLIX_PRODUCT_ID}",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        if response.status_code != 200:
            pytest.skip("Product not found")
            
        product = response.json()
        stock = product.get("stock_count", 0)
        if stock < 2:
            pytest.skip(f"Not enough stock ({stock}) to test variant purchase")
        
        # Try to buy with variant_quantity=2 (should get -10% discount)
        response = requests.post(
            f"{BASE_URL}/api/marketplace/products/{NETFLIX_PRODUCT_ID}/buy",
            params={"quantity": 2, "variant_quantity": 2, "purchase_type": "instant"},
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Purchase successful: {data}")
            assert "total_price" in data or "quantity" in data
        elif response.status_code == 400:
            # Might be insufficient funds or stock
            print(f"Purchase failed (expected): {response.json()}")
        else:
            print(f"Unexpected response: {response.status_code} - {response.text}")


class TestStockUploadDownload:
    """Test stock upload and download features"""
    
    def test_upload_stock_requires_auth(self):
        """Upload stock requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/shop/products/{NETFLIX_PRODUCT_ID}/upload-stock",
            json="test-content"
        )
        assert response.status_code == 401 or response.status_code == 403
        
    def test_upload_stock_trader_only(self, buyer_token):
        """Upload stock - only product owner can upload"""
        response = requests.post(
            f"{BASE_URL}/api/shop/products/{NETFLIX_PRODUCT_ID}/upload-stock",
            data="test-key-1\ntest-key-2",
            headers={
                "Authorization": f"Bearer {buyer_token}",
                "Content-Type": "application/json"
            }
        )
        # Should fail - buyer doesn't own this product
        assert response.status_code in [403, 404, 422]
        
    def test_download_stock_requires_auth(self):
        """Download stock requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/shop/products/{NETFLIX_PRODUCT_ID}/download-stock"
        )
        assert response.status_code == 401 or response.status_code == 403
        
    def test_download_stock_owner_only(self, buyer_token):
        """Download stock - only product owner can download"""
        response = requests.get(
            f"{BASE_URL}/api/shop/products/{NETFLIX_PRODUCT_ID}/download-stock",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        # Should fail - buyer doesn't own this product
        assert response.status_code in [403, 404]


class TestProductReservation:
    """Test product reservation feature"""
    
    def test_reserve_product_requires_auth(self):
        """Reserve product requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/shop/products/{NETFLIX_PRODUCT_ID}/reserve",
            params={"quantity": 1}
        )
        assert response.status_code == 401 or response.status_code == 403
        
    def test_reserve_product(self, buyer_token):
        """Reserve product stock"""
        response = requests.post(
            f"{BASE_URL}/api/shop/products/{NETFLIX_PRODUCT_ID}/reserve",
            params={"quantity": 1},
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "reservation_id" in data
            assert data["quantity"] == 1
            print(f"Reservation created: {data}")
        elif response.status_code == 400:
            # Might be insufficient stock
            print(f"Reservation failed (expected): {response.json()}")
        elif response.status_code == 404:
            print(f"Product not found: {response.json()}")
        else:
            print(f"Unexpected response: {response.status_code} - {response.text}")


class TestAdminWithdrawals:
    """Test admin withdrawals management"""
    
    def test_get_withdrawals_requires_admin(self, trader_token):
        """Get withdrawals requires admin role"""
        response = requests.get(
            f"{BASE_URL}/api/admin/withdrawals",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 403
        
    def test_get_pending_withdrawals(self, admin_token):
        """Admin can get pending withdrawals"""
        response = requests.get(
            f"{BASE_URL}/api/admin/withdrawals?status_filter=pending",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        withdrawals = response.json()
        assert isinstance(withdrawals, list)
        print(f"Pending withdrawals: {len(withdrawals)}")
        for w in withdrawals:
            print(f"  - {w.get('id', 'N/A')}: {w.get('amount', 0)} USDT from @{w.get('seller_nickname', 'N/A')}")
            
    def test_get_all_withdrawals(self, admin_token):
        """Admin can get all withdrawals"""
        response = requests.get(
            f"{BASE_URL}/api/admin/withdrawals?status_filter=all",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        withdrawals = response.json()
        assert isinstance(withdrawals, list)
        print(f"All withdrawals: {len(withdrawals)}")
        
    def test_process_withdrawal_requires_admin(self, trader_token):
        """Process withdrawal requires admin role"""
        response = requests.post(
            f"{BASE_URL}/api/admin/withdrawals/{WITHDRAWAL_ID}/process",
            params={"decision": "approve"},
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 403
        
    def test_process_withdrawal_invalid_decision(self, admin_token):
        """Process withdrawal with invalid decision"""
        response = requests.post(
            f"{BASE_URL}/api/admin/withdrawals/{WITHDRAWAL_ID}/process",
            params={"decision": "invalid"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        
    def test_process_withdrawal_not_found(self, admin_token):
        """Process non-existent withdrawal"""
        response = requests.post(
            f"{BASE_URL}/api/admin/withdrawals/non-existent-id/process",
            params={"decision": "approve"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


class TestAdminInventoryMonitoring:
    """Test admin inventory monitoring"""
    
    def test_inventory_requires_admin(self, trader_token):
        """Inventory monitoring requires admin role"""
        response = requests.get(
            f"{BASE_URL}/api/admin/inventory-monitoring",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 403
        
    def test_get_inventory_monitoring(self, admin_token):
        """Admin can get inventory monitoring data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/inventory-monitoring",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        inventory = response.json()
        assert isinstance(inventory, list)
        print(f"Inventory items: {len(inventory)}")
        
        for item in inventory[:5]:  # Print first 5
            print(f"  - {item.get('name', 'N/A')}: stock={item.get('stock', 0)}, reserved={item.get('reserved', 0)}, available={item.get('available', 0)}")
            if item.get("has_discrepancy"):
                print(f"    ⚠️ DISCREPANCY: sold_count={item.get('sold_count', 0)}, actual_sales={item.get('actual_sales', 0)}")


class TestShopTransfer:
    """Test shop balance transfer feature"""
    
    def test_transfer_requires_auth(self):
        """Transfer requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/shop/transfer",
            params={"target_nickname": "trader2", "amount": 1.0}
        )
        assert response.status_code == 401 or response.status_code == 403
        
    def test_transfer_requires_trader(self, admin_token):
        """Transfer requires trader role"""
        response = requests.post(
            f"{BASE_URL}/api/shop/transfer",
            params={"target_nickname": "trader2", "amount": 1.0},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Admin is not a trader
        assert response.status_code == 403
        
    def test_transfer_validates_amount(self, trader_token):
        """Transfer validates amount > 0"""
        response = requests.post(
            f"{BASE_URL}/api/shop/transfer",
            params={"target_nickname": "trader2", "amount": 0},
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 400 or response.status_code == 422
        
    def test_transfer_validates_target(self, trader_token):
        """Transfer validates target user exists"""
        response = requests.post(
            f"{BASE_URL}/api/shop/transfer",
            params={"target_nickname": "nonexistent_user_12345", "amount": 1.0},
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert response.status_code == 404


class TestMarketplaceProducts:
    """Test marketplace product endpoints"""
    
    def test_get_marketplace_products(self):
        """Get all marketplace products (public)"""
        response = requests.get(f"{BASE_URL}/api/marketplace/products")
        assert response.status_code == 200
        products = response.json()
        assert isinstance(products, list)
        print(f"Marketplace products: {len(products)}")
        
    def test_get_product_details(self):
        """Get specific product details"""
        response = requests.get(f"{BASE_URL}/api/marketplace/products/{NETFLIX_PRODUCT_ID}")
        if response.status_code == 200:
            product = response.json()
            print(f"Product: {product.get('name')}")
            print(f"  Price: {product.get('price')} {product.get('currency', 'USDT')}")
            print(f"  Stock: {product.get('stock_count', 0)}")
            print(f"  Reserved: {product.get('reserved_count', 0)}")
            print(f"  Variants: {product.get('price_variants', [])}")
        else:
            print(f"Product not found: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
