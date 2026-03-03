#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class ReptiloidAPITester:
    def __init__(self):
        self.base_url = "https://preview-stage-15.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.admin_token = None
        self.trader_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
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
            if isinstance(response, list):
                self.log(f"   Found {len(response)} operators")
            return True
        
        return success

    def run_all_tests(self):
        """Run all backend tests"""
        self.log("🚀 Starting Reptiloid-01 Backend API Tests")
        self.log(f"   Base URL: {self.base_url}")
        
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
    tester = ReptiloidAPITester()
    passed, total, failed = tester.run_all_tests()
    
    # Return appropriate exit code
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())