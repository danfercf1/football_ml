"""
Module containing specialized rules for real-time soccer match analysis.
These rules are designed to work with actual match data from databases.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SpecializedRules:
    """
    Collection of specialized rules for soccer match analysis.
    """
    
    @staticmethod
    def strong_home_team_rule(match_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Rule for detecting strong home team performance.
        
        Args:
            match_data: Processed match data dictionary
            
        Returns:
            Bet action dictionary or None if rule doesn't match
        """
        try:
            # Check if required data is available
            required_fields = ["minute", "possession_home", "home_shots", "away_shots", 
                              "home_dangerous_attacks", "away_dangerous_attacks", "odds"]
            if not all(field in match_data for field in required_fields):
                return None
            
            # Rule conditions
            minute = match_data["minute"]
            possession = match_data["possession_home"]
            home_shots = match_data["home_shots"]
            away_shots = match_data["away_shots"]
            home_dangerous = match_data.get("home_dangerous_attacks", 0)
            away_dangerous = match_data.get("away_dangerous_attacks", 0)
            
            # Only apply rule between minutes 15-35 of the first half
            if minute < 15 or minute > 35:
                return None
            
            # Check for strong home dominance
            if (possession >= 60 and 
                home_shots >= away_shots * 2 and
                home_shots >= 4 and
                home_dangerous >= away_dangerous * 1.5):
                
                # Get relevant odds
                odds = match_data.get("odds", {})
                over_1_5 = odds.get("over_1.5", 0)
                
                # Only bet if odds are reasonable
                if over_1_5 >= 1.2 and over_1_5 <= 1.6:
                    return {
                        "match_id": match_data.get("match_id", "unknown"),
                        "market": "over_1.5",
                        "action": "place",
                        "reason": "specialized_strong_home_team",
                        "confidence": 0.75,
                        "odds": over_1_5
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in strong_home_team_rule: {e}")
            return None
    
    @staticmethod
    def xg_value_rule(match_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Rule based on expected goals (xG) value.
        
        Args:
            match_data: Processed match data dictionary
            
        Returns:
            Bet action dictionary or None if rule doesn't match
        """
        try:
            # Check if required data is available
            required_fields = ["minute", "xg_home", "xg_away", "odds"]
            if not all(field in match_data for field in required_fields):
                return None
                
            minute = match_data["minute"]
            xg_home = match_data["xg_home"]
            xg_away = match_data["xg_away"]
            total_xg = xg_home + xg_away
            
            # Only apply in first half
            if minute > 45:
                return None
                
            # Get relevant odds
            odds = match_data.get("odds", {})
            
            # If total xG is high but score is likely 0-0, bet on over 0.5 goals
            if total_xg >= 2.0 and "score" in match_data:
                score = match_data["score"]
                if score == "0 - 0":
                    over_0_5 = odds.get("over_0.5", 0)
                    if over_0_5 >= 1.05 and over_0_5 <= 1.4:
                        return {
                            "match_id": match_data.get("match_id", "unknown"),
                            "market": "over_0.5",
                            "action": "place",
                            "reason": "specialized_xg_value",
                            "confidence": 0.85,
                            "odds": over_0_5
                        }
            
            # If one team has significantly higher xG, consider them to win
            if xg_home > xg_away * 2.0 and xg_home >= 1.5:
                home_win = odds.get("home_win", 0)
                if home_win >= 1.5 and home_win <= 2.5:
                    return {
                        "match_id": match_data.get("match_id", "unknown"),
                        "market": "home_win",
                        "action": "place",
                        "reason": "specialized_xg_home_advantage",
                        "confidence": 0.7,
                        "odds": home_win
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in xg_value_rule: {e}")
            return None
    
    @staticmethod
    def corner_opportunity_rule(match_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Rule for identifying corner betting opportunities.
        
        Args:
            match_data: Processed match data dictionary
            
        Returns:
            Bet action dictionary or None if rule doesn't match
        """
        try:
            # Check if required data is available
            required_fields = ["minute", "home_corners", "away_corners", "home_attacks", 
                              "away_attacks", "avg_corners", "odds"]
            if not all(field in match_data for field in required_fields):
                return None
            
            minute = match_data["minute"]
            home_corners = match_data["home_corners"]
            away_corners = match_data["away_corners"]
            total_corners = home_corners + away_corners
            home_attacks = match_data.get("home_attacks", 0)
            away_attacks = match_data.get("away_attacks", 0)
            total_attacks = home_attacks + away_attacks
            avg_corners = match_data.get("avg_corners", 9)
            
            # Only apply between minutes 20-40 or 65-85
            if not ((20 <= minute <= 40) or (65 <= minute <= 85)):
                return None
            
            # If we're seeing high attacking numbers but few corners so far
            if total_attacks >= 30 and total_corners < minute/10:
                # Get corner over/under odds
                odds = match_data.get("odds", {})
                corner_odds = {}
                
                # Find the most appropriate corner line based on average and current count
                expected_corners = avg_corners * (90 - minute) / 90 + total_corners
                target_line = None
                
                # Select the best corner line to bet on
                if expected_corners >= total_corners + 3:
                    for key in odds:
                        if key.startswith("over_") and key.endswith(".5") and "corner" in key:
                            corner_odds[key] = odds[key]
                    
                    if corner_odds:
                        # Find a good value corner bet
                        for line, odd in corner_odds.items():
                            line_value = float(line.split("_")[1])
                            if line_value > total_corners and line_value < expected_corners and odd >= 1.7:
                                target_line = line
                                break
                
                if target_line:
                    return {
                        "match_id": match_data.get("match_id", "unknown"),
                        "market": target_line,
                        "action": "place",
                        "reason": "specialized_corner_opportunity",
                        "confidence": 0.65,
                        "odds": odds.get(target_line, 0)
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in corner_opportunity_rule: {e}")
            return None
    
    @staticmethod
    def btts_value_rule(match_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Rule for identifying BTTS (both teams to score) value bets.
        
        Args:
            match_data: Processed match data dictionary
            
        Returns:
            Bet action dictionary or None if rule doesn't match
        """
        try:
            # Check if required data is available
            required_fields = ["minute", "home_shots_on_target", "away_shots_on_target", 
                              "home_btts_pct", "away_btts_pct", "predicted_btts", "odds"]
            if not all(field in match_data for field in required_fields):
                return None
            
            minute = match_data["minute"]
            home_shots_on_target = match_data["home_shots_on_target"]
            away_shots_on_target = match_data["away_shots_on_target"]
            home_btts_pct = match_data["home_btts_pct"]
            away_btts_pct = match_data["away_btts_pct"]
            predicted_btts = match_data["predicted_btts"]
            
            # Check for score
            score = match_data.get("score", "0 - 0")
            home_goals, away_goals = map(int, score.split(" - "))
            
            # Only apply before 60th minute
            if minute > 60:
                return None
            
            # If one team has scored and both teams are getting shots on target
            if ((home_goals > 0 and away_goals == 0) or (home_goals == 0 and away_goals > 0)) and \
               home_shots_on_target >= 1 and away_shots_on_target >= 1:
                
                # Get BTTS odds
                odds = match_data.get("odds", {})
                btts_yes = odds.get("btts_yes", 0)
                
                # If we have good BTTS potential
                avg_btts_pct = (home_btts_pct + away_btts_pct) / 2
                if predicted_btts >= 45 and avg_btts_pct >= 40 and btts_yes >= 1.8 and btts_yes <= 2.5:
                    return {
                        "match_id": match_data.get("match_id", "unknown"),
                        "market": "btts_yes",
                        "action": "place",
                        "reason": "specialized_btts_value",
                        "confidence": 0.68,
                        "odds": btts_yes
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in btts_value_rule: {e}")
            return None
    
    @staticmethod
    def late_goal_potential_rule(match_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Rule for identifying late goal potential based on team statistics.
        
        Args:
            match_data: Processed match data dictionary
            
        Returns:
            Bet action dictionary or None if rule doesn't match
        """
        try:
            # Check if required data is available
            required_fields = ["minute", "score", "home_dangerous_attacks", 
                             "away_dangerous_attacks", "home_shots", "away_shots", "odds"]
            if not all(field in match_data for field in required_fields):
                return None
            
            minute = match_data["minute"]
            score = match_data["score"]
            home_dangerous = match_data.get("home_dangerous_attacks", 0)
            away_dangerous = match_data.get("away_dangerous_attacks", 0)
            home_shots = match_data["home_shots"]
            away_shots = match_data["away_shots"]
            
            # Only apply between minutes 65-85
            if not (65 <= minute <= 85):
                return None
            
            # Parse score
            home_goals, away_goals = map(int, score.split(" - "))
            total_goals = home_goals + away_goals
            
            # If score is close (0-0, 1-0, 0-1, 1-1) and there's attacking intent
            if total_goals <= 1 and (home_dangerous + away_dangerous >= 20) and \
               (home_shots + away_shots >= 15):
                
                odds = match_data.get("odds", {})
                next_goal_odds = None
                
                # If one team is clearly dominating attacks
                if home_dangerous >= away_dangerous * 1.7:
                    next_goal_odds = odds.get("next_goal_home", 0) or odds.get("team_to_score_first_home", 0)
                elif away_dangerous >= home_dangerous * 1.7:
                    next_goal_odds = odds.get("next_goal_away", 0) or odds.get("team_to_score_first_away", 0)
                
                # If we have a valid next goal market with decent odds
                if next_goal_odds and next_goal_odds >= 1.4:
                    market = "next_goal_home" if home_dangerous >= away_dangerous * 1.7 else "next_goal_away"
                    return {
                        "match_id": match_data.get("match_id", "unknown"),
                        "market": market,
                        "action": "place",
                        "reason": "specialized_late_goal_potential",
                        "confidence": 0.66,
                        "odds": next_goal_odds
                    }
                
                # Alternatively, check for over 1.5 goals if still 0-0
                if total_goals == 0:
                    over_1_5 = odds.get("over_1.5", 0)
                    if over_1_5 >= 1.5 and over_1_5 <= 2.2:
                        return {
                            "match_id": match_data.get("match_id", "unknown"),
                            "market": "over_1.5",
                            "action": "place",
                            "reason": "specialized_late_over_1_5",
                            "confidence": 0.63,
                            "odds": over_1_5
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in late_goal_potential_rule: {e}")
            return None
    
    @staticmethod
    def evaluate_all_rules(match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all specialized rules against the match data.
        
        Args:
            match_data: Processed match data dictionary
            
        Returns:
            List of matching bet actions
        """
        matching_actions = []
        
        # Define all rule methods
        rules = [
            SpecializedRules.strong_home_team_rule,
            SpecializedRules.xg_value_rule,
            SpecializedRules.corner_opportunity_rule,
            SpecializedRules.btts_value_rule,
            SpecializedRules.late_goal_potential_rule
        ]
        
        # Apply each rule
        for rule in rules:
            try:
                result = rule(match_data)
                if result:
                    matching_actions.append(result)
            except Exception as e:
                logger.error(f"Error applying rule {rule.__name__}: {e}")
        
        return matching_actions


# Example using the match data when run directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    from src.match_processor import get_match_processor
    
    # Sample match document (stub)
    sample_doc = {
        "_id": "sample-id",
        "homeTeam": "Team A",
        "awayTeam": "Team B",
        "league": "Sample League",
        "liveStats": {
            "minute": "25",
            "score": "0 - 0",
            "stats": {
                "Shots Total": {"home": "8", "away": "3"},
                "Shots On Target": {"home": "3", "away": "1"},
                "Possession": {"home": "62", "away": "38"},
                "Corners": {"home": "4", "away": "1"},
                "Dangerous Attacks": {"home": "15", "away": "5"},
                "Attacks": {"home": "25", "away": "12"}
            }
        },
        "odds": {
            "moneyLineOdds": {
                "Home": {"odds": {"bet365": "1.8"}},
                "Draw": {"odds": {"bet365": "3.5"}},
                "Away": {"odds": {"bet365": "4.5"}}
            },
            "overUnderOdds": {
                "over": {
                    "1.5": {"odds": {"bet365": "1.4"}}
                }
            }
        }
    }
    
    processor = get_match_processor()
    match_data = processor.process_match_document(sample_doc)
    
    # Add some xG data for testing
    match_data["xg_home"] = 1.6
    match_data["xg_away"] = 0.7
    match_data["home_btts_pct"] = 55
    match_data["away_btts_pct"] = 45
    match_data["predicted_btts"] = 50
    match_data["avg_corners"] = 10
    
    # Test all rules
    bet_actions = SpecializedRules.evaluate_all_rules(match_data)
    
    logger.info(f"Found {len(bet_actions)} matching rules:")
    for action in bet_actions:
        logger.info(f"Market: {action['market']}, Reason: {action['reason']}, "
                   f"Confidence: {action['confidence']:.2f}, Odds: {action['odds']}")
