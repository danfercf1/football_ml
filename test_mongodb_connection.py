#!/usr/bin/env python3
"""
Script to test MongoDB connection.
"""
import os
import sys
import pymongo
import logging
import socket
import time
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
# Add the project root to the Python path
sys.path.insert(0, project_root)

def check_port_open(host, port, timeout=3):
    """Check if a TCP port is open."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except (socket.timeout, socket.error):
        return False
    finally:
        s.close()

def test_mongodb_connection():
    """Test the connection to MongoDB."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get MongoDB connection settings
    mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27018/")
    mongo_db = os.getenv("MONGO_DB", "footystats_ev")
    mongo_rules_collection = os.getenv("MONGO_RULES_COLLECTION", "bettingrules")
    
    # Extract host and port from URI for connection check
    try:
        # Basic parsing of the URI
        uri_parts = mongo_uri.split("://")[1].split("@")
        if len(uri_parts) > 1:
            host_port = uri_parts[1].split("/")[0]
        else:
            host_port = uri_parts[0].split("/")[0]
        
        host = host_port.split(":")[0]
        port = int(host_port.split(":")[1])
        
        # Check if MongoDB server is reachable
        if not check_port_open(host, port):
            logger.error(f"Cannot connect to MongoDB server at {host}:{port}. Server might be down or unreachable.")
            return False
    except Exception as e:
        logger.warning(f"Could not parse host/port from URI: {e}")
    
    logger.info(f"Testing MongoDB connection with URI: {mongo_uri}")
    logger.info(f"Database: {mongo_db}")
    logger.info(f"Collection: {mongo_rules_collection}")
    
    # Fix any escaping issues in the URI
    mongo_uri = mongo_uri.replace("\\x3a", ":").replace("\\x2f", "/")
    
    try:
        # Try to connect with a timeout of 5 seconds
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Check the connection by requesting server info
        logger.info("Connecting to MongoDB server...")
        server_info = client.server_info()
        logger.info(f"Connection successful! Server version: {server_info.get('version', 'unknown')}")
        
        # Check if database and collection exist
        logger.info(f"Checking database '{mongo_db}'...")
        db_list = client.list_database_names()
        if mongo_db in db_list:
            logger.info(f"Database '{mongo_db}' exists.")
        else:
            logger.warning(f"Database '{mongo_db}' does not exist yet. It will be created when data is inserted.")
        
        # Access the database
        db = client[mongo_db]
        
        # Check if collection exists
        logger.info(f"Checking collection '{mongo_rules_collection}'...")
        collection_list = db.list_collection_names()
        if mongo_rules_collection in collection_list:
            logger.info(f"Collection '{mongo_rules_collection}' exists.")
            # Count documents in the collection
            count = db[mongo_rules_collection].count_documents({})
            logger.info(f"Collection contains {count} documents.")
        else:
            logger.warning(f"Collection '{mongo_rules_collection}' does not exist yet. It will be created when data is inserted.")
        
        # Try to insert a test document
        logger.info("Attempting to insert a test document...")
        test_collection = db["test_connection"]
        result = test_collection.insert_one({"test": "connection", "timestamp": pymongo.datetime.datetime.utcnow()})
        if result.acknowledged:
            logger.info(f"Test document inserted with ID: {result.inserted_id}")
            # Clean up - delete the test document
            test_collection.delete_one({"_id": result.inserted_id})
            logger.info("Test document deleted.")
        
        return True
    except pymongo.errors.ServerSelectionTimeoutError as e:
        logger.error(f"MongoDB server selection timeout error: {e}")
        logger.error("Check if the MongoDB server is running and accessible.")
        return False
    except pymongo.errors.ConnectionFailure as e:
        logger.error(f"MongoDB connection failure: {e}")
        logger.error("Check your MongoDB URI and network configuration.")
        return False
    except pymongo.errors.OperationFailure as e:
        logger.error(f"MongoDB operation failure: {e}")
        if "Authentication failed" in str(e):
            logger.error("Authentication failed. Check your username and password.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error when connecting to MongoDB: {e}")
        return False
    finally:
        # Close the connection if it was established
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    print("MongoDB Connection Test")
    print("======================")
    
    # First check if MongoDB server is running at all
    print("\nChecking if MongoDB server is running...")
    if check_port_open("127.0.0.1", 27018):
        print("✅ MongoDB server is reachable on port 27018")
    else:
        print("❌ MongoDB server is NOT reachable on port 27018")
        print("Make sure the MongoDB server is running and accessible.")
        sys.exit(1)
        
    connection_results = []
    
    # Test various connection options
    uri_options = [
        # Try connecting with different authentication options
        ("original credentials (daniel:daniel)", "mongodb://daniel:daniel@127.0.0.1:27018/"),
        ("URI from betfair config", "mongodb://daniel:daniel@127.0.0.1:27018/footystats_ev"),
        ("admin credentials", "mongodb://admin:admin@127.0.0.1:27018/admin"),
        ("root credentials", "mongodb://root:root@127.0.0.1:27018/admin"),
        ("without authentication", "mongodb://127.0.0.1:27018/")
    ]
    
    for description, uri in uri_options:
        print(f"\nTesting with {description}...")
        os.environ["MONGO_URI"] = uri
        result = test_mongodb_connection()
        connection_results.append(result)
        # Wait a bit between attempts
        time.sleep(1)
    
    if any(connection_results):
        print("\n✅ At least one MongoDB connection test completed successfully!")
    else:
        print("\n❌ All MongoDB connection attempts failed!")
        print("\nPossible solutions:")
        print("1. Check that MongoDB is properly installed and running")
        print("2. Verify MongoDB authentication mechanism")
        print("3. Create a user with appropriate credentials")
        print("4. Try connecting with a MongoDB client tool to troubleshoot")
