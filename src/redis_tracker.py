import json
import time
import logging
import redis
import os
from typing import Dict, Any, List, Optional, Tuple

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class RedisTracker:
    """
    Class to track match states and bets in Redis.
    """
    def __init__(self):
        """Initialize Redis connection from environment variables."""
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_password = os.getenv('REDIS_PASSWORD', '')
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.ttl = int(os.getenv('REDIS_TTL', 86400))  # Default 24 hours
        
        # Connect to Redis
        self.client = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish connection to Redis server."""
        try:
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                decode_responses=True
            )
            logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        if not self.client:
            return False
        try:
            return self.client.ping()
        except:
            return False
    
    def track_bet(self, match_id: str, bet_details: Dict[str, Any]) -> bool:
        """
        Track a bet placed on a match.
        
        Args:
            match_id: Unique ID for the match
            bet_details: Dictionary with bet details
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            logger.error("Cannot track bet - Redis not connected")
            return False
            
        try:
            # Create a key for this bet
            key = f"bet:{match_id}"
            
            # Add timestamp for when bet was placed
            bet_details["timestamp"] = int(time.time())
            
            # Set TTL to 60 minutes (3600 seconds)
            self.client.set(key, json.dumps(bet_details), ex=3600)
            logger.info(f"Tracked bet for match {match_id} in Redis (TTL: 60 minutes)")
            return True
        except Exception as e:
            logger.error(f"Error tracking bet in Redis: {e}")
            return False
    
    def track_goal_event(self, match_id: str, event_type: str, 
                         minute: int, score: str, team: str = None) -> bool:
        """
        Track a goal event for a match.
        
        Args:
            match_id: Unique ID for the match
            event_type: Type of event (goal, goal_canceled, var_check)
            minute: Match minute when event occurred
            score: Current score after event
            team: Team that scored (home/away)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            logger.error("Cannot track goal event - Redis not connected")
            return False
            
        try:
            # Create a key for this match's events
            key = f"match_events:{match_id}"
            
            # Create event data
            event_data = {
                "type": event_type,
                "minute": minute,
                "score": score,
                "team": team,
                "timestamp": int(time.time())
            }
            
            # Store event in Redis list
            self.client.rpush(key, json.dumps(event_data))
            self.client.expire(key, self.ttl)
            
            logger.info(f"Tracked {event_type} for match {match_id} at minute {minute}")
            return True
        except Exception as e:
            logger.error(f"Error tracking goal event in Redis: {e}")
            return False
    
    def get_bet_details(self, match_id: str) -> Optional[Dict[str, Any]]:
        """
        Get bet details for a match.
        
        Args:
            match_id: Unique ID for the match
            
        Returns:
            Dictionary with bet details or None if not found
        """
        if not self.is_connected():
            logger.error("Cannot get bet details - Redis not connected")
            return None
            
        try:
            key = f"bet:{match_id}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting bet details from Redis: {e}")
            return None
    
    def get_match_events(self, match_id: str) -> List[Dict[str, Any]]:
        """
        Get all goal events for a match.
        
        Args:
            match_id: Unique ID for the match
            
        Returns:
            List of event dictionaries
        """
        if not self.is_connected():
            logger.error("Cannot get match events - Redis not connected")
            return []
            
        try:
            key = f"match_events:{match_id}"
            events = self.client.lrange(key, 0, -1)
            return [json.loads(event) for event in events]
        except Exception as e:
            logger.error(f"Error getting match events from Redis: {e}")
            return []
    
    def check_for_canceled_goals(self, match_id: str, 
                                current_score: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if any goals have been canceled since the bet was placed.
        
        Args:
            match_id: Unique ID for the match
            current_score: Current score to compare with
            
        Returns:
            Tuple of (has_canceled_goals, bet_details)
        """
        if not self.is_connected():
            logger.error("Cannot check for canceled goals - Redis not connected")
            return False, None
            
        try:
            # Get bet details
            bet_details = self.get_bet_details(match_id)
            if not bet_details:
                logger.info(f"No bet found for match {match_id}")
                return False, None
                
            # Compare scores
            bet_score = bet_details.get("score", "0 - 0")
            
            # Parse scores
            try:
                bet_home, bet_away = map(int, bet_score.split(" - "))
                current_home, current_away = map(int, current_score.split(" - "))
                
                # If current score is lower than bet score, a goal was canceled
                if current_home + current_away < bet_home + bet_away:
                    logger.warning(f"Goal cancelation detected for match {match_id}: " +
                                  f"Bet placed at {bet_score}, now {current_score}")
                    return True, bet_details
                
                return False, bet_details
                
            except (ValueError, TypeError):
                logger.error(f"Error parsing scores - bet: {bet_score}, current: {current_score}")
                return False, bet_details
                
        except Exception as e:
            logger.error(f"Error checking for canceled goals: {e}")
            return False, None
    
    def close(self):
        """Close the Redis connection."""
        if self.client:
            self.client.close()
            logger.info("Redis connection closed")

def get_redis_tracker() -> RedisTracker:
    """
    Get a RedisTracker instance.
    
    Returns:
        RedisTracker instance
    """
    return RedisTracker()
