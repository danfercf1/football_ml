#!/usr/bin/env python3
"""
Module containing advanced betting rules definitions for football matches.

This module provides functions and classes to define, evaluate, and manage 
betting rules for football matches, particularly for the "Under X In-Play" strategy.
"""
import logging
from typing import Dict, Any, List, Optional
from pymongo import MongoClient
import src.config as config  # Import the config file that contains DB settings
from src.mongo_handler import MongoHandler
from src.ml_predictor import get_ml_predictor  # Import ML predictor from new file

logger = logging.getLogger(__name__)

class BettingRule:
    """
    Base class for betting rules.
    """
    
    def __init__(
        self, 
        rule_type: str,
        active: bool = True,
        **params
    ):
        """
        Initialize a betting rule.
        
        Args:
            rule_type: Type of rule (e.g., "goals", "stake", "time", etc.)
            active: Whether the rule is active
            **params: Additional rule-specific parameters
        """
        self.rule_type = rule_type
        self.active = active
        self.params = params
        
    def evaluate(self, match_data: Dict[str, Any]) -> bool:
        """
        Evaluate if the rule conditions are met for the given match data.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            True if conditions are met, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")


class GoalsRule(BettingRule):
    """
    Rule for goals-related conditions.
    """
    
    def __init__(
        self,
        active: bool = True,
        min_odds: float = 1.01,
        max_odds: float = 1.05,
        match: str = None,
        country: str = None,
        league: str = None,
        min_goals: int = 1,
        max_goals: int = 3,
        min_goal_line_buffer: float = 2.5,
        **params
    ):
        """
        Initialize a goals-related rule.
        
        Args:
            active: Whether the rule is active
            min_odds: Minimum acceptable odds
            max_odds: Maximum acceptable odds
            match: Match identifier or filter
            country: Country filter
            league: League filter
            min_goals: Minimum total goals required
            max_goals: Maximum total goals allowed
            min_goal_line_buffer: Minimum buffer for the goal line
            **params: Additional parameters
        """
        super().__init__("goals", active)
        self.params.update({
            "odds": {"min": min_odds, "max": max_odds},
            "match": match,
            "country": country,
            "league": league,
            "min_goals": min_goals,
            "max_goals": max_goals,
            "min_goal_line_buffer": min_goal_line_buffer
        })
        self.params.update(params)
    
    def evaluate(self, match_data: Dict[str, Any]) -> bool:
        """
        Evaluate if the goals-related conditions are met.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            True if conditions are met, False otherwise
        """
        if not self.active:
            return False
            
        try:
            # Extract match information
            score = match_data.get("score", "0 - 0")
            
            # Parse score
            try:
                home_goals, away_goals = map(int, score.split(" - "))
                total_goals = home_goals + away_goals
            except ValueError:
                logger.error(f"Could not parse score: {score}")
                return False
                
            # Check league/country filters if specified
            if self.params["league"] and match_data.get("league") != self.params["league"]:
                return False
                
            if self.params["country"] and match_data.get("country") != self.params["country"]:
                return False
                
            # Check match filter if specified
            if self.params["match"] and not self._match_filter(match_data):
                return False
                
            # Check goals conditions
            min_goals = self.params["min_goals"]
            max_goals = self.params["max_goals"]
            
            if total_goals < min_goals or total_goals > max_goals:
                return False
                
            # Check odds if available
            if "odds" in match_data:
                try:
                    # Process odds with helper method - keep a local reference
                    local_odds_data = self._extract_odds(match_data)
                    target_goal_line = total_goals + self.params["min_goal_line_buffer"]
                    market = f"under_{target_goal_line}.5"
                    
                    # Debug the market we're looking for
                    logger.debug(f"Looking for market {market} in extracted odds")
                    
                    if market in local_odds_data:
                        odds_value = local_odds_data[market]
                        odds_min = self.params["odds"]["min"]
                        odds_max = self.params["odds"]["max"]
                        
                        if odds_value < odds_min or odds_value > odds_max:
                            return False
                except Exception as e:
                    import traceback
                    logger.error(f"Error extracting odds: {e}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                    # Don't fail the rule evaluation just because of odds issues
                    pass
            
            # All conditions passed
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Error evaluating GoalsRule: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return False
    
    def _extract_odds(self, match_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract and process odds data from match data.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            Dictionary of processed odds data
        """
        try:
            # Get the raw odds data
            odds_data = match_data.get("odds", {})
            processed_odds = {}
            
            # Debug the incoming odds structure
            logger.debug(f"Extracting odds from structure: {type(odds_data)}")
            
            # Handle direct format where market names are keys
            if isinstance(odds_data, dict):
                # Copy any direct market odds
                for key, value in odds_data.items():
                    if isinstance(key, str) and key.startswith("under_") and isinstance(value, (int, float)):
                        processed_odds[key] = float(value)
                
                # Check for nested odds structure
                if "overUnderOdds" in odds_data and "under" in odds_data["overUnderOdds"]:
                    under_odds = odds_data["overUnderOdds"]["under"]
                    
                    # Process the nested structure
                    for line_str, odds_info in under_odds.items():
                        try:
                            if "odds" in odds_info:
                                best_odd = 0
                                for bookie, odd_value in odds_info["odds"].items():
                                    try:
                                        odd = float(odd_value)
                                        best_odd = max(best_odd, odd)
                                    except (ValueError, TypeError):
                                        pass
                                
                                if best_odd > 0:
                                    # Format may vary, but try to get a clean line number
                                    line = float(line_str) if '.' in line_str else float(line_str + '.0')
                                    market_key = f"under_{line}"
                                    processed_odds[market_key] = best_odd
                        except Exception as e:
                            logger.debug(f"Error processing odds for line {line_str}: {e}")
            
            # If no processed odds were found, try simpler fallback
            if not processed_odds:
                # Simple fallback - just extract any numeric values with "under" keys
                if isinstance(odds_data, dict):
                    for key, value in odds_data.items():
                        if "under" in str(key).lower() and isinstance(value, (int, float, str)):
                            try:
                                processed_odds[str(key)] = float(value)
                            except (ValueError, TypeError):
                                pass
            
            logger.debug(f"Extracted odds data: {processed_odds}")
            return processed_odds
            
        except Exception as e:
            import traceback
            logger.error(f"Error in _extract_odds: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Return empty dict on error to avoid failures
            return {}

    def _match_filter(self, match_data: Dict[str, Any]) -> bool:
        """
        Apply match-specific filters.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            True if the match passes the filter, False otherwise
        """
        match_filter = self.params["match"]
        
        # If match is a string, check against match_id or teams
        if isinstance(match_filter, str):
            match_id = match_data.get("match_id", "")
            home_team = match_data.get("home_team", "")
            away_team = match_data.get("away_team", "")
            
            return (match_filter in match_id or 
                    match_filter in home_team or 
                    match_filter in away_team)
                    
        # If match is a callable function, apply it
        elif callable(match_filter):
            return match_filter(match_data)
            
        # Otherwise consider it's a complex filter we can't process
        return False


class StakeRule(BettingRule):
    """
    Rule for stake-related parameters.
    """
    
    def __init__(
        self,
        active: bool = True,
        stake: float = 0.5,
        stake_strategy: str = "fixed",
        **params
    ):
        """
        Initialize a stake-related rule.
        
        Args:
            active: Whether the rule is active
            stake: Amount to stake
            stake_strategy: Strategy for stake calculation
            **params: Additional parameters
        """
        super().__init__("stake", active)
        self.params.update({
            "stake": stake,
            "stake_strategy": stake_strategy
        })
        self.params.update(params)
    
    def evaluate(self, match_data: Dict[str, Any]) -> bool:
        """
        Stake rules always return true if active, as they don't filter matches.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            True if the rule is active, False otherwise
        """
        return self.active


class TimeRule(BettingRule):
    """
    Rule for time-related conditions.
    """
    
    def __init__(
        self,
        active: bool = True,
        min_minute: int = 65,
        max_minute: int = 75,
        **params
    ):
        """
        Initialize a time-related rule.
        
        Args:
            active: Whether the rule is active
            min_minute: Minimum match minute
            max_minute: Maximum match minute
            **params: Additional parameters
        """
        super().__init__("time", active)
        self.params.update({
            "min_minute": min_minute,
            "max_minute": max_minute
        })
        self.params.update(params)
    
    def evaluate(self, match_data: Dict[str, Any]) -> bool:
        """
        Evaluate if the time-related conditions are met.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            True if conditions are met, False otherwise
        """
        if not self.active:
            return False
            
        try:
            minute = match_data.get("minute", 0)
            min_minute = self.params["min_minute"]
            max_minute = self.params["max_minute"]
            
            return min_minute <= minute <= max_minute
            
        except Exception as e:
            logger.error(f"Error evaluating TimeRule: {e}")
            return False


class OddsRule(BettingRule):
    """
    Rule for odds-related conditions.
    """
    
    def __init__(
        self,
        active: bool = True,
        min_odds: float = 1.01,
        max_odds: float = 1.04,
        odds_type: str = "exact",
        **params
    ):
        """
        Initialize an odds-related rule.
        
        Args:
            active: Whether the rule is active
            min_odds: Minimum acceptable odds
            max_odds: Maximum acceptable odds
            odds_type: Type of odds to check (exact, under, over)
            **params: Additional parameters
        """
        super().__init__("odds", active)
        self.params.update({
            "min": min_odds,
            "max": max_odds,
            "odds_type": odds_type
        })
        self.params.update(params)
    
    def evaluate(self, match_data: Dict[str, Any]) -> bool:
        """
        Evaluate if the odds-related conditions are met.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            True if conditions are met, False otherwise
        """
        if not self.active:
            return False
            
        try:
            # Check countries/leagues filters if specified
            if "countries" in self.params and self.params["countries"]:
                country = match_data.get("country")
                if country not in self.params["countries"]:
                    return False
                    
            if "leagues" in self.params and self.params["leagues"]:
                league = match_data.get("league")
                if league not in self.params["leagues"]:
                    return False
            
            # Extract odds from match data
            odds_data = match_data.get("odds", {})
            if not odds_data:
                logger.warning("No odds data available for evaluation")
                return False
                
            # Try to extract the appropriate odds based on the match state
            score = match_data.get("score", "0 - 0")
            try:
                home_goals, away_goals = map(int, score.split(" - "))
                total_goals = home_goals + away_goals
                
                # Look for under odds with a reasonable buffer
                target_line = None
                for possible_line in [f"{total_goals + 0.5}", f"{total_goals + 1.5}", f"{total_goals + 2.5}", f"{total_goals + 3.5}"]:
                    if f"under_{possible_line}" in odds_data:
                        target_line = possible_line
                        break
                
                if not target_line:
                    return False
                    
                odds_value = odds_data.get(f"under_{target_line}")
                if not odds_value:
                    # Try to extract from complex structure
                    if "overUnderOdds" in odds_data and "under" in odds_data["overUnderOdds"]:
                        under_odds = odds_data["overUnderOdds"]["under"]
                        if target_line in under_odds and "odds" in under_odds[target_line]:
                            # Get the best (highest) odds available
                            best_odd = 0
                            for bookie, odd in under_odds[target_line]["odds"].items():
                                try:
                                    odd_value = float(odd)
                                    best_odd = max(best_odd, odd_value)
                                except (ValueError, TypeError):
                                    continue
                            odds_value = best_odd
                
                # Check if odds are within the acceptable range
                if not odds_value or not isinstance(odds_value, (int, float)):
                    return False
                    
                min_odds = self.params.get("min", 1.01)
                max_odds = self.params.get("max", 2.0)
                return min_odds <= odds_value <= max_odds
                
            except ValueError:
                logger.error(f"Could not parse score: {score}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating OddsRule: {e}")
            return False


class DivisorRule(BettingRule):
    """
    Rule for divisor-related conditions.
    """
    
    def __init__(
        self,
        active: bool = True,
        divisor: int = 8,
        **params
    ):
        """
        Initialize a divisor-related rule.
        
        Args:
            active: Whether the rule is active
            divisor: The divisor value
            **params: Additional parameters
        """
        super().__init__("divisor", active)
        self.params.update({
            "divisor": divisor
        })
        self.params.update(params)
    
    def evaluate(self, match_data: Dict[str, Any]) -> bool:
        """
        Evaluate if the divisor-related conditions are met.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            True if conditions are met, False otherwise
        """
        if not self.active:
            return False
            
        try:
            # Check countries/leagues filters if specified
            if "countries" in self.params and self.params["countries"]:
                country = match_data.get("country")
                if country not in self.params["countries"]:
                    return False
                    
            if "leagues" in self.params and self.params["leagues"]:
                league = match_data.get("league")
                if league not in self.params["leagues"]:
                    return False
            
            # A divisor rule usually applies to stake calculations or risk assessments
            # It doesn't necessarily filter out matches, but affects how they're handled
            # So we return True by default
            return True
                
        except Exception as e:
            logger.error(f"Error evaluating DivisorRule: {e}")
            return False


def get_betting_rules_from_db() -> List[Dict[str, Any]]:
    """
    Retrieve active betting rules from the MongoDB database.
    
    Returns:
        List of betting rule dictionaries from the database
    """
    try:
        # Create a MongoHandler instance
        mongo_handler = MongoHandler()
        
        # Use 'bettingrules' collection specifically
        collection = mongo_handler.db['bettingrules']
        
        # Find all active rules
        cursor = collection.find({"active": True})
        rules = list(cursor)
        
        # Close the connection
        mongo_handler.close()
        
        # Log how many rules were retrieved
        logger.info(f"Retrieved {len(rules)} active betting rules from MongoDB")
        
        # Convert MongoDB rules to the expected dictionary format
        formatted_rules = []
        for rule in rules:
            rule_type = rule.get("ruleType", "")
            
            # Create a base rule dictionary
            formatted_rule = {
                "rule_type": rule_type,
                "active": True
            }
            
            # Add specific fields based on rule type
            if rule_type == "goals":
                formatted_rule.update({
                    "min_goals": rule.get("minGoals", 1),
                    "max_goals": rule.get("maxGoals", 3),
                    "min_goal_line_buffer": rule.get("minGoalLineBuffer", 2.5)
                })
                # Add odds if present
                if "odds" in rule:
                    formatted_rule["odds"] = {
                        "min": rule["odds"].get("min", 1.01),
                        "max": rule["odds"].get("max", 1.05)
                    }
                
                # Add countries/leagues filters if present
                if "countries" in rule and rule["countries"]:
                    formatted_rule["countries"] = rule["countries"]
                if "leagues" in rule and rule["leagues"]:
                    formatted_rule["leagues"] = rule["leagues"]
                    
            elif rule_type == "stake":
                formatted_rule.update({
                    "stake": rule.get("stake", 0.5),
                    "stake_strategy": rule.get("stakeStrategy", "fixed")
                })
                
            elif rule_type == "time":
                formatted_rule.update({
                    "min_minute": rule.get("minMinute", 52),
                    "max_minute": rule.get("maxMinute", 61)
                })
                
            elif rule_type == "divisor":
                formatted_rule.update({
                    "divisor": rule.get("divisor", 8)
                })
                
            elif rule_type == "composite":
                formatted_rule.update({
                    "conditions": rule.get("conditions", [])
                })
                
            # Add the rule to the collection
            formatted_rules.append(formatted_rule)
                
        return formatted_rules
        
    except Exception as e:
        logger.error(f"Error retrieving betting rules from database: {e}")
        return []


def default_betting_rules():
    """
    Create default betting rules for the Under X In-Play strategy.
    First tries to retrieve rules from the database, then falls back to hardcoded rules.
    
    Returns:
        List of betting rules (BettingRule objects or dictionaries depending on implementation)
    """
    # First try to get rules from the database
    db_rules = get_betting_rules_from_db()
    if db_rules:
        logger.info("Using betting rules from database")
        return db_rules
    
    # If no database rules, fall back to hardcoded rules
    logger.info("Using hardcoded betting rules (no active rules found in database)")
    
    try:
        # Try to use class-based approach
        return [
            GoalsRule(
                active=True,
                min_odds=1.01,
                max_odds=1.05,
                min_goals=1,
                max_goals=3,
                min_goal_line_buffer=2.5
            ),
            StakeRule(
                active=True,
                stake=0.50,
                stake_strategy="fixed"
            ),
            TimeRule(
                active=True,
                min_minute=65,
                max_minute=75
            )
        ]
    except:
        # Fall back to dictionary-based approach
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
                "min_minute": 65,
                "max_minute": 75
            }
        ]


