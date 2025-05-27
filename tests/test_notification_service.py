"""
Test script for the notification service.
"""
import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.notification_service import NotificationService


class TestNotificationService(unittest.TestCase):
    """Test cases for the NotificationService."""

    @patch('firebase_admin.messaging')
    @patch('redis.Redis')
    @patch('firebase_admin.credentials.Certificate')
    @patch('firebase_admin.initialize_app')
    def setUp(self, mock_init_app, mock_cert, mock_redis, mock_messaging):
        """Set up test fixtures."""
        # Mock Redis client
        self.mock_redis_instance = MagicMock()
        mock_redis.return_value = self.mock_redis_instance
        
        # Set up the notification service with mocked dependencies
        self.service = NotificationService()
        self.mock_messaging = mock_messaging

    def test_register_device_token(self):
        """Test registering a new device token."""
        self.mock_redis_instance.sadd.return_value = True
        result = self.service.register_device_token("test_token")
        self.assertTrue(result)
        self.mock_redis_instance.sadd.assert_called_with('fcm_device_tokens', "test_token")

    def test_get_device_tokens(self):
        """Test retrieving device tokens."""
        self.mock_redis_instance.smembers.return_value = {"token1", "token2"}
        tokens = self.service.get_device_tokens()
        self.assertEqual(len(tokens), 2)
        self.assertIn("token1", tokens)
        self.assertIn("token2", tokens)

    @patch('firebase_admin.messaging.send_multicast')
    def test_send_suitable_matches_notification(self, mock_send):
        """Test sending notifications about suitable matches."""
        # Mock the return value of get_device_tokens
        self.mock_redis_instance.smembers.return_value = {"token1", "token2"}
        
        # Mock the response from send_multicast
        mock_response = MagicMock()
        mock_response.success_count = 2
        mock_send.return_value = mock_response
        
        # Test data
        matches = [
            {
                "home_team": "Team A",
                "away_team": "Team B",
                "score": "1-0",
                "league": "Premier League",
                "minute": 45
            },
            {
                "home_team": "Team C",
                "away_team": "Team D",
                "score": "2-2",
                "league": "La Liga",
                "minute": 60
            }
        ]
        
        # Call the method and verify result
        result = self.service.send_suitable_matches_notification(matches, len(matches))
        self.assertTrue(result)
        
        # Verify Redis operations
        self.mock_redis_instance.setex.assert_called()
        self.mock_redis_instance.lpush.assert_called()
        self.mock_redis_instance.ltrim.assert_called_with("notifications_list", 0, 99)

    def test_send_fcm_message_example(self):
        """Test sending an FCM message using NotificationService with example data."""
        # Setup the example matches
        example_matches = [
            {
                "home_team": "Team A",
                "away_team": "Team B",
                "score": "1-0",
                "league": "Premier League",
                "minute": 45
            },
            {
                "home_team": "Team C",
                "away_team": "Team D",
                "score": "2-2",
                "league": "La Liga",
                "minute": 60
            },
            {
                "home_team": "Team E",
                "away_team": "Team F",
                "score": "0-1",
                "league": "Bundesliga",
                "minute": 30
            },
            {
                "home_team": "Team G",
                "away_team": "Team H",
                "score": "3-1",
                "league": "Serie A",
                "minute": 75
            }
        ]
        count = len(example_matches)
        
        # Mock get_device_tokens and messaging.send_multicast
        self.mock_redis_instance.smembers.return_value = {"device_token_1", "device_token_2"}
        
        mock_response = MagicMock()
        mock_response.success_count = 2
        self.mock_messaging.send_multicast.return_value = mock_response
        
        # Call the method
        result = self.service.send_suitable_matches_notification(example_matches, count)
        
        # Verify successful execution
        self.assertTrue(result)
        self.mock_messaging.send_multicast.assert_called_once()
        self.assertEqual(self.mock_redis_instance.setex.call_count, 1)
        self.assertEqual(self.mock_redis_instance.lpush.call_count, 1)
        self.assertEqual(self.mock_redis_instance.ltrim.call_count, 1)


def test_send_fcm_manual():
    """
    Manual test function to test sending an actual FCM message.
    This can be used for manual testing with real Firebase configuration.
    
    Note: This test requires actual Firebase credentials and will send actual notifications.
    """
    service = NotificationService()
    
    # You might want to register a test token first
    # service.register_device_token("your_test_device_token")
    
    example_matches = [
        {
            "home_team": "Team A",
            "away_team": "Team B",
            "score": "1-0",
            "league": "Premier League",
            "minute": 45
        },
        {
            "home_team": "Team C",
            "away_team": "Team D",
            "score": "2-2",
            "league": "La Liga",
            "minute": 60
        },
        {
            "home_team": "Team E",
            "away_team": "Team F",
            "score": "0-1",
            "league": "Bundesliga",
            "minute": 30
        },
        {
            "home_team": "Team G",
            "away_team": "Team H",
            "score": "3-1",
            "league": "Serie A",
            "minute": 75
        }
    ]
    count = len(example_matches)
    result = service.send_suitable_matches_notification(example_matches, count)
    print(f"Manual FCM test result: {result}")


if __name__ == "__main__":
    # Run unit tests
    unittest.main()
    
    # For manual testing, uncomment this line:
    # test_send_fcm_manual()
