import os
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId

# Load environment variables from .env file
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

def get_db_connection():
    """
    Creates and returns a MongoDB connection.
    
    Returns:
        MongoClient: MongoDB client connection
    """
    try:
        client = MongoClient(MONGO_URI)
        # Test connection with ping
        client.admin.command('ping')
        print("Connected to MongoDB successfully")
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        raise

def get_game_data(game_id):
    """
    Fetches a specific game by ID.
    
    Args:
        game_id (str): MongoDB ObjectId as string
        
    Returns:
        dict: Game document or None if not found
    """
    client = None
    try:
        client = get_db_connection()
        db = client.get_default_database()
        matches_collection = db['underxmatches']
        
        game_data = matches_collection.find_one({"_id": ObjectId(game_id)})
        if game_data:
            print(f"Found game: {game_data.get('match', 'N/A')}")
        else:
            print(f"No game found with ID: {game_id}")
        
        return game_data
        
    except Exception as e:
        print(f"Error fetching game data: {e}")
        raise
    finally:
        if client:
            client.close()

def get_historical_games(game_data, max_games=100, relevance_threshold=None):
    """
    Fetches historical games relevant to the specified game with enhanced filtering.
    
    Args:
        game_data (dict): Target game document containing league, country, teams
        max_games (int): Maximum number of historical games to retrieve
        relevance_threshold (float, optional): Minimum relevance score to include a game
        
    Returns:
        list: List of historical game documents
    """
    client = None
    try:
        # Extract game details
        game_id = game_data['_id']
        league = game_data.get('league')
        country = game_data.get('country')
        home_team = game_data.get('homeTeam')
        away_team = game_data.get('awayTeam')
        
        # Print available fields for debugging
        print(f"Target game fields: {list(game_data.keys())}")
        print(f"Game info: {league}, {country}, {home_team} vs {away_team}")
        
        missing_fields = []
        if not league: missing_fields.append("league")
        if not country: missing_fields.append("country")
        if not home_team: missing_fields.append("homeTeam")
        if not away_team: missing_fields.append("awayTeam")
        
        if missing_fields:
            print(f"WARNING: Missing fields in game data: {', '.join(missing_fields)}")
            # Try alternative field names if possible
            if not home_team and "teams" in game_data:
                home_team = game_data.get("teams", {}).get("home")
                print(f"Found alternative homeTeam: {home_team}")
            if not away_team and "teams" in game_data:
                away_team = game_data.get("teams", {}).get("away")
                print(f"Found alternative awayTeam: {away_team}")
        
        if not all([league, country, home_team, away_team]):
            print("Missing required game details for historical data query")
            # Fall back to just a basic query excluding the current game
            client = get_db_connection()
            db = client.get_default_database()
            matches_collection = db['underxmatches']
            
            # Basic query - just get some completed games with success field
            fallback_query = {
                "_id": {"$ne": ObjectId(game_id)},
                "success": {"$exists": True}
            }
            print("Using fallback query to get some historical data")
            cursor = matches_collection.find(fallback_query).sort("date", -1).limit(max_games)
            fallback_results = list(cursor)
            print(f"Fetched {len(fallback_results)} documents using fallback query")
            return fallback_results
        
        client = get_db_connection()
        db = client.get_default_database()
        matches_collection = db['underxmatches']
        
        # Build enhanced query for historical games
        base_query = {
            "_id": {"$ne": ObjectId(game_id)},
            "success": {"$exists": True}
        }
        
        # Create multiple specialized queries for different types of relevant matches
        queries = [
            # 1. Same league AND country - highest relevance
            {**base_query, "league": league, "country": country},
            
            # 2. Home team historical matches
            {**base_query, "$or": [{"homeTeam": home_team}, {"awayTeam": home_team}]},
            
            # 3. Away team historical matches
            {**base_query, "$or": [{"homeTeam": away_team}, {"awayTeam": away_team}]}
        ]
        
        # Try to use prediction stats if available
        if 'predictionStats' in game_data:
            pred_stats = game_data.get('predictionStats', {})
            
            # Find games with similar prediction characteristics
            if 'avgTotalGoals' in pred_stats:
                avg_goals = float(pred_stats.get('avgTotalGoals', 0))
                # Add query for games with similar expected goals
                goal_range_query = {
                    **base_query,
                    "predictionStats.avgTotalGoals": {"$gte": avg_goals - 0.5, "$lte": avg_goals + 0.5}
                }
                queries.append(goal_range_query)
                
            # Find games with similar corner predictions
            if 'avgCorners' in pred_stats:
                avg_corners = float(pred_stats.get('avgCorners', 0))
                corner_range_query = {
                    **base_query,
                    "predictionStats.avgCorners": {"$gte": avg_corners - 2, "$lte": avg_corners + 2}
                }
                queries.append(corner_range_query)
        
        # Add livescore-based queries if game is in progress
        if 'livescore' in game_data and game_data.get('livescore', {}).get('isLive'):
            live_stats = game_data.get('livescore', {})
            current_minute = live_stats.get('minute')
            
            if current_minute and str(current_minute).isdigit() and int(current_minute) > 0:
                # Find completed games with similar stats at this stage
                # This is approximate as we don't store minute-by-minute stats historically
                if 'stats' in live_stats:
                    stats = live_stats.get('stats', {})
                    
                    # Query for games with similar shot patterns
                    if 'Shots Total' in stats:
                        shots_home = int(stats['Shots Total'].get('home', 0))
                        shots_away = int(stats['Shots Total'].get('away', 0))
                        
                        shots_query = {
                            **base_query,
                            "$expr": {
                                "$and": [
                                    {"$gte": ["$livescore.stats.Shots Total.home", shots_home * 0.7]},
                                    {"$lte": ["$livescore.stats.Shots Total.home", shots_home * 1.3]},
                                    {"$gte": ["$livescore.stats.Shots Total.away", shots_away * 0.7]},
                                    {"$lte": ["$livescore.stats.Shots Total.away", shots_away * 1.3]},
                                ]
                            }
                        }
                        queries.append(shots_query)
        
        # Execute all queries and merge results, prioritizing by relevance
        all_results = []
        seen_ids = set()
        
        # Track the source of each query for debugging
        query_results = {}
        
        for idx, query in enumerate(queries):
            query_name = f"query_{idx}"
            if idx == 0: query_name = "league_country"
            elif idx == 1: query_name = "home_team"
            elif idx == 2: query_name = "away_team"
            
            cursor = matches_collection.find(query).sort("date", -1).limit(max_games)
            query_count = 0
            
            for doc in cursor:
                # Skip duplicates we've already seen from other queries
                if str(doc["_id"]) not in seen_ids:
                    seen_ids.add(str(doc["_id"]))
                    all_results.append(doc)
                    query_count += 1
                    
                # Stop if we've reached the maximum
                if len(all_results) >= max_games:
                    break
                    
            query_results[query_name] = query_count
            
            if len(all_results) >= max_games:
                break
                
        print(f"Fetched {len(all_results)} relevant historical documents using enhanced criteria")
        print(f"Query results breakdown: {query_results}")
        
        # Analyze historical data
        success_values = {}
        for doc in all_results:
            success_val = doc.get('success')
            if success_val not in success_values:
                success_values[success_val] = 0
            success_values[success_val] += 1
            
        print(f"Success values distribution: {success_values}")
        
        return all_results
        
    except Exception as e:
        print(f"Error fetching historical games: {e}")
        traceback.print_exc()
        return []
    finally:
        if client:
            client.close()
