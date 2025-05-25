#!/usr/bin/env python3
"""
Cron script to find live UnderX matches and store them in Redis.
"""
import logging
import sys
import os
import time
from datetime import datetime

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.underx_match_handler import get_underx_match_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_live_games():
    """
    Find today's live games and save them to Redis.
    """
    logger.info("Starting live games crawler...")
    
    try:
        handler = get_underx_match_handler()
        
        # Find and save today's live games
        success = handler.save_live_games_to_redis()
        
        if success:
            logger.info("Live games successfully saved to Redis")
        else:
            logger.error("Failed to save live games to Redis")
            
        handler.close()
        
    except Exception as e:
        logger.error(f"Error in live games crawler: {e}")


def main():
    """Main entry point for the script."""
    find_live_games()


if __name__ == "__main__":
    main()
