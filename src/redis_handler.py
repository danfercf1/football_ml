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
LIVE_GAMES_KEY = config.LIVE_GAMES_KEY if hasattr(config, 'LIVE_GAMES_KEY') else "live_games"
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
        Save a list of live games to Redis, with each game stored under its own key.
        
        Args:
            games: List of game objects with id, matchType, and timestamp
            
        Returns:
            Boolean indicating success
        """
        try:
            # Track games saved
            new_games_count = 0
            updated_games_count = 0
            
            for game in games:
                # Get the game ID - support both MongoDB _id and regular id
                game_id = str(game.get("_id", game.get("id", "")))
                if not game_id:
                    logger.warning(f"Skipping game without ID: {game}")
                    continue
                
                # Create the Redis key for this game
                game_key = f"{LIVE_GAMES_KEY}:{game_id}"
                
                # Check if game already exists in Redis
                existing_game_data = self.redis_client.get(game_key)
                
                # Calculate game end time (start time + 120 minutes)
                game_date = int(game.get("date", datetime.now().timestamp() * 1000)) / 1000  # Convert ms to seconds
                game_end_time = game_date + (120 * 60)  # Add 120 minutes in seconds
                current_time = datetime.now().timestamp()
                ttl = max(int(game_end_time - current_time), 60)  # At least 60 seconds TTL
                
                # Add game TTL to the game data
                formatted_game = game.copy()
                formatted_game["id"] = game_id
                formatted_game["ttl"] = ttl
                formatted_game["end_time"] = game_end_time
                formatted_game["matchType"] = "underXmatch"
                if "timestamp" not in formatted_game:
                    formatted_game["timestamp"] = int(game.get("date", datetime.now().timestamp() * 1000))
                
                # Format to JSON
                json_data = json.dumps(formatted_game, separators=(',', ':'))
                
                # Check if game has changed or is new
                should_save = True
                if existing_game_data:
                    try:
                        existing_game = json.loads(existing_game_data)
                        # Only update if important data has changed
                        # Compare scores or other critical fields that would trigger an update
                        if (existing_game.get("score") == formatted_game.get("score") and 
                            existing_game.get("minute") == formatted_game.get("minute")):
                            should_save = False
                        else:
                            updated_games_count += 1
                    except json.JSONDecodeError:
                        # Invalid JSON, overwrite it
                        should_save = True
                
                # Save to Redis if new or changed
                if should_save:
                    self.redis_client.set(game_key, json_data, ex=ttl)
                    if not existing_game_data:
                        new_games_count += 1
            
            logger.info(f"Saved {new_games_count} new games and updated {updated_games_count} existing games in Redis")
            return True
            
        except Exception as e:
            logger.error(f"Error saving live games to Redis: {e}")
            return False
    
    def get_live_games(self) -> List[Dict[str, Any]]:
        """
        Get the list of live games from Redis.
        
        Returns:
            List of live game objects
        """
        try:
            # Find all game keys using the pattern
            pattern = f"{LIVE_GAMES_KEY}:*"
            game_keys = self.redis_client.keys(pattern)
            
            if not game_keys:
                logger.info(f"No live games found in Redis with pattern {pattern}")
                return []
            
            logger.info(f"Found {len(game_keys)} game keys in Redis")
            
            # Use pipeline to get all games in one batch for better performance
            pipe = self.redis_client.pipeline()
            for key in game_keys:
                pipe.get(key)
            
            # Execute pipeline and process results
            game_data_list = pipe.execute()
            active_games = []
            
            for i, game_data in enumerate(game_data_list):
                if game_data:
                    try:
                        game = json.loads(game_data)
                        # Check if game has valid data
                        if "id" in game:
                            active_games.append(game)
                        else:
                            logger.warning(f"Game missing ID field: {game_keys[i]}")
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in Redis for game key {game_keys[i]}")
            
            logger.info(f"Retrieved {len(active_games)} active live games from Redis")
            return active_games
            
        except redis.RedisError as e:
            logger.error(f"Redis error retrieving live games: {e}")
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
