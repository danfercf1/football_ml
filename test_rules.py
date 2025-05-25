#!/usr/bin/env python3
"""
Test script for the betting rules system.
"""
import sys
import os
import logging
from pprint import pprint

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
# Add the project root to the Python path
sys.path.insert(0, project_root)

try:
    logger.info("Importing modules...")
    from src.betting_rules import default_betting_rules, evaluate_betting_rules
    from src.rules_loader import load_betting_rules
    
    logger.info("Testing rules loader...")
    loaded_rules = load_betting_rules("under_x_inplay")
    logger.info(f"Loaded {len(loaded_rules)} rules from rules loader")
    
    # Create a test match
    match_data = {
        "match_id": "test_match",
        "home_team": "Test Home",
        "away_team": "Test Away",
        "league": "Test League",
        "country": "Test Country",
        "minute": 70,  # Updated to be within 65-75 window
        "score": "1 - 1",
        "total_goals": 2,
        "home_avg_goals": 1.5,
        "away_avg_goals": 1.3,
        "combined_avg_goals": 2.8,
        "odds": {
            "under_4.5": 1.03  # Updated to match our target market
        }
    }
    
    logger.info("Getting betting rules...")
    rules = default_betting_rules()
    logger.info(f"Got {len(rules)} rules from default_betting_rules()")
    
    # Compare loaded rules with default rules
    logger.info("Comparing loaded rules with default rules...")
    if len(loaded_rules) > 0:
        logger.info("Using rules from loader for evaluation")
        evaluation_rules = loaded_rules
    else:
        logger.info("Falling back to default hardcoded rules")
        evaluation_rules = rules
    
    # Print rules summary
    for i, rule in enumerate(evaluation_rules):
        if hasattr(rule, 'rule_type'):
            rule_type = rule.rule_type
            active = rule.active
            logger.info(f"Rule {i+1}: {rule_type} (class-based, active: {active})")
        else:
            rule_type = rule.get('rule_type')
            active = rule.get('active', False)
            logger.info(f"Rule {i+1}: {rule_type} (dict-based, active: {active})")
    
    # Evaluate rules from both sources
    logger.info("\nEvaluating with default rules...")
    result_default = evaluate_betting_rules(match_data, rules)
    logger.info("Default rules evaluation result:")
    for key, value in result_default.items():
        logger.info(f"  {key}: {value}")
    
    logger.info("\nEvaluating with loaded rules...")
    result_loaded = evaluate_betting_rules(match_data, evaluation_rules)
    logger.info("Loaded rules evaluation result:")
    for key, value in result_loaded.items():
        logger.info(f"  {key}: {value}")
    
    # Compare results
    logger.info("\nComparing results:")
    if result_default["is_suitable"] == result_loaded["is_suitable"]:
        logger.info("✅ Both rule sources produce the same suitability result")
    else:
        logger.info("❌ Rule sources produce different suitability results!")
        
    if result_default["stake"] == result_loaded["stake"]:
        logger.info("✅ Both rule sources produce the same stake amount")
    else:
        logger.info(f"Different stake amounts: Default={result_default['stake']}, Loaded={result_loaded['stake']}")
        
except Exception as e:
    logger.error(f"Error in test script: {e}", exc_info=True)
