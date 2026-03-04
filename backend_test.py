#!/usr/bin/env python3
"""
Backend API Testing for Russian Merchant Shop Integration
Tests merchant API key connection, payment creation, and transaction history
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any

class RussianMerchantShopTester:
    def __init__(self):
        self.base_url = "https://blockchain-finance.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.api_key = "merch_sk_8581cf8f655c4f858511e26d1dc3f3f3"
        self.merchant_name = "Мерчант Казино"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.test_results = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def log_test(self, name: str, success: bool, details: Dict[str, Any] = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            self.log(f"✅ {name}", "PASS")
        else:
            self.log(f"❌ {name}", "FAIL")
            self.failed_tests.append(name)
        
        self.test_results.append({
            "test_name": name,
            "success": success,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        })

    def test_merchant_info(self):
        """Test merchant info retrieval by API key"""
        self.log("Testing merchant info retrieval...")
        try:
            url = f"{self.api_url}/shop/merchant-info/{self.api_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                expected_fields = ["merchant_id", "company_name", "balance_usdt"]
                
                if all(field in data for field in expected_fields):
                    merchant_id = data.get("merchant_id")
                    balance = data.get("balance_usdt", 0)
                    company_name = data.get("company_name", "")
                    
                    self.log_test(
                        f"Merchant Info Retrieved - ID: {merchant_id}, Balance: {balance} USDT, Name: {company_name}",
                        True,
                        {"merchant_id": merchant_id, "balance_usdt": balance, "company_name": company_name}
                    )
                    return data
                else:
                    self.log_test("Merchant Info - Missing required fields", False, {"response": data})
                    return None
            else:
                self.log_test(f"Merchant Info - HTTP {response.status_code}", False, {"status_code": response.status_code})
                return None
        except Exception as e:
            self.log_test(f"Merchant Info - Error: {str(e)}", False, {"error": str(e)})
            return None

    def test_quick_payment_creation(self, amount_rub=5000):
        """Test quick payment creation"""
        self.log(f"Testing payment creation for {amount_rub} RUB...")
        try:
            url = f"{self.api_url}/shop/quick-payment"
            payload = {
                "amount_rub": amount_rub,
                "description": f"Тестовое пополнение на {amount_rub} руб.",
                "merchant_api_key": self.api_key
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("invoice_id"):
                    invoice_id = data.get("invoice_id")
                    payment_url = data.get("payment_url", "")
                    
                    self.log_test(
                        f"Payment Created - Invoice ID: {invoice_id}",
                        True,
                        {"invoice_id": invoice_id, "amount_rub": amount_rub, "payment_url": payment_url}
                    )
                    return data
                else:
                    self.log_test("Payment Creation - Invalid response format", False, {"response": data})
                    return None
            else:
                self.log_test(f"Payment Creation - HTTP {response.status_code}", False, {"status_code": response.status_code})
                return None
        except Exception as e:
            self.log_test(f"Payment Creation - Error: {str(e)}", False, {"error": str(e)})
            return None

    def test_operators_loading(self, invoice_id: str, amount_rub=5000):
        """Test operators loading for payment"""
        self.log(f"Testing operators loading for invoice {invoice_id}...")
        try:
            url = f"{self.api_url}/public/operators?amount_rub={amount_rub}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                operators = data.get("operators", [])
                exchange_rate = data.get("exchange_rate", 0)
                
                if operators:
                    operator_count = len(operators)
                    first_operator = operators[0]
                    trader_id = first_operator.get("trader_id")
                    price_rub = first_operator.get("price_rub", 0)
                    requisites_count = len(first_operator.get("requisites", []))
                    
                    self.log_test(
                        f"Operators Loaded - {operator_count} operators, Exchange Rate: {exchange_rate}",
                        True,
                        {
                            "operator_count": operator_count,
                            "exchange_rate": exchange_rate,
                            "first_operator_id": trader_id,
                            "price_rub": price_rub,
                            "requisites_count": requisites_count
                        }
                    )
                    return data
                else:
                    self.log_test("Operators Loading - No operators available", False, {"response": data})
                    return None
            else:
                self.log_test(f"Operators Loading - HTTP {response.status_code}", False, {"status_code": response.status_code})
                return None
        except Exception as e:
            self.log_test(f"Operators Loading - Error: {str(e)}", False, {"error": str(e)})
            return None

    def test_transaction_history(self):
        """Test transaction history loading"""
        self.log("Testing transaction history...")
        try:
            # Get merchant info first
            merchant_info = self.test_merchant_info()
            if not merchant_info:
                self.log_test("Transaction History - Merchant info required", False)
                return None
            
            merchant_id = merchant_info.get("merchant_id")
            
            url = f"{self.api_url}/v1/invoice/transactions"
            headers = {"X-Api-Key": self.api_key}
            params = {"merchant_id": merchant_id, "limit": 20}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    transactions = data.get("data", {}).get("transactions", [])
                    total = data.get("data", {}).get("total", 0)
                    
                    self.log_test(
                        f"Transaction History Loaded - {len(transactions)} transactions, Total: {total}",
                        True,
                        {"transactions_count": len(transactions), "total": total}
                    )
                    return data
                else:
                    self.log_test("Transaction History - Invalid response status", False, {"response": data})
                    return None
            else:
                self.log_test(f"Transaction History - HTTP {response.status_code}", False, {"status_code": response.status_code})
                return None
        except Exception as e:
            self.log_test(f"Transaction History - Error: {str(e)}", False, {"error": str(e)})
            return None

    def run_merchant_shop_tests(self):
        """Run merchant shop specific tests"""
        self.log("🚀 Starting Russian Merchant Shop API testing...")
        
        # 1. Test merchant connection
        self.log("=" * 60)
        merchant_info = self.test_merchant_info()
        
        # 2. Test payment creation
        self.log("=" * 60)
        payment_data = self.test_quick_payment_creation(7500)
        
        # 3. Test operators loading
        if payment_data:
            self.log("=" * 60)
            invoice_id = payment_data.get("invoice_id")
            operators_data = self.test_operators_loading(invoice_id, 7500)
        
        # 4. Test transaction history
        self.log("=" * 60)
        self.test_transaction_history()
        
        # Print summary
        self.log("=" * 60)
        self.log(f"📊 Test Summary:")
        self.log(f"Tests Run: {self.tests_run}")
        self.log(f"Tests Passed: {self.tests_passed}")
        self.log(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            self.log(f"Failed tests: {', '.join(self.failed_tests)}", "ERROR")
        
        return self.tests_passed == self.tests_run

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, description=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        self.log(f"🔍 Testing {name} - {description or endpoint}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                self.log(f"❌ {name} - {error_msg}")
                self.failed_tests.append(f"{name}: {error_msg}")
                try:
                    error_detail = response.json() if response.text else "No response"
                    self.log(f"   Response: {error_detail}")
                except:
                    self.log(f"   Response: {response.text[:200]}")
                return False, {}
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            self.log(f"❌ {name} - {error_msg}")
            self.failed_tests.append(f"{name}: {error_msg}")
            return False, {}

    def test_health_endpoint(self):
        """Test basic health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET", 
            "health",
            200,
            description="Check if backend is responding"
        )
        
        if success and isinstance(response, dict):
            status = response.get('status')
            if status == 'healthy':
                self.log("✅ Backend is healthy")
                return True
            else:
                self.log(f"⚠️ Backend status: {status}")
                return False
        return success

    def test_root_endpoint(self):
        """Test root API endpoint"""
        success, response = self.run_test(
            "Root API",
            "GET",
            "",
            200,
            description="Check root API endpoint"
        )
        
        if success and isinstance(response, dict):
            message = response.get('message', '')
            if 'P2P Exchange' in message:
                self.log("✅ Root API responding correctly")
                return True
        return success

    def test_admin_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={
                "login": "admin",
                "password": "000000"
            },
            description="Login as admin user"
        )
        
        if success and isinstance(response, dict):
            token = response.get('token')
            user = response.get('user')
            if token and user:
                self.admin_token = token
                self.log(f"✅ Admin login successful - Role: {user.get('role', 'unknown')}")
                return True
        
        self.log("❌ Admin login failed - no token received")
        return False

    def test_trader_login(self):
        """Test trader login"""
        success, response = self.run_test(
            "Trader Login",
            "POST",
            "auth/login", 
            200,
            data={
                "login": "user1",
                "password": "000000"
            },
            description="Login as trader user1"
        )
        
        if success and isinstance(response, dict):
            token = response.get('token')
            user = response.get('user')
            if token and user:
                self.trader_token = token
                self.log(f"✅ Trader login successful - Role: {user.get('role', 'unknown')}")
                return True
        
        self.log("❌ Trader login failed - no token received")
        return False

    def test_protected_endpoint(self):
        """Test protected endpoint with admin token"""
        if not self.admin_token:
            self.log("⚠️ Skipping protected endpoint test - no admin token")
            return False
            
        success, response = self.run_test(
            "Protected Endpoint",
            "GET",
            "auth/me",
            200,
            headers={'Authorization': f'Bearer {self.admin_token}'},
            description="Test authenticated endpoint"
        )
        
        if success and isinstance(response, dict):
            user = response.get('user')
            if user and user.get('role') == 'admin':
                self.log("✅ Protected endpoint working")
                return True
        
        return success

    def test_offers_endpoint(self):
        """Test offers endpoint (public)"""
        success, response = self.run_test(
            "Offers Endpoint",
            "GET",
            "offers",
            200,
            description="Get public offers list"
        )
        
        if success:
            self.log(f"✅ Offers endpoint responding")
            if isinstance(response, list):
                self.log(f"   Found {len(response)} offers")
            return True
        
        return success

    def test_exchange_rate_endpoint(self):
        """Test exchange rate endpoint"""
        success, response = self.run_test(
            "Exchange Rate",
            "GET",
            f"{self.base_url}/api/exchange-rate",
            200,
            description="Get USDT/RUB exchange rate"
        )
        
        if success and isinstance(response, dict):
            base_rate = response.get('base_rate', 0)
            self.log(f"✅ Exchange rate endpoint - Base rate: {base_rate}")
            return True
        
        return success

    def test_public_operators(self):
        """Test public operators endpoint"""
        success, response = self.run_test(
            "Public Operators",
            "GET", 
            "public/operators",
            200,
            description="Get public operators list"
        )
        
        if success:
            self.log(f"✅ Public operators endpoint responding")
            if isinstance(response, dict):
                operators = response.get('operators', [])
                self.log(f"   Found {len(operators)} operators")
                if len(operators) >= 3:
                    self.log("✅ Expected 3+ operators found for testing")
                else:
                    self.log(f"⚠️ Only {len(operators)} operators found, expected 3+")
            elif isinstance(response, list):
                self.log(f"   Found {len(response)} operators")
            return True
        
        return success

    def test_merchant_api_key_connection(self):
        """Test merchant API key connection"""
        api_key = "merch_sk_8581cf8f655c4f858511e26d1dc3f3f3"
        
        success, response = self.run_test(
            "Merchant API Connection",
            "GET",
            f"shop/merchant-info/{api_key}",
            200,
            description="Test merchant API key connection"
        )
        
        if success and isinstance(response, dict):
            merchant_id = response.get('merchant_id')
            company_name = response.get('company_name')
            balance_usdt = response.get('balance_usdt', 0)
            status = response.get('status')
            
            self.log(f"✅ Merchant connected - ID: {merchant_id}")
            self.log(f"   Company: {company_name}")
            self.log(f"   Balance: {balance_usdt} USDT")
            self.log(f"   Status: {status}")
            
            if balance_usdt >= 500:
                self.log("✅ Expected balance (500+ USDT) confirmed")
            else:
                self.log(f"⚠️ Balance is {balance_usdt} USDT, expected 500+")
            
            return True
        
        return success

    def test_quick_payment_creation(self):
        """Test quick payment creation for 1000 RUB"""
        success, response = self.run_test(
            "Quick Payment Creation",
            "POST",
            "shop/quick-payment",
            200,
            data={
                "amount_rub": 1000,
                "description": "Тест пополнения на 1000 RUB"
            },
            description="Create 1000 RUB payment"
        )
        
        if success and isinstance(response, dict):
            invoice_id = response.get('invoice_id')
            amount_rub = response.get('amount_rub')
            amount_usdt = response.get('amount_usdt')
            payment_url = response.get('payment_url')
            
            self.log(f"✅ Payment created - ID: {invoice_id}")
            self.log(f"   Amount: {amount_rub} RUB = {amount_usdt} USDT")
            self.log(f"   Payment URL: {payment_url}")
            
            # Store invoice_id for further testing
            self.test_invoice_id = invoice_id
            return True
        
        return success

    def test_operators_for_payment(self):
        """Test operators available for 1000 RUB payment"""
        success, response = self.run_test(
            "Operators for Payment",
            "GET",
            "public/operators?amount_rub=1000",
            200,
            description="Get operators for 1000 RUB payment"
        )
        
        if success and isinstance(response, dict):
            operators = response.get('operators', [])
            exchange_rate = response.get('exchange_rate')
            
            self.log(f"✅ Found {len(operators)} operators for 1000 RUB")
            self.log(f"   Exchange rate: {exchange_rate}")
            
            # Check for expected 3 operators (user1, user2, user3)
            trader_logins = [op.get('trader_login', '') for op in operators]
            expected_traders = ['user1', 'user2', 'user3']
            found_expected = [t for t in expected_traders if t in trader_logins]
            
            self.log(f"   Expected traders found: {found_expected}")
            
            if len(found_expected) >= 2:
                self.log("✅ Expected test traders found")
            else:
                self.log(f"⚠️ Expected traders (user1, user2, user3) not found")
            
            # Check payment methods
            for op in operators[:3]:  # Check first 3 operators
                trader_login = op.get('trader_login', 'Unknown')
                requisites = op.get('requisites', [])
                payment_methods = [r.get('type') for r in requisites if r.get('type')]
                
                self.log(f"   {trader_login}: {payment_methods}")
                
                if 'card' in payment_methods or 'sbp' in payment_methods:
                    self.log(f"   ✅ {trader_login} has expected payment methods")
            
            return True
        
        return success

    def test_invoice_api_payment_methods(self):
        """Test Invoice API payment methods endpoint"""
        api_key = "merch_sk_8581cf8f655c4f858511e26d1dc3f3f3"
        
        success, response = self.run_test(
            "Invoice API Payment Methods",
            "GET",
            "v1/invoice/payment-methods",
            200,
            headers={'X-Api-Key': api_key},
            description="Get available payment methods via Invoice API"
        )
        
        if success and isinstance(response, dict):
            payment_methods = response.get('payment_methods', [])
            
            self.log(f"✅ Payment methods endpoint working")
            self.log(f"   Available methods: {len(payment_methods)}")
            
            method_ids = [pm.get('id') for pm in payment_methods]
            expected_methods = ['card', 'sbp']
            
            for method in expected_methods:
                if method in method_ids:
                    self.log(f"   ✅ {method} method available")
                else:
                    self.log(f"   ⚠️ {method} method not found")
            
            return True
        
        return success

    def test_invoice_api_transactions(self):
        """Test Invoice API transactions endpoint"""
        api_key = "merch_sk_8581cf8f655c4f858511e26d1dc3f3f3"
        
        success, response = self.run_test(
            "Invoice API Transactions",
            "GET",
            "v1/invoice/transactions?limit=10",
            200,
            headers={'X-Api-Key': api_key},
            description="Get transaction history via Invoice API"
        )
        
        if success and isinstance(response, dict):
            data = response.get('data', {})
            transactions = data.get('transactions', [])
            total = data.get('total', 0)
            
            self.log(f"✅ Transactions endpoint working")
            self.log(f"   Total transactions: {total}")
            self.log(f"   Retrieved: {len(transactions)}")
            
            return True
        
        return success

    def run_all_tests(self):
        """Run all backend tests"""
        self.log("🚀 Starting Reptiloid-01 Backend API Tests")
        self.log(f"   Base URL: {self.base_url}")
        
        # Initialize test variables
        self.test_invoice_id = None
        
        # Basic connectivity tests
        self.test_root_endpoint()
        self.test_health_endpoint()
        
        # Authentication tests  
        self.test_admin_login()
        self.test_trader_login()
        
        # Protected endpoint test
        self.test_protected_endpoint()
        
        # Public endpoints
        self.test_offers_endpoint()
        self.test_exchange_rate_endpoint()
        self.test_public_operators()
        
        # Merchant API tests (new)
        self.log("\n" + "="*40)
        self.log("🏪 Testing Merchant Shop API")
        self.test_merchant_api_key_connection()
        self.test_quick_payment_creation()
        self.test_operators_for_payment()
        
        # Invoice API tests  
        self.log("\n" + "="*40)
        self.log("📝 Testing Invoice API")
        self.test_invoice_api_payment_methods()
        self.test_invoice_api_transactions()
        
        # Print summary
        self.log("\n" + "="*60)
        self.log(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            self.log("\n❌ Failed Tests:")
            for failed in self.failed_tests:
                self.log(f"   - {failed}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"📈 Success Rate: {success_rate:.1f}%")
        
        return self.tests_passed, self.tests_run, self.failed_tests

def main():
    tester = RussianMerchantShopTester()
    passed, total, failed = tester.run_all_tests()
    
    # Return appropriate exit code
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())