"""
Module for rule-based analysis of live soccer match data.
"""
import logging
from typing import Dict, Any, List, Optional

from src import config

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Engine for evaluating betting rules against live match data.
    """
    
    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize the rule engine with a list of rules.
        
        Args:
            rules: Optional list of rule documents from MongoDB
        """
        self.rules = rules or []
    
    def set_rules(self, rules: List[Dict[str, Any]]) -> None:
        """
        Update the rules used by the engine.
        
        Args:
            rules: List of rule documents from MongoDB
        """
        self.rules = rules
        logger.info(f"Updated rules in rule engine: {len(rules)} rules loaded")
    
    def evaluate(self, match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against the current match data.
        
        Args:
            match_data: Dictionary containing live match data
            
        Returns:
            List of dictionaries containing matching rules and bet actions
        """
        if not self.rules:
            logger.warning("No rules available for evaluation")
            return []
            
        matching_rules = []
        
        # Extract match league
        match_league = match_data.get("league")
        
        for rule in self.rules:
            # Skip disabled rules
            if not rule.get("enabled", False):
                continue
                
            # Skip rules that don't match the current league if specified
            rule_league = rule.get("league")
            if rule_league and match_league and rule_league != match_league:
                continue
                
            # Check if conditions match
            if self._evaluate_conditions(rule.get("conditions", {}), match_data):
                bet_action = {
                    "match_id": match_data.get("match_id", "unknown"),
                    "market": rule.get("market"),
                    "action": "place",
                    "reason": f"rule_{rule.get('type', 'unknown')}",
                    "rule_id": str(rule.get("_id", ""))
                }
                
                # Add odds if available
                market = rule.get("market")
                if market and "odds" in match_data and market in match_data["odds"]:
                    bet_action["odds"] = match_data["odds"][market]
                
                matching_rules.append(bet_action)
                logger.info(f"Rule match: {rule.get('type')} rule triggered for {market}")
        
        return matching_rules
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], match_data: Dict[str, Any]) -> bool:
        """
        Evaluate if all conditions in a rule match the current match data.
        
        Args:
            conditions: Dictionary of conditions from a rule
            match_data: Dictionary containing live match data
            
        Returns:
            True if all conditions match, False otherwise
        """
        # If no conditions, rule always matches
        if not conditions:
            return True
            
        for field, condition in conditions.items():
            # Skip if field not in match data
            if field not in match_data:
                return False
                
            # Get value from match data
            value = match_data[field]
            
            # Handle different condition types
            if isinstance(condition, dict):
                for operator, threshold in condition.items():
                    if not self._check_condition(value, operator, threshold):
                        return False
            else:
                # Simple equality check
                if value != condition:
                    return False
        
        return True
    
    @staticmethod
    def _check_condition(value: Any, operator: str, threshold: Any) -> bool:
        """
        Check if a single condition matches a value using the specified operator.
        
        Args:
            value: Value from match data
            operator: String representing the operator (e.g., "$gt", "$lt")
            threshold: Threshold value to compare against
            
        Returns:
            True if condition is met, False otherwise
        """
        if operator == "$gt":
            return value > threshold
        elif operator == "$gte":
            return value >= threshold
        elif operator == "$lt":
            return value < threshold
        elif operator == "$lte":
            return value <= threshold
        elif operator == "$eq":
            return value == threshold
        elif operator == "$ne":
            return value != threshold
        elif operator == "$in":
            return value in threshold
        elif operator == "$nin":
            return value not in threshold
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False


def get_rule_engine(rules: Optional[List[Dict[str, Any]]] = None) -> RuleEngine:
    """
    Create and return a rule engine instance.
    
    Args:
        rules: Optional list of rule documents from MongoDB
        
    Returns:
        Configured RuleEngine
    """
    return RuleEngine(rules=rules)


if __name__ == "__main__":
    # Test the rule engine with some sample data
    logging.basicConfig(level=logging.INFO)
    
    # Sample rules
    sample_rules = [
        {
            "type": "shots",
            "league": "premier_league",
            "conditions": {
                "home_shots": {"$gt": 10},
                "minute": {"$gt": 60}
            },
            "market": "over_2.5",
            "enabled": True
        },
        {
            "type": "xg",
            "league": "premier_league",
            "conditions": {
                "total_xg": {"$gt": 2.0}
            },
            "market": "over_2.5",
            "enabled": True
        }
    ]
    
    # Sample match data
    match_data = {
        "match_id": "test-123",
        "minute": 75,
        "league": "premier_league",
        "home_shots": 12,
        "away_shots": 5,
        "total_xg": 2.5,
        "odds": {
            "over_2.5": 1.5,
            "under_2.5": 2.5
        }
    }
    
    # Create rule engine and evaluate
    rule_engine = get_rule_engine(sample_rules)
    results = rule_engine.evaluate(match_data)
    
    # Print results
    print(f"Found {len(results)} matching rules:")
    for result in results:
        print(f"  - {result['market']}: {result['reason']}")
