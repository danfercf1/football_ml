#!/usr/bin/env python3
"""
Test script for the Under X In-Play betting strategy.
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

# Import the strategy
from scripts.under_x_inplay import UnderXInPlayStrategy


class TestUnderXInPlayStrategy(unittest.TestCase):
    """Test cases for the Under X In-Play strategy."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = UnderXInPlayStrategy()
        
        # Create a suitable match document
        self.suitable_match = {
            "match_id": "123456",
            "home_team": "Team A",
            "away_team": "Team B",
            "minute": 55,
            "score": "1 - 1",
            "home_goals_scored": 1.2,  # Average goals per match
            "away_goals_scored": 0.9,  # Average goals per match
            "home_dangerous_attacks": 25,
            "away_dangerous_attacks": 15,
            "odds": {
                "overUnderOdds": {
                    "under": {
                        "5.5": {"odds": {"bet365": "1.02", "unibet": "1.03"}}
                    }
                }
            }
        }
        
        # Create an unsuitable match document
        self.unsuitable_match = {
            "match_id": "789012",
            "home_team": "Team C",
            "away_team": "Team D",
            "minute": 35,  # Outside target window
            "score": "3 - 3",  # Too many goals
            "home_goals_scored": 2.5,  # High average
            "away_goals_scored": 2.2,  # High average
            "home_dangerous_attacks": 45,
            "away_dangerous_attacks": 38
        }
        
        # Mock the match processor
        self.mock_processor = MagicMock()
        self.mock_processor.process_match_document.side_effect = lambda x: x

    @patch('scripts.under_x_inplay.get_match_processor')
    def test_suitable_match(self, mock_get_processor):
        """Test that a suitable match returns the correct recommendation."""
        # Set up the mock
        mock_get_processor.return_value = self.mock_processor
        self.strategy.processor = self.mock_processor
        
        # Run the analysis
        result = self.strategy.analyze_match(self.suitable_match)
        
        # Check the results
        self.assertTrue(result["is_suitable"])
        self.assertIsNotNone(result["recommendation"])
        self.assertEqual(result["recommendation"]["action"], "PLACE BET")
        self.assertTrue("under" in result["recommendation"]["market"])
        self.assertIsNotNone(result["bet_signal"])
        
    @patch('scripts.under_x_inplay.get_match_processor')
    def test_unsuitable_match(self, mock_get_processor):
        """Test that an unsuitable match returns no recommendation."""
        # Set up the mock
        mock_get_processor.return_value = self.mock_processor
        self.strategy.processor = self.mock_processor
        
        # Run the analysis
        result = self.strategy.analyze_match(self.unsuitable_match)
        
        # Check the results
        self.assertFalse(result["is_suitable"])
        self.assertIsNone(result["recommendation"])
        self.assertNotIn("bet_signal", result)
        self.assertTrue(len(result["reasons"]) > 0)
        
    @patch('scripts.under_x_inplay.get_match_processor')
    def test_risk_calculation(self, mock_get_processor):
        """Test that risk calculation works correctly."""
        # Set up the mock
        mock_get_processor.return_value = self.mock_processor
        self.strategy.processor = self.mock_processor
        
        # Calculate risk for different scenarios
        low_risk_match = self.suitable_match.copy()
        low_risk_match["home_goals_scored"] = 0.8
        low_risk_match["away_goals_scored"] = 0.7
        
        medium_risk_match = self.suitable_match.copy()
        medium_risk_match["home_goals_scored"] = 1.8
        medium_risk_match["away_goals_scored"] = 1.1
        medium_risk_match["home_dangerous_attacks"] = 35
        medium_risk_match["away_dangerous_attacks"] = 30
        
        # Test risk levels
        low_risk_result = self.strategy.analyze_match(low_risk_match)
        medium_risk_result = self.strategy.analyze_match(medium_risk_match)
        
        # Verify that risk assessment is working
        self.assertEqual(low_risk_result["recommendation"]["risk_level"], "LOW")
        
        # For the medium risk match, it should be either MEDIUM or HIGH
        # depending on other factors in the calculation
        risk_level = medium_risk_result["recommendation"]["risk_level"]
        self.assertIn(risk_level, ["MEDIUM", "HIGH"])


if __name__ == "__main__":
    unittest.main()
