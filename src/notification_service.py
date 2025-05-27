"""
Notification Service for sending push notifications to mobile devices.
"""
import os
import json
import logging
import time
import firebase_admin
from firebase_admin import credentials, messaging
import redis

logger = logging.getLogger(__name__)

class NotificationService:
    """Service to handle push notifications to mobile devices."""
    
    def __init__(self):
        """Initialize the notification service with Firebase."""
        try:
            # Path to Firebase service account key
            cred_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config',
                'firebase-service-account.json'
            )
            
            # Initialize Firebase if not already initialized
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            
            # Connect to Redis to get device tokens
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=int(os.getenv('REDIS_DB', 0)),
                decode_responses=True
            )
            
            logger.info("NotificationService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize NotificationService: {e}")
    
    def get_device_tokens(self):
        """Retrieve all registered device tokens from Redis."""
        try:
            tokens = self.redis_client.smembers('fcm_device_tokens')
            return list(tokens) if tokens else []
        except Exception as e:
            logger.error(f"Error retrieving device tokens: {e}")
            return []
    
    def register_device_token(self, token):
        """Register a new device token."""
        try:
            self.redis_client.sadd('fcm_device_tokens', token)
            logger.info(f"Device token registered successfully")
            return True
        except Exception as e:
            logger.error(f"Error registering device token: {e}")
            return False
    
    def send_suitable_matches_notification(self, matches, count):
        """Send notification for suitable betting matches."""
        try:
            tokens = self.get_device_tokens()
            if not tokens:
                logger.warning("No device tokens found. Notification not sent.")
                return False

            # Create a summary of matches for the notification
            match_info = []
            match_ids = []
            for match in matches[:3]:  # Limit to 3 matches in the notification
                match_info.append(f"{match.get('home_team', '')} vs {match.get('away_team', '')}")
            for match in matches:
                if "match_id" in match:
                    match_ids.append(match["match_id"])

            # More match info is available
            more_info = ""
            if count > 3:
                more_info = f" and {count-3} more"

            # Android specific notification settings
            android_config = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='notification_icon',
                    color='#4CAF50',
                    sound='default',
                    channel_id='betting_alerts',
                    click_action='FLUTTER_NOTIFICATION_CLICK'  # This is correct for Android
                )
            )

            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=f"Betting Opportunity: {count} Suitable Matches",
                    body=f"{', '.join(match_info)}{more_info}. Tap to view details."
                ),
                android=android_config,
                # Remove APNS config if only targeting Android/Kotlin
                data={
                    "type": "suitable_matches",
                    "match_count": str(count),
                    "timestamp": str(int(time.time())),
                    "click_action": "FLUTTER_NOTIFICATION_CLICK"
                },
                tokens=tokens
            )

            # Use the new recommended method
            response = messaging.send_each_for_multicast(message)

            failed_tokens = []
            if hasattr(response, "responses"):
                for idx, resp in enumerate(response.responses):
                    if resp.success:
                        logger.info(f"Notification to token {tokens[idx]}: SUCCESS")
                    else:
                        logger.error(f"Notification to token {tokens[idx]}: FAILURE - {resp.exception}")
                        # Handle specific errors, e.g., SenderId mismatch
                        if resp.exception and "SenderId mismatch" in str(resp.exception):
                            failed_tokens.append(tokens[idx])
            if failed_tokens:
                logger.error(f"The following tokens failed due to SenderId mismatch: {failed_tokens}")
                logger.error(
                    "SenderId mismatch means the token was generated for a different Firebase project. "
                    "Make sure the device is registered with the correct Firebase project (project_id) "
                    "that matches your service account."
                )

            # response is a BatchResponse object with .responses and .success_count
            success_count = sum(1 for r in response.responses if r.success)
            logger.info(f"Successfully sent {success_count} notifications")

            # Save notification to Redis for history/retrieval by the app
            notification_data = {
                "title": f"Betting Opportunity: {count} Suitable Matches",
                "body": f"{', '.join(match_info)}{more_info}. Tap to view details.",
                "match_count": count,
                "timestamp": int(time.time()),
                "match_ids": match_ids,  # Save match IDs in the notification data
                "matches": [
                    {
                        "match_id": match.get("match_id", ""),
                        "home_team": match.get("home_team", ""),
                        "away_team": match.get("away_team", ""),
                        "score": match.get("score", ""),
                        "league": match.get("league", ""),
                        "minute": match.get("minute", 0)
                    } 
                    for match in matches
                ]
            }

            # Save notification in Redis with TTL of 24 hours (86400 seconds)
            notification_id = f"notification:{int(time.time())}"
            self.redis_client.setex(notification_id, 86400, json.dumps(notification_data))
            # Add to notification list for the app to query
            self.redis_client.lpush("notifications_list", notification_id)
            self.redis_client.ltrim("notifications_list", 0, 99)  # Keep only last 100 notifications

            # Map notification to each device token
            for token in tokens:
                device_notifications_key = f"device_notifications:{token}"
                self.redis_client.lpush(device_notifications_key, notification_id)
                self.redis_client.ltrim(device_notifications_key, 0, 49)  # Keep last 50 notifications per device

            print(f"Notification saved with ID: {notification_id}")
            logger.info(f"Notification sent successfully to {success_count} devices")

            return success_count > 0
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
