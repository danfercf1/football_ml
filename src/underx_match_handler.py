"""
Module for handling UnderX match data from MongoDB.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import pymongo
from bson import ObjectId

from src.mongo_handler import MongoHandler
from src.redis_handler import get_redis_handler

logger = logging.getLogger(__name__)


class UnderXMatchHandler:
    """Handler for UnderX match data from MongoDB."""
    
    def __init__(self):
        """Initialize handlers and connections."""
        self.mongo_handler = MongoHandler()
        self.redis_handler = get_redis_handler()
        self.underx_collection = self.mongo_handler.db["underxmatches"]
    
    def get_todays_live_games(self) -> List[Dict[str, Any]]:
        """
        Get today's games that are currently live based on timestamp.
        
        Returns:
            List of live game documents
        """
        try:
            # Calculate today's date boundaries
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            
            logger.info(f"Today date: {today.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Tomorrow date: {tomorrow.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Convert to timestamp in milliseconds
            today_timestamp = int(today.timestamp() * 1000)
            tomorrow_timestamp = int(tomorrow.timestamp() * 1000)
            
            logger.info(f"Today timestamp (ms): {today_timestamp}")
            logger.info(f"Tomorrow timestamp (ms): {tomorrow_timestamp}")
            
            # Get current timestamp
            now = datetime.now()
            now_timestamp = int(now.timestamp() * 1000)
            
            logger.info(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Current timestamp (ms): {now_timestamp}")
            
            # First, try to find the specific game mentioned (directly by ID)
            specific_game_id = "6829fa7e5339ae0210b662b6"  # The game ID you mentioned
            try:
                specific_game = self.underx_collection.find_one({"_id": ObjectId(specific_game_id)})
                if specific_game:
                    game_timestamp = specific_game.get("timestamp", specific_game.get("date", 0))
                    game_time = datetime.fromtimestamp(game_timestamp / 1000)
                    is_added = specific_game.get("added", False)
                    logger.info(f"Found specific game: {specific_game_id}")
                    logger.info(f"Game timestamp: {game_timestamp}, Date: {game_time}")
                    logger.info(f"Game added status: {is_added}")
                    logger.info(f"Is game within today's range: {today_timestamp <= game_timestamp < tomorrow_timestamp}")
                    
                    # Check if game is live based on our time range logic
                    end_time = game_timestamp + (125 * 60 * 1000)
                    is_live_by_time = game_timestamp <= now_timestamp <= end_time
                    logger.info(f"Is game considered live by time: {is_live_by_time}")
                    
                    # Check if game has liveStats
                    has_live_stats = "liveStats" in specific_game
                    is_marked_live = has_live_stats and specific_game["liveStats"].get("isLive", False)
                    logger.info(f"Game has liveStats: {has_live_stats}, Marked as live: {is_marked_live}")
                else:
                    logger.info(f"Could not find game with ID: {specific_game_id}")
            except Exception as e:
                logger.error(f"Error looking up specific game: {e}")
            
            # Check if any games exist regardless of criteria (debugging)
            all_games = list(self.underx_collection.find({}, {"_id": 1, "timestamp": 1, "date": 1, "added": 1}))
            logger.info(f"Total games in collection: {len(all_games)}")
            
            # Try alternative timestamp field
            date_query = {
                "$or": [
                    {
                        "timestamp": {
                            "$gte": today_timestamp,
                            "$lt": tomorrow_timestamp
                        }
                    },
                    {
                        "date": {
                            "$gte": today_timestamp,
                            "$lt": tomorrow_timestamp
                        }
                    }
                ],
                "added": True
            }
            
            logger.info(f"Using modified query with $or for timestamp/date: {date_query}")
            games_today = list(self.underx_collection.find(date_query, {"_id": 1, "timestamp": 1, "date": 1, "added": 1}))
            logger.info(f"Games today (with modified query): {len(games_today)}")
            
            if games_today:
                for game in games_today[:5]:  # Show details for up to 5 games
                    game_timestamp = game.get("timestamp", game.get("date", 0))
                    game_time = datetime.fromtimestamp(game_timestamp / 1000)
                    logger.info(f"Game ID: {game['_id']}, Time: {game_time}, Added: {game.get('added', False)}")
            
            # Use the modified query for the main search instead of the original timestamp-only query
            query = date_query
            
            logger.info(f"MongoDB query: {query}")
            
            games = list(self.underx_collection.find(query, {"_id": 1, "timestamp": 1, "date": 1}))
            logger.info(f"Games today with added=True: {len(games)}")
            
            # Filter for live games (current time is between start time and start time + 125 minutes)
            live_games = []
            for game in games:
                # Use either timestamp or date field, whichever is available
                start_time = game.get("timestamp", game.get("date", 0))
                end_time = start_time + (125 * 60 * 1000)  # Add 125 minutes in milliseconds
                
                # Debug information about the time comparison
                game_start = datetime.fromtimestamp(start_time / 1000)
                game_end = datetime.fromtimestamp(end_time / 1000)
                is_live = start_time <= now_timestamp <= end_time
                
                logger.info(f"Game: {game['_id']}, Start: {game_start}, End: {game_end}, Is Live: {is_live}")
                
                if is_live:
                    live_games.append({
                        "id": str(game["_id"]),
                        "matchType": "underXmatch",
                        "timestamp": start_time
                    })
            
            logger.info(f"Found {len(live_games)} live games out of {len(games)} today's games")
            return live_games
            
        except Exception as e:
            logger.error(f"Error getting today's live games: {e}")
            return []
    
    def save_live_games_to_redis(self) -> bool:
        """
        Find today's live games and save them to Redis.
        
        Returns:
            Boolean indicating success
        """
        live_games = self.get_todays_live_games()
        if not live_games:
            logger.info("No live games found to save to Redis")
            return True
            
        return self.redis_handler.save_live_games(live_games)
    
    def get_live_match_data(self) -> List[Dict[str, Any]]:
        """
        Get full match data for all games currently stored in Redis.
        
        Returns:
            List of complete match documents
        """
        try:
            # Get game IDs from Redis
            redis_games = self.redis_handler.get_live_games()
            if not redis_games:
                logger.info("No live games found in Redis")
                return []
                
            # Extract IDs
            match_ids = [ObjectId(game["id"]) for game in redis_games]
            
            # Fetch full data from MongoDB
            query = {"_id": {"$in": match_ids}}
            matches = list(self.underx_collection.find(query))
            
            # Convert ObjectId to string
            for match in matches:
                match["_id"] = str(match["_id"])
            
            logger.info(f"Retrieved {len(matches)} live matches from MongoDB")
            return matches
            
        except Exception as e:
            logger.error(f"Error retrieving live match data: {e}")
            return []
    
    def close(self):
        """Close all connections."""
        self.mongo_handler.close()
        self.redis_handler.close()


def get_underx_match_handler() -> UnderXMatchHandler:
    """
    Create and return an UnderXMatchHandler instance.
    
    Returns:
        Configured UnderXMatchHandler
    """
    return UnderXMatchHandler()
