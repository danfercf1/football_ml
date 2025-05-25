#!/usr/bin/env python3
"""
Test script for the fixed Under X In-Play strategy with a match that meets all criteria.
"""
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
# Add the project root to the Python path
sys.path.insert(0, project_root)

# Import the fixed strategy
from scripts.fixed_under_x_inplay import UnderXInPlayStrategy

def run_test_with_perfect_match():
    """Run a test with a match that meets all criteria for the Under X In-Play strategy."""
    # We'll use the default rules from our fixed module without using the match processor
    # Create our own dictionary-based version of the evaluate_betting_rules function
    
    from scripts.fixed_under_x_inplay import default_betting_rules, evaluate_betting_rules
    
    # Create a match data dictionary that would normally come from match_processor
    match_data = {
        "match_id": "perfect_match_123",
        "home_team": "Low Scoring FC",
        "away_team": "Defensive United",
        "minute": 55,  # Within target range 52-61
        "score": "1 - 0",  # Within target range 1-3 goals
        "league": "Test League",
        "country": "Test Country",
        "total_goals": 1,
        "home_avg_goals": 1.2,
        "away_avg_goals": 0.9,
        "combined_avg_goals": 2.1,  # Below the 3.0 threshold
        "odds": {
            "under_5.5": 1.04  # Good odds for under market
        }
    }
    
    # Get our rules
    rules = default_betting_rules()
    
    # Evaluate the rules
    results = evaluate_betting_rules(match_data, rules)
    
    # Print the results of the rule evaluation
    logger.info("=" * 80)
    logger.info("TEST WITH PERFECT MATCH DATA")
    logger.info("=" * 80)
    logger.info(f"Match: {match_data['home_team']} vs {match_data['away_team']}")
    logger.info(f"Current minute: {match_data['minute']}")
    logger.info(f"Current score: {match_data['score']}")
    logger.info(f"Combined avg goals: {match_data['combined_avg_goals']}")
    logger.info("-" * 80)
    logger.info(f"Rules passed: {results['rules_passed']}")
    logger.info(f"Rules failed: {results['rules_failed']}")
    logger.info(f"Is suitable: {results['is_suitable']}")
    logger.info(f"Recommended stake: {results['stake']} ({results['stake_strategy']})")
    logger.info("=" * 80)
    
    # Optional: If we want to test the full strategy workflow
    logger.info("\nRunning full strategy analysis:")
    strategy = UnderXInPlayStrategy()
    # We need to create a match document that can be processed by the match processor
    # For simplicity, we'll just use a basic structure
    match_doc = {
        "match_id": "perfect_match_123",
        "home_team": "Low Scoring FC",
        "away_team": "Defensive United",
        "minute": 55,
        "score": "1 - 0",
        "league": "Test League",
        "country": "Test Country",
        "stats": {
            "home": {"possession": 55},
            "away": {"possession": 45}
        },
        "history": {
            "home_team": {"avg_goals_scored": 1.2, "avg_goals_conceded": 0.8},
            "away_team": {"avg_goals_scored": 0.9, "avg_goals_conceded": 1.0}
        }
    }
    
    # Patch the match processor's process_match_document method to return our match_data
    original_process = strategy.processor.process_match_document
    strategy.processor.process_match_document = lambda *args, **kwargs: match_data
    
    # Now run the analysis
    analysis = strategy.analyze_match(match_doc)
    
    # Restore the original method
    strategy.processor.process_match_document = original_process
    
    # Print the results
    logger.info("=" * 80)
    logger.info("TEST MATCH THAT SHOULD MEET ALL CRITERIA")
    logger.info("=" * 80)
    logger.info("UNDER X IN-PLAY STRATEGY ANALYSIS")
    logger.info("-" * 80)
    logger.info(f"Match: {analysis['home_team']} vs {analysis['away_team']}")
    logger.info(f"Current minute: {analysis['minute']}")
    logger.info(f"Current score: {analysis['score']}")
    logger.info(f"Team stats:")
    logger.info(f"  - Home team avg goals: {analysis['home_avg_goals']:.2f}")
    logger.info(f"  - Away team avg goals: {analysis['away_avg_goals']:.2f}")
    logger.info(f"  - Combined avg goals: {analysis['combined_avg_goals']:.2f}")
    logger.info(f"Target bet: {analysis['target_under_line']}")
    logger.info(f"Available odds: {analysis['odds']}")
    logger.info("-" * 80)
    logger.info(f"Match suitable for strategy: {'YES' if analysis['is_suitable'] else 'NO'}")
    if analysis["reasons"]:
        logger.info(f"Reasons:")
        for reason in analysis["reasons"]:
            logger.info(f"  - {reason}")
    if analysis.get("rules_passed"):
        logger.info(f"Rules passed: {', '.join(analysis['rules_passed'])}")
    if analysis.get("recommendation"):
        logger.info("-" * 80)
        logger.info(f"Recommendation: {analysis['recommendation']['action']}")
        logger.info(f"Market: {analysis['recommendation']['market']}")
        logger.info(f"Odds: {analysis['recommendation']['odds']}")
        logger.info(f"Risk level: {analysis['recommendation']['risk_level']}")
        logger.info(f"Suggested stake: {analysis['recommendation']['stake_recommendation']}")
        logger.info(f"Cashout trigger: {analysis['recommendation']['cashout_trigger']}")
    logger.info("=" * 80)


if __name__ == "__main__":
    run_test_with_perfect_match()
