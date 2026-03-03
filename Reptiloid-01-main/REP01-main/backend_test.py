import requests
import sys
import json
from datetime import datetime

class P2PExchangeAPITester:
    def __init__(self, base_url="https://p2p-gateway.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tokens = {}
        self.users = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            if not success:
                details += f", Expected: {expected_status}"
                if response.text:
                    try:
                        error_data = response.json()
                        details += f", Error: {error_data.get('detail', response.text)}"
                    except:
                        details += f", Response: {response.text[:100]}"

            self.log_test(name, success, details)
            return success, response.json() if success and response.text else {}

        except Exception as e:
            self.log_test(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test basic health endpoints"""
        print("\n🔍 Testing Health Endpoints...")
        self.run_test("Health Check", "GET", "", 200)
        self.run_test("API Health", "GET", "health", 200)

    def test_admin_login(self):
        """Test admin login"""
        print("\n🔍 Testing Admin Authentication...")
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"login": "admin", "password": "admin123"}
        )
        if success and 'token' in response:
            self.tokens['admin'] = response['token']
            self.users['admin'] = response['user']
            return True
        return False

    def test_trader_registration(self):
        """Test trader registration"""
        print("\n🔍 Testing Trader Registration...")
        timestamp = datetime.now().strftime('%H%M%S')
        trader_data = {
            "login": f"test_trader_{timestamp}",
            "password": "testpass123"
        }
        
        success, response = self.run_test(
            "Trader Registration",
            "POST",
            "auth/trader/register",
            200,
            data=trader_data
        )
        
        if success and 'token' in response:
            self.tokens['trader'] = response['token']
            self.users['trader'] = response['user']
            self.users['trader']['login_data'] = trader_data
            return True
        return False

    def test_trader_login(self):
        """Test trader login"""
        print("\n🔍 Testing Trader Login...")
        if 'trader' not in self.users:
            self.log_test("Trader Login", False, "No trader registered")
            return False
            
        login_data = self.users['trader']['login_data']
        success, response = self.run_test(
            "Trader Login",
            "POST",
            "auth/login",
            200,
            data=login_data
        )
        return success

    def test_merchant_registration(self):
        """Test merchant registration"""
        print("\n🔍 Testing Merchant Registration...")
        timestamp = datetime.now().strftime('%H%M%S')
        merchant_data = {
            "login": f"test_merchant_{timestamp}",
            "password": "testpass123",
            "merchant_name": f"Test Casino {timestamp}",
            "merchant_type": "casino",
            "telegram": "@testmerchant"
        }
        
        success, response = self.run_test(
            "Merchant Registration",
            "POST",
            "auth/merchant/register",
            200,
            data=merchant_data
        )
        
        if success and 'token' in response:
            self.tokens['merchant'] = response['token']
            self.users['merchant'] = response['user']
            self.users['merchant']['login_data'] = merchant_data
            
            # Check if status is pending
            if response['user'].get('status') == 'pending':
                self.log_test("Merchant Status Check", True, "Status: pending")
            else:
                self.log_test("Merchant Status Check", False, f"Status: {response['user'].get('status')}")
            return True
        return False

    def test_admin_merchant_management(self):
        """Test admin merchant management"""
        print("\n🔍 Testing Admin Merchant Management...")
        if 'admin' not in self.tokens:
            self.log_test("Admin Merchant Management", False, "No admin token")
            return False

        admin_headers = {'Authorization': f'Bearer {self.tokens["admin"]}'}
        
        # Get pending merchants
        success, response = self.run_test(
            "Get Pending Merchants",
            "GET",
            "merchants/pending",
            200,
            headers=admin_headers
        )
        
        if success and len(response) > 0:
            # Find our specific merchant by ID
            our_merchant_id = self.users['merchant']['id']
            merchant_to_approve = None
            
            for merchant in response:
                if merchant['id'] == our_merchant_id:
                    merchant_to_approve = merchant
                    break
            
            if not merchant_to_approve:
                self.log_test("Find Our Merchant", False, f"Our merchant {our_merchant_id} not found in pending list")
                return False
                
            merchant_id = merchant_to_approve['id']
            print(f"DEBUG: Approving our merchant ID: {merchant_id}")
            
            # Approve merchant
            success, response = self.run_test(
                "Approve Merchant",
                "POST",
                f"merchants/{merchant_id}/approve",
                200,
                data={"approved": True},
                headers=admin_headers
            )
            
            if success:
                print(f"DEBUG: Approval response: {response}")
                
                # Check merchant status after approval
                success2, merchant_data = self.run_test(
                    "Get Merchant After Approval",
                    "GET",
                    f"merchants/{merchant_id}",
                    200,
                    headers=admin_headers
                )
                
                if success2:
                    status = merchant_data.get('status', 'unknown')
                    print(f"DEBUG: Merchant data after approval: status={status}, id={merchant_data.get('id')}")
                    self.log_test("Merchant Status After Approval", 
                                status == 'active', f"Status: {status}")
                    
                    # Update merchant user data
                    if 'merchant' in self.users:
                        print(f"DEBUG: Current merchant user ID: {self.users['merchant'].get('id')}")
                        self.users['merchant'].update(merchant_data)
                        
                        # Refresh merchant token with updated data
                        if status == 'active' and 'login_data' in self.users['merchant']:
                            # Add small delay to ensure database update is processed
                            import time
                            time.sleep(1)
                            
                            login_data = self.users['merchant']['login_data']
                            success3, login_response = self.run_test(
                                "Refresh Merchant Token",
                                "POST",
                                "auth/login",
                                200,
                                data={"login": login_data["login"], "password": login_data["password"]}
                            )
                            if success3:
                                self.tokens['merchant'] = login_response['token']
                                self.users['merchant'] = login_response['user']
                                print(f"DEBUG: Merchant after token refresh: status={login_response['user'].get('status')}")
                        
        return success

    def test_trader_deposit(self):
        """Test trader deposit"""
        print("\n🔍 Testing Trader Deposit...")
        if 'trader' not in self.tokens:
            self.log_test("Trader Deposit", False, "No trader token")
            return False

        trader_headers = {'Authorization': f'Bearer {self.tokens["trader"]}'}
        
        success, response = self.run_test(
            "Trader Deposit USDT",
            "POST",
            "traders/deposit?amount=100",
            200,
            headers=trader_headers
        )
        
        if success and 'balance_usdt' in response:
            self.log_test("Deposit Balance Check", True, f"Balance: {response['balance_usdt']}")
        
        return success

    def test_trader_offers(self):
        """Test trader offer creation"""
        print("\n🔍 Testing Trader Offers...")
        if 'trader' not in self.tokens:
            self.log_test("Trader Offers", False, "No trader token")
            return False

        trader_headers = {'Authorization': f'Bearer {self.tokens["trader"]}'}
        
        offer_data = {
            "min_amount": 100,
            "max_amount": 1000,
            "price_rub": 92.5,
            "payment_methods": ["sberbank", "tinkoff"],
            "accepted_merchant_types": ["casino", "shop"]
        }
        
        success, response = self.run_test(
            "Create Trader Offer",
            "POST",
            "offers",
            200,
            data=offer_data,
            headers=trader_headers
        )
        
        if success and 'id' in response:
            self.users['trader']['offer_id'] = response['id']
            
        # Get offers
        self.run_test(
            "Get Public Offers",
            "GET",
            "offers",
            200
        )
        
        return success

    def test_merchant_payment_links(self):
        """Test merchant payment link creation"""
        print("\n🔍 Testing Merchant Payment Links...")
        if 'merchant' not in self.tokens:
            self.log_test("Merchant Payment Links", False, "No merchant token")
            return False
            
        # Debug: Print merchant status
        merchant_status = self.users['merchant'].get('status', 'unknown')
        print(f"DEBUG: Merchant status: {merchant_status}")
        
        if merchant_status != 'active':
            self.log_test("Merchant Payment Links", False, f"Merchant not active (status: {merchant_status})")
            return False

        merchant_headers = {'Authorization': f'Bearer {self.tokens["merchant"]}'}
        
        link_data = {
            "amount_rub": 9250,
            "price_rub": 92.5
        }
        
        success, response = self.run_test(
            "Create Payment Link",
            "POST",
            "payment-links",
            200,
            data=link_data,
            headers=merchant_headers
        )
        
        if success and 'id' in response:
            self.users['merchant']['payment_link_id'] = response['id']
            
        # Get payment links
        self.run_test(
            "Get Merchant Payment Links",
            "GET",
            "payment-links",
            200,
            headers=merchant_headers
        )
        
        return success

    def test_trade_creation(self):
        """Test trade creation and commission calculation"""
        print("\n🔍 Testing Trade Creation...")
        
        if 'trader' not in self.users or 'merchant' not in self.users:
            self.log_test("Trade Creation", False, "Missing trader or merchant")
            return False
            
        if not self.users['merchant'].get('payment_link_id'):
            self.log_test("Trade Creation", False, "No payment link available")
            return False

        trade_data = {
            "amount_usdt": 100,
            "price_rub": 92.5,
            "trader_id": self.users['trader']['id'],
            "payment_link_id": self.users['merchant']['payment_link_id']
        }
        
        success, response = self.run_test(
            "Create Trade",
            "POST",
            "trades",
            200,
            data=trade_data
        )
        
        if success and 'id' in response:
            self.users['trade_id'] = response['id']
            
            # Check commission calculation
            trader_commission = response.get('trader_commission', 0)
            merchant_commission = response.get('merchant_commission', 0)
            
            self.log_test("Commission Calculation", True, 
                         f"Trader: {trader_commission}, Merchant: {merchant_commission}")
        
        return success

    def test_commission_settings(self):
        """Test commission settings management"""
        print("\n🔍 Testing Commission Settings...")
        if 'admin' not in self.tokens:
            self.log_test("Commission Settings", False, "No admin token")
            return False

        admin_headers = {'Authorization': f'Bearer {self.tokens["admin"]}'}
        
        # Get current settings
        success, response = self.run_test(
            "Get Commission Settings",
            "GET",
            "admin/commission-settings",
            200,
            headers=admin_headers
        )
        
        if success:
            # Update settings
            update_data = {
                "trader_commission": 1.0,
                "casino_commission": 0.5
            }
            
            self.run_test(
                "Update Commission Settings",
                "PUT",
                "admin/commission-settings",
                200,
                data=update_data,
                headers=admin_headers
            )
        
        return success

    def test_chat_system(self):
        """Test chat system"""
        print("\n🔍 Testing Chat System...")
        if 'merchant' not in self.tokens or 'admin' not in self.tokens:
            self.log_test("Chat System", False, "Missing merchant or admin token")
            return False

        merchant_headers = {'Authorization': f'Bearer {self.tokens["merchant"]}'}
        admin_headers = {'Authorization': f'Bearer {self.tokens["admin"]}'}
        
        # Get chats as admin
        success, response = self.run_test(
            "Admin Get Chats",
            "GET",
            "chats",
            200,
            headers=admin_headers
        )
        
        if success and len(response) > 0:
            # Find our merchant's chat
            our_merchant_id = self.users['merchant']['id']
            our_chat = None
            
            for chat in response:
                if chat.get('merchant_id') == our_merchant_id:
                    our_chat = chat
                    break
            
            if not our_chat:
                self.log_test("Find Our Chat", False, f"Chat for merchant {our_merchant_id} not found")
                return False
                
            chat_id = our_chat['id']
            print(f"DEBUG: Using chat ID: {chat_id} for merchant: {our_merchant_id}")
            
            # Send message as merchant
            message_data = {"content": "Test message from merchant"}
            self.run_test(
                "Merchant Send Message",
                "POST",
                f"chats/{chat_id}/messages",
                200,
                data=message_data,
                headers=merchant_headers
            )
            
            # Get messages as admin
            self.run_test(
                "Admin Get Messages",
                "GET",
                f"chats/{chat_id}/messages",
                200,
                headers=admin_headers
            )
        
        return success

    def test_admin_stats(self):
        """Test admin statistics"""
        print("\n🔍 Testing Admin Statistics...")
        if 'admin' not in self.tokens:
            self.log_test("Admin Stats", False, "No admin token")
            return False

        admin_headers = {'Authorization': f'Bearer {self.tokens["admin"]}'}
        
        success, response = self.run_test(
            "Get Admin Stats",
            "GET",
            "admin/stats",
            200,
            headers=admin_headers
        )
        
        if success:
            required_fields = ['total_merchants', 'pending_merchants', 'active_merchants', 'total_traders']
            for field in required_fields:
                if field in response:
                    self.log_test(f"Stats Field: {field}", True, f"Value: {response[field]}")
                else:
                    self.log_test(f"Stats Field: {field}", False, "Missing field")
        
        return success

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting P2P Exchange API Tests")
        print(f"Backend URL: {self.base_url}")
        print("=" * 50)

        # Test sequence
        self.test_health_check()
        
        if self.test_admin_login():
            self.test_commission_settings()
            self.test_admin_stats()
        
        if self.test_trader_registration():
            self.test_trader_login()
            self.test_trader_deposit()
            self.test_trader_offers()
        
        if self.test_merchant_registration():
            if self.test_admin_merchant_management():
                self.test_merchant_payment_links()
                self.test_trade_creation()
                self.test_chat_system()

        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("❌ Some tests failed")
            return 1

def main():
    tester = P2PExchangeAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())