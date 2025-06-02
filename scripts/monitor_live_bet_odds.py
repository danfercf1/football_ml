#!/usr/bin/env python3
"""
Monitor live bet games and request updated odds information every minute.
Sends 'get_odds' requests to the betfair_bets queue for each live match.
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, List
from bson import ObjectId

# Setup path to include project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.redis_tracker import get_redis_tracker
from src.mongo_handler import MongoHandler
from src.rabbitmq_publisher import get_rabbitmq_publisher  # Use the existing publisher utility

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_odds_request(match_id: str, rabbitmq_queue: str = "betfair_bets"):
    """
    Send a request for odds updates to the RabbitMQ queue.
    
    Args:
        match_id: The ID of the match to request odds for
        rabbitmq_queue: The name of the target RabbitMQ queue
    """
    # Create the message payload - ensure exact format matching the example
    message = {
        "type": "get_odds",
        "matchType": "underXmatch",
        "matchId": str(match_id)  # Ensure match_id is a string
    }
    
    # Check for simulation mode
    simulation_mode = os.environ.get("SIMULATION_MODE", "false").lower() in ("true", "1", "yes")
    
    if simulation_mode:
        # Simulation mode - just log the message
        logger.info("=" * 60)
        logger.info(f"🔄 SIMULATED ODDS REQUEST for match {match_id}")
        logger.info(f"Queue: {rabbitmq_queue}")
        logger.info(f"Message: {json.dumps(message, indent=2)}")  # Pretty print JSON for logs
        logger.info("=" * 60)
        return True
    
    # Try to send message to RabbitMQ using the publisher utility
    try:
        # Get the publisher instance
        publisher = get_rabbitmq_publisher()
        
        # Ensure we're sending to betfair_bets queue specifically
        queue_name = "betfair_bets"
        
        # Use the general publish method
        success = publisher.publish_message(
            queue_name=queue_name,
            message=message,
            routing_key=queue_name
        )
        
        # Close the connection
        publisher.close()
        
        if success:
            logger.debug(f"Sent odds request for match {match_id} to {queue_name} queue")
            return True
        else:
            raise Exception("Publisher returned False")
    
    except Exception as e:
        logger.error(f"Error sending odds request for match {match_id}: {e}")
        
        # Fall back to simulation mode when errors occur
        logger.info("Falling back to simulation mode")
        logger.info("=" * 60)
        logger.info(f"🔄 FALLBACK SIMULATED ODDS REQUEST for match {match_id}")
        logger.info(f"Message: {json.dumps(message)}")
        logger.info("=" * 60)
        
        # Also log the odds request to a file for retry later
        try:
            os.makedirs(os.path.dirname("/home/daniel/Projects/football_ml/logs/"), exist_ok=True)
            with open(f"/home/daniel/Projects/football_ml/logs/failed_odds_requests.json", "a") as f:
                f.write(json.dumps({
                    "timestamp": int(time.time()),
                    "match_id": match_id,
                    "message": message
                }) + "\n")
        except Exception as file_error:
            logger.error(f"Failed to log failed request to file: {file_error}")
        
        return True  # Return true to avoid repeated errors in logs

def monitor_live_bet_odds():
    """
    Monitor all live games where bets have been placed and request updated odds.
    """
    logger.info("=" * 80)
    logger.info("MONITORING LIVE BET GAMES FOR ODDS UPDATES")
    logger.info("-" * 80)
    
    redis_tracker = get_redis_tracker()
    
    # Get all live games from Redis (keys like live_games:{match_id})
    live_game_keys = redis_tracker.client.keys("live_games:*")
    live_game_ids = []
    
    for key in live_game_keys:
        if isinstance(key, bytes):
            key = key.decode()
        # Extract match_id after the colon
        parts = key.split(":")
        if len(parts) == 2:
            live_game_ids.append(parts[1])
    
    if not live_game_ids:
        logger.info("No live games found in Redis")
        return
    
    logger.info(f"Found {len(live_game_ids)} live games")
    
    # Setup MongoDB connection
    mongo_handler = MongoHandler()
    underx_collection = mongo_handler.db["underxmatches"]
    
    # Track matches we've sent requests for
    requested_matches = []
    
    for match_id in live_game_ids:
        try:
            # Try to find by string _id, then by ObjectId if valid
            match_doc = underx_collection.find_one({"_id": match_id})
            if not match_doc and ObjectId.is_valid(match_id):
                match_doc = underx_collection.find_one({"_id": ObjectId(match_id)})
            
            if not match_doc:
                logger.debug(f"No underxmatches doc found for match_id: {match_id}")
                continue
            
            # Get match details for logging
            home_team = match_doc.get("homeTeam", "N/A")
            away_team = match_doc.get("awayTeam", "N/A")
            live_stats = match_doc.get("liveStats", {})
            mongo_score_str = live_stats.get("score", "N/A")
            mongo_minute = live_stats.get("minute", "N/A")
            
            # Check if game is finished
            is_finished = mongo_minute == "FT"
            if is_finished:
                logger.debug(f"Skipping finished match: {home_team} vs {away_team}")
                continue
            
            # Parse the score to determine if it's not 0-0
            score_not_zero = False
            try:
                if mongo_score_str != "N/A":
                    score_parts = mongo_score_str.split("-")
                    if len(score_parts) == 2:
                        home_goals = int(score_parts[0].strip())
                        away_goals = int(score_parts[1].strip())
                        score_not_zero = (home_goals > 0 or away_goals > 0)
            except (ValueError, IndexError):
                logger.debug(f"Failed to parse score: {mongo_score_str}")
            
            # Request odds for matches with active bets OR with scores different from 0-0
            if (match_doc.get("bet") is True and not match_doc.get("cashout", False)) or score_not_zero:
                logger.info(f"Requesting odds for: {home_team} vs {away_team} | Minute: {mongo_minute} | Score: {mongo_score_str}")
                
                # Send the odds request
                success = send_odds_request(str(match_doc.get("_id")))
                if success:
                    requested_matches.append(match_id)
                    if score_not_zero and not match_doc.get("bet"):
                        logger.info(f"  ↳ Requested because score is not 0-0")
                    elif match_doc.get("bet") is True:
                        logger.info(f"  ↳ Requested because active bet exists")
            else:
                logger.debug(f"Skipping odds request for {home_team} vs {away_team} - No active bet and score is 0-0")
        
        except Exception as e:
            logger.error(f"Error processing match {match_id} for odds request: {e}")
    
    # Summary
    logger.info(f"Sent odds update requests for {len(requested_matches)} out of {len(live_game_ids)} live matches")
    logger.info("=" * 80)
    
    # Close MongoDB connection
    mongo_handler.close()

def main():
    """Main function to run the odds monitor at regular intervals."""
    logger.info("Starting live bet odds monitor")
    
    while True:
        try:
            monitor_live_bet_odds()
            # Wait for 1 minute before checking again
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            # Still wait before trying again
            time.sleep(60)

if __name__ == "__main__":
    main()
