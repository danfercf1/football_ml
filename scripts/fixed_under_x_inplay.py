#!/usr/bin/env python3
"""
Fixed implementation of the Under X In-Play betting strategy using dictionary-based rules only.
"""
import json
import logging
import sys
import os
import time
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.match_processor import get_match_processor
from src.rules_loader import load_betting_rules

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def default_betting_rules():
    """
    Return a list of default betting rules for the Under X In-Play strategy.
    
    Returns:
        List of betting rule dictionaries
    """
    # Always use dictionary-based approach for maximum compatibility
    return [
        {
            "rule_type": "goals",
            "active": True,
            "odds": {
                "min": 1.01,
                "max": 1.05
            },
            "min_goals": 1,
            "max_goals": 3,
            "min_goal_line_buffer": 2.5
        },
        {
            "rule_type": "stake",
            "active": True,
            "stake": 0.50,
            "stake_strategy": "fixed"
        },
        {
            "rule_type": "time",
            "active": True,
            "min_minute": 52,
            "max_minute": 61
        }
    ]


def evaluate_betting_rules(match_data: Dict[str, Any], rules: list) -> Dict[str, Any]:
    """
    Evaluate a list of betting rules against match data.
    
    Args:
        match_data: Match data dictionary
        rules: List of betting rule dictionaries
        
    Returns:
        Dictionary with evaluation results
    """
    # Enable testing without MongoDB connection
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get testing mode configuration
    TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
    NO_RULES_MODE = os.getenv("NO_RULES_MODE", "true").lower() == "true"
    
    results = {
        "match_id": match_data.get("match_id", "unknown"),
        "is_suitable": True,  # Default to True, will be set to False if any active rule fails
        "rules_passed": [],
        "rules_failed": [],
        "stake": 0.0,
        "stake_strategy": "none"
    }
    
    # In NO_RULES_MODE, always return that the match is suitable
    if NO_RULES_MODE and TEST_MODE:
        logger.info("Running in NO_RULES_MODE - all matches will be considered suitable")
        results["rules_passed"] = ["goals", "stake", "time"]
        results["stake"] = float(os.getenv("TEST_BET_AMOUNT", "0.50"))
        results["stake_strategy"] = "fixed"
        return results
    
    # Check each rule
    for rule in rules:
        # Dictionary-based rule
        if not rule.get("active", True):
            continue
            
        rule_type = rule.get("rule_type", "")
        
        if rule_type == "goals":
            # Parse score to get total goals
            score = match_data.get("score", "0 - 0")
            try:
                home_goals, away_goals = map(int, score.split(" - "))
                total_goals = home_goals + away_goals
            except ValueError:
                logger.error(f"Could not parse score: {score}")
                total_goals = 0
                
            # Check goals conditions
            min_goals = rule.get("min_goals", 0)
            max_goals = rule.get("max_goals", 99)
            
            if total_goals < min_goals or total_goals > max_goals:
                results["rules_failed"].append("goals")
                results["is_suitable"] = False
            else:
                results["rules_passed"].append("goals")
                
        elif rule_type == "time":
            # Check time conditions
            minute = match_data.get("minute", 0)
            min_minute = rule.get("min_minute", 0)
            max_minute = rule.get("max_minute", 90)
            
            if minute < min_minute or minute > max_minute:
                results["rules_failed"].append("time")
                results["is_suitable"] = False
            else:
                results["rules_passed"].append("time")
                
        elif rule_type == "stake":
            # Handle stake parameters
            results["stake"] = rule.get("stake", 0.0)
            results["stake_strategy"] = rule.get("stake_strategy", "fixed")
            results["rules_passed"].append("stake")
    
    return results


