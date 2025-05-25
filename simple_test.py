#!/usr/bin/env python3
"""
Simple test script to test betting rules functionality without requiring database connections.
"""
import os
import sys
import logging
from pprint import pprint

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
# Add the project root to the Python path
sys.path.insert(0, project_root)

# Import the functions directly from the fixed_under_x_inplay.py script
from scripts.fixed_under_x_inplay import default_betting_rules, evaluate_betting_rules

def main():
    """
    Run a simple test of the betting rules functionality.
    """
    try:
        # Temporarily set NO_RULES_MODE to False for this test
        import os
        os.environ["NO_RULES_MODE"] = "false"
        
        # Create a test match
        match_data = {
            "match_id": "test_match_123",
            "home_team": "Test FC",
            "away_team": "Test United",
            "league": "Test League",
            "country": "Test Country",
            "minute": 55,  # Within 52-61 range
            "score": "1 - 1",  # 2 goals total, within 1-3 range
            "total_goals": 2,
            "odds": {
                "under_6.5": 1.04  # Good odds
            }
        }
        
        # Log that we're starting the test
        logger.info("Starting the betting rules test...")
    except Exception as e:
        logger.error(f"Error setting up test: {e}", exc_info=True)
    
    try:
        # Get the default betting rules
        logger.info("Getting default betting rules...")
        rules = default_betting_rules()
        logger.info(f"Got {len(rules)} rules: {[rule.get('rule_type') for rule in rules]}")
        
        # Evaluate the rules against the match data
        logger.info("Evaluating rules against match data...")
        results = evaluate_betting_rules(match_data, rules)
        
        # Print the results
        logger.info("Evaluation results:")
        for key, value in results.items():
            logger.info(f"  {key}: {value}")
        
        # Test with a match that doesn't meet the criteria
        bad_match = match_data.copy()
        bad_match["minute"] = 30  # Outside 52-61 range
        bad_match["score"] = "0 - 0"  # 0 goals, outside 1-3 range
        bad_match["total_goals"] = 0  # Update this too
        
        # Evaluate the rules against the bad match data
        logger.info("\nEvaluating rules against match that doesn't meet criteria...")
        bad_results = evaluate_betting_rules(bad_match, rules)
        
        # Print the results
        logger.info("Evaluation results:")
        for key, value in bad_results.items():
            logger.info(f"  {key}: {value}")
    except Exception as e:
        logger.error(f"Error running test: {e}", exc_info=True)

if __name__ == "__main__":
    main()
