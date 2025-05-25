"""
Module for loading and utilizing ML models for bet predictions.
"""
import logging
import os
from typing import Dict, Any, Optional, List

import joblib
import numpy as np

from src import config

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    Handles loading and prediction using a pre-trained ML model.
    """
    
    def __init__(self):
        """Initialize the ML predictor and load the model."""
        self.model = None
        self.model_loaded = False
        self.feature_names = [
            'minute', 'home_shots', 'away_shots', 'possession_home', 
            'xg_home', 'xg_away', 'total_xg'
        ]
        
        # Load the model if enabled in config
        if config.ENABLE_ML_MODEL:
            self._load_model()
    
    def _load_model(self) -> bool:
        """
        Load the pre-trained ML model from disk.
        
        Returns:
            True if model was loaded successfully, False otherwise
        """
        model_path = config.ML_MODEL_PATH
        
        try:
            if not os.path.exists(model_path):
                logger.error(f"Model file not found: {model_path}")
                return False
                
            self.model = joblib.load(model_path)
            self.model_loaded = True
            logger.info(f"Successfully loaded ML model from {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self.model_loaded = False
            return False
    
    def _extract_features(self, match_data: Dict[str, Any]) -> np.ndarray:
        """
        Extract feature array from match data.
        
        Args:
            match_data: Dictionary containing live match data
            
        Returns:
            NumPy array of feature values
        """
        features = []
        
        for feature in self.feature_names:
            if feature not in match_data:
                logger.warning(f"Feature {feature} not found in match data")
                features.append(0.0)  # Default value
            else:
                features.append(float(match_data[feature]))
        
        return np.array(features).reshape(1, -1)
    
    def predict(self, match_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make a prediction based on current match data.
        
        Args:
            match_data: Dictionary containing live match data
            
        Returns:
            Dictionary with prediction results or None if prediction couldn't be made
        """
        if not self.model_loaded:
            if not self._load_model():
                logger.error("Cannot make prediction: model not loaded")
                return None
        
        try:
            # Extract features from match data
            features = self._extract_features(match_data)
            
            # Make prediction
            prediction_raw = self.model.predict_proba(features)[0]
            prediction = float(prediction_raw[1])  # Assuming binary classification with class 1 = place bet
            
            # Determine confidence
            confidence = max(prediction, 1 - prediction)
            
            # Determine recommended action based on threshold
            action = "place" if prediction >= 0.6 else "skip"
            
            # Create prediction result
            result = {
                "prediction": prediction,
                "confidence": confidence,
                "action": action,
                "match_id": match_data.get("match_id", "unknown"),
                "market": self._determine_best_market(match_data, prediction)
            }
            
            logger.info(f"Made prediction for match {result['match_id']}: {result['action']} with {result['confidence']:.2f} confidence")
            return result
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return None
    
    def _determine_best_market(self, match_data: Dict[str, Any], prediction: float) -> str:
        """
        Determine the best market to bet on based on match data and prediction.
        
        Args:
            match_data: Dictionary containing live match data
            prediction: Raw prediction value from model
            
        Returns:
            String indicating the recommended market
        """
        # Simple logic - in a real system this would be more sophisticated
        total_xg = match_data.get("xg_home", 0) + match_data.get("xg_away", 0)
        
        if total_xg > 2.0:
            return "over_2.5"
        elif match_data.get("xg_home", 0) > match_data.get("xg_away", 0) + 0.5:
            return "home_win"
        elif match_data.get("xg_away", 0) > match_data.get("xg_home", 0) + 0.5:
            return "away_win"
        else:
            return "under_2.5"


def get_ml_predictor() -> MLPredictor:
    """
    Create and return an ML predictor instance.
    
    Returns:
        Configured MLPredictor
    """
    return MLPredictor()


# Create a dummy model for testing if it doesn't exist
def create_dummy_model() -> None:
    """
    Create a simple dummy model for testing purposes if no model exists.
    """
    from sklearn.ensemble import RandomForestClassifier
    import os
    
    if os.path.exists(config.ML_MODEL_PATH):
        logger.info(f"Model already exists at {config.ML_MODEL_PATH}")
        return
    
    try:
        # Ensure models directory exists
        os.makedirs(os.path.dirname(config.ML_MODEL_PATH), exist_ok=True)
        
        # Create a simple random forest classifier
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        
        # Generate some dummy training data
        # Features: minute, home_shots, away_shots, possession_home, xg_home, xg_away, total_xg
        X = np.random.rand(100, 7)
        # Make the dummy model somewhat sensible - more likely to predict bet when xG is high
        X[:, 4:7] = np.random.rand(100, 3) * 3  # xG features
        y = (X[:, 6] > 1.5).astype(int)  # Bet when total_xg > 1.5
        
        # Fit the model
        model.fit(X, y)
        
        # Save the model
        joblib.dump(model, config.ML_MODEL_PATH)
        logger.info(f"Created and saved dummy model to {config.ML_MODEL_PATH}")
    
    except Exception as e:
        logger.error(f"Failed to create dummy model: {e}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create a dummy model for testing
    create_dummy_model()
    
    # Test the ML predictor
    predictor = get_ml_predictor()
    
    # Test with some sample match data
    test_data = {
        "match_id": "test-123",
        "minute": 75,
        "home_shots": 12,
        "away_shots": 8,
        "possession_home": 55.2,
        "xg_home": 1.8,
        "xg_away": 0.9,
        "total_xg": 2.7
    }
    
    result = predictor.predict(test_data)
    if result:
        print(f"Prediction: {result['action']} {result['market']} bet with {result['confidence']:.2f} confidence")
