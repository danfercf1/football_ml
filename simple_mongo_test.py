#!/usr/bin/env python3
import pymongo
import socket

def check_mongodb_port():
    """Check if MongoDB port is open"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(("127.0.0.1", 27018))
        print("✅ MongoDB port 27018 is OPEN.")
        s.close()
        return True
    except (socket.timeout, socket.error) as e:
        print(f"❌ MongoDB port 27018 is CLOSED: {e}")
        s.close()
        return False

def try_mongo_connection(uri):
    """Try connecting to MongoDB with the given URI"""
    print(f"\nTrying to connect with URI: {uri}")
    try:
        # Try to connect with a timeout
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        
        # Force a connection check
        server_info = client.server_info()
        print(f"✅ Connection successful! Server info: {server_info}")
        
        # Try to list databases
        try:
            dbs = client.list_database_names()
            print(f"Available databases: {dbs}")
        except Exception as e:
            print(f"Could not list databases: {e}")
            
        client.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("MONGODB SIMPLE CONNECTION TEST")
    print("=============================")
    
    # Check if port is open
    if not check_mongodb_port():
        print("Cannot proceed - MongoDB server is not accessible")
        exit(1)
    
    # Try different connection strings
    uris = [
        "mongodb://127.0.0.1:27018/",
        "mongodb://daniel:daniel@127.0.0.1:27018/",
        "mongodb://127.0.0.1:27018/footystats_ev"
    ]
    
    success = False
    for uri in uris:
        if try_mongo_connection(uri):
            success = True
    
    if success:
        print("\n✅ At least one MongoDB connection was successful")
    else:
        print("\n❌ All MongoDB connection attempts failed")
