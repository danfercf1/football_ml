"""
Main analyzer module for soccer match analysis.
This module coordinates the entire analysis process:
1. Loads rules from MongoDB
2. Processes live match data
3. Evaluates rules and ML predictions
4. Sends bet signals to RabbitMQ
"""
import logging
import time
from typing import Dict, Any, List, Optional

from src import config
from src.mock_data import get_mock_match_generator
from src.mongo_handler import get_mongo_handler
from src.ml_predictor import get_ml_predictor, create_dummy_model
from src.rule_engine import get_rule_engine
from src.rabbitmq_publisher import get_rabbitmq_publisher
# Import specialized modules for real match data
from src.match_processor import get_match_processor
from src.specialized_rules import SpecializedRules
# Import API client for real data integration
from src.api_client import get_api_client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MatchAnalyzer:
    """
    Main analyzer class that coordinates all components of the system.
    """
    
    def __init__(self, use_api_client: bool = False):
        """
        Initialize all components of the system.
        
        Args:
            use_api_client: Whether to use the API client for real data
        """
        logger.info("Initializing Match Analyzer")
        
        # Store API client option
        self.use_api_client = use_api_client
        
        # Initialize MongoHandler and load rules
        self.mongo_handler = get_mongo_handler()
        self.rules = self.mongo_handler.get_rules()
        logger.info(f"Loaded {len(self.rules)} rules from MongoDB")
        
        # Initialize RabbitMQ publisher
        self.rabbitmq_publisher = get_rabbitmq_publisher()
        
        # Initialize Rule Engine with rules
        self.rule_engine = get_rule_engine(self.rules)
        
        # Create dummy ML model if needed
        if config.ENABLE_ML_MODEL:
            create_dummy_model()
            
        # Initialize ML Predictor
        self.ml_predictor = get_ml_predictor() if config.ENABLE_ML_MODEL else None
        
        # Set up change stream for rule updates if enabled
        if config.ENABLE_CHANGE_STREAMS:
            self.mongo_handler.setup_change_stream(self._handle_rule_change)
        
        # Initialize match processor for real data
        self.match_processor = get_match_processor()
        
        # Initialize API client if needed
        self.api_client = get_api_client() if use_api_client else None
    
    def _handle_rule_change(self, change_event: Dict[str, Any]) -> None:
        """
        Handle rule changes from MongoDB change stream.
        
        Args:
            change_event: Change event document from MongoDB
        """
        logger.info(f"Received rule change event: {change_event['operationType']}")
        
        # Reload all rules from MongoDB
        self.rules = self.mongo_handler.get_rules()
        logger.info(f"Reloaded {len(self.rules)} rules after change event")
        
        # Update rule engine with new rules
        self.rule_engine.set_rules(self.rules)
    
    def analyze_match_data(self, match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze match data using rules and ML model.
        
        Args:
            match_data: Dictionary containing live match data
            
        Returns:
            List of bet actions to take
        """
        bet_actions = []
        
        # Skip analysis for early match minutes if needed
        if match_data.get("minute", 0) < 5:
            logger.debug("Skipping analysis for early match minutes")
            return []
            
        # 1. Rule-based analysis
        if config.ENABLE_RULE_ENGINE:
            rule_actions = self.rule_engine.evaluate(match_data)
            bet_actions.extend(rule_actions)
        
        # 2. ML-based analysis
        if config.ENABLE_ML_MODEL and self.ml_predictor:
            ml_prediction = self.ml_predictor.predict(match_data)
            if ml_prediction and ml_prediction.get("action") == "place":
                bet_actions.append({
                    "match_id": match_data.get("match_id", "unknown"),
                    "market": ml_prediction.get("market"),
                    "action": "place",
                    "reason": "ml_prediction",
                    "confidence": ml_prediction.get("confidence", 0)
                })
        
        logger.info(f"Analysis complete: found {len(bet_actions)} bet opportunities")
        return bet_actions
    
    def analyze_real_match_data(self, match_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze real match data from API or database.
        
        Args:
            match_doc: Full match document from API or database
            
        Returns:
            List of bet actions to take
        """
        bet_actions = []
        
        try:
            # 1. Process the raw match document
            processed_data = self.match_processor.process_match_document(match_doc)
            
            # Skip if we couldn't process the data properly
            if not processed_data:
                logger.error("Failed to process match document")
                return []
                
            # Log match info
            minute = processed_data.get("minute", "Unknown")
            home_team = processed_data.get("home_team", "Home")
            away_team = processed_data.get("away_team", "Away")
            score = processed_data.get("score", "0 - 0")
            
            logger.info(f"Analyzing real match: {home_team} vs {away_team} at minute {minute} (Score: {score})")
                
            # 2. Apply specialized rules first
            specialized_actions = SpecializedRules.evaluate_all_rules(processed_data)
            if specialized_actions:
                logger.info(f"Found {len(specialized_actions)} specialized rule matches")
                bet_actions.extend(specialized_actions)
                
            # 3. Apply standard rules as fallback
            # Note: We also convert the processed data to the format expected by standard rules
            standard_format_data = self._convert_to_standard_format(processed_data)
            standard_actions = self.rule_engine.evaluate(standard_format_data)
            
            if standard_actions:
                logger.info(f"Found {len(standard_actions)} standard rule matches")
                bet_actions.extend(standard_actions)
                
            # 4. Use ML model if enabled
            if config.ENABLE_ML_MODEL and self.ml_predictor:
                ml_prediction = self.ml_predictor.predict(standard_format_data)
                if ml_prediction and ml_prediction.get("action") == "place":
                    logger.info("ML model recommends placing a bet")
                    ml_action = {
                        "match_id": processed_data.get("match_id", "unknown"),
                        "market": ml_prediction.get("market"),
                        "action": "place",
                        "reason": "ml_prediction",
                        "confidence": ml_prediction.get("confidence", 0)
                    }
                    bet_actions.append(ml_action)
        
        except Exception as e:
            logger.error(f"Error analyzing real match data: {e}")
        
        return bet_actions
    
    def _convert_to_standard_format(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert processed real match data to standard format for regular rule engine.
        
        Args:
            processed_data: Processed match data from match_processor
            
        Returns:
            Dictionary in standard format for rule engine
        """
        # Extract relevant fields and ensure they match expected format
        return {
            "match_id": processed_data.get("match_id", "unknown"),
            "minute": processed_data.get("minute", 0),
            "league": processed_data.get("league", "unknown"),
            "home_team": processed_data.get("home_team", "Home"),
            "away_team": processed_data.get("away_team", "Away"),
            "home_shots": processed_data.get("home_shots", 0),
            "away_shots": processed_data.get("away_shots", 0), 
            "possession_home": processed_data.get("possession_home", 50),
            "xg_home": processed_data.get("xg_home", 0.0),
            "xg_away": processed_data.get("xg_away", 0.0),
            "total_xg": processed_data.get("total_xg", 0.0),
            "odds": processed_data.get("odds", {})
        }
    
    def process_bet_actions(self, bet_actions: List[Dict[str, Any]]) -> None:
        """
        Process bet actions by sending them to RabbitMQ.
        
        Args:
            bet_actions: List of bet action dictionaries
        """
        for action in bet_actions:
            success = self.rabbitmq_publisher.publish_bet_signal(action)
            if success:
                logger.info(f"Successfully sent bet signal for {action['match_id']}: {action['market']}")
            else:
                logger.error(f"Failed to send bet signal for {action['match_id']}: {action['market']}")
    
    def run(self, 
            use_mock_data: bool = True, 
            match_leagues: List[str] = None,
            update_interval: float = 1.0,
            run_duration: Optional[int] = None) -> None:
        """
        Run the analyzer in a continuous loop.
        
        Args:
            use_mock_data: Whether to use mock data or real data
            match_leagues: List of leagues to analyze
            update_interval: Time in seconds between analyses
            run_duration: Optional duration in seconds to run the analyzer for
        """
        if match_leagues is None:
            match_leagues = ["premier_league"]
            
        logger.info(f"Starting Match Analyzer for leagues: {', '.join(match_leagues)}")
        
        # Create mock data generators for each league
        mock_generators = {}
        if use_mock_data:
            for league in match_leagues:
                mock_generators[league] = get_mock_match_generator(league=league)
        
        start_time = time.time()
        running = True
        
        try:
            while running:
                current_time = time.time()
                
                # Check if we should stop
                if run_duration and current_time - start_time > run_duration:
                    logger.info(f"Run duration of {run_duration}s reached, stopping")
                    break
                
                # Process each league
                for league in match_leagues:
                    # Get match data (either from mock generator or external source)
                    if use_mock_data and league in mock_generators:
                        match_data = mock_generators[league].update_match_state()
                    else:
                        if self.api_client:
                            match_data = self.api_client.get_match_data(league)
                        else:
                            logger.error("Real data source not implemented")
                            continue
                    
                    # Log match state
                    logger.info(f"Processing {league} match {match_data['match_id']} at minute {match_data['minute']}")
                    
                    # Analyze match data
                    bet_actions = self.analyze_match_data(match_data)
                    
                    # Process any bet actions
                    if bet_actions:
                        self.process_bet_actions(bet_actions)
                
                # Sleep until next update
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            logger.info("Analyzer stopped by user")
        finally:
            self._cleanup()
    
    def _cleanup(self) -> None:
        """Clean up resources when shutting down."""
        logger.info("Cleaning up resources")
        self.mongo_handler.close()
        self.rabbitmq_publisher.close()


def main() -> None:
    """Main entry point for the analyzer."""
    analyzer = MatchAnalyzer()
    analyzer.run(use_mock_data=True, update_interval=2.0)
    

if __name__ == "__main__":
    main()
