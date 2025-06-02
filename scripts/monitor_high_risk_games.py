#!/usr/bin/env python3
"""
Monitor high-risk games after a bet is placed for emergency cashout logic.
"""

import json
import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, Any
from bson import ObjectId

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.redis_tracker import get_redis_tracker
from src.rabbitmq_publisher import get_rabbitmq_publisher
from src.mongo_handler import MongoHandler
from src.notification_service import NotificationService  # Add import for notifications

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_cashout_signal(match_id: str, reason: str, extra: Dict[str, Any] = None):
    # Create the signal
    signal = {
        "match_id": match_id,
        "action": "cashout",
        "reason": reason,
        "timestamp": int(time.time())
    }
    if extra:
        signal.update(extra)
    
    # SIMULATION MODE: Don't actually send to RabbitMQ
    logger.info("=" * 80)
    logger.info(f"🔔 SIMULATED CASHOUT SIGNAL for match {match_id}")
    logger.info(f"Reason: {reason}")
    logger.info(f"Details: {json.dumps(signal, indent=2)}")
    logger.info("=" * 80)
    
    # Get match details for the notification
    try:
        mongo_handler = MongoHandler()
        underx_collection = mongo_handler.db["underxmatches"]
        
        match_doc = underx_collection.find_one({"_id": match_id if not ObjectId.is_valid(match_id) else ObjectId(match_id)})
        if not match_doc:
            logger.warning(f"Could not find match {match_id} for notification")
            return
        
        home_team = match_doc.get("homeTeam", "Unknown")
        away_team = match_doc.get("awayTeam", "Unknown")
        live_stats = match_doc.get("liveStats", {})
        current_score = live_stats.get("score", "0-0")
        current_minute = live_stats.get("minute", "?")
        
        # Extract goals scored from reason or get from match data
        goals_scored = 0
        if reason == "2_goals_before_70":
            goals_scored = 2
        elif "3rd_goal" in reason:
            goals_scored = 3
        elif extra and "goals_scored" in extra:
            goals_scored = extra["goals_scored"]
        
        # Send FCM notification with match details
        notification_service = NotificationService()
        
        # Prepare notification data
        title = f"⚠️ CASHOUT ALERT: {home_team} vs {away_team}"
        body = f"{goals_scored} new goals! Score: {current_score} (Minute {current_minute})"
        
        notification_data = {
            "title": title,
            "body": body,
            "icon": "alert",  # This will be used by the client app to show an alert icon
            "match_id": match_id,
            "match_details": {
                "home_team": home_team,
                "away_team": away_team,
                "score": current_score,
                "minute": current_minute,
                "goals_scored": goals_scored,
                "reason": reason
            },
            "action": "cashout",
            "priority": "high"
        }
        
        # Send the notification
        result = notification_service.send_notification(
            title=title,
            body=body,
            data=notification_data
        )
        
        if result:
            logger.info("✅ FCM notification sent successfully")
        else:
            logger.error("❌ Failed to send FCM notification")
        
        # Update MongoDB to simulate a successful cashout
        result = underx_collection.update_one(
            {"_id": match_id if not ObjectId.is_valid(match_id) else ObjectId(match_id)},
            {"$set": {
                "cashout": True,
                "cashoutReason": reason,
                "cashoutTime": int(time.time()),
                "cashoutDetails": signal
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"👍 Successfully updated MongoDB to mark match {match_id} as cashed out")
        else:
            logger.warning(f"⚠️ Failed to update MongoDB for match {match_id}")
        
        mongo_handler.close()
        
        # Also save to Redis for reference
        redis_tracker = get_redis_tracker()
        cashout_key = f"cashout_signals:{match_id}"
        redis_tracker.client.set(cashout_key, json.dumps(signal))
        redis_tracker.client.expire(cashout_key, 86400)  # Expire after 24 hours
        
    except Exception as e:
        logger.error(f"Error simulating cashout in database: {e}")

def parse_score_str(score_str):
    """Parse score string like '1-0', 'HT', 'FT'."""
    if not score_str or score_str in ("HT", "FT"):
        return None, None
    try:
        home, away = score_str.split("-")
        return int(home.strip()), int(away.strip())
    except Exception:
        return None, None

def monitor_high_risk_games():
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

    now = int(time.time())

    # Setup MongoDB connection
    mongo_handler = MongoHandler()
    underx_collection = mongo_handler.db["underxmatches"]

    for match_id in live_game_ids:
        logger.info(f"Processing match_id: {match_id}")
        try:
            # Try to find by string _id, then by ObjectId if valid
            match_doc = underx_collection.find_one({"_id": match_id})
            if not match_doc and ObjectId.is_valid(match_id):
                match_doc = underx_collection.find_one({"_id": ObjectId(match_id)})
            if not match_doc:
                logger.info(f"No underxmatches doc found for match_id: {match_id}")
                continue

            # Print teams, time, and score for the live game (always)
            home_team = match_doc.get("homeTeam", "N/A")
            away_team = match_doc.get("awayTeam", "N/A")
            live_stats = match_doc.get("liveStats", {})
            mongo_score_str = live_stats.get("score")
            mongo_minute = live_stats.get("minute")
            logger.info(f"Live: {home_team} vs {away_team} | Minute: {mongo_minute} | Score: {mongo_score_str}")

            # Get score from bet_scores:{match_id}
            bet_score_key = f"bet_scores:{match_id}"
            bet_score_json = redis_tracker.client.get(bet_score_key)
            if not bet_score_json:
                logger.info(f"No bet_score found for match_id: {match_id}")
                continue
            import json
            bet_score = json.loads(bet_score_json)
            bet_home = bet_score.get("homeScore")
            bet_away = bet_score.get("awayScore")
            bet_timestamp = bet_score.get("timestamp", 0)

            # If a bet was placed, show the bet minute and score
            bet_minute = match_doc.get("betGameTime")
            if bet_home is not None and bet_away is not None and bet_minute is not None:
                logger.info(f"Bet placed at minute {bet_minute} with score: {bet_home}-{bet_away}")

            # Check MongoDB for cashout property
            if match_doc.get("cashout", False):
                logger.info(f"Skipping match {match_id}: cashout already performed in MongoDB.")
                continue

            live_stats = match_doc.get("liveStats", {})
            mongo_score_str = live_stats.get("score")
            mongo_minute = live_stats.get("minute")
            mongo_home, mongo_away = parse_score_str(mongo_score_str)

            # Compare scores, skip if not matching and not None
            if mongo_home is not None and mongo_away is not None:
                if bet_home != mongo_home or bet_away != mongo_away:
                    # A goal has been scored if the MongoDB score is ahead of the Redis score
                    bet_total = (bet_home or 0) + (bet_away or 0)
                    mongo_total = (mongo_home or 0) + (mongo_away or 0)
                    if mongo_total > bet_total:
                        # Goal(s) detected since last bet_score update
                        goals_scored = mongo_total - bet_total
                        logger.info(f"Detected {goals_scored} new goal(s) in match {match_id}: Redis {bet_home}-{bet_away} -> Mongo {mongo_home}-{mongo_away}")
                        # Use mongo_minute if it's a number, else skip minute-based logic
                        try:
                            minute_val = int(mongo_minute)
                        except Exception:
                            minute_val = None
                        # High-risk logic
                        if goals_scored == 2 and minute_val is not None and minute_val < 70:
                            send_cashout_signal(match_id, "2_goals_before_70")
                        elif goals_scored == 3 and minute_val is not None and minute_val < 82:
                            send_cashout_signal(match_id, "3rd_goal_before_82")
                        elif goals_scored == 3 and minute_val is not None and 82 <= minute_val < 85:
                            send_cashout_signal(match_id, "3rd_goal_after_82_before_85")
                    else:
                        logger.info(f"Skipping match {match_id}: Redis score {bet_home}-{bet_away} != Mongo score {mongo_home}-{mongo_away}")
                    continue

            # Get high risk game data if present
            high_risk_data = redis_tracker.client.hget("high_risk_game", match_id)
            game = None
            try:
                if high_risk_data:
                    game = json.loads(high_risk_data)
            except Exception:
                continue
            if not game:
                continue

            # No need to fetch events or use get_match_events
            # All goal detection is handled by score comparison above

        except Exception as e:
            logger.error(f"Error monitoring high risk game {match_id}: {e}")

    mongo_handler.close()

def main():
    while True:
        monitor_high_risk_games()
        time.sleep(30)

if __name__ == "__main__":
    main()
