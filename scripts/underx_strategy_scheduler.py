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
        
        # Get live matches data
        live_matches = match_handler.get_live_match_data()
        
        if not live_matches:
            logger.info("No live matches found for analysis")
            return
        
        logger.info(f"Found {len(live_matches)} live matches for analysis")
        
        # Analyze matches
        results = strategy.analyze_live_matches(live_matches)
        
        # Count suitable matches
        suitable_count = sum(1 for result in results if result.get("is_suitable", False))
        
        logger.info("-" * 80)
        logger.info(f"Analysis complete: {suitable_count} out of {len(results)} matches are suitable for betting")
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
