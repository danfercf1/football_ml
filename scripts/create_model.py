#!/usr/bin/env python3
"""
Script to generate a sample ML model for testing purposes.
"""
import os
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define model path
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'betting_model.pkl')

def create_sample_model():
    """Create a simple sample model for betting predictions."""
    logger.info(f"Creating sample ML model at {MODEL_PATH}")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    
    # Create a random forest classifier
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    
    # Generate synthetic training data
    # Features: minute, home_shots, away_shots, possession_home, xg_home, xg_away, total_xg
    n_samples = 1000
    X = np.zeros((n_samples, 7))
    
    # Generate somewhat realistic soccer match data
    X[:, 0] = np.random.randint(1, 90, n_samples)  # minute
    X[:, 1] = np.random.randint(0, 25, n_samples)  # home_shots
    X[:, 2] = np.random.randint(0, 20, n_samples)  # away_shots
    X[:, 3] = np.random.randint(30, 70, n_samples)  # possession_home
    X[:, 4] = X[:, 1] * np.random.uniform(0.05, 0.15, n_samples)  # xg_home (based on shots)
    X[:, 5] = X[:, 2] * np.random.uniform(0.05, 0.15, n_samples)  # xg_away (based on shots)
    X[:, 6] = X[:, 4] + X[:, 5]  # total_xg
    
    # Generate labels - this creates a model that bets when:
    # 1. Total xG is high (> 2.0) OR
    # 2. Late in the game (> 70 min) and one team has high xG advantage
    xg_diff = np.abs(X[:, 4] - X[:, 5])
    y = ((X[:, 6] > 2.0) | ((X[:, 0] > 70) & (xg_diff > 1.0))).astype(int)
    
    # Fit the model
    model.fit(X, y)
    
    # Save the model
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved successfully with {n_samples} training samples")
    
    # Print feature importances
    feature_names = ['minute', 'home_shots', 'away_shots', 'possession_home', 
                     'xg_home', 'xg_away', 'total_xg']
    importances = model.feature_importances_
    for feature, importance in zip(feature_names, importances):
        logger.info(f"Feature {feature}: importance = {importance:.4f}")

if __name__ == "__main__":
    create_sample_model()