def evaluate_betting_rules(match_data: Dict[str, Any], rules: List[Any]) -> Dict[str, Any]:
    """
    Evaluate a list of betting rules against match data.
    
    Args:
        match_data: Match data dictionary
        rules: List of betting rule dictionaries or BettingRule objects
        
    Returns:
        Dictionary with evaluation results
    """
    results = {
        "match_id": match_data.get("match_id", "unknown"),
        "is_suitable": True,  # Default to True, will be set to False if any active rule fails
        "rules_passed": [],
        "rules_failed": [],
        "stake": 0.0,
        "stake_strategy": "none",
        "divisor": None  # Store divisor value if applicable
    }
    
    # Check each rule
    for rule in rules:
        # Handle both class-based rules and dictionary-based rules
        if isinstance(rule, BettingRule):
            # Class-based rule
            if not rule.active:
                continue
                
            rule_type = rule.rule_type
            
            # Evaluate the rule using its evaluate method
            if rule.evaluate(match_data):
                results["rules_passed"].append(rule_type)
                
                # If it's a stake rule, extract stake info
                if rule_type == "stake" and isinstance(rule, StakeRule):
                    results["stake"] = rule.params.get("stake", 0.0)
                    results["stake_strategy"] = rule.params.get("stake_strategy", "fixed")
            else:
                results["rules_failed"].append(rule_type)
                results["is_suitable"] = False
        else:
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
                
                # Check odds conditions if specified
                if "odds" in rule and "odds" in match_data:
                    try:
                        # Get odds range from rule
                        odds_min = rule["odds"].get("min", 0)
                        odds_max = rule["odds"].get("max", float('inf'))
                        
                        # Calculate target goal line
                        target_goal_line = total_goals + rule.get("min_goal_line_buffer", 2.5)
                        market = f"under_{target_goal_line}.5"
                        
                        # Get odds data directly from match_data (not processed_data)
                        odds_data = match_data.get("odds", {})
                        market_odds = 0
                        
                        # Extract the odds based on the structure
                        if market in odds_data:
                            # Direct access if available
                            market_odds = odds_data.get(market, 0)
                        elif isinstance(odds_data, dict) and "overUnderOdds" in odds_data:
                            # Try to extract from nested structure
                            if "under" in odds_data["overUnderOdds"]:
                                under_odds = odds_data["overUnderOdds"]["under"]
                                
                                # Find closest line
                                for line_str, odds_info in under_odds.items():
                                    try:
                                        if "odds" in odds_info:
                                            for bookie, odd_value in odds_info["odds"].items():
                                                try:
                                                    odd = float(odd_value)
                                                    if odd > market_odds:
                                                        market_odds = odd
                                                except (ValueError, TypeError):
                                                    pass
                                    except Exception:
                                        continue
                        
                        # Check if odds meet criteria
                        if market_odds > 0 and (market_odds < odds_min or market_odds > odds_max):
                            results["rules_failed"].append("odds")
                            results["is_suitable"] = False
                    except Exception as e:
                        logger.error(f"Error extracting odds: {e}")
                        # Don't fail the evaluation just because of odds issues
                    
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
    
    # Apply divisor to stake if applicable
    if results["stake"] > 0 and results["divisor"]:
        divisor = results["divisor"]
        # Adjust stake based on divisor
        if results["stake_strategy"] == "fixed":
            # Convert to percentage of bankroll
            results["stake"] /= divisor
            results["stake_strategy"] = "percentage"
    
    # Add ML prediction to enhance the rule-based decision
    try:
        ml_predictor = get_ml_predictor()
        ml_suitable, ml_confidence = ml_predictor.predict(match_data)
        
        # Add ML results to the overall results
        results["ml_prediction"] = {
            "is_suitable": ml_suitable,
            "confidence": ml_confidence
        }
        
        # Apply ML decision logic based on confidence levels
        if results["is_suitable"] and not ml_suitable:
            if ml_confidence < 0.3:  # ML is very confident this is not suitable
                results["is_suitable"] = False
                results["rules_failed"].append("ml_prediction")
                logger.info(f"ML prediction overrode rule-based decision for match {results['match_id']}: Not suitable with {ml_confidence:.2f} confidence")
            elif ml_confidence < 0.5:  # ML is somewhat confident this is not suitable
                # Reduce stake but still consider suitable
                results["stake"] *= ml_confidence  # Scale down stake based on confidence
                logger.info(f"ML prediction reduced stake for match {results['match_id']} to {results['stake']:.2f}")
        
        # If rules say not suitable but ML is very confident it is
        elif not results["is_suitable"] and ml_suitable and ml_confidence > 0.8:
            results["is_suitable"] = True
            results["rules_passed"].append("ml_prediction_override")
            logger.info(f"ML prediction overrode rules for match {results['match_id']}: Suitable with {ml_confidence:.2f} confidence")
            
    except Exception as e:
        logger.error(f"Error applying ML prediction: {e}")
        # Don't let ML errors affect the overall decision
    
    return results
