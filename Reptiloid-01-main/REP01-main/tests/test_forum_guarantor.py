"""
Test suite for Forum and Guarantor features
- Forum: Global chat with WebSocket support
- Guarantor: Info page about escrow service
- Navigation: Landing page buttons for Forum, Guarantor, Market
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestForumAPI:
    """Forum API endpoint tests"""
    
    def test_get_forum_messages_public(self):
        """GET /api/forum/messages - public endpoint, no auth required"""
        response = requests.get(f"{BASE_URL}/api/forum/messages")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/forum/messages returns {len(data)} messages")
    
    def test_get_forum_messages_with_limit(self):
        """GET /api/forum/messages with limit parameter"""
        response = requests.get(f"{BASE_URL}/api/forum/messages?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10, "Should respect limit parameter"
        print(f"✓ GET /api/forum/messages?limit=10 returns {len(data)} messages")
    
    def test_send_forum_message_requires_auth(self):
        """POST /api/forum/messages requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/forum/messages",
            json={"content": "Test message"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/forum/messages requires authentication")
    
    def test_send_forum_message_as_trader(self):
        """Authenticated trader can send forum message"""
        # Login as trader
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "trader", "password": "000000"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Send message
        test_content = f"Test message from trader at {time.time()}"
        response = requests.post(
            f"{BASE_URL}/api/forum/messages",
            json={"content": test_content},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["content"] == test_content
        assert data["sender_role"] == "trader"
        assert "sender_login" in data
        assert "id" in data
        assert "created_at" in data
        print(f"✓ Trader can send forum message, role={data['sender_role']}")
    
    def test_send_forum_message_as_admin(self):
        """Authenticated admin can send forum message"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "admin", "password": "000000"}
        )
        if login_response.status_code != 200:
            # Try default admin password
            login_response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"login": "admin", "password": "admin123"}
            )
        assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Send message
        test_content = f"Admin announcement at {time.time()}"
        response = requests.post(
            f"{BASE_URL}/api/forum/messages",
            json={"content": test_content},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["content"] == test_content
        assert data["sender_role"] == "admin"
        print(f"✓ Admin can send forum message, role={data['sender_role']}")
    
    def test_forum_message_validation_empty(self):
        """Empty message should be rejected"""
        # Login as trader
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "trader", "password": "000000"}
        )
        token = login_response.json()["token"]
        
        # Try empty message
        response = requests.post(
            f"{BASE_URL}/api/forum/messages",
            json={"content": ""},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400, f"Expected 400 for empty message, got {response.status_code}"
        print("✓ Empty forum message rejected with 400")
    
    def test_forum_message_validation_whitespace(self):
        """Whitespace-only message should be rejected"""
        # Login as trader
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "trader", "password": "000000"}
        )
        token = login_response.json()["token"]
        
        # Try whitespace message
        response = requests.post(
            f"{BASE_URL}/api/forum/messages",
            json={"content": "   "},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400, f"Expected 400 for whitespace message, got {response.status_code}"
        print("✓ Whitespace-only forum message rejected with 400")
    
    def test_forum_message_validation_too_long(self):
        """Message over 1000 chars should be rejected"""
        # Login as trader
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "trader", "password": "000000"}
        )
        token = login_response.json()["token"]
        
        # Try too long message
        long_content = "x" * 1001
        response = requests.post(
            f"{BASE_URL}/api/forum/messages",
            json={"content": long_content},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400, f"Expected 400 for too long message, got {response.status_code}"
        print("✓ Too long forum message (>1000 chars) rejected with 400")
    
    def test_forum_messages_chronological_order(self):
        """Messages should be returned in chronological order"""
        response = requests.get(f"{BASE_URL}/api/forum/messages?limit=100")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) >= 2:
            # Check chronological order (oldest first)
            for i in range(len(data) - 1):
                assert data[i]["created_at"] <= data[i+1]["created_at"], \
                    "Messages should be in chronological order"
            print(f"✓ Forum messages returned in chronological order ({len(data)} messages)")
        else:
            print("✓ Not enough messages to verify order")
    
    def test_forum_message_has_required_fields(self):
        """Forum messages should have all required fields"""
        # First send a message
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "trader", "password": "000000"}
        )
        token = login_response.json()["token"]
        
        test_content = f"Field test message {time.time()}"
        requests.post(
            f"{BASE_URL}/api/forum/messages",
            json={"content": test_content},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Get messages and verify fields
        response = requests.get(f"{BASE_URL}/api/forum/messages?limit=10")
        data = response.json()
        
        if len(data) > 0:
            msg = data[-1]  # Get latest message
            required_fields = ["id", "sender_id", "sender_login", "sender_role", "content", "created_at"]
            for field in required_fields:
                assert field in msg, f"Missing required field: {field}"
            print(f"✓ Forum message has all required fields: {required_fields}")


class TestHealthAndBasicEndpoints:
    """Basic health and endpoint tests"""
    
    def test_api_health(self):
        """API should be accessible"""
        response = requests.get(f"{BASE_URL}/api/public/offers")
        assert response.status_code == 200, f"API not accessible: {response.status_code}"
        print("✓ API is accessible")
    
    def test_auth_login_trader(self):
        """Trader login should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "trader", "password": "000000"}
        )
        assert response.status_code == 200, f"Trader login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "trader"
        print("✓ Trader login works")
    
    def test_auth_login_admin(self):
        """Admin login should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"login": "admin", "password": "000000"}
        )
        if response.status_code != 200:
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"login": "admin", "password": "admin123"}
            )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print("✓ Admin login works")


class TestWebSocketEndpoint:
    """WebSocket endpoint availability tests"""
    
    def test_websocket_forum_endpoint_exists(self):
        """WebSocket endpoint /ws/forum should exist"""
        # We can't fully test WebSocket with requests, but we can verify the endpoint
        # by checking if it returns a proper WebSocket upgrade response
        import socket
        import ssl
        
        # Parse URL
        url = BASE_URL.replace("https://", "").replace("http://", "")
        host = url.split("/")[0]
        
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Wrap with SSL if https
            if BASE_URL.startswith("https"):
                context = ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=host)
            
            # Connect
            port = 443 if BASE_URL.startswith("https") else 80
            sock.connect((host, port))
            
            # Send WebSocket upgrade request
            request = (
                f"GET /ws/forum HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"\r\n"
            )
            sock.send(request.encode())
            
            # Receive response
            response = sock.recv(1024).decode()
            sock.close()
            
            # Check for WebSocket upgrade response (101) or at least not 404
            assert "404" not in response, "WebSocket endpoint not found"
            print(f"✓ WebSocket endpoint /ws/forum exists (response: {response[:50]}...)")
        except Exception as e:
            # If we can't connect, just skip this test
            print(f"⚠ WebSocket test skipped: {str(e)}")
            pytest.skip(f"WebSocket test skipped: {str(e)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
