#!/usr/bin/env python3
"""
Script to demonstrate processing and analyzing real match data.
"""
import json
import logging
import sys
import os
from typing import Dict, Any

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.match_processor import get_match_processor
from src.specialized_rules import SpecializedRules
from src.rabbitmq_publisher import get_rabbitmq_publisher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_match_document(match_doc: Dict[str, Any]) -> None:
    """
    Process a match document and analyze it for betting opportunities.
    
    Args:
        match_doc: Dictionary containing match data
    """
    # 1. Process the match document to extract relevant features
    processor = get_match_processor()
    match_data = processor.process_match_document(match_doc)
    
    logger.info("=" * 80)
    logger.info(f"MATCH ANALYSIS: {match_data.get('home_team', 'Home')} vs {match_data.get('away_team', 'Away')}")
    logger.info(f"League: {match_data.get('league', 'Unknown')}")
    logger.info(f"Minute: {match_data.get('minute', 0)}")
    logger.info(f"Score: {match_data.get('score', '0 - 0')}")
    logger.info("-" * 80)
    
    # 2. Print key match statistics
    shots_home = match_data.get('home_shots', 0)
    shots_away = match_data.get('home_shots', 0)
    home_attacks = match_data.get('home_dangerous_attacks', 0)
    away_attacks = match_data.get('away_dangerous_attacks', 0)
    possession_home = match_data.get('possession_home', 50)
    
    logger.info(f"Shots: {shots_home}-{shots_away}")
    logger.info(f"Dangerous Attacks: {home_attacks}-{away_attacks}")
    logger.info(f"Possession: {possession_home}%")
    
    # 3. Apply specialized rules
    bet_actions = SpecializedRules.evaluate_all_rules(match_data)
    
    logger.info("-" * 80)
    logger.info(f"Found {len(bet_actions)} potential betting opportunities:")
    
    if bet_actions:
        for i, action in enumerate(bet_actions, 1):
            logger.info(f"{i}. Market: {action['market']}")
            logger.info(f"   Reason: {action['reason']}")
            logger.info(f"   Confidence: {action['confidence']:.2f}")
            if 'odds' in action:
                logger.info(f"   Odds: {action['odds']}")
            logger.info("")
        
        # 4. Send bet signals to RabbitMQ
        publisher = get_rabbitmq_publisher()
        for action in bet_actions:
            success = publisher.publish_bet_signal(action)
            if success:
                logger.info(f"Sent bet signal for {action['market']}")
        publisher.close()
    else:
        logger.info("No betting opportunities found.")
    
    logger.info("=" * 80)


def load_match_from_file(file_path: str) -> Dict[str, Any]:
    """
    Load match document from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary containing match data
    """
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading match document from {file_path}: {e}")
        return {}


def load_match_from_string(json_str: str) -> Dict[str, Any]:
    """
    Load match document from a JSON string.
    
    Args:
        json_str: JSON string containing match data
        
    Returns:
        Dictionary containing match data
    """
    try:
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Error parsing JSON string: {e}")
        return {}


def main():
    """Main entry point for the script."""
    if len(sys.argv) > 1:
        # Load from file if provided
        match_doc = load_match_from_file(sys.argv[1])
    else:
        # Ask for JSON input if no file provided
        print("Please paste the match document JSON (Ctrl+D when finished):")
        json_str = sys.stdin.read()
        match_doc = load_match_from_string(json_str)
    
    if match_doc:
        process_match_document(match_doc)
    else:
        logger.error("No valid match document provided.")


if __name__ == "__main__":
    main()
