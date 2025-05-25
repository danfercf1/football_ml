#!/usr/bin/env python3
"""
Script to test the betting_rules module.
"""
import sys
import os
import json

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.betting_rules import default_betting_rules

def main():
    """Test the betting_rules module."""
    print("Testing betting_rules module...")
    
    # Create a sample match data dictionary
    match_data = {
        "match_id": "test_match_123",
        "home_team": "Test Home",
        "away_team": "Test Away",
        "league": "Test League",
        "country": "Test Country",
        "minute": 70,
        "score": "2 - 1",
        "odds": {
            "under_6.5": 1.03
        }
    }
    
    print(f"\nSample match data: {json.dumps(match_data, indent=2)}")
    
    # Get default rules
    try:
        rules = default_betting_rules()
        print(f"\nDefault betting rules: {len(rules)} rules found")
        
        # Handle either class-based or dictionary-based rules
        for i, rule in enumerate(rules, 1):
            try:
                # Try to handle as class-based rule
                rule_type = rule.rule_type
                active = rule.active
                params_str = json.dumps(rule.params, indent=2)
                print(f"\nRule {i}: {rule_type}")
                print(f"  Active: {active}")
                print(f"  Parameters: {params_str}")
            except AttributeError:
                # Handle as dictionary-based rule
                rule_type = rule.get("rule_type", "unknown")
                active = rule.get("active", False)
                params = {k: v for k, v in rule.items() if k not in ["rule_type", "active"]}
                print(f"\nRule {i}: {rule_type}")
                print(f"  Active: {active}")
                print(f"  Parameters: {json.dumps(params, indent=2)}")
    except Exception as e:
        print(f"Error getting betting rules: {e}")

if __name__ == "__main__":
    print("Starting test_betting_rules.py script...")
    main()
    print("Script execution complete.")
