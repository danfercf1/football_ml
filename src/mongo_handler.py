"""
Module for handling MongoDB connections and data operations.
"""
import logging
from typing import List, Dict, Any, Optional, Callable

import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, PyMongoError

from src import config

logger = logging.getLogger(__name__)


class MongoHandler:
    """Handler for MongoDB operations related to football analysis rules."""
    
    def __init__(self):
        """Initialize MongoDB connection and set up collections."""
        self.client = None
        self.db = None
        self.rules_collection = None
        self.change_stream = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish connection to MongoDB."""
        try:
            # Prepare connection parameters with optional authentication
            connection_params = {
                "host": config.MONGO_URI,
                "port": config.MONGO_DB_PORT,
                "serverSelectionTimeoutMS": 5000,  # 5 seconds timeout
            }
            
            # Add authentication credentials only if both username and password are provided
            if hasattr(config, 'MONGO_DB_USERNAME') and hasattr(config, 'MONGO_DB_PASSWORD') and \
               config.MONGO_DB_USERNAME and config.MONGO_DB_PASSWORD:
                connection_params.update({
                    "username": config.MONGO_DB_USERNAME,
                    "password": config.MONGO_DB_PASSWORD,
                    "authSource": "footystats_ev",  # Changed from "admin" to match your user's database
                    "authMechanism": "SCRAM-SHA-256"
                })
            
            # Create the client with the appropriate parameters
            self.client = MongoClient(**connection_params)
            
            # Ping the server to verify connection
            self.client.admin.command('ping')

            self.db = self.client[config.MONGO_DB]
            self.rules_collection = self.db[config.MONGO_RULES_COLLECTION]

            logger.info("MongoDB connection established successfully")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
        except pymongo.errors.OperationFailure as e:
            if e.code == 18:  # Authentication error code
                logger.error("MongoDB authentication failed. Please check your username and password.")
                logger.debug(f"Full authentication error: {str(e)}")
            else:
                logger.error(f"MongoDB operation failed: {e}")
            raise
    
    def get_rules(self, league: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch analysis rules from MongoDB.
        
        Args:
            league: Optional league filter to get only rules for specific league
            
        Returns:
            List of rule documents
        """
        try:
            query = {"enabled": True}
            if league:
                query["league"] = league
                
            rules = list(self.rules_collection.find(query))
            logger.info(f"Fetched {len(rules)} rules from MongoDB")
            return rules
        except PyMongoError as e:
            logger.error(f"Error fetching rules from MongoDB: {e}")
            return []
    
    def setup_change_stream(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set up MongoDB change stream to detect rule changes.
        
        Args:
            callback: Function to call when a rule change is detected
        """
        if not config.ENABLE_CHANGE_STREAMS:
            logger.info("Change streams are disabled in configuration")
            return
            
        try:
            logger.info("Setting up MongoDB change stream for rules collection")
            self.change_stream = self.rules_collection.watch(
                pipeline=[{"$match": {"operationType": {"$in": ["insert", "update", "replace", "delete"]}}}],
                full_document='updateLookup'
            )
            
            # Start a thread to monitor the change stream
            import threading
            self.change_stream_thread = threading.Thread(
                target=self._monitor_change_stream,
                args=(callback,),
                daemon=True
            )
            self.change_stream_thread.start()
        except PyMongoError as e:
            logger.error(f"Failed to set up change stream: {e}")
    
    def _monitor_change_stream(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Monitor the change stream and call the callback when changes occur.
        
        Args:
            callback: Function to call when a rule change is detected
        """
        try:
            for change in self.change_stream:
                logger.info(f"Detected change in rules: {change['operationType']}")
                callback(change)
        except PyMongoError as e:
            logger.error(f"Error in change stream: {e}")
        finally:
            if self.change_stream:
                self.change_stream.close()
    
    def close(self) -> None:
        """Close MongoDB connection."""
        if self.change_stream:
            self.change_stream.close()
            
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


def get_mongo_handler() -> MongoHandler:
    """
    Create and return a MongoHandler instance.
    
    Returns:
        Configured MongoHandler
    """
    return MongoHandler()


# Example of inserting a sample rule
def insert_sample_rules() -> None:
    """
    Insert sample rules into MongoDB for testing purposes.
    """
    try:
        handler = get_mongo_handler()
        
        # Check if rules already exist
        if handler.rules_collection.count_documents({}) > 0:
            logger.info("Rules already exist in the database")
            return
        
        # Sample rules
        sample_rules = [
            {
                "type": "shots",
                "league": "premier_league",
                "conditions": {
                    "home_shots": {"$gt": 10},
                    "minute": {"$gt": 60}
                },
                "market": "over_2.5",
                "enabled": True
            },
            {
                "type": "xg",
                "league": "la_liga",
                "conditions": {
                    "total_xg": {"$gt": 2.0},
                    "minute": {"$gt": 70}
                },
                "market": "over_2.5",
                "enabled": True
            },
            {
                "type": "possession",
                "league": "premier_league",
                "conditions": {
                    "possession_home": {"$gt": 65},
                    "minute": {"$gt": 20},
                    "minute": {"$lt": 80}
                },
                "market": "home_win",
                "enabled": True
            }
        ]
        
        # Insert sample rules
        handler.rules_collection.insert_many(sample_rules)
        logger.info(f"Inserted {len(sample_rules)} sample rules")
        
    except PyMongoError as e:
        logger.error(f"Error inserting sample rules: {e}")
    finally:
        if 'handler' in locals():
            handler.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Insert sample rules for testing
    insert_sample_rules()
    
    # Test fetching rules
    handler = get_mongo_handler()
    rules = handler.get_rules()
    print(f"Fetched {len(rules)} rules:")
    for rule in rules:
        print(f"  - {rule['type']} rule for {rule['league']}: {rule['market']}")
    handler.close()
