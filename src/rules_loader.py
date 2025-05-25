#!/usr/bin/env python3
"""
Module for loading betting rules from various sources (MongoDB or JSON file).
"""
import os
import sys
import json
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import List, Dict, Any, Optional

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BettingRulesLoader:
    """Class for loading betting rules from different sources."""
    
    def __init__(self):
        """Initialize the loader."""
        self.mongodb_available = False
        self.client = None
        self.db = None
        self.rules_collection = None
        
        # Try to connect to MongoDB
        try:
            self.client = MongoClient(host=config.MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.server_info()
            self.db = self.client[config.MONGO_DB]
            self.rules_collection = self.db[config.MONGO_RULES_COLLECTION]
            self.mongodb_available = True
            logger.info("Successfully connected to MongoDB")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"Could not connect to MongoDB: {e}")
            self.mongodb_available = False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            self.mongodb_available = False
    
    def load_rules(self, strategy: str = "under_x_inplay") -> List[Dict[str, Any]]:
        """
        Load betting rules from the best available source.
        
        Args:
            strategy: The strategy name to load rules for
            
        Returns:
            List of betting rule dictionaries
        """
        # Try MongoDB first if available
        if self.mongodb_available:
            try:
                logger.info(f"Attempting to load '{strategy}' rules from MongoDB...")
                rules = list(self.rules_collection.find({"strategy": strategy}))
                
                if rules:
                    logger.info(f"Loaded {len(rules)} rules from MongoDB")
                    # Clean up MongoDB _id field which isn't JSON serializable
                    for rule in rules:
                        if '_id' in rule:
                            del rule['_id']
                    return rules
                else:
                    logger.warning(f"No rules found in MongoDB for strategy: {strategy}")
            except Exception as e:
                logger.error(f"Error loading rules from MongoDB: {e}")
        
        # Fall back to JSON file
        json_path = os.path.join(project_root, "betting_rules.json")
        if os.path.exists(json_path):
            try:
                logger.info(f"Attempting to load rules from JSON file: {json_path}")
                with open(json_path, 'r') as f:
                    rules = json.load(f)
                
                # Filter rules for the requested strategy if needed
                if isinstance(rules, list):
                    if all(isinstance(rule, dict) and "strategy" in rule for rule in rules):
                        rules = [rule for rule in rules if rule.get("strategy") == strategy]
                    
                    logger.info(f"Loaded {len(rules)} rules from JSON file")
                    return rules
                else:
                    logger.error("Invalid JSON format: expected a list of rules")
            except Exception as e:
                logger.error(f"Error loading rules from JSON file: {e}")
        else:
            logger.warning(f"JSON rules file not found: {json_path}")
        
        # Fall back to default rules
        logger.info("Using default hardcoded rules")
        return self._default_rules(strategy)
    
    def _default_rules(self, strategy: str) -> List[Dict[str, Any]]:
        """
        Return default hardcoded rules for the specified strategy.
        
        Args:
            strategy: The strategy name
            
        Returns:
            List of default rule dictionaries
        """
        if strategy == "under_x_inplay":
            return [
                {
                    "strategy": "under_x_inplay",
                    "rule_type": "goals",
                    "active": True,
                    "description": "Goals-related conditions for Under X In-Play strategy",
                    "odds": {
                        "min": 1.01,
                        "max": 1.05
                    },
                    "min_goals": 1,
                    "max_goals": 3,
                    "min_goal_line_buffer": 2.5,
                    "league": None,
                    "country": None,
                    "match": None
                },
                {
                    "strategy": "under_x_inplay",
                    "rule_type": "stake",
                    "active": True,
                    "description": "Stake parameters for Under X In-Play strategy",
                    "stake": 0.50,
                    "stake_strategy": "fixed"
                },
                {
                    "strategy": "under_x_inplay",
                    "rule_type": "time",
                    "active": True,
                    "description": "Time window conditions for Under X In-Play strategy",
                    "min_minute": 65,
                    "max_minute": 75
                }
            ]
        else:
            logger.warning(f"No default rules defined for strategy: {strategy}")
            return []
    
    def close(self):
        """Close the MongoDB connection if open."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


def load_betting_rules(strategy: str = "under_x_inplay") -> List[Dict[str, Any]]:
    """
    Helper function to load betting rules using the BettingRulesLoader.
    
    Args:
        strategy: The strategy name to load rules for
        
    Returns:
        List of betting rule dictionaries
    """
    loader = BettingRulesLoader()
    try:
        return loader.load_rules(strategy)
    finally:
        loader.close()


if __name__ == "__main__":
    """Test the betting rules loader."""
    print("Testing BettingRulesLoader")
    print("=========================")
    
    rules = load_betting_rules()
    print(f"Loaded {len(rules)} rules")
    
    for i, rule in enumerate(rules, 1):
        print(f"\nRule {i}:")
        print(f"  Type: {rule.get('rule_type')}")
        print(f"  Description: {rule.get('description', 'No description')}")
        print(f"  Active: {rule.get('active', False)}")
