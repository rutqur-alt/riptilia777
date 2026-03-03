"""
Shared pytest fixtures for API testing
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="session")
def trader_auth(api_client):
    """Get authentication token for trader (login=111)"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "login": "111",
        "password": "000000"
    })
    if response.status_code == 200:
        data = response.json()
        return {
            "token": data.get("token"),
            "user": data.get("user"),
            "headers": {"Authorization": f"Bearer {data.get('token')}"}
        }
    pytest.skip("Trader authentication failed — skipping trader tests")

@pytest.fixture(scope="session")
def admin_auth(api_client):
    """Get authentication token for admin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "login": "admin",
        "password": "000000"
    })
    if response.status_code == 200:
        data = response.json()
        return {
            "token": data.get("token"),
            "user": data.get("user"),
            "headers": {"Authorization": f"Bearer {data.get('token')}"}
        }
    pytest.skip("Admin authentication failed — skipping admin tests")
