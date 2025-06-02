"""
Module for training and maintaining the ML betting model.
"""
import os
import logging
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)

# Define the model path
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'betting_model.joblib')

def get_training_data():
    """
    Get training data for the betting model.
    You should implement this based on your data source.
    
    Returns:
        Tuple of (features, labels)
    """
    # This is a placeholder - implement based on your data source
    # For example, you might load data from a CSV file or database
    try:
        data_path = os.path.join(os.path.dirname(MODEL_DIR), 'data', 'betting_data.csv')
        if os.path.exists(data_path):
            df = pd.read_csv(data_path)
            
            # Extract features and labels
            X = df.drop(['is_suitable'], axis=1)
            y = df['is_suitable']
            
            return X, y
    except Exception as e:
        logger.error(f"Error loading training data: {e}")
    
    # If we can't load real data, create a dummy dataset
    # This is just for demonstration - replace with real data!
    logger.warning("Using dummy training data - replace with real data!")
    
    # Generate 1000 random samples
    np.random.seed(42)
    n_samples = 1000
    
    # Features: minute, home_goals, away_goals, total_goals, goal_diff, various stats...
    X = np.zeros((n_samples, 16))
    X[:, 0] = np.random.uniform(45, 85, n_samples)  # minute
    X[:, 1] = np.random.randint(0, 4, n_samples)    # home_goals
    X[:, 2] = np.random.randint(0, 4, n_samples)    # away_goals
    X[:, 3] = X[:, 1] + X[:, 2]                     # total_goals
    X[:, 4] = X[:, 1] - X[:, 2]                     # goal_diff
    X[:, 5:] = np.random.randint(0, 20, (n_samples, 11))  # other stats
    
    # Define a simple rule for the target
    # e.g., suitable if minute > 65 and total_goals between 1-3
    y = ((X[:, 0] > 65) & (X[:, 3] >= 1) & (X[:, 3] <= 3)).astype(int)
    
    return X, y

def train_model(save=True):
    """
    Train the betting model.
    
    Args:
        save: Whether to save the model to disk
        
    Returns:
        Trained model
    """
    # Make sure the model directory exists
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # Get training data
    X, y = get_training_data()
    
    # Split into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Create and train the model
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # Evaluate the model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    
    logger.info(f"Model performance: Accuracy={accuracy:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, F1={f1:.4f}")
    
    # Save the model if requested
    if save:
        joblib.dump(model, MODEL_PATH)
        logger.info(f"Model saved to {MODEL_PATH}")
    
    return model

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Train and save the model
    train_model(save=True)
