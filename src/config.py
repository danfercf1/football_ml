"""
Configuration settings for the football_ml project.
Loads environment variables from .env file.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB_PORT = int(os.getenv('MONGO_DB_PORT', 27017))
MONGO_DB = os.getenv('MONGO_DB', 'football_analysis')
MONGO_RULES_COLLECTION = os.getenv('MONGO_RULES_COLLECTION', 'rules')
MONGO_DB_USERNAME = os.getenv('MONGO_DB_USERNAME', '')
MONGO_DB_PASSWORD = os.getenv('MONGO_DB_PASSWORD', '')

# RabbitMQ Configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE', 'bet_signals')
RABBITMQ_STATS_QUEUE = os.getenv('RABBITMQ_STATS_QUEUE', 'footystats_queue')
RABBITMQ_URL_QUEUE = os.getenv('RABBITMQ_URL_QUEUE', 'footystats_url_queue')

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', 6379)
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
REDIS_DB = os.getenv('REDIS_DB', 0)
REDIS_TTL = os.getenv('REDIS_TTL', 120)
LIVE_GAMES_KEY = os.getenv('LIVE_GAMES_KEY', 'live_games')

# ML Model Configuration
ML_MODEL_PATH = os.getenv('ML_MODEL_PATH', 'models/betting_model.pkl')

# Feature Flags
ENABLE_ML_MODEL = os.getenv('ENABLE_ML_MODEL', 'true').lower() == 'true'
ENABLE_RULE_ENGINE = os.getenv('ENABLE_RULE_ENGINE', 'true').lower() == 'true'
ENABLE_CHANGE_STREAMS = os.getenv('ENABLE_CHANGE_STREAMS', 'false').lower() == 'true'

# Testing Configuration
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
TEST_BET_AMOUNT = float(os.getenv('TEST_BET_AMOUNT', 0.5))
NO_RULES_MODE = os.getenv('NO_RULES_MODE', 'false').lower() == 'true'
MAX_STAKE_LIMIT = float(os.getenv('MAX_STAKE_LIMIT', 20))
