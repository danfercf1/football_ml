"""
Module for handling Redis operations for football analysis.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import redis

from src import config

logger = logging.getLogger(__name__)

# Redis constants
LIVE_GAMES_KEY = config.LIVE_GAMES_KEY if hasattr(config, 'LIVE_GAMES_KEY') else "live_games:underXmatch"
REDIS_TTL = int(config.REDIS_TTL) if hasattr(config, 'REDIS_TTL') else 120


class RedisHandler:
    """Handler for Redis operations related to football matches."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.redis_client = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.redis_client = redis.Redis(
                host=config.REDIS_HOST,
                port=int(config.REDIS_PORT),
                password=config.REDIS_PASSWORD if hasattr(config, 'REDIS_PASSWORD') else None,
                db=int(config.REDIS_DB) if hasattr(config, 'REDIS_DB') else 0,
                decode_responses=True  # Automatically decode responses to strings
            )
            # Test the connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            raise
    
    def save_live_games(self, games: List[Dict[str, Any]]) -> bool:
        """
        Save a list of live games to Redis.
        
        Args:
            games: List of game objects with id, matchType, and timestamp
            
        Returns:
            Boolean indicating success
        """
        try:
            # Format each game to ensure it has exactly the required fields
            formatted_games = []
            for game in games:
                # Ensure each game has only the required fields in the exact format
                formatted_game = {
                    "id": game["id"],
                    "matchType": "underXmatch",
                    "timestamp": int(game.get("timestamp", datetime.now().timestamp() * 1000))
                }
                formatted_games.append(formatted_game)
                
            # Check if we already have data in Redis
            existing_data_str = self.redis_client.get(LIVE_GAMES_KEY)
            existing_games = []
            
            if existing_data_str:
                try:
                    existing_games = json.loads(existing_data_str)
                    # Ensure we're working with a list
                    if not isinstance(existing_games, list):
                        existing_games = []
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in Redis for key {LIVE_GAMES_KEY}, resetting")
                    existing_games = []
                
            # Filter out games that already exist in Redis by ID
            existing_ids = {game.get('id') for game in existing_games if 'id' in game}
            new_games = [game for game in formatted_games if game['id'] not in existing_ids]
            
            if not new_games:
                logger.debug("No new games to add to Redis")
                return True
                
            # Combine existing and new games
            combined_games = existing_games + new_games
            
            # Save to Redis with TTL - ensure exact JSON format
            json_data = json.dumps(combined_games, separators=(',', ':'))
            logger.debug(f"Saving to Redis: {json_data}")
            
            self.redis_client.set(
                LIVE_GAMES_KEY,
                json_data,
                ex=REDIS_TTL
            )
            
            logger.info(f"Saved {len(new_games)} new games to Redis (total: {len(combined_games)})")
            return True
            
        except Exception as e:
            logger.error(f"Error saving live games to Redis: {e}")
            return False
    
    def get_live_games(self) -> List[Dict[str, Any]]:
        """
        Get the list of live games from Redis.
        
        Returns:
            List of live game objects with id, matchType, and timestamp
        """
        try:
            data_str = self.redis_client.get(LIVE_GAMES_KEY)
            if data_str:
                return json.loads(data_str)
            return []
        except Exception as e:
            logger.error(f"Error retrieving live games from Redis: {e}")
            return []
    
    def close(self) -> None:
        """Close Redis connection if it exists."""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")


def get_redis_handler() -> RedisHandler:
    """
    Create and return a RedisHandler instance.
    
    Returns:
        Configured RedisHandler
    """
    return RedisHandler()
