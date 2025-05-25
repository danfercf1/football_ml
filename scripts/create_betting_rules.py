#!/usr/bin/env python3
"""
Script to create and store betting rules for the Under X In-Play strategy.
"""
import logging
import sys
import os
import json
from pymongo import MongoClient
from typing import Dict, Any, List

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src import config
from src.betting_rules import default_betting_rules

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_betting_rules():
    """Create and store betting rules for the Under X In-Play strategy."""
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB: {config.MONGO_URI}")
        try:
            client = MongoClient(host=config.MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            client.server_info()
            db = client[config.MONGO_DB]
            print(f"Using database: {config.MONGO_DB}")
            rules_collection = db[config.MONGO_RULES_COLLECTION]
            mongodb_available = True
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            logger.warning("Continuing without MongoDB - rules will be saved to JSON only")
            mongodb_available = False
        
        # Only attempt database operations if MongoDB is available
        if mongodb_available:
            try:
                # Check if Under X In-Play rules already exist
                if rules_collection.count_documents({"strategy": "under_x_inplay"}) > 0:
                    logger.info("Under X In-Play betting rules already exist in the database")
                    choice = input("Do you want to delete existing Under X In-Play rules and create new ones? (y/n): ")
                    if choice.lower() != 'y':
                        logger.info("Operation cancelled")
                        return
                    
                    # Delete existing Under X In-Play rules
                    result = rules_collection.delete_many({"strategy": "under_x_inplay"})
                    logger.info(f"Deleted {result.deleted_count} existing Under X In-Play rules")
            except Exception as e:
                logger.error(f"Error checking existing rules: {e}")
                logger.warning("Continuing without checking for existing rules")
        
        # Create betting rules
        rules = default_betting_rules()
        
        # Convert rules to MongoDB-friendly format
        mongo_rules = []
        
        for rule in rules:
            try:
                # Try to handle as class-based rule
                if not rule.active:
                    continue
                    
                mongo_rule = {
                    "strategy": "under_x_inplay",
                    "rule_type": rule.rule_type,
                    "active": True
                }
                
                # Copy all parameters
                mongo_rule.update(rule.params)
                
            except AttributeError:
                # Handle as dictionary-based rule
                # Skip inactive rules
                if not rule.get("active", True):
                    continue
                    
                mongo_rule = {
                    "strategy": "under_x_inplay",
                    "rule_type": rule.get("rule_type", "unknown"),
                    "active": True
                }
                
                # Copy all rule parameters
                for key, value in rule.items():
                    if key not in ["active", "rule_type"]:
                        mongo_rule[key] = value
            
            # Add type-specific details
            if rule.get("rule_type") == "goals":
                mongo_rule["description"] = "Goals-related conditions for Under X In-Play strategy"
            elif rule.get("rule_type") == "stake":
                mongo_rule["description"] = "Stake parameters for Under X In-Play strategy"
            elif rule.get("rule_type") == "time":
                mongo_rule["description"] = "Time window conditions for Under X In-Play strategy"
            elif rule.get("rule_type") == "composite":
                mongo_rule["description"] = "Composite conditions for Under X In-Play strategy"
            
            mongo_rules.append(mongo_rule)
        
        # Insert into MongoDB if available, otherwise save to JSON
        if mongo_rules:
            # Always save rules to JSON as backup
            json_path = os.path.join(project_root, "betting_rules.json")
            with open(json_path, 'w') as f:
                json.dump(mongo_rules, f, indent=2)
            logger.info(f"Successfully saved {len(mongo_rules)} betting rules to {json_path}")
            
            # Try to insert into MongoDB if available
            if mongodb_available:
                try:
                    result = rules_collection.insert_many(mongo_rules)
                    logger.info(f"Successfully inserted {len(result.inserted_ids)} betting rules into MongoDB")
                except Exception as e:
                    logger.error(f"Failed to insert rules into MongoDB: {e}")
                    logger.info("Rules were saved to JSON file as fallback")
            else:
                logger.info("MongoDB not available. Rules were saved to JSON file only.")
                
            # Print summary of created rules
            logger.info("\nCreated the following Under X In-Play betting rules:")
            for i, rule in enumerate(mongo_rules, 1):
                logger.info(f"{i}. {rule['rule_type']} rule: {rule.get('description', 'No description')}")
        else:
            logger.info("No active betting rules to insert")
        
    except Exception as e:
        logger.error(f"Error creating betting rules: {e}")
    finally:
        if 'client' in locals():
            client.close()


def export_rules_to_json(file_path: str = "betting_rules.json"):
    """
    Export the default betting rules to a JSON file.
    
    Args:
        file_path: Path to save the JSON file
    """
    try:
        rules = default_betting_rules()
        
        # Convert class instances to dictionaries for serialization
        serializable_rules = []
        for rule in rules:
            try:
                # Try to handle as class-based rule
                rule_dict = {
                    "rule_type": rule.rule_type,
                    "active": rule.active
                }
                # Add all parameters
                rule_dict.update(rule.params)
                serializable_rules.append(rule_dict)
            except AttributeError:
                # Handle as dictionary-based rule
                serializable_rules.append(rule)
        
        # Write to JSON file
        with open(file_path, 'w') as f:
            json.dump(serializable_rules, f, indent=2)
            
        logger.info(f"Successfully exported betting rules to {file_path}")
        
    except Exception as e:
        logger.error(f"Error exporting betting rules to JSON: {e}")


def create_js_example():
    """Create a JavaScript example of the betting rules."""
    try:
        js_example = """const defaultBettingRules = (match, team, country, league) => [
  {
    ruleType: "goals",  // Rule type for goals-related conditions
    odds: {
      min: 1.01,
      max: 1.05
    },
    active: true,
    // Strategy-specific parameters
    match: match,
    country: country,
    league: league,
    // Goals-specific conditions
    minGoals: 1,  // Minimum total goals required for the rule to apply (e.g., don't bet if 0-0)
    maxGoals: 3,  // Maximum total goals allowed for the rule to apply (e.g., don't bet if score is already high)
    // goalMargin: 3.5 // Removed - Replaced by buffer logic in strategy
    minGoalLineBuffer: 2.5 // Optional: Minimum buffer for selecting the standard goal line (e.g., target line >= score + buffer)
  },
  {
    ruleType: "stake",  // Rule type for stake-related parameters
    active: true,
    stake: 0.50,      // Amount to stake
    // Additional stake parameters could be added here
    stakeStrategy: "fixed",  // Alternative could be "percentage", "kelly", etc.
  },
  // {
  //   ruleType: "divisor", // Rule type for divisor-related parameters
  //   active: true,
  //   divisor: 8,      // Divisor used for stake calculations when using balance
  // },
  {
    ruleType: "time",  // Rule type for time-related conditions
    active: true,
    // Time-specific conditions
    // Example: Shifted window later in the match (e.g., 65-75 minutes)
    minMinute: 65,  // Increased minimum minute
    maxMinute: 75,  // Adjusted maximum minute
  }
  // Additional rules can be added as needed
  // Example composite rule:
  // {
  //   ruleType: "composite",
  //   active: true,
  //   conditions: [
  //     { type: "goals", comparison: "<=", value: 3 },
  //     { type: "time", comparison: "between", min: 52, max: 61 }
  //   ]
  // }
]

module.exports = { defaultBettingRules };
"""
        
        with open("betting_rules_example.js", 'w') as f:
            f.write(js_example)
            
        logger.info("Created JavaScript example of betting rules")
        
    except Exception as e:
        logger.error(f"Error creating JavaScript example: {e}")


def main():
    """Main entry point."""
    print("Under X In-Play Betting Rules Manager")
    print("====================================")
    print("1. Create rules in MongoDB")
    print("2. Export rules to JSON")
    print("3. Create JavaScript example")
    print("4. Exit")
    
    # For testing purposes, let's automatically export the rules to JSON
    print("\nAutomatically exporting rules to JSON...")
    export_rules_to_json('betting_rules.json')
    print("\nCreating JavaScript example...")
    create_js_example()
    print("\nComplete! Check betting_rules.json and betting_rules_example.js")
    return
    
    try:
        choice = int(input("\nEnter your choice (1-4): "))
        
        if choice == 1:
            create_betting_rules()
        elif choice == 2:
            file_path = input("Enter file path (default: betting_rules.json): ") or "betting_rules.json"
            export_rules_to_json(file_path)
        elif choice == 3:
            create_js_example()
        elif choice == 4:
            print("Exiting...")
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")
            
    except ValueError:
        print("Invalid input. Please enter a valid number.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
