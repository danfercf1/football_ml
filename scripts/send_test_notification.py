#!/usr/bin/env python3
"""
Script for sending test FCM notifications using the NotificationService.
This script sends actual notifications to registered devices.
"""
import os
import sys
import argparse
import logging

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.notification_service import NotificationService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_firebase_config():
    """Check if Firebase configuration exists and is correctly set up."""
    # Check if service account file exists
    cred_path = os.path.join(
        project_root, 'config', 'firebase-service-account.json'
    )
    if not os.path.exists(cred_path):
        logger.error(f"Firebase service account file not found at {cred_path}")
        logger.error("Please make sure you have placed your Firebase credentials file at the correct location")
        return False
    
    # Try to read the file to see if it's valid JSON
    try:
        import json
        with open(cred_path, 'r') as f:
            cred_data = json.load(f)
            
        # Check for required keys in the service account file
        required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_keys = [key for key in required_keys if key not in cred_data]
        
        if missing_keys:
            logger.error(f"Firebase credentials file is missing required keys: {', '.join(missing_keys)}")
            return False
        
        # Store project_id as a global variable for error handling
        global firebase_project_id
        firebase_project_id = cred_data.get('project_id')
        logger.info(f"Firebase configuration file looks valid (Project: {firebase_project_id})")
        return True
    except json.JSONDecodeError:
        logger.error(f"Firebase credentials file is not valid JSON")
        return False
    except Exception as e:
        logger.error(f"Error checking Firebase configuration: {str(e)}")
        return False

def main():
    """Main function to send a test FCM notification."""
    global firebase_project_id
    firebase_project_id = None
    
    # Check Firebase configuration first
    if not check_firebase_config():
        logger.error("Firebase configuration check failed. Please fix the issues above.")
        return 1
        
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Send a test FCM notification.')
    parser.add_argument('--token', help='FCM device token to send notification to')
    parser.add_argument('--register-only', action='store_true', 
                        help='Only register the token without sending a notification')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    args = parser.parse_args()
    
    # Enable more detailed logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('firebase_admin').setLevel(logging.DEBUG)
    
    # Create notification service
    try:
        service = NotificationService()
    except Exception as e:
        logger.error(f"Failed to initialize NotificationService: {e}")
        logger.error("Check your Firebase configuration and permissions.")
        return 1
    
    # If token provided, register it
    if args.token:
        logger.info(f"Registering device token: {args.token}")
        result = service.register_device_token(args.token)
        if result:
            logger.info("Token registered successfully")
        else:
            logger.error("Failed to register token")
            return 1
        
        # If only registering, exit
        if args.register_only:
            return 0
    
    # Check if we have any registered tokens
    tokens = service.get_device_tokens()
    if not tokens:
        logger.error("No device tokens registered. Please provide a token with --token")
        return 1
    
    logger.info(f"Found {len(tokens)} registered device tokens")
    
    # Create example matches
    example_matches = [
        {
            "home_team": "Arsenal",
            "away_team": "Manchester United",
            "score": "2-1",
            "league": "Premier League",
            "minute": 75
        },
        {
            "home_team": "Barcelona",
            "away_team": "Real Madrid",
            "score": "1-1",
            "league": "La Liga",
            "minute": 60
        },
        {
            "home_team": "Bayern Munich",
            "away_team": "Borussia Dortmund",
            "score": "3-2",
            "league": "Bundesliga",
            "minute": 82
        },
        {
            "home_team": "Juventus",
            "away_team": "AC Milan",
            "score": "0-0",
            "league": "Serie A",
            "minute": 55
        }
    ]
    
    # Send notification
    count = len(example_matches)
    logger.info(f"Sending notification for {count} matches...")
    try:
        result = service.send_suitable_matches_notification(example_matches, count)
        
        if result:
            logger.info("✅ Notification sent successfully")
            return 0
        else:
            logger.error("❌ Failed to send notification")
            logger.error("This could be due to invalid device tokens or Firebase configuration issues.")
            return 1
    except Exception as e:
        logger.error(f"❌ Exception while sending notification: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
