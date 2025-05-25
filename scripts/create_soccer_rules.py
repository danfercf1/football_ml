#!/usr/bin/env python3
"""
Script to insert specialized soccer rules into MongoDB.
"""
import logging
from pymongo import MongoClient
import sys
import os
import json

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_soccer_rules():
    """Create and insert specialized soccer rules into MongoDB."""
    try:
        # Connect to MongoDB
        client = MongoClient(config.MONGO_URI)
        db = client[config.MONGO_DB]
        rules_collection = db[config.MONGO_RULES_COLLECTION]
        
        # Check if specialized rules already exist
        if rules_collection.count_documents({"type": {"$regex": "^soccer_"}}) > 0:
            logger.info("Specialized soccer rules already exist in the database")
            choice = input("Do you want to delete existing specialized rules and create new ones? (y/n): ")
            if choice.lower() != 'y':
                logger.info("Operation cancelled")
                return
            
            # Delete existing specialized rules
            result = rules_collection.delete_many({"type": {"$regex": "^soccer_"}})
            logger.info(f"Deleted {result.deleted_count} existing specialized rules")
        
        # Create specialized soccer rules
        soccer_rules = [
            {
                "type": "soccer_first_half_shots",
                "league": "all",
                "conditions": {
                    "minute": {"$lt": 35},
                    "minute": {"$gt": 15},
                    "home_shots": {"$gt": 4},
                    "away_shots": {"$lt": 2},
                    "possession_home": {"$gt": 60}
                },
                "market": "over_1.5",
                "enabled": True,
                "description": "Bet on over 1.5 goals when home team is dominating with shots and possession in first half"
            },
            {
                "type": "soccer_home_win_strong",
                "league": "all",
                "conditions": {
                    "minute": {"$gt": 20},
                    "minute": {"$lt": 40},
                    "possession_home": {"$gt": 60},
                    "home_dangerous_attacks": {"$gt": 15},
                    "away_dangerous_attacks": {"$lt": 10}
                },
                "market": "home_win",
                "enabled": True,
                "description": "Bet on home team to win when they're dominating dangerous attacks and possession before halftime"
            },
            {
                "type": "soccer_corner_frenzy",
                "league": "all",
                "conditions": {
                    "minute": {"$gt": 15},
                    "home_corners": {"$gt": 3},
                    "away_corners": {"$lt": 2},
                    "home_attacks": {"$gt": 15}
                },
                "market": "corners_over_9.5",
                "enabled": True,
                "description": "Bet on high corner count when home team is generating lots of attacks and corners already"
            },
            {
                "type": "soccer_btts_potential",
                "league": "all",
                "conditions": {
                    "minute": {"$gt": 30},
                    "minute": {"$lt": 60},
                    "home_shots_on_target": {"$gt": 1},
                    "away_shots_on_target": {"$gt": 1},
                    "score": "0 - 0"
                },
                "market": "btts_yes",
                "enabled": True,
                "description": "Bet on both teams to score when both are generating shots on target but haven't scored yet"
            },
            {
                "type": "soccer_copa_sudamericana_home_advantage",
                "league": "Copa Sudamericana",
                "conditions": {
                    "minute": {"$gt": 10},
                    "possession_home": {"$gt": 55},
                    "home_shots": {"$gt": 2},
                    "home_dangerous_attacks": {"$gt": 10}
                },
                "market": "over_1.5",
                "enabled": True,
                "description": "Specialized rule for Copa Sudamericana matches with strong home advantage"
            },
            {
                "type": "soccer_under_x_inplay",
                "league": "all",
                "conditions": {
                    "minute": {"$gte": 52},
                    "minute": {"$lte": 61},
                    "total_goals": {"$gte": 1},
                    "total_goals": {"$lte": 3},
                    "combined_avg_goals": {"$lt": 3.0}
                },
                "market": "under_current_plus_4.5",
                "enabled": True,
                "description": "Bet on Under (current goals + 4) when match is between minutes 52-61 with 1-3 goals already scored and low-scoring teams"
            }
        ]
        
        # Insert rules into MongoDB
        result = rules_collection.insert_many(soccer_rules)
        
        logger.info(f"Successfully inserted {len(result.inserted_ids)} specialized soccer rules")
        
        # Display the inserted rules
        logger.info("Inserted rules:")
        for i, rule_id in enumerate(result.inserted_ids, 1):
            rule = rules_collection.find_one({"_id": rule_id})
            logger.info(f"{i}. {rule['type']}: {rule['description']}")
        
    except Exception as e:
        logger.error(f"Error creating specialized soccer rules: {e}")
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    create_soccer_rules()
