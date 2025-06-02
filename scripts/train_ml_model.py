#!/usr/bin/env python3
"""
Script to train the ML model for the UnderX In-Play strategy.
"""
import logging
import sys
import os
import argparse

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.ml_predictor import get_ml_predictor  # Updated import path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Train the ML model for UnderX strategy."""
    parser = argparse.ArgumentParser(description='Train the ML model for UnderX strategy.')
    parser.add_argument('--no-save', action='store_true', help='Don\'t save the model to disk')
    parser.add_argument('--verbose', action='store_true', help='Show detailed training information')
    args = parser.parse_args()
    
    # Set logging level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting ML model training...")
    
    # Get ML predictor and train model
    ml_predictor = get_ml_predictor()
    success = ml_predictor.train_model(save_model=not args.no_save)
    
    if success:
        logger.info("✅ Model training completed successfully")
        return 0
    else:
        logger.error("❌ Model training failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
