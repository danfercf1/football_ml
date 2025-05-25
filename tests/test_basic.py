"""
Basic test script for the football_ml system.
"""
import logging
import time

from src.mock_data import get_mock_match_generator
from src.mongo_handler import get_mongo_handler, insert_sample_rules
from src.rule_engine import get_rule_engine
from src.ml_predictor import get_ml_predictor, create_dummy_model
from src.rabbitmq_publisher import get_rabbitmq_publisher

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_components():
    """Test each component individually."""
    logger.info("------ Testing Individual Components ------")
    
    # 1. Test MongoDB and rules
    logger.info("Testing MongoDB connection and sample rules...")
    insert_sample_rules()
    mongo_handler = get_mongo_handler()
    rules = mongo_handler.get_rules()
    logger.info(f"Found {len(rules)} rules in MongoDB")
    mongo_handler.close()
    
    # 2. Test mock data generator
    logger.info("Testing mock data generator...")
    mock_gen = get_mock_match_generator()
    for _ in range(3):
        data = mock_gen.update_match_state()
        logger.info(f"Mock data: Minute {data['minute']}, Shots {data['home_shots']}-{data['away_shots']}")
    
    # 3. Test rule engine
    logger.info("Testing rule engine...")
    rule_engine = get_rule_engine(rules)
    test_data = {
        "match_id": "test-123",
        "minute": 75,
        "league": "premier_league",
        "home_shots": 12,
        "away_shots": 5,
        "total_xg": 2.5,
        "odds": {
            "over_2.5": 1.5,
            "under_2.5": 2.5
        }
    }
    results = rule_engine.evaluate(test_data)
    logger.info(f"Rule engine found {len(results)} matching rules")
    
    # 4. Test ML predictor
    logger.info("Testing ML predictor...")
    create_dummy_model()
    ml_predictor = get_ml_predictor()
    prediction = ml_predictor.predict(test_data)
    if prediction:
        logger.info(f"ML prediction: {prediction['action']} on {prediction['market']} "
                   f"with {prediction['confidence']:.2f} confidence")
    
    # 5. Test RabbitMQ
    logger.info("Testing RabbitMQ publisher...")
    publisher = get_rabbitmq_publisher()
    sample_bet = {
        "match_id": "test-123",
        "market": "over_2.5",
        "action": "place",
        "reason": "test"
    }
    success = publisher.publish_bet_signal(sample_bet)
    logger.info(f"RabbitMQ publish {'successful' if success else 'failed'}")
    publisher.close()


def test_integrated_flow():
    """Test the integrated system flow for a single match state."""
    logger.info("\n------ Testing Integrated Flow ------")
    
    # Set up components
    mongo_handler = get_mongo_handler()
    rules = mongo_handler.get_rules()
    rule_engine = get_rule_engine(rules)
    create_dummy_model()
    ml_predictor = get_ml_predictor()
    publisher = get_rabbitmq_publisher()
    
    # Generate mock match data
    mock_gen = get_mock_match_generator()
    # Fast forward to minute 70
    for _ in range(70):
        mock_gen.update_match_state()
    match_data = mock_gen.update_match_state()
    
    logger.info(f"Analyzing match {match_data['match_id']} at minute {match_data['minute']}")
    logger.info(f"Match stats: Shots {match_data['home_shots']}-{match_data['away_shots']}, "
               f"xG {match_data['xg_home']:.2f}-{match_data['xg_away']:.2f}")
    
    # 1. Rule-based analysis
    rule_results = rule_engine.evaluate(match_data)
    logger.info(f"Rule engine found {len(rule_results)} bet opportunities")
    for result in rule_results:
        logger.info(f"Rule suggests: {result['market']} - {result['reason']}")
        publisher.publish_bet_signal(result)
    
    # 2. ML-based analysis
    ml_result = ml_predictor.predict(match_data)
    if ml_result and ml_result.get('action') == 'place':
        logger.info(f"ML model suggests: {ml_result['market']} with {ml_result['confidence']:.2f} confidence")
        publisher.publish_bet_signal({
            "match_id": match_data['match_id'],
            "market": ml_result['market'],
            "action": ml_result['action'],
            "confidence": ml_result['confidence'],
            "reason": "ml_prediction"
        })
    else:
        logger.info("ML model does not suggest placing a bet")
    
    # Clean up
    mongo_handler.close()
    publisher.close()


if __name__ == "__main__":
    # Test individual components
    test_components()
    
    # Give a little time for RabbitMQ operations to complete
    time.sleep(1)
    
    # Test integrated flow
    test_integrated_flow()
    
    logger.info("\nAll tests complete. Run 'python -m src.analyzer' to start the full system.")
