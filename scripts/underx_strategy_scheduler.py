#!/usr/bin/env python3
"""
Scheduler to run the UnderX In-Play strategy against live matches every 60 seconds.
"""
import logging
import sys
import os
import time
import schedule
from datetime import datetime

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.underx_match_handler import get_underx_match_handler
from scripts.under_x_inplay import UnderXInPlayStrategy
from src.notification_service import NotificationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_live_matches():
    """
    Fetch live matches from Redis/MongoDB and analyze them with the UnderX strategy.
    """
    logger.info("=" * 80)
    logger.info("ANALYZING LIVE MATCHES WITH UNDER X IN-PLAY STRATEGY")
    logger.info("-" * 80)
    
    try:
        # Get match handler and strategy
        match_handler = get_underx_match_handler()
        strategy = UnderXInPlayStrategy()
        notification_service = NotificationService()
        
        # Get live matches data
        live_matches = match_handler.get_live_match_data()
        
        if not live_matches:
            logger.info("No live matches found for analysis")
            return
        
        logger.info(f"Found {len(live_matches)} live matches for analysis")
        
        # Analyze matches
        results = strategy.analyze_live_matches(live_matches)
        
        # Count suitable matches and skipped matches
        suitable_matches = [result for result in results if result.get("is_suitable", False)]
        skipped_matches = [result for result in results if result.get("skipped") and result.get("reason") == "bet already placed"]
        
        suitable_count = len(suitable_matches)
        skipped_count = len(skipped_matches)
        
        # Log information about skipped matches
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} matches that already have bets placed:")
            for match in skipped_matches[:5]:  # Show the first 5 at most to keep logs manageable
                match_id = match.get("match_id", "unknown")
                logger.info(f"  - Match ID: {match_id}")
            if skipped_count > 5:
                logger.info(f"  - ... and {skipped_count - 5} more")
        
        # If suitable matches found, send push notification
        if suitable_count > 0:
            logger.info(f"Sending notification for {suitable_count} matches...")
            try:
                result = notification_service.send_suitable_matches_notification(suitable_matches, suitable_count)
                if result:
                    logger.info("✅ Notification sent successfully")
                else:
                    logger.error("❌ Failed to send notification")
                    logger.error("This could be due to invalid device tokens or Firebase configuration issues.")
            except Exception as e:
                logger.error(f"❌ Exception while sending notification: {e}")
            logger.info(f"Push notification sent for {suitable_count} suitable matches")
        
        logger.info("-" * 80)
        logger.info(f"Analysis complete: {len(live_matches)} total, {skipped_count} skipped, {suitable_count} suitable for betting")
        logger.info("=" * 80)
        
        # Close connections
        match_handler.close()
        
    except Exception as e:
        logger.error(f"Error analyzing live matches: {e}")


def main():
    """Main entry point for the scheduler."""
    logger.info("Starting UnderX In-Play Strategy Scheduler")
    
    # Run once immediately on startup
    analyze_live_matches()
    
    # Schedule to run every 60 seconds
    schedule.every(60).seconds.do(analyze_live_matches)
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
