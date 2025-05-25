"""
Module for handling and processing real match data.
This module extends the system to work with actual match data from databases.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class MatchDataProcessor:
    """
    Processes real match data to extract features for analysis.
    """
    
    def __init__(self):
        """Initialize the match data processor."""
        pass
    
    def process_match_document(self, match_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a full match document and extract relevant features for analysis.
        
        Args:
            match_doc: A dictionary containing match data from the database
            
        Returns:
            Dictionary with extracted and processed features
        """
        processed_data = {}
        
        try:
            # Basic match information
            processed_data["match_id"] = str(match_doc.get("_id", ""))
            
            # Preserve the minute value if already present in the input document
            if "minute" in match_doc:
                processed_data["minute"] = match_doc["minute"]
            
            # Extract team names from input and preserve them
            home_team = match_doc.get("home_team", "")
            away_team = match_doc.get("away_team", "")
            
            # If not already defined in the input, try to extract from other fields
            if not home_team and "homeTeam" in match_doc:
                home_team = match_doc["homeTeam"]
            if not away_team and "awayTeam" in match_doc:
                away_team = match_doc["awayTeam"]
                
            # Try from liveStats if available
            if not home_team and "liveStats" in match_doc and "teams" in match_doc["liveStats"]:
                home_team = match_doc["liveStats"]["teams"].get("home", "")
            if not away_team and "liveStats" in match_doc and "teams" in match_doc["liveStats"]:
                away_team = match_doc["liveStats"]["teams"].get("away", "")
                
            # Try from teamOverviews if available
            if not home_team and "teamOverviews" in match_doc and "home" in match_doc["teamOverviews"]:
                home_team = match_doc["teamOverviews"]["home"].get("teamName", "")
            if not away_team and "teamOverviews" in match_doc and "away" in match_doc["teamOverviews"]:
                away_team = match_doc["teamOverviews"]["away"].get("teamName", "")
                
            # Try to extract from match field
            if not (home_team and away_team) and "match" in match_doc:
                try:
                    teams = match_doc["match"].split(" vs ")
                    if len(teams) == 2:
                        home_team = home_team or teams[0]
                        away_team = away_team or teams[1]
                except:
                    pass
            
            # Set team names in processed data
            processed_data["home_team"] = home_team
            processed_data["away_team"] = away_team
            
            processed_data["league"] = match_doc.get("league", "")
            processed_data["country"] = match_doc.get("country", "")
            
            # Extract date information
            if "date" in match_doc:
                processed_data["date"] = match_doc["date"]
                
            # Log match being processed with minimal information
            logger.info(f"Processing match: {processed_data.get('home_team', 'Unknown')} vs {processed_data.get('away_team', 'Unknown')}")
            
            # Process match state (either from top level or nested in liveStats)
            # Only set minute if not already set from the input
            if "minute" not in processed_data and "minute" in match_doc:
                processed_data["minute"] = self._extract_minute(match_doc.get("minute", "0"))
                
            # Get the score and parse it to extract goal counts
            if "score" in match_doc:
                score = match_doc.get("score", "0 - 0")
                processed_data["score"] = score
                
                # Track VAR/canceled goals if available
                processed_data["canceled_goals"] = 0
                processed_data["goals_pending_var"] = 0
                
                # Parse the score to get total goals - use more robust parsing
                try:
                    # First, normalize the score format (handle different separators)
                    normalized_score = score.replace("-", " - ")
                    while "  " in normalized_score:
                        normalized_score = normalized_score.replace("  ", " ")
                    
                    # Now split and parse
                    if " - " in normalized_score:
                        home_goals, away_goals = map(int, normalized_score.split(" - "))
                    elif "-" in normalized_score:
                        home_goals, away_goals = map(int, normalized_score.split("-"))
                    else:
                        # Alternative parsing for other formats
                        logger.warning(f"Using alternative score parsing for: '{score}'")
                        parts = ''.join(c if c.isdigit() else ' ' for c in score).split()
                        if len(parts) >= 2:
                            home_goals, away_goals = int(parts[0]), int(parts[1])
                        else:
                            raise ValueError(f"Cannot parse score: {score}")
                    
                    # Calculate and store totals
                    total_goals = home_goals + away_goals
                    processed_data["raw_total_goals"] = total_goals  # Original score
                    processed_data["total_goals"] = total_goals
                    processed_data["home_goals"] = home_goals
                    processed_data["away_goals"] = away_goals
                    
                    logger.info(f"Score analysis: '{score}' → raw_total={total_goals}")
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse score '{score}': {e}")
                    processed_data["total_goals"] = match_doc.get("total_goals", 0)  # Try to get from direct field
                    processed_data["home_goals"] = 0
                    processed_data["away_goals"] = 0
            elif "total_goals" in match_doc:
                # If score parsing failed but we have a total_goals field, use it
                processed_data["total_goals"] = match_doc["total_goals"]
            
            # Always extract available stats directly from match_doc (flat format)
            # Shots
            if "home_shots_total" in match_doc and "away_shots_total" in match_doc:
                processed_data["home_shots"] = int(match_doc.get("home_shots_total", 0))
                processed_data["away_shots"] = int(match_doc.get("away_shots_total", 0))
            
            # Shots on target
            if "home_shots_on_target" in match_doc and "away_shots_on_target" in match_doc:
                processed_data["home_shots_on_target"] = int(match_doc.get("home_shots_on_target", 0))
                processed_data["away_shots_on_target"] = int(match_doc.get("away_shots_on_target", 0))
            
            # Corners
            if "home_corners" in match_doc and "away_corners" in match_doc:
                processed_data["home_corners"] = int(match_doc.get("home_corners", 0))
                processed_data["away_corners"] = int(match_doc.get("away_corners", 0))
            
            # Attacks
            if "home_attacks" in match_doc and "away_attacks" in match_doc:
                processed_data["home_attacks"] = int(match_doc.get("home_attacks", 0))
                processed_data["away_attacks"] = int(match_doc.get("away_attacks", 0))
            
            # Dangerous Attacks
            if "home_dangerous_attacks" in match_doc and "away_dangerous_attacks" in match_doc:
                processed_data["home_dangerous_attacks"] = int(match_doc.get("home_dangerous_attacks", 0))
                processed_data["away_dangerous_attacks"] = int(match_doc.get("away_dangerous_attacks", 0))
                
            # Fall back to liveStats only if needed fields are missing and liveStats exists
            if ("liveStats" in match_doc and match_doc["liveStats"] and 
                (not all(key in processed_data for key in ["score", "minute", "home_shots", "away_shots"]))):
                live_stats = match_doc["liveStats"]
                
                # Live match state if available
                if "liveStats" in match_doc and match_doc["liveStats"]:
                    live_stats = match_doc["liveStats"]
                    
                    # Only set minute if not already set from the input
                    if "minute" not in processed_data:
                        processed_data["minute"] = self._extract_minute(live_stats.get("minute", "0"))
                        
                    # Get the score and parse it to extract goal counts
                    score = live_stats.get("score", "0 - 0")
                    processed_data["score"] = score
                    
                    # Track VAR/canceled goals if available
                    processed_data["canceled_goals"] = 0
                    processed_data["goals_pending_var"] = 0
                    
                    # Check if there are any canceled goals in the event stream
                    if "events" in live_stats:
                        for event in live_stats.get("events", []):
                            # Check if this is a canceled goal event
                            if event.get("type") == "goal_canceled" or event.get("type") == "var_decision" and event.get("decision") == "goal_canceled":
                                processed_data["canceled_goals"] += 1
                                logger.info(f"Found canceled goal in match events")
                                
                            # Check for goals under VAR review
                            if event.get("type") == "var_check" and event.get("check_type") == "goal" and event.get("status") == "in_progress":
                                processed_data["goals_pending_var"] += 1
                                logger.info(f"Goal under VAR review detected")
                    
                    # Parse the score to get total goals - use more robust parsing
                    try:
                        # First, normalize the score format (handle different separators)
                        normalized_score = score.replace("-", " - ")
                        while "  " in normalized_score:
                            normalized_score = normalized_score.replace("  ", " ")
                        
                        # Now split and parse
                        if " - " in normalized_score:
                            home_goals, away_goals = map(int, normalized_score.split(" - "))
                        elif "-" in normalized_score:
                            home_goals, away_goals = map(int, normalized_score.split("-"))
                        else:
                            # Alternative parsing for other formats
                            logger.warning(f"Using alternative score parsing for: '{score}'")
                            parts = ''.join(c if c.isdigit() else ' ' for c in score).split()
                            if len(parts) >= 2:
                                home_goals, away_goals = int(parts[0]), int(parts[1])
                            else:
                                raise ValueError(f"Cannot parse score: {score}")
                        
                        # Calculate and store totals, accounting for canceled goals
                        total_goals = home_goals + away_goals
                        processed_data["raw_total_goals"] = total_goals  # Original score
                        
                        # For confirmed goals, subtract any that were canceled
                        confirmed_goals = max(0, total_goals - processed_data["goals_pending_var"])
                        processed_data["total_goals"] = confirmed_goals
                        processed_data["home_goals"] = home_goals
                        processed_data["away_goals"] = away_goals
                        
                        # Analyze goal efficiency based on shots (if available)
                        shots_home = processed_data.get("home_shots", 0)
                        shots_away = processed_data.get("away_shots", 0)
                        shots_on_target_home = processed_data.get("home_shots_on_target", 0)
                        shots_on_target_away = processed_data.get("away_shots_on_target", 0)
                        
                        # Calculate shooting efficiency metrics when possible
                        if shots_home > 0:
                            processed_data["home_conversion_rate"] = round(home_goals / shots_home * 100, 2)
                        if shots_away > 0:
                            processed_data["away_conversion_rate"] = round(away_goals / shots_away * 100, 2)
                        if shots_on_target_home > 0:
                            processed_data["home_on_target_conversion"] = round(home_goals / shots_on_target_home * 100, 2)
                        if shots_on_target_away > 0:
                            processed_data["away_on_target_conversion"] = round(away_goals / shots_on_target_away * 100, 2)
                            
                        # Include possession analysis if available
                        home_possession = processed_data.get("possession_home", 0)
                        away_possession = processed_data.get("possession_away", 0)
                        if home_possession and away_possession:
                            # Calculate possession efficiency (goals per % possession)
                            if home_possession > 0:
                                processed_data["home_possession_efficiency"] = round(home_goals / home_possession * 100, 3)
                            if away_possession > 0:
                                processed_data["away_possession_efficiency"] = round(away_goals / away_possession * 100, 3)
                        
                        # Enhanced logging including key match statistics
                        logger.info(f"Match analysis: '{score}' → Goals: {total_goals} " +
                                   f"(Home: {home_goals}, Away: {away_goals}), " +
                                   f"Shots: {shots_home}-{shots_away}, " +
                                   f"On target: {shots_on_target_home}-{shots_on_target_away}, " +
                                   f"Possession: {home_possession}-{away_possession}")
                        
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse score '{score}': {e}")
                        processed_data["total_goals"] = 0
                        processed_data["home_goals"] = 0
                        processed_data["away_goals"] = 0
                    
                    # Check for direct flat stats in match_doc first, then fall back to nested stats
                    # Shots
                    if "home_shots_total" in match_doc and "away_shots_total" in match_doc:
                        processed_data["home_shots"] = int(match_doc.get("home_shots_total", 0))
                        processed_data["away_shots"] = int(match_doc.get("away_shots_total", 0))
                    elif "stats" in live_stats:
                        shots = live_stats["stats"].get("Shots Total", {})
                        processed_data["home_shots"] = int(shots.get("home", 0))
                        processed_data["away_shots"] = int(shots.get("away", 0))
                    
                    # Shots on target
                    if "home_shots_on_target" in match_doc and "away_shots_on_target" in match_doc:
                        processed_data["home_shots_on_target"] = int(match_doc.get("home_shots_on_target", 0))
                        processed_data["away_shots_on_target"] = int(match_doc.get("away_shots_on_target", 0))
                    elif "stats" in live_stats:
                        shots_on_target = live_stats["stats"].get("Shots On Target", {})
                        processed_data["home_shots_on_target"] = int(shots_on_target.get("home", 0))
                        processed_data["away_shots_on_target"] = int(shots_on_target.get("away", 0))
                    
                    # Possession
                    if "home_possession" in match_doc and "away_possession" in match_doc:
                        processed_data["possession_home"] = int(match_doc.get("home_possession", 50))
                        processed_data["possession_away"] = int(match_doc.get("away_possession", 50))
                    elif "stats" in live_stats:
                        possession = live_stats["stats"].get("Possession", {})
                        processed_data["possession_home"] = int(possession.get("home", 50))
                        processed_data["possession_away"] = int(possession.get("away", 50))
                    
                    # Corners
                    if "home_corners" in match_doc and "away_corners" in match_doc:
                        processed_data["home_corners"] = int(match_doc.get("home_corners", 0))
                        processed_data["away_corners"] = int(match_doc.get("away_corners", 0))
                    elif "stats" in live_stats:
                        corners = live_stats["stats"].get("Corners", {})
                        processed_data["home_corners"] = int(corners.get("home", 0))
                        processed_data["away_corners"] = int(corners.get("away", 0))
                    
                    # Attacks
                    if "home_attacks" in match_doc and "away_attacks" in match_doc:
                        processed_data["home_attacks"] = int(match_doc.get("home_attacks", 0))
                        processed_data["away_attacks"] = int(match_doc.get("away_attacks", 0))
                    elif "stats" in live_stats:
                        attacks = live_stats["stats"].get("Attacks", {})
                        processed_data["home_attacks"] = int(attacks.get("home", 0))
                        processed_data["away_attacks"] = int(attacks.get("away", 0))
                    
                    # Dangerous Attacks
                    if "home_dangerous_attacks" in match_doc and "away_dangerous_attacks" in match_doc:
                        processed_data["home_dangerous_attacks"] = int(match_doc.get("home_dangerous_attacks", 0))
                        processed_data["away_dangerous_attacks"] = int(match_doc.get("away_dangerous_attacks", 0))
                    elif "stats" in live_stats:
                        dangerous_attacks = live_stats["stats"].get("Dangerous Attacks", {})
                        processed_data["home_dangerous_attacks"] = int(dangerous_attacks.get("home", 0))
                        processed_data["away_dangerous_attacks"] = int(dangerous_attacks.get("away", 0))
                    
                    # Add derived metrics
                    processed_data["total_shots"] = processed_data.get("home_shots", 0) + processed_data.get("away_shots", 0)
                    processed_data["total_corners"] = processed_data.get("home_corners", 0) + processed_data.get("away_corners", 0)
            
            # Extract prediction stats
            if "predictionStats" in match_doc:
                pred_stats = match_doc["predictionStats"]
                processed_data["predicted_over_1.5"] = pred_stats.get("predictedOver1_5", 0)
                processed_data["predicted_over_2.5"] = pred_stats.get("predictedOver2_5", 0)
                processed_data["predicted_btts"] = pred_stats.get("predictedBTTS", 0)
                processed_data["avg_total_goals"] = pred_stats.get("avgTotalGoals", 0)
                processed_data["avg_cards"] = pred_stats.get("avgCards", 0)
                processed_data["avg_corners"] = pred_stats.get("avgCorners", 0)
                
            # Extract odds if available
            if "odds" in match_doc:
                odds_data = match_doc["odds"]
                processed_data["odds"] = self._extract_odds(odds_data)
            
            # Extract team statistics for both teams
            if "teamOverviews" in match_doc:
                team_overviews = match_doc["teamOverviews"]
                if "home" in team_overviews:
                    home_stats = self._extract_team_stats(team_overviews["home"], "home")
                    processed_data.update(home_stats)
                    
                if "away" in team_overviews:
                    away_stats = self._extract_team_stats(team_overviews["away"], "away")
                    processed_data.update(away_stats)
            
            # Extract expected goals (xG) values
            self._extract_xg_values(match_doc, processed_data)
            
            # Add debug logs to verify key data
            logger.debug(f"Processed match: minute={processed_data.get('minute')}, " +
                         f"score={processed_data.get('score')}, " +
                         f"total_goals={processed_data.get('total_goals')}")
            
            logger.info(f"Processed match data for {processed_data.get('home_team', 'Unknown')} vs " +
                      f"{processed_data.get('away_team', 'Unknown')} " +
                      f"(Score: {processed_data.get('score', '0-0')}, Goals: {processed_data.get('total_goals', 0)})")
            
        except Exception as e:
            logger.error(f"Error processing match document: {e}")
        
        return processed_data
    
    def _extract_minute(self, minute_str: str) -> int:
        """
        Extract minute from string representation, handling special cases.
        
        Args:
            minute_str: String representation of match minute
            
        Returns:
            Integer minute value
        """
        try:
            # Handle cases like '45+2', 'HT', 'FT', etc.
            if isinstance(minute_str, int):
                return minute_str
                
            minute_str = str(minute_str).strip().lower()
            
            if minute_str in ('ht', 'half time'):
                return 45
            elif minute_str in ('ft', 'full time'):
                return 90
            elif '+' in minute_str:
                # Extract base minute (e.g. '45+2' -> 45)
                return int(minute_str.split('+')[0])
            else:
                return int(minute_str)
                
        except (ValueError, TypeError):
            logger.warning(f"Could not parse minute value: {minute_str}, defaulting to 0")
            return 0
    
    def _extract_odds(self, odds_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract the best available odds for different markets.
        
        Args:
            odds_data: Dictionary containing all odds information
            
        Returns:
            Dictionary with structured odds information
        """
        result = {}
        
        try:
            # Extract 1X2 (money line) odds
            if "moneyLineOdds" in odds_data:
                money_line = odds_data["moneyLineOdds"]
                
                if "Home" in money_line and "odds" in money_line["Home"]:
                    home_odds = money_line["Home"]["odds"]
                    result["home_win"] = self._get_best_odd(home_odds)
                
                if "Draw" in money_line and "odds" in money_line["Draw"]:
                    draw_odds = money_line["Draw"]["odds"]
                    result["draw"] = self._get_best_odd(draw_odds)
                    
                if "Away" in money_line and "odds" in money_line["Away"]:
                    away_odds = money_line["Away"]["odds"]
                    result["away_win"] = self._get_best_odd(away_odds)
            
            # Extract over/under odds
            if "overUnderOdds" in odds_data:
                over_under = odds_data["overUnderOdds"]
                
                # Get current total goals if available
                current_goals = processed_data.get("total_goals", 0)
                relevant_threshold = (current_goals + 0.5) if current_goals is not None else 2.5
                
                # Process over odds
                if "over" in over_under:
                    relevant_over_found = False
                    for threshold, data in over_under["over"].items():
                        if "odds" in data:
                            result[f"over_{threshold}"] = self._get_best_odd(data["odds"])
                            # Mark the most relevant threshold based on current score
                            threshold_float = float(threshold)
                            if threshold_float >= relevant_threshold and not relevant_over_found:
                                result["recommended_over_threshold"] = threshold
                                result["recommended_over_odds"] = result[f"over_{threshold}"]
                                relevant_over_found = True
                
                # Process under odds
                if "under" in over_under:
                    relevant_under_found = False
                    for threshold, data in over_under["under"].items():
                        if "odds" in data:
                            result[f"under_{threshold}"] = self._get_best_odd(data["odds"])
                            # Mark the most relevant threshold based on current score
                            threshold_float = float(threshold)
                            if threshold_float > current_goals and not relevant_under_found:
                                result["recommended_under_threshold"] = threshold
                                result["recommended_under_odds"] = result[f"under_{threshold}"]
                                relevant_under_found = True
                
                # Add explanation for available markets
                if current_goals > 0:
                    result["market_explanation"] = (f"With current score of {processed_data.get('score', '0-0')} "
                                                   f"({current_goals} total goals), betting on under_{relevant_threshold} "
                                                   f"would be the next relevant threshold")
            
            # Add additional odds data processing for canceled goals if available
            if "var_info" in odds_data:
                result["var_applied"] = True
                result["original_odds_before_var"] = odds_data.get("pre_var_odds", {})
            
            # Extract BTTS (both teams to score) odds
            if "bothTeamsToScoreOdds" in odds_data:
                btts = odds_data["bothTeamsToScoreOdds"]
                
                if "Yes" in btts and "odds" in btts["Yes"]:
                    result["btts_yes"] = self._get_best_odd(btts["Yes"]["odds"])
                    
                if "No" in btts and "odds" in btts["No"]:
                    result["btts_no"] = self._get_best_odd(btts["No"]["odds"])
            
        except Exception as e:
            logger.error(f"Error extracting odds: {e}")
        
        return result
    
    def _get_best_odd(self, odds_dict: Dict[str, str]) -> float:
        """
        Get the best (highest) odd value from a dictionary of bookmaker odds.
        
        Args:
            odds_dict: Dictionary mapping bookmaker names to odd values
            
        Returns:
            Float value of the best odd
        """
        try:
            # Convert all valid odds to floats
            valid_odds = []
            for _, odd_str in odds_dict.items():
                if odd_str and odd_str not in ('-', ''):
                    try:
                        valid_odds.append(float(odd_str))
                    except (ValueError, TypeError):
                        pass
            
            # Return the highest odd or 0 if none are valid
            return max(valid_odds) if valid_odds else 0.0
            
        except Exception as e:
            logger.error(f"Error getting best odd: {e}")
            return 0.0
    
    def _extract_team_stats(self, team_data: Dict[str, Any], team_type: str) -> Dict[str, Any]:
        """
        Extract relevant team statistics.
        
        Args:
            team_data: Dictionary containing team statistics
            team_type: Either 'home' or 'away'
            
        Returns:
            Dictionary with processed team statistics
        """
        result = {}
        prefix = f"{team_type}_"
        
        try:
            # Extract form data
            if "form" in team_data:
                form = team_data["form"]
                
                if "overall" in form and "ppg" in form["overall"]:
                    result[f"{prefix}form"] = float(form["overall"]["ppg"])
                    
                if team_type == "home" and "home" in form and "ppg" in form["home"]:
                    result[f"{prefix}home_form"] = float(form["home"]["ppg"])
                    
                if team_type == "away" and "away" in form and "ppg" in form["away"]:
                    result[f"{prefix}away_form"] = float(form["away"]["ppg"])
            
            # Extract detailed stats
            if "stats" in team_data:
                stats = team_data["stats"]
                
                # Win percentage
                if "winPercent" in stats:
                    win_pct = stats["winPercent"]
                    if "overall" in win_pct:
                        win_str = win_pct["overall"].replace("%", "")
                        result[f"{prefix}win_pct"] = float(win_str) if win_str else 0
                
                # Goals scored and conceded
                if "scored" in stats:
                    scored = stats["scored"]
                    if "overall" in scored:
                        result[f"{prefix}goals_scored"] = float(scored["overall"])
                
                if "conceded" in stats:
                    conceded = stats["conceded"]
                    if "overall" in conceded:
                        result[f"{prefix}goals_conceded"] = float(conceded["overall"])
                
                # BTTS and clean sheets
                if "btts" in stats:
                    btts = stats["btts"]
                    if "overall" in btts:
                        btts_str = btts["overall"].replace("%", "")
                        result[f"{prefix}btts_pct"] = float(btts_str) if btts_str else 0
                
                if "cs" in stats:
                    cs = stats["cs"]
                    if "overall" in cs:
                        cs_str = cs["overall"].replace("%", "")
                        result[f"{prefix}clean_sheet_pct"] = float(cs_str) if cs_str else 0
                
                # xG (expected goals)
                if "xg" in stats:
                    xg = stats["xg"]
                    if "overall" in xg:
                        result[f"{prefix}xg"] = float(xg["overall"])
                
                if "xga" in stats:
                    xga = stats["xga"]
                    if "overall" in xga:
                        result[f"{prefix}xga"] = float(xga["overall"])
            
        except Exception as e:
            logger.error(f"Error extracting team stats: {e}")
        
        return result
    
    def _extract_xg_values(self, match_doc: Dict[str, Any], processed_data: Dict[str, Any]) -> None:
        """
        Extract xG values from the match document and update processed data in-place.
        
        Args:
            match_doc: Original match document
            processed_data: Dictionary to update with xG values
        """
        try:
            # Try to get xG from team overviews
            if "teamOverviews" in match_doc:
                team_overviews = match_doc["teamOverviews"]
                
                if "home" in team_overviews and "stats" in team_overviews["home"]:
                    home_stats = team_overviews["home"]["stats"]
                    if "xg" in home_stats and "overall" in home_stats["xg"]:
                        processed_data["xg_home"] = float(home_stats["xg"]["overall"])
                
                if "away" in team_overviews and "stats" in team_overviews["away"]:
                    away_stats = team_overviews["away"]["stats"]
                    if "xg" in away_stats and "overall" in away_stats["xg"]:
                        processed_data["xg_away"] = float(away_stats["xg"]["overall"])
            
            # Calculate total xG if not already present
            if "xg_home" in processed_data and "xg_away" in processed_data:
                processed_data["total_xg"] = processed_data["xg_home"] + processed_data["xg_away"]
                
        except Exception as e:
            logger.error(f"Error extracting xG values: {e}")


def get_match_processor() -> MatchDataProcessor:
    """
    Create and return a match data processor instance.
    
    Returns:
        Configured MatchDataProcessor
    """
    return MatchDataProcessor()


# Example usage when run directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Sample match document (stub)
    sample_doc = {
        "_id": "sample-id",
        "homeTeam": "Team A",
        "awayTeam": "Team B",
        "league": "Sample League",
        "liveStats": {
            "minute": "45",
            "score": "1 - 0",
            "stats": {
                "Shots Total": {"home": "10", "away": "5"},
                "Shots On Target": {"home": "4", "away": "2"},
                "Possession": {"home": "60", "away": "40"},
                "Corners": {"home": "5", "away": "2"}
            }
        }
    }
    
    processor = get_match_processor()
    result = processor.process_match_document(sample_doc)
    
    logger.info("Processed match data:")
    for key, value in result.items():
        logger.info(f"  {key}: {value}")
