"""
Test Notification Count Consistency Bug Fix

Bug: Header badge showed different number than actual notification list
Root cause: /api/notifications/sidebar-badges was using max() instead of sum
Fix: Changed to event_notifications_count + old_notifications_count

Test scenarios:
1. sidebar-badges total matches event-notifications/unread-count
2. Both endpoints sum from event_notifications AND notifications collections
3. Mark all as read clears both systems and returns 0
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def testtrader2_auth():
    """Authenticate as testtrader2 (test user with known notification data)"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "login": "testtrader2",
        "password": "test123"
    })
    
    if response.status_code != 200:
        pytest.skip(f"testtrader2 authentication failed: {response.text}")
    
    data = response.json()
    session.headers.update({"Authorization": f"Bearer {data['token']}"})
    return {
        "session": session,
        "token": data["token"],
        "user": data["user"]
    }


class TestNotificationCountConsistency:
    """Tests for notification count consistency between endpoints"""
    
    def test_sidebar_badges_returns_event_notifications(self, testtrader2_auth):
        """Test that sidebar-badges endpoint returns event_notifications field"""
        session = testtrader2_auth["session"]
        
        response = session.get(f"{BASE_URL}/api/notifications/sidebar-badges")
        assert response.status_code == 200, f"sidebar-badges failed: {response.text}"
        
        data = response.json()
        assert "event_notifications" in data, "Missing event_notifications field in sidebar-badges"
        assert "total" in data, "Missing total field in sidebar-badges"
        assert isinstance(data["event_notifications"], int), "event_notifications should be int"
        assert isinstance(data["total"], int), "total should be int"
    
    def test_unread_count_returns_count(self, testtrader2_auth):
        """Test that event-notifications/unread-count returns count field"""
        session = testtrader2_auth["session"]
        
        response = session.get(f"{BASE_URL}/api/event-notifications/unread-count")
        assert response.status_code == 200, f"unread-count failed: {response.text}"
        
        data = response.json()
        assert "count" in data, "Missing count field in unread-count"
        assert isinstance(data["count"], int), "count should be int"
    
    def test_notification_counts_are_consistent(self, testtrader2_auth):
        """
        CRITICAL TEST: sidebar-badges.event_notifications MUST equal unread-count.count
        This was the bug - max() made them inconsistent, sum() fixes it
        """
        session = testtrader2_auth["session"]
        
        # Get sidebar badges
        badges_response = session.get(f"{BASE_URL}/api/notifications/sidebar-badges")
        assert badges_response.status_code == 200
        badges_data = badges_response.json()
        
        # Get unread count
        count_response = session.get(f"{BASE_URL}/api/event-notifications/unread-count")
        assert count_response.status_code == 200
        count_data = count_response.json()
        
        sidebar_count = badges_data["event_notifications"]
        unread_count = count_data["count"]
        
        assert sidebar_count == unread_count, (
            f"CONSISTENCY BUG! sidebar-badges.event_notifications ({sidebar_count}) "
            f"!= unread-count.count ({unread_count}). "
            f"These must be equal for notification badge consistency."
        )
    
    def test_total_equals_event_notifications_for_user(self, testtrader2_auth):
        """
        Test that sidebar-badges total equals event_notifications (unified count)
        """
        session = testtrader2_auth["session"]
        
        response = session.get(f"{BASE_URL}/api/notifications/sidebar-badges")
        assert response.status_code == 200
        data = response.json()
        
        # The total should use the combined_notifications value
        assert data["total"] == data["event_notifications"], (
            f"total ({data['total']}) should equal event_notifications ({data['event_notifications']})"
        )
    
    def test_get_event_notifications_list(self, testtrader2_auth):
        """Test that event-notifications list endpoint works"""
        session = testtrader2_auth["session"]
        
        response = session.get(f"{BASE_URL}/api/event-notifications")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Event notifications should return a list"
    
    def test_notification_list_count_matches_unread_count(self, testtrader2_auth):
        """
        Verify the actual notification list count matches the unread-count endpoint
        """
        session = testtrader2_auth["session"]
        
        # Get the list of unread notifications
        list_response = session.get(f"{BASE_URL}/api/event-notifications?include_read=false")
        assert list_response.status_code == 200
        notifications_list = list_response.json()
        
        # Get the count
        count_response = session.get(f"{BASE_URL}/api/event-notifications/unread-count")
        assert count_response.status_code == 200
        count_data = count_response.json()
        
        list_count = len(notifications_list)
        api_count = count_data["count"]
        
        assert list_count == api_count, (
            f"Notification list length ({list_count}) != unread-count ({api_count}). "
            f"Both should return the same number of notifications."
        )


class TestMarkAllAsRead:
    """Tests for mark-all-as-read functionality"""
    
    @pytest.fixture(scope="class")
    def fresh_trader_auth(self):
        """Get fresh authentication for mark-as-read tests"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "login": "testtrader2",
            "password": "test123"
        })
        
        if response.status_code != 200:
            pytest.skip("Authentication failed for mark-as-read tests")
        
        data = response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    def test_mark_all_as_read_endpoint(self, fresh_trader_auth):
        """Test mark all as read endpoint exists and responds"""
        session = fresh_trader_auth
        
        response = session.post(
            f"{BASE_URL}/api/event-notifications/mark-read",
            json={"all": True}
        )
        
        # Should succeed (even if nothing to mark)
        assert response.status_code == 200, f"mark-read failed: {response.text}"
        data = response.json()
        assert "marked" in data, "Response should include 'marked' count"
    
    def test_counts_zero_after_mark_all_read(self, fresh_trader_auth):
        """
        After marking all as read, both endpoints should return 0
        """
        session = fresh_trader_auth
        
        # Mark all as read
        mark_response = session.post(
            f"{BASE_URL}/api/event-notifications/mark-read",
            json={"all": True}
        )
        assert mark_response.status_code == 200
        
        # Check sidebar-badges
        badges_response = session.get(f"{BASE_URL}/api/notifications/sidebar-badges")
        assert badges_response.status_code == 200
        badges_data = badges_response.json()
        
        # Check unread-count
        count_response = session.get(f"{BASE_URL}/api/event-notifications/unread-count")
        assert count_response.status_code == 200
        count_data = count_response.json()
        
        # Both should be 0 after marking all as read
        assert count_data["count"] == 0, f"unread-count should be 0, got {count_data['count']}"
        assert badges_data["event_notifications"] == 0, (
            f"sidebar-badges.event_notifications should be 0, got {badges_data['event_notifications']}"
        )
        
        # And they should still be consistent (both 0)
        assert badges_data["event_notifications"] == count_data["count"], (
            "After mark-all-read, both endpoints should return 0"
        )


class TestEdgeCases:
    """Edge case tests for notification consistency"""
    
    def test_no_auth_sidebar_badges(self):
        """Test sidebar-badges requires authentication"""
        response = requests.get(f"{BASE_URL}/api/notifications/sidebar-badges")
        assert response.status_code in [401, 403], "sidebar-badges should require auth"
    
    def test_no_auth_unread_count(self):
        """Test unread-count requires authentication"""
        response = requests.get(f"{BASE_URL}/api/event-notifications/unread-count")
        assert response.status_code in [401, 403], "unread-count should require auth"
    
    def test_invalid_mark_read_body(self, testtrader2_auth):
        """Test mark-read with invalid body returns error"""
        session = testtrader2_auth["session"]
        
        response = session.post(
            f"{BASE_URL}/api/event-notifications/mark-read",
            json={}  # Empty body - should fail
        )
        
        # Should return 400 bad request
        assert response.status_code == 400, "Empty body should return 400"
