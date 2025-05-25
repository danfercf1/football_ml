#!/usr/bin/env python3
"""
Specialized script to implement the Under X In-Play betting strategy.

Strategy steps:
1. Find matches between minutes 52-61
2. Match should have 1-3 goals already scored
3. Teams should have low average total goal counts
4. Bet on Under (current goals + 4) market
5. Cash out if 2+ more goals before minute 82
"""
import json
import logging
import sys
import os
import time
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.match_processor import get_match_processor
from src.rabbitmq_publisher import get_rabbitmq_publisher
from src.betting_rules import default_betting_rules, evaluate_betting_rules
from src.redis_tracker import get_redis_tracker
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        self.redis_tracker = get_redis_tracker()
        self.publisher = get_rabbitmq_publisher()
    
    def analyze_match(self, match_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a match to determine if it's suitable for the Under X In-Play strategy.
        
        Args:
            match_doc: The match document to analyze
            
        Returns:
            Analysis results dictionary
        """
        # Save original team names before processing
        original_home_team = match_doc.get("home_team", "")
        original_away_team = match_doc.get("away_team", "")
        
        try:
            # Process the match document with error handling
            try:
                match_data = self.processor.process_match_document(match_doc)
                logger.info(f"Score analysis: '{match_data.get('score', 'unknown')}' → raw_total={match_data.get('total_goals', 'unknown')}")
            except Exception as proc_error:
                import traceback
                logger.error(f"Error in match processor: {proc_error}")
                logger.error(f"Match processor stack trace: {traceback.format_exc()}")
                
                # Create a minimal match_data with essential fields from the raw document
                match_data = {
                    "match_id": match_doc.get("match_id", str(match_doc.get("_id", "unknown"))),
                    "home_team": match_doc.get("home_team") or match_doc.get("homeTeam", "Unknown Home"),
                    "away_team": match_doc.get("away_team") or match_doc.get("awayTeam", "Unknown Away"),
                    "score": match_doc.get("score", "0 - 0"),
                    "minute": match_doc.get("minute", 0)
                }
                
                # Copy any odds information directly
                if "odds" in match_doc:
                    match_data["odds"] = match_doc["odds"]
            
            # Extract key information
            match_minute = match_data.get("minute", 0)
            score = match_data.get("score", "0 - 0")
            
            # Get teams' average goals per match
            home_team = match_data.get("home_team", "")
            away_team = match_data.get("away_team", "")
            
            # Log with formatted string that includes the actual values, not the variables
            logger.info(f"Processed match data for {match_data.get('home_team', 'Unknown')} vs {match_data.get('away_team', 'Unknown')} (Score: {score}, Goals: {match_data.get('total_goals', '?')})")
            
            # Get teams' average goals per match
            home_avg_goals = self._get_team_avg_goals(match_data, "home")
            away_avg_goals = self._get_team_avg_goals(match_data, "away")
            combined_avg_goals = home_avg_goals + away_avg_goals
            
            # Parse score to get goals
            try:
                home_goals, away_goals = map(int, score.split(" - "))
                total_goals = home_goals + away_goals
            except ValueError:
                logger.error(f"Could not parse score: {score}")
                total_goals = 0
            
            # Calculate the target under goal line
            # Strategy rule: bet on Under (current goals + 3) market
            # Example: score 1-2 (3 goals) -> bet on under_6.5
            target_goal_line = total_goals + 3
            bet_market = f"under_{target_goal_line}.5"
            
            # Get current odds for this market if available
            # Use a try-except block to catch any errors in odds processing
            try:
                under_odds = self._get_under_odds(match_data, target_goal_line)
            except Exception as e:
                import traceback
                logger.error(f"Error in odds extraction during analyze_match: {e}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                under_odds = 0
            
            # Check if match meets our criteria using the legacy method
            is_suitable_legacy = (
                self.min_minute <= match_minute <= self.max_minute and
                self.min_goals <= total_goals <= self.max_goals and
                combined_avg_goals <= 3.0  # Low scoring teams threshold
            )
            
            # Add detailed logging about criteria matching
            logger.info(f"Suitability check: Minute {match_minute} (need {self.min_minute}-{self.max_minute}): {self.min_minute <= match_minute <= self.max_minute}")
            logger.info(f"Suitability check: Goals {total_goals} (need {self.min_goals}-{self.max_goals}): {self.min_goals <= total_goals <= self.max_goals}")
            logger.info(f"Suitability check: Combined avg goals {combined_avg_goals:.2f} (need <=3.0): {combined_avg_goals <= 3.0}")
            
            # For testing/debugging - temporaril allow half-time matches
            # Remove or comment this out in production
            if match_minute == 45 and self.min_goals <= total_goals <= self.max_goals and combined_avg_goals <= 3.0:
                logger.info("⚠️ Testing mode: Treating half-time (45 min) as suitable for betting strategy")
                is_suitable_legacy = True
            
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
                },
                "confirmed_goals": total_goals - match_data.get("goals_pending_var", 0),
                "canceled_goals": match_data.get("canceled_goals", 0),
                "goals_pending_var": match_data.get("goals_pending_var", 0),
            }
            
            # Add a waiting period for recently scored goals (might be canceled)
            recent_goals = match_data.get("recent_goal_timestamps", [])
            goal_confirmation_window = 180  # seconds (3 minutes)
            current_time = int(time.time())
            
            # Count goals that were scored within the last 3 minutes (high risk of VAR review)
            goals_in_confirmation_window = sum(1 for timestamp in recent_goals 
                                             if current_time - timestamp < goal_confirmation_window)
            
            # If there are any goals pending confirmation, we might want to be cautious
            if goals_in_confirmation_window > 0 or match_data.get("goals_pending_var", 0) > 0:
                logger.warning(f"Match has {goals_in_confirmation_window} recently scored goals and " +
                             f"{match_data.get('goals_pending_var', 0)} goals under VAR review - proceeding with caution")
                # You might want to add a delay or skip this match until goals are confirmed
            
            # Check if match meets our criteria using the legacy method
            is_suitable_legacy = (
                self.min_minute <= match_minute <= self.max_minute and
                self.min_goals <= total_goals <= self.max_goals and
                combined_avg_goals <= 3.0 and
                match_data.get("goals_pending_var", 0) == 0  # No goals under VAR review
            )
            
            # Apply the new betting rules system
            try:
                # Force dictionary-based rules for now
                rules = [
                    {
                        "rule_type": "goals",
                        "active": True,
                        "odds": {
                            "min": 1.01,
                            "max": 1.04
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
            
            if combined_avg_goals > 3.0:
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
                        "market": bet_market,
                        "action": "place",
                        "reason": "under_x_inplay_strategy",
                        "odds": under_odds,
                        "confidence": max(0.5, min(0.95, 1.0 - (risk_score / 10))),  # Convert risk to confidence
                        "risk_level": risk_level,
                        "cashout_trigger": f"{self.cashout_threshold_goals}+ goals before minute {self.cashout_max_minute}"
                    }
                    
                    # Track the bet signal in Redis for later goal cancelation checks
                    match_id = match_data.get("match_id", "unknown")
                    if match_id != "unknown":
                        self.track_bet_signal(
                            match_id, 
                            result["bet_signal"], 
                            match_data.get("score", "0 - 0"),
                            match_data.get("minute", 0)
                        )
        
        except Exception as e:
            logger.error(f"Error processing match document: {e}")
            return {
                "match_id": match_doc.get("match_id", "unknown"),
                "error": str(e)
            }
        
        return result
    
    def _get_team_avg_goals(self, match_data: Dict[str, Any], team_type: str) -> float:
        """
        Extract average goals per match for a team.
        
        Args:
            match_data: Processed match data
            team_type: Either 'home' or 'away'
            
        Returns:
            Average goals per match
        """
        try:
            # Check for direct stats
            avg_goals = match_data.get(f"{team_type}_goals_scored", 0)
            if avg_goals > 0:
                return float(avg_goals)
            
            # Try to extract from team overviews if available
            if "teamOverviews" in match_data and team_type in match_data["teamOverviews"]:
                team_data = match_data["teamOverviews"][team_type]
                if "stats" in team_data and "scored" in team_data["stats"]:
                    overall_scored = team_data["stats"]["scored"].get("overall", "0")
                    try:
                        return float(overall_scored)
                    except (ValueError, TypeError):
                        pass
            
            # Default fallback
            return 1.5  # Average default
        
        except Exception as e:
            import traceback
            logger.error(f"Error getting {team_type} team average goals: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return 1.5  # Average default
    
    def _get_under_odds(self, match_data: Dict[str, Any], target_line: int) -> float:
        """
        Get the best under odds for a specific goal line.
        
        Args:
            match_data: Processed match data
            target_line: The goal line to look for (e.g., 6.5)
            
        Returns:
            The best odds found or 0 if not available
        """
        try:
            # Try to get odds directly - ensure we use local variables only
            odds_data = match_data.get("odds", {})
            
            # Check in overUnderOdds if available
            if isinstance(odds_data, dict) and "overUnderOdds" in odds_data and "under" in odds_data["overUnderOdds"]:
                under_odds = odds_data["overUnderOdds"]["under"]
                
                # Find the closest line
                closest_line = None
                min_diff = float('inf')
                
                for line_str in under_odds:
                    try:
                        line = float(line_str)
                        diff = abs(line - target_line)
                        if diff < min_diff:
                            min_diff = diff
                            closest_line = line_str
                    except (ValueError, TypeError):
                        continue
                
                if closest_line and "odds" in under_odds[closest_line]:
                    # Get the best odds
                    best_odd = 0
                    for bookie, odd_str in under_odds[closest_line]["odds"].items():
                        try:
                            odd = float(odd_str)
                            if odd > best_odd:
                                best_odd = odd
                        except (ValueError, TypeError):
                            continue
                    
                    return best_odd
            
            # Try simpler direct format where market name might be a key
            market_key = f"under_{target_line}.5"
            if isinstance(odds_data, dict) and market_key in odds_data:
                try:
                    return float(odds_data[market_key])
                except (ValueError, TypeError):
                    pass
            
            # If we couldn't find real odds, simulate what they might be
            # This is for testing purposes only
            total_goals = 0
            if "score" in match_data:
                try:
                    home_goals, away_goals = map(int, match_data["score"].split(" - "))
                    total_goals = home_goals + away_goals
                except (ValueError, TypeError):
                    pass
            
            # Higher goal lines have lower odds
            simulated_odds = 1.0 + (0.01 * (target_line - total_goals))
            return round(max(1.01, min(simulated_odds, 1.50)), 3)
                
        except Exception as e:
            import traceback
            logger.error(f"Error getting under odds: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return 0
    
    def _calculate_risk_score(self, match_data: Dict[str, Any], total_goals: int) -> int:
        """
        Calculate a risk score for the bet (0-10 scale).
        
        Args:
            match_data: Processed match data
            total_goals: Current total goals
            
        Returns:
            Risk score from 0 (lowest risk) to 10 (highest risk)
        """
        risk_score = 0
        
        # Base risk starts at 2
        risk_score += 2
        
        # Factor 1: Combined average goals
        home_avg = self._get_team_avg_goals(match_data, "home")
        away_avg = self._get_team_avg_goals(match_data, "away")
        combined_avg = home_avg + away_avg
        
        if combined_avg > 5.0:
            risk_score += 4
        elif combined_avg > 4.0:
            risk_score += 3
        elif combined_avg > 3.0:
            risk_score += 2
        elif combined_avg > 2.5:
            risk_score += 1
        
        # Factor 2: Current goal pace
        minute = match_data.get("minute", 0)
        if minute > 0:
            goals_per_minute = total_goals / minute
            projected_goals = goals_per_minute * 90
            
            if projected_goals > 5.5:
                risk_score += 3
            elif projected_goals > 4.5:
                risk_score += 2
            elif projected_goals > 3.5:
                risk_score += 1
        
        # Factor 3: Recent attacking momentum
        home_dangerous = match_data.get("home_dangerous_attacks", 0)
        away_dangerous = match_data.get("away_dangerous_attacks", 0)
        
        dangerous_rate = (home_dangerous + away_dangerous) / max(1, minute)
        if dangerous_rate > 1.5:
            risk_score += 1
        
        # Clamp risk score between 0-10
        return max(0, min(10, risk_score))
    
    def simulate_live_monitoring(self, match_doc: Dict[str, Any], minutes_to_simulate: int = 30) -> None:
        """
        Simulate monitoring a live match to demonstrate the cash-out strategy.
        
        Args:
            match_doc: Initial match document
            minutes_to_simulate: Number of minutes to simulate
        """
        # Process the initial match document
        match_data = self.processor.process_match_document(match_doc)
        
        # Extract key information
        initial_minute = match_data.get("minute", 0)
        score = match_data.get("score", "0 - 0")
        home_team = match_data.get("home_team", "Home")
        away_team = match_data.get("away_team", "Away")
        
        # Parse score to get initial goals
        try:
            home_goals, away_goals = map(int, score.split(" - "))
        except ValueError:
            home_goals = away_goals = 0
        
        # Calculate the target under goal line
        total_goals = home_goals + away_goals
        target_goal_line = total_goals + 4
        bet_market = f"under_{target_goal_line}.5"
        
        # Display initial state
        logger.info("=" * 80)
        logger.info(f"UNDER X IN-PLAY STRATEGY LIVE MONITORING: {home_team} vs {away_team}")
        logger.info("-" * 80)
        logger.info(f"Initial state: Minute {initial_minute}, Score {score}")
        logger.info(f"Betting on: {bet_market}")
        logger.info(f"Cash-out trigger: {self.cashout_threshold_goals}+ more goals before minute {self.cashout_max_minute}")
        logger.info("-" * 80)
        logger.info("Starting simulation...")
        
        # Simulate progression of the match
        goals_scored_after_bet = 0
        should_cash_out = False
        
        for i in range(1, minutes_to_simulate + 1):
            current_minute = initial_minute + i
            
            # Simulate a small chance for a goal in each minute
            goal_probability = 0.05  # 5% chance of goal per minute
            if random.random() < goal_probability:
                # Decide which team scores
                if random.random() < 0.5:
                    home_goals += 1
                    scorer = home_team
                else:
                    away_goals += 1
                    scorer = away_team
                
                goals_scored_after_bet += 1
                new_score = f"{home_goals} - {away_goals}"
                
                logger.info(f"⚽ GOAL! Minute {current_minute}: {scorer} scores! New score: {new_score}")
                
                # Check if we should cash out
                if goals_scored_after_bet >= self.cashout_threshold_goals and current_minute < self.cashout_max_minute:
                    should_cash_out = True
                    logger.info(f"🛑 CASH OUT TRIGGER! {goals_scored_after_bet} goals scored before minute {self.cashout_max_minute}")
                    break
            
            # Every 5 minutes, show an update
            if i % 5 == 0:
                logger.info(f"Minute {current_minute}: Score {home_goals} - {away_goals}, Goals after bet: {goals_scored_after_bet}")
            
            # Sleep to simulate real-time passing
            time.sleep(0.1)
        
        # Show final result
        logger.info("-" * 80)
        logger.info(f"Simulation ended at minute {initial_minute + minutes_to_simulate}")
        logger.info(f"Final score: {home_goals} - {away_goals}")
        logger.info(f"Goals after placing bet: {goals_scored_after_bet}")
        
        if should_cash_out:
            logger.info("RECOMMENDATION: CASH OUT (triggered)")
            logger.info("Expected outcome: Small loss (10-20% of stake)")
        else:
            total_final_goals = home_goals + away_goals
            if total_final_goals <= target_goal_line:
                logger.info("RECOMMENDATION: LET BET RUN")
                logger.info(f"Expected outcome: WIN (Under {target_goal_line}.5 bet successful)")
            else:
                logger.info("RECOMMENDATION: BET LOST")
                logger.info(f"Expected outcome: LOSS (More than {target_goal_line}.5 goals scored)")
        
        logger.info("=" * 80)
    
    def process_live_match(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a live match from the MongoDB underxmatches collection.
        
        Args:
            match_data: Complete match document from MongoDB
            
        Returns:
            Analysis results dictionary
        """
        # Extract and format the relevant data for analysis
        try:
            live_stats = match_data.get("liveStats", {})
            if not live_stats:
                logger.warning(f"No live stats available for match {match_data.get('_id')}")
                return {"error": "No live stats available"}
            
            # Parse minute safely, handling additional time format like "45+5"
            minute_str = live_stats.get("minute", "0").replace("'", "")
            try:
                # Handle special time values
                if minute_str.upper() == "HT":
                    minute = 45
                    logger.info("Match is at half time, using minute 45 for calculations")
                elif minute_str.upper() == "FT":
                    minute = 90
                    logger.info("Match is finished (full time), using minute 90 for calculations")
                # Handle additional time format (e.g., "45+5")
                elif "+" in minute_str:
                    base_minute = minute_str.split("+")[0]
                    minute = int(base_minute)
                    logger.info(f"Parsed minute '{minute_str}' as {minute} (ignoring added time)")
                else:
                    minute = int(minute_str)
            except ValueError:
                # If parsing fails, default to 0
                logger.warning(f"Could not parse minute value: '{minute_str}', using 0")
                minute = 0
            
            # Get team names from multiple possible locations in the document
            home_team = None
            away_team = None
            
            # Try liveStats.teams first (most reliable for live data)
            if "teams" in live_stats:
                home_team = live_stats["teams"].get("home")
                away_team = live_stats["teams"].get("away")
            
            # If not found, try top-level homeTeam/awayTeam fields
            if not home_team and "homeTeam" in match_data:
                home_team = match_data["homeTeam"]
            if not away_team and "awayTeam" in match_data:
                away_team = match_data["awayTeam"]
                
            # Try from teamOverviews if available
            if not home_team and "teamOverviews" in match_data and "home" in match_data["teamOverviews"]:
                home_team = match_data["teamOverviews"]["home"].get("teamName")
            if not away_team and "teamOverviews" in match_data and "away" in match_data["teamOverviews"]:
                away_team = match_data["teamOverviews"]["away"].get("teamName")
                
            # Try to extract from match field
            if not (home_team and away_team) and "match" in match_data:
                try:
                    teams = match_data["match"].split(" vs ")
                    if len(teams) == 2:
                        home_team = home_team or teams[0]
                        away_team = away_team or teams[1]
                except:
                    pass
                
            # If still not found, try teams[0]/teams[1] pattern
            if not home_team and "teams" in match_data and isinstance(match_data["teams"], list) and len(match_data["teams"]) > 1:
                home_team = match_data["teams"][0]
                away_team = match_data["teams"][1]
            
            # Final fallback
            home_team = home_team or "Unknown Home"
            away_team = away_team or "Unknown Away"
            
            logger.info(f"Processing match: {home_team} vs {away_team}")
            
            # Create a formatted match document for analysis
            formatted_match = {
                "match_id": str(match_data.get("_id")),
                "home_team": home_team,
                "away_team": away_team,
                "score": live_stats.get("score", "0 - 0"),
                "minute": minute,  # Set the minute value explicitly
                "isLive": live_stats.get("isLive", False),
                "league": match_data.get("league", "Unknown"),
                "country": match_data.get("country", "Unknown"),
                "timestamp": match_data.get("timestamp", 0)
            }
            
            # Add statistics
            stats = live_stats.get("stats", {})
            for stat_name, stat_values in stats.items():
                key_name = stat_name.lower().replace(" ", "_")
                if isinstance(stat_values, dict) and "home" in stat_values and "away" in stat_values:
                    formatted_match[f"home_{key_name}"] = stat_values.get("home", "0")
                    formatted_match[f"away_{key_name}"] = stat_values.get("away", "0")
            
            # Get total goals from the score (more reliable than goals array)
            try:
                home_goals, away_goals = map(int, formatted_match["score"].split(" - "))
                total_goals = home_goals + away_goals
                formatted_match["total_goals"] = total_goals
                logger.debug(f"Extracted total_goals={total_goals} from score={formatted_match['score']}")
            except (ValueError, TypeError):
                formatted_match["total_goals"] = 0
                logger.warning(f"Could not parse goals from score: {formatted_match['score']}, using 0")
            
            # Extract team stats from teamOverviews if available
            if "teamOverviews" in match_data:
                team_overviews = match_data["teamOverviews"]
                
                # Home team stats
                if "home" in team_overviews and "stats" in team_overviews["home"]:
                    home_stats = team_overviews["home"]["stats"]
                    if "scored" in home_stats and "overall" in home_stats["scored"]:
                        formatted_match["home_goals_scored"] = float(home_stats["scored"]["overall"])
                    if "conceded" in home_stats and "overall" in home_stats["conceded"]:
                        formatted_match["home_goals_conceded"] = float(home_stats["conceded"]["overall"])
                
                # Away team stats
                if "away" in team_overviews and "stats" in team_overviews["away"]:
                    away_stats = team_overviews["away"]["stats"]
                    if "scored" in away_stats and "overall" in away_stats["scored"]:
                        formatted_match["away_goals_scored"] = float(away_stats["scored"]["overall"])
                    if "conceded" in away_stats and "overall" in away_stats["conceded"]:
                        formatted_match["away_goals_conceded"] = float(away_stats["conceded"]["overall"])
            
            # Add teamOverviews to the formatted match directly
            formatted_match["teamOverviews"] = match_data.get("teamOverviews", {})
            
            # Add odds information if available - ensuring proper format
            if "odds" in match_data:
                # Create a simple copy of odds data without complex nested structures
                # This avoids passing problematic data to the processor
                try:
                    odds_data = match_data.get("odds", {})
                    simplified_odds = {}
                    
                    # If there's an overUnderOdds structure, extract under values directly
                    if (isinstance(odds_data, dict) and "overUnderOdds" in odds_data 
                            and "under" in odds_data["overUnderOdds"]
                            and isinstance(odds_data["overUnderOdds"]["under"], dict)):  # Ensure it's a dict
                        
                        under_odds = odds_data["overUnderOdds"]["under"]
                        
                        # Now safe to iterate since we've verified it's a dictionary
                        for line_str, odds_info in under_odds.items():
                            try:
                                if isinstance(odds_info, dict) and "odds" in odds_info:  # Additional check
                                    best_odd = 0
                                    for bookie, odd_value in odds_info["odds"].items():
                                        try:
                                            odd = float(odd_value)
                                            best_odd = max(best_odd, odd)
                                        except (ValueError, TypeError):
                                            pass
                                    
                                    if best_odd > 0:
                                        line = float(line_str) if '.' in line_str else float(f"{line_str}.0")
                                        market_key = f"under_{line}"
                                        simplified_odds[market_key] = best_odd
                            except Exception as e:
                                logger.debug(f"Error processing odds line {line_str}: {e}")
                                continue
                    
                    formatted_match["odds"] = simplified_odds
                except Exception as e:
                    logger.error(f"Error processing odds data: {e}")
                    # Fallback to empty odds structure
                    formatted_match["odds"] = {}
            
            # Analyze the match with the existing strategy
            return self.analyze_match(formatted_match)
            
        except Exception as e:
            logger.error(f"Error processing live match: {e}")
            return {"error": str(e)}
    
    def analyze_live_matches(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze a list of live matches with the strategy.
        
        Args:
            matches: List of match documents from MongoDB
            
        Returns:
            List of analysis results
        """
        results = []
        suitable_matches = []
        
        for match in matches:
            try:
                result = self.process_live_match(match)
                results.append(result)
                
                if result.get("is_suitable", False):
                    suitable_matches.append(result)
                    logger.info(f"✅ MATCH FOUND: {result['home_team']} vs {result['away_team']}")
                    
                    # Print detailed analysis for suitable matches
                    logger.info(f"  - Score: {result['score']}")
                    logger.info(f"  - Minute: {result['minute']}")
                    logger.info(f"  - Recommendation: {result.get('recommendation', {}).get('action', 'N/A')}")
                    logger.info(f"  - Market: {result.get('recommendation', {}).get('market', 'N/A')}")
                    logger.info(f"  - Odds: {result.get('recommendation', {}).get('odds', 'N/A')}")
                    logger.info(f"  - Risk: {result.get('recommendation', {}).get('risk_level', 'N/A')}")
                
            except Exception as e:
                logger.error(f"Error analyzing match {match.get('_id')}: {e}")
        
        # Summary of analysis
        logger.info(f"Analyzed {len(matches)} live matches, found {len(suitable_matches)} suitable for betting")
        return results

    def track_bet_signal(self, match_id: str, bet_signal: Dict[str, Any], 
                         score: str, minute: int) -> bool:
        """
        Track a bet signal in Redis for later validation.
        
        Args:
            match_id: Unique match identifier
            bet_signal: The bet signal data
            score: Score at the time of the bet
            minute: Match minute at the time of the bet
            
        Returns:
            True if tracking successful, False otherwise
        """
        try:
            # Save the bet details to Redis
            bet_details = {
                "bet_signal": bet_signal,
                "score": score,
                "minute": minute,
                "timestamp": int(time.time())
            }
            return self.redis_tracker.track_bet(match_id, bet_details)
        except Exception as e:
            logger.error(f"Failed to track bet signal: {e}")
            return False
    
    def check_for_canceled_goals_and_act(self, match_id: str, 
                                         current_score: str, current_minute: int, 
                                         match_document: Dict[str, Any] = None) -> None:
        """
        Check if any goals have been canceled since the bet was placed,
        and send an emergency cashout signal if needed.
        
        Args:
            match_id: Unique match identifier
            current_score: Current match score
            current_minute: Current match minute
            match_document: Original match document (optional)
        """
        try:
            # Check if bet was placed by looking at the document property
            bet_was_placed = False
            
            # First check if we have the full match document 
            if match_document:
                bet_was_placed = match_document.get("bet", False)
                logger.debug(f"Bet status from match document: {bet_was_placed}")
                
            # If bet wasn't indicated in document, check Redis for bet details
            if not bet_was_placed:
                bet_details = self.redis_tracker.get_bet_details(match_id)
                bet_was_placed = bet_details is not None
                logger.debug(f"Bet status from Redis: {bet_was_placed}")
            
            # If no bet was placed, no need to check for canceled goals
            if not bet_was_placed:
                logger.debug(f"No bet was placed on match {match_id}, skipping canceled goal check")
                return
                
            # Check if any goals have been canceled
            has_canceled, bet_details = self.redis_tracker.check_for_canceled_goals(
                match_id, current_score)
                
            if has_canceled and bet_details:
                # Get the bet signal details
                bet_signal = bet_details.get("bet_signal", {})
                bet_score = bet_details.get("score", "0 - 0")
                bet_minute = bet_details.get("minute", 0)
                
                # Parse scores
                try:
                    bet_home, bet_away = map(int, bet_score.split(" - "))
                    current_home, current_away = map(int, current_score.split(" - "))
                    
                    # Check if we need to send an emergency cashout
                    # Specifically checking for case where total goals is now 0
                    if current_home + current_away == 0 and bet_home + bet_away > 0:
                        logger.warning(f"EMERGENCY CASHOUT: Goal(s) canceled for match {match_id}. " +
                                      f"Score was {bet_score}, now {current_score}")
                        
                        # Create emergency cashout signal
                        cashout_signal = {
                            "match_id": match_id,
                            "market": bet_signal.get("market", ""),
                            "action": "cashout",
                            "reason": "goal_canceled_emergency",
                            "original_bet": bet_signal,
                            "urgency": "high",
                            "timestamp": int(time.time())
                        }
                        
                        # Send the cashout signal
                        success = self.publisher.publish_cashout_signal(cashout_signal)
                        
                        if success:
                            logger.info("✅ Emergency cashout signal sent successfully")
                        else:
                            logger.error("❌ Failed to send emergency cashout signal")
                
                except (ValueError, TypeError):
                    logger.error(f"Error parsing scores in canceled goal check")
        
        except Exception as e:
            logger.error(f"Error checking for canceled goals: {e}")

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


def process_match(match_doc: Dict[str, Any]) -> None:
    """
    Process a match document with the Under X In-Play strategy.
    
    Args:
        match_doc: Match document to analyze
    """
    # Initialize the strategy
    strategy = UnderXInPlayStrategy()
    
    # Analyze the match
    result = strategy.analyze_match(match_doc)
    
    # Display analysis results
    logger.info("=" * 80)
    logger.info("UNDER X IN-PLAY STRATEGY ANALYSIS")
    logger.info("-" * 80)
    logger.info(f"Match: {result['home_team']} vs {result['away_team']}")
    logger.info(f"Current minute: {result['minute']}")
    logger.info(f"Current score: {result['score']}")
    logger.info(f"Team stats:")
    logger.info(f"  - Home team avg goals: {result['home_avg_goals']:.2f}")
    logger.info(f"  - Away team avg goals: {result['away_avg_goals']:.2f}")
    logger.info(f"  - Combined avg goals: {result['combined_avg_goals']:.2f}")
    logger.info(f"Target bet: {result['target_under_line']}")
    logger.info(f"Available odds: {result['odds']}")
    
    logger.info("-" * 80)
    logger.info(f"Match suitable for strategy: {'YES' if result['is_suitable'] else 'NO'}")
    
    if result['reasons']:
        logger.info("Reasons:")
        for reason in result['reasons']:
            logger.info(f"  - {reason}")
    
    if result.get('recommendation'):
        rec = result['recommendation']
        logger.info("-" * 80)
        logger.info("RECOMMENDATION:")
        logger.info(f"  Action: {rec['action']}")
        logger.info(f"  Market: {rec['market']}")
        logger.info(f"  Odds: {rec['odds']}")
        logger.info(f"  Risk level: {rec['risk_level']}")
        logger.info(f"  Cash-out trigger: {rec['cashout_trigger']}")
        logger.info(f"  Suggested stake: {rec['stake_recommendation']}")
        
        # If we have a bet signal, send it to RabbitMQ
        if 'bet_signal' in result:
            logger.info("-" * 80)
            logger.info("Sending bet signal to RabbitMQ...")
            
            publisher = get_rabbitmq_publisher()
            success = publisher.publish_bet_signal(result['bet_signal'])
            
            if success:
                logger.info("✅ Bet signal sent successfully")
            else:
                logger.info("❌ Failed to send bet signal")
            
            publisher.close()
    
        # Run a simulation if the match is suitable
        if result['is_suitable']:
            logger.info("-" * 80)
            logger.info("Running live monitoring simulation...")
            strategy.simulate_live_monitoring(match_doc)
    
    logger.info("=" * 80)


def main():
    """Main entry point for the script."""
    # Add import for simulation
    global random
    import random
    
    if len(sys.argv) > 1:
        # Load from file if provided
        match_doc = load_match_from_file(sys.argv[1])
    else:
        # Ask for JSON input if no file provided
        print("Please paste the match document JSON (Ctrl+D when finished):")
        json_str = sys.stdin.read()
        try:
            match_doc = json.loads(json_str)
        except Exception:
            logger.error("Invalid JSON input")
            return
    
    if match_doc:
        process_match(match_doc)
    else:
        logger.error("No valid match document provided")


if __name__ == "__main__":
    main()
