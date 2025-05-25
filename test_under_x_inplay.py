#!/usr/bin/env python3
"""
Direct test of the Under X In-Play strategy to identify issues.
"""
import sys
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
# Add the project root to the Python path
sys.path.insert(0, project_root)

try:
    # Import only the necessary module
    from scripts.under_x_inplay import UnderXInPlayStrategy

    # Create sample match data
    match_data = {
        "match_id": "test_match_123",
        "home_team": "Team A",
        "away_team": "Team B",
        "league": "Test League",
        "country": "Test Country",
        "minute": 55,
        "score": "1 - 1",
        "stats": {
            "home": {
                "shots": 5,
                "shots_on_target": 2,
                "dangerous_attacks": 15,
                "possession": 65
            },
            "away": {
                "shots": 3,
                "shots_on_target": 1,
                "dangerous_attacks": 8,
                "possession": 35
            }
        },
        "odds": {
            "under_5.5": 1.04,
            "over_5.5": 10.0
        },
        "history": {
            "home_team": {
                "avg_goals_scored": 1.5,
                "avg_goals_conceded": 1.0
            },
            "away_team": {
                "avg_goals_scored": 1.0,
                "avg_goals_conceded": 1.3
            }
        }
    }
    
    # Create the strategy
    logger.info("Creating Under X In-Play strategy")
    strategy = UnderXInPlayStrategy()
    
    # Analyze the match
    logger.info("Analyzing match")
    analysis = strategy.analyze_match(match_data)
    
    # Print the results
    logger.info("Analysis complete")
    logger.info("Results:")
    for key, value in analysis.items():
        if isinstance(value, dict):
            logger.info(f"  {key}:")
            for k, v in value.items():
                logger.info(f"    {k}: {v}")
        else:
            logger.info(f"  {key}: {value}")
            
except Exception as e:
    logger.error(f"Error in test script: {e}", exc_info=True)
