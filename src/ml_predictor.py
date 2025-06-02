"""
Machine Learning predictor for football betting decisions.

This module provides a class for training and making predictions
using historical betting data.
"""
import logging
import os
import random
from typing import Dict, Any, Tuple, List
from datetime import datetime, timedelta

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from src.mongo_handler import MongoHandler

logger = logging.getLogger(__name__)

class MLPredictor:
    """Machine Learning predictor for betting decisions."""
    
    # Class-level cache for training data
    _cached_data = {
        'features': None,
        'labels': None,
        'last_loaded': None,
        'cache_valid': False
    }
    
    # Default cache expiration time in hours
    CACHE_EXPIRY_HOURS = 24
    
    def __init__(self, model_path: str = None):
        """
        Initialize the ML predictor.
        
        Args:
            model_path: Path to a saved sklearn model
        """
        self.model = None
        self.model_path = model_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'models',
            'betting_model.joblib'
        )
        self.load_model()
        
    def load_model(self):
        """Load the ML model from disk."""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded ML model from {self.model_path}")
            else:
                # Create a simple default model if none exists
                self.model = self.create_default_model()
                logger.info("Created default ML model")
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            self.model = self.create_default_model()
    
    def create_default_model(self):
        """Create a simple default model."""
        # Simple RandomForest with reasonable defaults
        return RandomForestClassifier(
            n_estimators=100, 
            max_depth=10,
            random_state=42
        )
    
    def extract_features(self, match_data: Dict[str, Any]) -> np.ndarray:
        """
        Extract features from match data for ML prediction.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            NumPy array of features
        """
        # Extract basic features that most models would need
        features = []
        
        # Match time
        minute = match_data.get("minute", 0)
        features.append(minute)
        
        # Score
        score = match_data.get("score", "0 - 0")
        try:
            home_goals, away_goals = map(int, score.split(" - "))
            total_goals = home_goals + away_goals
            goal_diff = home_goals - away_goals
        except ValueError:
            home_goals = away_goals = total_goals = goal_diff = 0
        
        features.extend([home_goals, away_goals, total_goals, goal_diff])
        
        # Add league/country tier as a feature
        league_tier = self._get_league_tier(match_data.get("league", ""), match_data.get("country", ""))
        features.append(league_tier)
        
        # Add average goals for the league as a feature (prefer from predictionStats if available)
        league_avg_goals = None
        prediction_stats = match_data.get("predictionStats", {})
        if isinstance(prediction_stats, dict):
            league_avg_goals = prediction_stats.get("leagueAvgGoals")
        if league_avg_goals is None:
            # Fallback to static mapping if not present
            league_avg_goals = self._get_league_avg_goals(match_data.get("league", ""), match_data.get("country", ""))
        features.append(league_avg_goals)
        
        # Team stats
        features.append(match_data.get("home_avg_goals", 0))
        features.append(match_data.get("away_avg_goals", 0))
        
        # Match stats
        features.append(match_data.get("home_shots", 0))
        features.append(match_data.get("away_shots", 0))
        features.append(match_data.get("home_shots_on_target", 0))
        features.append(match_data.get("away_shots_on_target", 0))
        features.append(match_data.get("home_corners", 0))
        features.append(match_data.get("away_corners", 0))
        features.append(match_data.get("home_fouls", 0))
        features.append(match_data.get("away_fouls", 0))
        features.append(match_data.get("home_dangerous_attacks", 0))
        features.append(match_data.get("away_dangerous_attacks", 0))
        
        # Calculate rates based on minute
        if minute > 0:
            features.append(total_goals / minute)  # Goals per minute
            features.append((match_data.get("home_shots", 0) + match_data.get("away_shots", 0)) / minute)  # Shots per minute
            features.append((match_data.get("home_shots_on_target", 0) + match_data.get("away_shots_on_target", 0)) / minute)  # Shots on target per minute
        else:
            features.extend([0, 0, 0])  # Add zeros if minute is 0

        # Ensure feature vector matches the number of features used during training (20)
        # Remove any extra features if present
        if len(features) > 20:
            features = features[:20]
        elif len(features) < 20:
            # Pad with zeros if for some reason there are not enough features
            features.extend([0] * (20 - len(features)))

        return np.array(features).reshape(1, -1)
    
    def predict(self, match_data: Dict[str, Any]) -> Tuple[bool, float]:
        """
        Make a prediction for a match.
        
        Args:
            match_data: Match data dictionary
            
        Returns:
            Tuple of (is_suitable, confidence)
        """
        if self.model is None:
            logger.error("ML model not initialized")
            return False, 0.0
        
        # Get minute and check if we're in the second half
        minute = match_data.get("minute", 0)
        
        # Check if we're still in the first half
        first_half = False
        minute_raw = match_data.get("minute_raw", "")  # Original minute string if available
        
        # Handle half-time specifically
        if minute == "HT" or minute == 45:
            first_half = True
            logger.info(f"Match at half-time, not evaluating with ML")
            return True, 0.75  # Default to positive with medium-high confidence
        
        # Consider first half situations - common indicators
        if isinstance(minute_raw, str) and (
            "1H" in minute_raw or 
            "1st" in minute_raw or
            "HT" in minute_raw or
            (minute_raw.isdigit() and int(minute_raw) <= 45) or
            ('+' in minute_raw and int(minute_raw.split('+')[0]) <= 45)
        ):
            first_half = True
        
        # If it's first half added time, don't use ML prediction regardless of minute
        if first_half:
            logger.info(f"Match still in first half (minute {minute}), not evaluating with ML")
            return True, 0.75  # Default to positive with medium-high confidence
            
        # Only apply ML prediction after minute 50 of second half
        if minute < 50:
            logger.info(f"Match at minute {minute}, not evaluating with ML (requires minute >= 50)")
            return True, 0.75  # Default to positive with medium-high confidence
        
        try:
            # Extract features
            features = self.extract_features(match_data)
            
            # Log feature array shape for debugging
            logger.debug(f"Feature array shape: {features.shape}")
            
            # Make prediction
            if hasattr(self.model, "predict_proba"):
                probas = self.model.predict_proba(features)
                # Assuming binary classification (not suitable, suitable)
                if probas.shape[1] >= 2:
                    confidence = probas[0][1]  # Probability of class 1 (suitable)
                else:
                    confidence = probas[0][0]
            else:
                # If model doesn't support probabilities, use binary prediction
                prediction = self.model.predict(features)[0]
                confidence = 1.0 if prediction else 0.0
            
            is_suitable = confidence >= 0.6  # Threshold for suitability
            return is_suitable, confidence
            
        except Exception as e:
            logger.error(f"Error making ML prediction: {e}")
            # More detailed error information
            import traceback
            logger.error(f"ML prediction traceback: {traceback.format_exc()}")
            return False, 0.0
        
    def load_training_data_from_mongodb(self, use_cache: bool = True, force_reload: bool = False) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load training data from MongoDB underxmatches collection.
        
        Args:
            use_cache: Whether to use cached data if available
            force_reload: Whether to force reload data from database
            
        Returns:
            Tuple of (features array, labels array)
        """
        # Check if we can use cached data
        cache = MLPredictor._cached_data
        now = datetime.now()
        
        if (use_cache and 
            not force_reload and 
            cache['cache_valid'] and 
            cache['features'] is not None and 
            cache['labels'] is not None and 
            cache['last_loaded'] is not None and 
            (now - cache['last_loaded']) < timedelta(hours=self.CACHE_EXPIRY_HOURS)):
            
            logger.info(f"Using cached training data from {cache['last_loaded']}")
            return cache['features'], cache['labels']
        
        try:
            logger.info("Loading training data from MongoDB...")
            
            # Use MongoHandler instead of direct connection
            mongo_handler = MongoHandler()
            underx_collection = mongo_handler.db["underxmatches"]
            
            # Query for matches that have been bet on (bet: true)
            matches = list(underx_collection.find({
                "bet": True,
                "$or": [
                    {"profitLoss": {"$gt": 0}},  # Successful bets
                    {"profitLoss": {"$lt": 0}}   # Unsuccessful bets
                ]
            }))
            
            logger.info(f"Found {len(matches)} matches for training")
            
            # Prepare features and labels
            features = []
            labels = []
            
            for match in matches:
                try:
                    # Create a standardized match data dictionary
                    match_data = self._prepare_match_data(match)
                    
                    # Extract features
                    match_features = self.extract_features_for_training(match_data)
                    
                    # Set label: 1 for successful bets, 0 for unsuccessful
                    label = 1 if match.get("profitLoss", 0) > 0 else 0
                    
                    features.append(match_features)
                    labels.append(label)
                    
                except Exception as e:
                    logger.error(f"Error processing match {match.get('_id')}: {e}")
                    continue
            
            # Close the MongoDB connection when done
            mongo_handler.close()
            
            if not features:
                logger.error("No valid training data could be extracted")
                return np.array([]), np.array([])
            
            features_array = np.array(features)
            labels_array = np.array(labels)
            
            # Update the cache
            cache['features'] = features_array
            cache['labels'] = labels_array
            cache['last_loaded'] = now
            cache['cache_valid'] = True
            
            logger.info(f"Successfully extracted features for {len(features)} matches and updated cache")
            return features_array, labels_array
            
        except Exception as e:
            logger.error(f"Error loading training data from MongoDB: {e}")
            # Invalidate cache on error
            cache['cache_valid'] = False
            return np.array([]), np.array([])
    
    def _is_cache_valid(self) -> bool:
        """Check if the cached data is still valid."""
        if not self._cached_data['cache_valid']:
            return False
        
        # Check the age of the cached data
        elapsed_time = datetime.now() - self._cached_data['last_loaded']
        if elapsed_time > timedelta(hours=self.CACHE_EXPIRY_HOURS):
            logger.info("Cached data expired")
            return False
        
        return True
    
    def _prepare_match_data(self, match_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare match document for feature extraction.
        
        Args:
            match_doc: Raw MongoDB document
            
        Returns:
            Processed match data dictionary
        """
        # Extract the score if available
        score = "0 - 0"
        if "result" in match_doc:
            score = match_doc["result"].replace("-", " - ")
        elif "liveStats" in match_doc and "score" in match_doc["liveStats"]:
            score = match_doc["liveStats"]["score"]
        
        # Extract minute when the bet was placed - this is critical for training
        minute = 0
        
        # First priority: Use betGameTime if available (most accurate)
        if "betGameTime" in match_doc and match_doc["betGameTime"] is not None:
            minute = int(match_doc["betGameTime"])
            logger.debug(f"Using betGameTime: {minute}")
            
        # Second priority: Use betTime to estimate the minute if possible
        elif "betTime" in match_doc and match_doc["betTime"] is not None:
            # If we have both bet time and game start time, we can calculate the minute
            if "date" in match_doc:
                try:
                    bet_time = match_doc["betTime"].timestamp() if hasattr(match_doc["betTime"], "timestamp") else 0
                    game_start_time = match_doc["date"] / 1000 if match_doc["date"] > 1000000000 else match_doc["date"]
                    
                    # Calculate minutes elapsed between game start and bet placement
                    elapsed_seconds = bet_time - game_start_time
                    if 0 < elapsed_seconds < 120 * 60:  # Valid range: 0-120 minutes
                        minute = int(elapsed_seconds / 60)
                        logger.debug(f"Calculated minute from betTime: {minute}")
                except Exception as e:
                    logger.debug(f"Could not calculate minute from betTime: {e}")
        
        # Third priority: Try liveStats.minute but be careful with finished games
        elif "liveStats" in match_doc and "minute" in match_doc["liveStats"]:
            minute_str = match_doc["liveStats"]["minute"]
            
            # For finished games, liveStats.minute would be "FT" or close to 90
            # This doesn't represent when the bet was placed
            finished_game = match_doc.get("isFinalResult", False) or "result" in match_doc
            
            if not finished_game and isinstance(minute_str, str):
                if minute_str.isdigit():
                    minute = int(minute_str)
                elif minute_str == "HT":
                    minute = 45
                elif "+" in minute_str:  # Handle added time format like "45+2"
                    minute = int(minute_str.split("+")[0])
                logger.debug(f"Using liveStats.minute for in-progress game: {minute}")
            else:
                # For finished games, estimate when the bet was placed
                # Since we're looking at underX in-play bets, the typical window is 52-55 minutes
                minute = random.randint(52, 55)
                logger.debug(f"Game appears finished. Estimated betting minute: {minute}")
        
        # If all else fails, use our default estimate
        else:
            minute = random.randint(52, 55)
            logger.debug(f"No minute information found. Using estimated minute: {minute}")
        
        # Get stats if available
        live_stats = match_doc.get("liveStats", {})
        stats = live_stats.get("stats", {})
        
        # Prepare the standardized match data
        match_data = {
            "match_id": str(match_doc.get("_id", "")),
            "home_team": match_doc.get("homeTeam", ""),
            "away_team": match_doc.get("awayTeam", ""),
            "score": score,
            "minute": minute,
            "country": match_doc.get("country", ""),
            "league": match_doc.get("league", ""),
            
            # Stats - convert to integers safely
            "home_shots": self._safe_int(stats.get("Shots Total", {}).get("home", 0)),
            "away_shots": self._safe_int(stats.get("Shots Total", {}).get("away", 0)),
            "home_shots_on_target": self._safe_int(stats.get("Shots On Target", {}).get("home", 0)),
            "away_shots_on_target": self._safe_int(stats.get("Shots On Target", {}).get("away", 0)),
            "home_corners": self._safe_int(stats.get("Corners", {}).get("home", 0)),
            "away_corners": self._safe_int(stats.get("Corners", {}).get("away", 0)),
            "home_fouls": self._safe_int(stats.get("Fouls", {}).get("home", 0)),
            "away_fouls": self._safe_int(stats.get("Fouls", {}).get("away", 0)),
            "home_dangerous_attacks": self._safe_int(stats.get("Dangerous Attacks", {}).get("home", 0)),
            "away_dangerous_attacks": self._safe_int(stats.get("Dangerous Attacks", {}).get("away", 0)),
            
            # Team stats from team overviews
            "home_avg_goals": self._get_team_avg_goals(match_doc, "home"),
            "away_avg_goals": self._get_team_avg_goals(match_doc, "away"),
            
            # Add odds if available
            "odds": match_doc.get("odds", {}),
            
            # Add result for training purposes
            "profitLoss": match_doc.get("profitLoss", 0),
            "bet_type": match_doc.get("betType", ""),
            "stake": match_doc.get("stake", 0),
            "odd": match_doc.get("odd", 0)
        }
        
        return match_data
    
    def _safe_int(self, value) -> int:
        """Convert value to integer safely."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _get_team_avg_goals(self, match_doc: Dict[str, Any], team_type: str) -> float:
        """Extract average goals per match for a team."""
        try:
            # Check if team overviews are available
            if "teamOverviews" in match_doc and team_type in match_doc["teamOverviews"]:
                team_data = match_doc["teamOverviews"][team_type]
                if "stats" in team_data and "scored" in team_data["stats"]:
                    overall_scored = team_data["stats"]["scored"].get("overall", "0")
                    try:
                        return float(overall_scored)
                    except (ValueError, TypeError):
                        pass
            
            # Default fallback
            return 1.5
        except Exception:
            return 1.5
    
    def _get_league_avg_goals(self, league: str, country: str) -> float:
        """
        Return the average goals per match for a given league/country.
        Uses a hardcoded mapping for major leagues, otherwise returns a default.
        """
        league = league.lower()
        country = country.lower()
        # Example averages, adjust as needed for your data
        league_avg_goals_map = {
            "premier league": 2.8,
            "la liga": 2.5,
            "bundesliga": 3.1,
            "serie a": 2.6,
            "ligue 1": 2.7,
            "eredivisie": 3.0,
            "primeira liga": 2.4,
            "championship": 2.5,
            "mls": 3.0,
            "jupiler pro": 2.9,
            "ekstraklasa": 2.6,
            "super lig": 2.8,
            "allsvenskan": 2.9,
            "a-league": 3.1,
            "brasileirão": 2.3,
            "liga mx": 2.7,
            "russian premier league": 2.4,
            "scottish premiership": 2.7,
            "belgian pro league": 2.9,
            "swiss super league": 3.0,
            "turkish super lig": 2.8,
            "portuguese primeira liga": 2.4,
            "greek super league": 2.3,
            "norwegian eliteserien": 3.1,
            "swedish allsvenskan": 2.9,
            "danish superliga": 2.8,
            "austrian bundesliga": 3.0,
            "czech first league": 2.7,
            "polish ekstraklasa": 2.6,
            "argentine primera division": 2.3,
            "chilean primera division": 2.7,
            "mexican liga mx": 2.7,
            "japanese j1 league": 2.6,
            "k league 1": 2.5,
            "major league soccer": 3.0,
        }
        # Try to match by league name
        for key in league_avg_goals_map:
            if key in league:
                return league_avg_goals_map[key]
        # Try to match by country if league not found
        country_avg_goals_map = {
            "england": 2.8,
            "spain": 2.5,
            "germany": 3.1,
            "italy": 2.6,
            "france": 2.7,
            "netherlands": 3.0,
            "portugal": 2.4,
            "usa": 3.0,
            "belgium": 2.9,
            "poland": 2.6,
            "turkey": 2.8,
            "sweden": 2.9,
            "australia": 3.1,
            "brazil": 2.3,
            "mexico": 2.7,
            "russia": 2.4,
            "scotland": 2.7,
            "switzerland": 3.0,
            "greece": 2.3,
            "norway": 3.1,
            "denmark": 2.8,
            "austria": 3.0,
            "czech republic": 2.7,
            "argentina": 2.3,
            "chile": 2.7,
            "japan": 2.6,
            "south korea": 2.5,
        }
        for key in country_avg_goals_map:
            if key in country:
                return country_avg_goals_map[key]
        # Default average if not found
        return 2.7
    
    def _get_league_tier(self, league: str, country: str) -> float:
        """
        Categorize leagues into tiers based on quality/competitiveness.
        
        Args:
            league: League name
            country: Country name
            
        Returns:
            League tier score from 1.0 (top tier) to 5.0 (lower tier)
        """
        league_lower = league.lower()
        country_lower = country.lower()
        # Top tier leagues (tier 1)
        if any(name in league_lower for name in ["premier league", "la liga", "bundesliga", "serie a", "ligue 1"]):
            return 1.0
        # Major second tier leagues and good leagues (tier 2)
        if any(name in league_lower for name in ["eredivisie", "primeira liga", "championship", "primera division", 
                                               "super lig", "primeira liga", "brasileirão", "mls"]):
            return 2.0
        # Mid-tier leagues (tier 3)
        if any(name in league_lower for name in ["2. bundesliga", "serie b", "ligue 2", "segunda division", 
                                               "süper lig", "allsvenskan", "jupiler pro", "ekstraklasa", 
                                               "superliga", "a-league"]):
            return 3.0
        # Lower tier but still professional leagues (tier 4)
        if any(name in league_lower for name in ["league one", "league two", "3. liga", "primera nacional",
                                               "national league", "eliteserien"]):
            return 4.0
        # Everything else (tier 5)
        return 5.0

    def extract_features_for_training(self, match_data: Dict[str, Any]) -> np.ndarray:
        """
        Extract features for training from match data.
        More comprehensive than the predict-time feature extraction.
        
        Args:
            match_data: Processed match data dictionary
            
        Returns:
            NumPy array of features
        """
        features = []
        
        # Basic match info
        minute = match_data.get("minute", 0)
        features.append(minute)
        
        # Score
        score = match_data.get("score", "0 - 0")
        try:
            home_goals, away_goals = map(int, score.split(" - "))
            total_goals = home_goals + away_goals
            goal_diff = home_goals - away_goals
        except ValueError:
            home_goals, away_goals, total_goals, goal_diff = 0, 0, 0, 0
        
        features.extend([home_goals, away_goals, total_goals, goal_diff])
        
        # Team stats
        features.append(match_data.get("home_avg_goals", 0))
        features.append(match_data.get("away_avg_goals", 0))
        
        # Match stats
        features.append(match_data.get("home_shots", 0))
        features.append(match_data.get("away_shots", 0))
        features.append(match_data.get("home_shots_on_target", 0))
        features.append(match_data.get("away_shots_on_target", 0))
        features.append(match_data.get("home_corners", 0))
        features.append(match_data.get("away_corners", 0))
        features.append(match_data.get("home_fouls", 0))
        features.append(match_data.get("away_fouls", 0))
        features.append(match_data.get("home_dangerous_attacks", 0))
        features.append(match_data.get("away_dangerous_attacks", 0))
        
        # Calculate rates based on minute
        if minute > 0:
            features.append(total_goals / minute)  # Goals per minute
            features.append((match_data.get("home_shots", 0) + match_data.get("away_shots", 0)) / minute)  # Shots per minute
            features.append((match_data.get("home_shots_on_target", 0) + match_data.get("away_shots_on_target", 0)) / minute)  # Shots on target per minute
        else:
            features.extend([0, 0, 0])  # Add zeros if minute is 0
        
        return np.array(features)
    
    def train_model(self, save_model=True, force_reload=False) -> bool:
        """
        Train the ML model using data from MongoDB.
        
        Args:
            save_model: Whether to save the trained model to disk
            force_reload: Whether to force reload data from database
            
        Returns:
            True if training was successful, False otherwise
        """
        try:
            # Load training data, with options to use cache or force reload
            X, y = self.load_training_data_from_mongodb(use_cache=True, force_reload=force_reload)
            
            if len(X) == 0 or len(y) == 0:
                logger.error("No training data available")
                return False
            
            # Split into training and validation sets
            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Create and train the model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                class_weight='balanced',  # Handle class imbalance
                random_state=42
            )
            
            self.model.fit(X_train, y_train)
            
            # Evaluate the model
            y_pred = self.model.predict(X_val)
            accuracy = accuracy_score(y_val, y_pred)
            precision = precision_score(y_val, y_pred, zero_division=0)
            recall = recall_score(y_val, y_pred, zero_division=0)
            f1 = f1_score(y_val, y_pred, zero_division=0)
            
            logger.info(f"Model evaluation:")
            logger.info(f"- Accuracy: {accuracy:.4f}")
            logger.info(f"- Precision: {precision:.4f}")
            logger.info(f"- Recall: {recall:.4f}")
            logger.info(f"- F1 Score: {f1:.4f}")
            
            # Save the model if requested
            if save_model:
                # Make sure the models directory exists
                os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
                joblib.dump(self.model, self.model_path)
                logger.info(f"Model saved to {self.model_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False


# Singleton instance
_ml_predictor_instance = None

def get_ml_predictor():
    """Get the global ML predictor singleton instance."""
    global _ml_predictor_instance
    if _ml_predictor_instance is None:
        _ml_predictor_instance = MLPredictor()
    return _ml_predictor_instance
