"""
Extended test script that includes testing the real match data analysis.
"""
import json
import logging
import os
import sys
import time

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.mock_data import get_mock_match_generator
from src.mongo_handler import get_mongo_handler, insert_sample_rules
from src.rule_engine import get_rule_engine
from src.ml_predictor import get_ml_predictor, create_dummy_model
from src.rabbitmq_publisher import get_rabbitmq_publisher
from src.match_processor import get_match_processor
from src.specialized_rules import SpecializedRules

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_real_match_data():
    """Test the system with real match data."""
    logger.info("\n------ Testing Real Match Data Analysis ------")
    
    # 1. Load the sample match data
    match_file = os.path.join(project_root, 'data', 'fluminense_match.json')
    try:
        with open(match_file, 'r') as f:
            match_doc = json.load(f)
        logger.info(f"Loaded match data: {match_doc.get('homeTeam', 'Unknown')} vs {match_doc.get('awayTeam', 'Unknown')}")
    except Exception as e:
        logger.error(f"Error loading match data: {e}")
        return

    # 2. Process the match data
    processor = get_match_processor()
    match_data = processor.process_match_document(match_doc)
    logger.info(f"Processed match data for {match_data.get('home_team')} vs {match_data.get('away_team')}")
    
    # 3. Apply specialized rules
    specialized_results = SpecializedRules.evaluate_all_rules(match_data)
    logger.info(f"Specialized rules found {len(specialized_results)} bet opportunities")
    for result in specialized_results:
        logger.info(f"Rule suggests: {result['market']} - {result['reason']} (confidence: {result.get('confidence', 'N/A')})")
    
    # 4. Send to RabbitMQ if any opportunities found
    if specialized_results:
        publisher = get_rabbitmq_publisher()
        for result in specialized_results:
            publisher.publish_bet_signal(result)
        publisher.close()
        logger.info(f"Sent {len(specialized_results)} bet signals to RabbitMQ")


def test_standard_and_real_data():
    """Run both standard tests and real match data test."""
    # First run the standard tests
    from tests.test_basic import test_components, test_integrated_flow
    
    # Test individual components
    test_components()
    
    # Give a little time for RabbitMQ operations to complete
    time.sleep(1)
    
    # Test integrated flow
    test_integrated_flow()
    
    # Now test with real match data
    time.sleep(1)
    test_real_match_data()
    
    logger.info("\nAll tests complete. Run './test_match_analysis.sh' to test the real match analysis.")


if __name__ == "__main__":
    # Run all tests
    test_standard_and_real_data()