class UnderXInPlayStrategy:
    """
    Implementation of the Under X In-Play betting strategy.
    """
    
    def __init__(self):
        """Initialize the strategy parameters."""
        self.min_minute = 52
        self.max_minute = 61
        self.min_goals = 1
        self.max_goals = 3
        self.cashout_threshold_goals = 2
        self.cashout_max_minute = 82
        self.processor = get_match_processor()
    
    def analyze_match(self, match_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a match to determine if it's suitable for the Under X In-Play strategy.
        
        Args:
            match_doc: The match document to analyze
            
        Returns:
            Analysis results dictionary
        """
        # Process the match document
        match_data = self.processor.process_match_document(match_doc)
        
        # Extract key information
        match_minute = match_data.get("minute", 0)
        score = match_data.get("score", "0 - 0")
        
        # Parse score to get goals
        try:
            home_goals, away_goals = map(int, score.split(" - "))
            total_goals = home_goals + away_goals
        except ValueError:
            logger.error(f"Could not parse score: {score}")
            total_goals = 0
        
        # Get teams' average goals per match
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")
        home_avg_goals = self._get_team_avg_goals(match_data, "home")
        away_avg_goals = self._get_team_avg_goals(match_data, "away")
        combined_avg_goals = home_avg_goals + away_avg_goals
        
        # Calculate the target under goal line
        target_goal_line = total_goals + 4
        bet_market = f"under_{target_goal_line}.5"
        
        # Get current odds for this market if available
        under_odds = self._get_under_odds(match_data, target_goal_line)
        
        # Check if match meets our criteria using the legacy method
        is_suitable_legacy = (
            self.min_minute <= match_minute <= self.max_minute and
            self.min_goals <= total_goals <= self.max_goals and
            combined_avg_goals < 3.0  # Low scoring teams threshold
        )
        
        # Create enhanced match data with all the information needed for rule evaluation
        enhanced_match_data = {
            "match_id": match_data.get("match_id", "unknown"),
            "home_team": home_team,
            "away_team": away_team,
            "league": match_data.get("league", ""),
            "country": match_data.get("country", ""),
            "minute": match_minute,
            "score": score,
            "total_goals": total_goals,
            "home_avg_goals": home_avg_goals,
            "away_avg_goals": away_avg_goals,
            "combined_avg_goals": combined_avg_goals,
            "odds": {
                f"under_{target_goal_line}.5": under_odds
            }
        }
        
        # Apply the betting rules system
        try:
            # Load rules from MongoDB or JSON file using the new loader
            rules = load_betting_rules("under_x_inplay")
            
            # If no rules were loaded, use the hardcoded default rules
            if not rules:
                logger.warning("No rules loaded from MongoDB or JSON, using hardcoded defaults")
                rules = default_betting_rules()
                
            rule_results = evaluate_betting_rules(enhanced_match_data, rules)
            
            # Combine legacy and new rule system results
            is_suitable = is_suitable_legacy and rule_results["is_suitable"]
        except Exception as e:
            logger.error(f"Error applying betting rules: {e}")
            rule_results = {"is_suitable": False, "rules_passed": [], "rules_failed": []}
            is_suitable = is_suitable_legacy
        
        # Prepare the result dictionary
        result = {
            "match_id": match_data.get("match_id", "unknown"),
            "home_team": home_team,
            "away_team": away_team,
            "minute": match_minute,
            "score": score,
            "total_goals": total_goals,
            "home_avg_goals": home_avg_goals,
            "away_avg_goals": away_avg_goals,
            "combined_avg_goals": combined_avg_goals,
            "target_under_line": f"Under {target_goal_line}.5",
            "odds": under_odds,
            "is_suitable": is_suitable,
            "reasons": [],
            "recommendation": None
        }
        
        # Add reasons why match is or isn't suitable
        if match_minute < self.min_minute or match_minute > self.max_minute:
            result["reasons"].append(f"Match minute {match_minute} outside target range {self.min_minute}-{self.max_minute}")
        
        if total_goals < self.min_goals or total_goals > self.max_goals:
            result["reasons"].append(f"Total goals {total_goals} outside target range {self.min_goals}-{self.max_goals}")
        
        if combined_avg_goals >= 3.0:
            result["reasons"].append(f"Teams have high combined average goals ({combined_avg_goals:.2f})")
            
        # Add results from rule evaluation system
        if rule_results["rules_passed"]:
            result["rules_passed"] = rule_results["rules_passed"]
            
        if rule_results["rules_failed"]:
            result["rules_failed"] = rule_results["rules_failed"]
            for failed_rule in rule_results["rules_failed"]:
                result["reasons"].append(f"Failed {failed_rule} rule criteria")
        
        # Make recommendation
        if is_suitable:
            # Calculate risk level based on various factors
            risk_score = self._calculate_risk_score(match_data, total_goals)
            
            if risk_score < 3:
                risk_level = "LOW"
            elif risk_score < 5:
                risk_level = "MEDIUM"
            else:
                risk_level = "HIGH"
                
            # Get stake amount from rules if available
            stake_amount = rule_results.get("stake", 0.0)
            stake_strategy = rule_results.get("stake_strategy", "fixed")
            
            # Format stake recommendation based on rules and risk level
            if stake_amount > 0:
                if stake_strategy == "fixed":
                    stake_recommendation = f"{stake_amount:.2f} units (fixed)"
                else:
                    stake_recommendation = f"{stake_amount:.2f}% of bankroll ({stake_strategy})"
            else:
                stake_recommendation = "2% of bankroll (low risk)" if risk_score < 3 else "1% of bankroll"
            
            result["recommendation"] = {
                "action": "PLACE BET",
                "market": bet_market,
                "odds": under_odds,
                "risk_level": risk_level,
                "cashout_trigger": f"{self.cashout_threshold_goals}+ more goals before minute {self.cashout_max_minute}",
                "stake_recommendation": stake_recommendation
            }
            
            # Add the bet signal
            if under_odds > 0:
                result["bet_signal"] = {
                    "match_id": match_data.get("match_id", "unknown"),
                    "home_team": home_team,
                    "away_team": away_team,
                    "market": bet_market,
                    "odds": under_odds,
                    "stake": stake_amount if stake_amount > 0 else (0.02 if risk_score < 3 else 0.01),
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "under_x_inplay",
                    "risk_level": risk_level
                }
        
        return result
    
    def _get_team_avg_goals(self, match_data: Dict[str, Any], team_type: str) -> float:
        """
        Get average goals for a team based on historical data.
        
        Args:
            match_data: Match data dictionary
            team_type: Either "home" or "away"
            
        Returns:
            Average goals per match
        """
        try:
            history = match_data.get("history", {})
            team_history = history.get(f"{team_type}_team", {})
            return team_history.get("avg_goals_scored", 1.5)
        except Exception as e:
            logger.error(f"Error getting average goals: {e}")
            return 1.5  # Default value if not available
    
    def _get_under_odds(self, match_data: Dict[str, Any], target_line: int) -> float:
        """
        Get the current odds for an under market.
        
        Args:
            match_data: Match data dictionary
            target_line: Target goal line (e.g., 4 for Under 4.5)
            
        Returns:
            Odds value or 0 if not available
        """
        try:
            # Try to get odds directly if available in the data
            odds = match_data.get("odds", {})
            market = f"under_{target_line}.5"
            if market in odds:
                return odds[market]
            
            # If not found directly, use a fallback calculation (very simplified)
            # This is just a placeholder for when real odds are not available
            current_goals = match_data.get("total_goals", 0)
            # Simplified odds calculation: higher line = lower odds
            buffer = target_line - current_goals
            if buffer <= 1:
                return 1.20
            elif buffer <= 2:
                return 1.10
            elif buffer <= 3:
                return 1.05
            else:
                return 1.03
        except Exception as e:
            logger.error(f"Error calculating under odds: {e}")
            return 0.0
    
    def _calculate_risk_score(self, match_data: Dict[str, Any], total_goals: int) -> int:
        """
        Calculate a risk score for this bet.
        
        Args:
            match_data: Match data dictionary
            total_goals: Total goals scored so far
            
        Returns:
            Risk score (0-10)
        """
        risk = 0
        
        # More goals = higher risk
        risk += total_goals
        
        # High scoring teams = higher risk
        combined_avg_goals = match_data.get("combined_avg_goals", 0)
        if combined_avg_goals > 2.5:
            risk += 1
        if combined_avg_goals > 3.0:
            risk += 1
        
        # High possession differential = higher risk
        try:
            stats = match_data.get("stats", {})
            home_possession = stats.get("home", {}).get("possession", 50)
            possession_diff = abs(home_possession - 50)
            if possession_diff > 20:
                risk += 1
        except:
            pass
        
        # Limit to 0-10 scale
        return max(0, min(10, risk))


if __name__ == "__main__":
    """
    Run a standalone test of the Under X In-Play strategy.
    """
    # Create a simple test match
    test_match = {
        "match_id": "test_match_123",
        "home_team": "Team A",
        "away_team": "Team B",
        "minute": 55,
        "score": "1 - 1",
        "league": "Test League",
        "country": "Test Country",
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
    
    # Run the analysis
    strategy = UnderXInPlayStrategy()
    analysis = strategy.analyze_match(test_match)
    
    # Print the results
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
    if analysis.get("recommendation"):
        logger.info("-" * 80)
        logger.info(f"Recommendation: {analysis['recommendation']['action']}")
        logger.info(f"Market: {analysis['recommendation']['market']}")
        logger.info(f"Odds: {analysis['recommendation']['odds']}")
        logger.info(f"Risk level: {analysis['recommendation']['risk_level']}")
        logger.info(f"Suggested stake: {analysis['recommendation']['stake_recommendation']}")
        logger.info(f"Cashout trigger: {analysis['recommendation']['cashout_trigger']}")
    logger.info("=" * 80)
