import os
from flask import Flask, request, jsonify, send_file
from bson import ObjectId, json_util
from celery_worker import celery_app
from celery_worker import analyze_game_task
from celery.result import AsyncResult
from db_connector import get_db_connection
# import json
import tempfile
import traceback
import logging
import time
from werkzeug.exceptions import HTTPException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- Flask App Setup ---
app = Flask(__name__)

# Error handling for all exceptions
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    traceback.print_exc()
    
    if isinstance(e, HTTPException):
        return jsonify({"error": str(e), "status": "error"}), e.code
        
    # Return a generic 500 error for any other exception
    return jsonify({
        "error": "An internal server error occurred",
        "details": str(e),
        "status": "error"
    }), 500

# Dictionary to store task IDs mapped to game IDs for quicker lookups (optional)
# In production, use Redis or a database for this
task_registry = {}

# Use REDIS_URL from environment variables if available
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
print(f"[api] REDIS_URL = {redis_url}")  # <-- Add this line

@app.route('/analyze/<string:game_id>', methods=['GET'])
def analyze_game_endpoint(game_id):
    """
    API endpoint to trigger game analysis.
    Starts a background task and returns immediately with a task ID.
    """
    start_time = time.time()
    logger.info(f"API received request for game_id: {game_id}")
    
    try:
        # Validate ObjectId format
        try:
            ObjectId(game_id)
        except Exception as e:
            logger.error(f"Invalid game ID format: {game_id}, Error: {e}")
            return jsonify({
                "error": f"Invalid game ID format: {game_id}",
                "status": "failed"
            }), 400
        
        # Parameter for forcing synchronous execution (for testing or small datasets)
        sync_mode = request.args.get('sync', '').lower() == 'true'
        
        if sync_mode:
            # Synchronous mode - blocks until complete (useful for testing)
            try:
                logger.info(f"Running analysis SYNCHRONOUSLY for game_id: {game_id}")
                
                # Import locally to avoid circular imports
                from main import analyze_game
                
                # Set a timeout for synchronous requests to avoid empty responses
                start_sync_time = time.time()
                
                # Add more detailed logging
                try:
                    # Verify game exists in database first
                    client = get_db_connection()
                    db = client.get_default_database()
                    collection = db['underxmatches']
                    
                    game_doc = collection.find_one({"_id": ObjectId(game_id)})
                    if not game_doc:
                        client.close()
                        logger.error(f"Game not found: {game_id}")
                        return jsonify({
                            "error": f"Game not found with ID: {game_id}",
                            "game_id": game_id,
                            "status": "failed"
                        }), 404
                    
                    client.close()
                    logger.info(f"Found game in database: {game_doc.get('match', 'Unknown match')}")
                except Exception as db_error:
                    logger.error(f"Database error when checking game: {db_error}")
                    # Continue with analysis anyway
                
                # Execute analysis with improved error handling
                try:
                    logger.info(f"Starting analyze_game function call for {game_id}")
                    result = analyze_game(game_id)
                    logger.info(f"analyze_game function completed for {game_id}")
                except Exception as analyze_error:
                    logger.error(f"Error in analyze_game function: {analyze_error}")
                    traceback.print_exc()
                    return jsonify({
                        "error": f"Analysis function error: {str(analyze_error)}",
                        "game_id": game_id,
                        "status": "failed",
                        "traceback": traceback.format_exc()
                    }), 500
                
                elapsed = time.time() - start_sync_time
                logger.info(f"Synchronous analysis completed in {elapsed:.2f}s")
                
                # Handle None result
                if result is None:
                    logger.error("analyze_game returned None")
                    return jsonify({
                        "error": "Analysis returned None",
                        "game_id": game_id,
                        "status": "failed",
                        "analysis_time_seconds": elapsed
                    }), 500
                
                # Add analysis time to response
                if isinstance(result, dict):
                    result["analysis_time_seconds"] = elapsed
                    result["game_id"] = game_id
                else:
                    logger.warning(f"analyze_game returned non-dict result: {type(result)}")
                    # Convert non-dict result to dict
                    result = {
                        "result": result,
                        "analysis_time_seconds": elapsed,
                        "game_id": game_id
                    }
                
                logger.info(f"Returning successful synchronous response for {game_id}")
                return jsonify(result), 200
                
            except Exception as e:
                logger.error(f"Error in synchronous analysis: {e}")
                traceback.print_exc()
                return jsonify({
                    "error": f"Analysis error: {str(e)}",
                    "game_id": game_id,
                    "status": "failed",
                    "traceback": traceback.format_exc()
                }), 500
        else:
            # Asynchronous mode - returns immediately, processing happens in background
            try:
                # Check if Celery worker is running
                try:
                    i = celery_app.control.inspect()
                    if not i.ping():
                        logger.warning("No Celery workers appear to be online!")
                except Exception as worker_error:
                    logger.warning(f"Couldn't check for Celery workers: {worker_error}")
                
                # Create task with explicit timeout
                task = analyze_game_task.apply_async(args=[game_id], expires=3600)  # 1 hour expiry
                task_id = task.id
                
                # Store the mapping for easier lookups
                task_registry[task_id] = game_id
                
                logger.info(f"Asynchronous task started with ID: {task_id}")
                return jsonify({
                    "message": "Analysis started in background",
                    "task_id": task_id,
                    "game_id": game_id,
                    "status": "pending",
                    "result_endpoint": f"/results/{task_id}"
                }), 202  # 202 Accepted indicates processing started but not complete
            except Exception as e:
                logger.error(f"Error starting task: {e}")
                traceback.print_exc()
                return jsonify({
                    "error": f"Failed to start analysis: {str(e)}",
                    "game_id": game_id,
                    "status": "failed"
                }), 500

    except Exception as e:
        logger.error(f"Unexpected error in analyze endpoint: {e}")
        traceback.print_exc()
        return jsonify({
            "error": f"Server error: {str(e)}",
            "status": "error"
        }), 500

@app.route('/results/<string:task_id>', methods=['GET'])
def check_results(task_id):
    """
    Check the status or retrieve results of a background analysis task.
    """
    try:
        # First check if we have this task ID in our registry
        task_game_id = task_registry.get(task_id)
        
        # Try to get the result from Celery
        try:
            task_result = AsyncResult(task_id, app=celery_app)
            # Remove this misleading log:
            # logger.info(f"task_result: {task_result}")

            backend_type = type(task_result.backend).__name__
            if backend_type == 'DisabledBackend':
                # ...existing DisabledBackend handling...
                response = {
                    "task_id": task_id,
                    "status": "configuration_error",
                    "message": "Celery result backend is disabled. Please configure a result backend.",
                    "error": "DisabledBackend detected"
                }
                if task_game_id:
                    response["game_id"] = task_game_id
                    # Try to get game status directly from database as fallback
                    try:
                        client = get_db_connection()
                        db = client.get_default_database()
                        collection = db['underxmatches']
                        game = collection.find_one({"_id": ObjectId(task_game_id)})
                        if game:
                            response["game_found"] = True
                            response["game_match"] = game.get("match", "Unknown match")
                            if 'success' in game:
                                response["game_success"] = game['success']
                                response["message"] += f" Game found with success={game['success']}"
                        client.close()
                    except Exception as db_error:
                        logger.error(f"Error retrieving game info as fallback: {db_error}")
                return jsonify(response), 200

            # --- FIX: Log the actual result value for debugging ---
            result_value = None
            if task_result.ready():
                try:
                    result_value = task_result.get(timeout=3)
                    logger.info(f"task_result value for {task_id}: {result_value}")
                except Exception as result_error:
                    logger.error(f"Error retrieving result for task {task_id}: {result_error}")
                    result_value = None

            # ...existing code for normal backend...
            try:
                if task_result.state == 'PENDING':
                    response = {
                        "task_id": task_id,
                        "status": "pending",
                        "message": "Task is pending execution"
                    }
                elif task_result.state == 'STARTED':
                    response = {
                        "task_id": task_id,
                        "status": "processing",
                        "message": "Analysis is in progress"
                    }
                elif task_result.state == 'SUCCESS':
                    response = {
                        "task_id": task_id,
                        "status": "completed",
                        "result": result_value
                    }
                elif task_result.state == 'FAILURE':
                    response = {
                        "task_id": task_id,
                        "status": "failed",
                        "message": str(task_result.info) if task_result.info else "Task failed"
                    }
                else:
                    response = {
                        "task_id": task_id,
                        "status": task_result.state.lower(),
                        "message": str(task_result.info) if task_result.info else f"Task in {task_result.state} state"
                    }
            except AttributeError as attr_error:
                if 'DisabledBackend' in str(attr_error):
                    logger.error(f"DisabledBackend detected: {attr_error}")
                    response = {
                        "task_id": task_id,
                        "status": "configuration_error",
                        "message": "Celery result backend is disabled. Please configure a result backend.",
                        "error_details": str(attr_error)
                    }
                else:
                    raise

        except AttributeError as attr_error:
            logger.error(f"Celery backend configuration error: {attr_error}")
            response = {
                "task_id": task_id,
                "status": "configuration_error",
                "message": "Celery result backend is not configured correctly",
                "error_details": str(attr_error)
            }
        except Exception as celery_error:
            logger.error(f"Celery error checking task {task_id}: {celery_error}")
            response = {
                "task_id": task_id,
                "status": "error",
                "message": f"Error checking task: {str(celery_error)}"
            }
        
        if task_game_id:
            response["game_id"] = task_game_id
            
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error checking results: {e}")
        traceback.print_exc()
        return jsonify({
            "task_id": task_id,
            "status": "error",
            "error": str(e)
        }), 500

# Add a more explicit Celery configuration endpoint
@app.route('/system/celery-info', methods=['GET'])
def celery_info():
    """Get detailed information about Celery configuration"""
    try:
        # Try to import celery_worker and inspect its configuration
        try:
            from celery_worker import celery_app
            
            # Basic configuration check
            config = {
                "broker_url": celery_app.conf.get('broker_url', 'Not configured'),
                "result_backend": celery_app.conf.get('result_backend', 'Not configured'),
                "backend_type": type(celery_app.backend).__name__,
                "backend_dir": str(dir(celery_app.backend))
            }
            
            # Check for DisabledBackend
            if config["backend_type"] == 'DisabledBackend':
                config["status"] = "WARNING: DisabledBackend detected!"
                config["recommendation"] = (
                    "You need to configure a result backend in celery_worker.py. "
                    "For example: celery_app.conf.result_backend = 'redis://localhost:6379/0'"
                )
            else:
                config["status"] = "Backend configured correctly"
                
            return jsonify({
                "status": "ok",
                "celery_config": config
            })
            
        except ImportError:
            return jsonify({
                "status": "error",
                "message": "Could not import celery_worker module",
                "recommendation": "Make sure celery_worker.py exists and is properly configured"
            }), 500
            
    except Exception as e:
        logger.error(f"Error retrieving Celery configuration: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

# Add diagnostic endpoint for Celery configuration
@app.route('/system/celery-status', methods=['GET'])
def celery_status():
    """Check Celery configuration and connectivity"""
    try:
        from celery_worker import celery_app
        
        # Basic information about Celery configuration
        config = {
            "broker_url": celery_app.conf.get('broker_url', 'Not configured'),
            "result_backend": celery_app.conf.get('result_backend', 'Not configured'),
            "backend_type": type(celery_app.backend).__name__
        }
        
        # Check Redis connectivity if using Redis
        redis_ok = False
        redis_error = None
        if 'redis' in str(config['result_backend']).lower():
            try:
                import redis
                redis_url = config['result_backend'].replace('redis://', '')
                r = redis.from_url(f"redis://{redis_url}")
                redis_ok = r.ping()
            except Exception as e:
                redis_error = str(e)
                
            config["redis_connectivity"] = {
                "ok": redis_ok,
                "error": redis_error
            }
        
        # Check for registered tasks
        try:
            config["registered_tasks"] = list(celery_app.tasks.keys())
        except:
            config["registered_tasks"] = ["Error retrieving registered tasks"]
        
        # Check for active workers
        try:
            i = celery_app.control.inspect()
            ping_result = i.ping() or {}
            config["active_workers"] = list(ping_result.keys()) if ping_result else []
        except Exception as e:
            config["active_workers_error"] = str(e)
        
        return jsonify({
            "status": "ok",
            "celery_config": config
        })
    except Exception as e:
        logger.error(f"Error checking Celery status: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# --- Historical Data Endpoints ---
@app.route('/historical/import', methods=['POST'])
def import_historical_data():
    """
    Endpoint to import historical match data from JSON
    Accepts JSON data in the request body
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415
    
    try:
        data = request.get_json()
        client = get_db_connection()
        db = client.get_default_database()
        collection = db['underxmatches']
        
        # For single document
        if isinstance(data, dict):
            # Remove _id if present to avoid conflicts
            if '_id' in data:
                del data['_id']
            result = collection.insert_one(data)
            client.close()
            return jsonify({
                "message": "Successfully imported 1 document",
                "inserted_id": str(result.inserted_id)
            }), 201
        
        # For multiple documents
        elif isinstance(data, list):
            # Remove _id keys if present
            for doc in data:
                if '_id' in doc:
                    del doc['_id']
            
            result = collection.insert_many(data)
            client.close()
            return jsonify({
                "message": f"Successfully imported {len(result.inserted_ids)} documents",
                "inserted_count": len(result.inserted_ids)
            }), 201
        
        else:
            client.close()
            return jsonify({"error": "Invalid JSON format. Expected object or array."}), 400
    
    except Exception as e:
        if 'client' in locals() and client:
            client.close()
        return jsonify({"error": f"Import failed: {str(e)}"}), 500

@app.route('/historical/export', methods=['GET'])
def export_historical_data():
    """
    Endpoint to export historical match data to JSON
    Optional query parameters:
    - league: Filter by league name
    - country: Filter by country name
    - team: Filter by team name (matches either home or away team)
    - limit: Maximum number of documents to export (default: 100)
    """
    try:
        # Parse query parameters
        league = request.args.get('league')
        country = request.args.get('country')
        team = request.args.get('team')
        limit = int(request.args.get('limit', 100))
        
        # Build query
        query = {}
        if league:
            query['league'] = league
        if country:
            query['country'] = country
        if team:
            query['$or'] = [{'homeTeam': team}, {'awayTeam': team}]
            
        # Execute query
        client = get_db_connection()
        db = client.get_default_database()
        collection = db['underxmatches']
        cursor = collection.find(query).limit(limit)
        data = list(cursor)
        client.close()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp:
            temp.write(json_util.dumps(data, indent=2).encode('utf-8'))
        
        # Return the file for download
        return send_file(
            temp.name,
            as_attachment=True,
            download_name=f"historical_matches_{limit}.json",
            mimetype='application/json'
        )
        
    except Exception as e:
        if 'client' in locals() and client:
            client.close()
        return jsonify({"error": f"Export failed: {str(e)}"}), 500

@app.route('/historical/count', methods=['GET'])
def count_historical_data():
    """
    Endpoint to count historical match data
    Optional query parameters for filtering
    """
    try:
        # Parse query parameters (same as export)
        league = request.args.get('league')
        country = request.args.get('country')
        team = request.args.get('team')
        
        # Build query
        query = {}
        if league:
            query['league'] = league
        if country:
            query['country'] = country
        if team:
            query['$or'] = [{'homeTeam': team}, {'awayTeam': team}]
            
        # Count matching documents
        client = get_db_connection()
        db = client.get_default_database()
        collection = db['underxmatches']
        count = collection.count_documents(query)
        client.close()
        
        return jsonify({
            "count": count,
            "query": query
        }), 200
        
    except Exception as e:
        if 'client' in locals() and client:
            client.close()
        return jsonify({"error": f"Count failed: {str(e)}"}), 500

# Add a new endpoint specifically for finding Under X System matches
@app.route('/under-x-matches', methods=['GET'])
def find_under_x_matches():
    """
    Finds matches that meet the Under X In-Play System criteria:
    - In-play between minutes 52-61
    - 1-3 goals already scored
    - Teams with low goal average (optional)
    - Low shots on target (additional safety filter)
    """
    try:
        client = get_db_connection()
        db = client.get_default_database()
        collection = db['underxmatches']
        
        # Find live matches that might qualify
        live_matches_query = {
            "$or": [
                {"status": {"$in": ["in-progress", "live", "playing"]}},
                {"livescore.isLive": True}
            ]
        }
        
        live_matches = list(collection.find(live_matches_query))
        logger.info(f"Found {len(live_matches)} potential live matches")
        
        # Filter for matches that meet the Under X criteria
        under_x_matches = []
        
        for match in live_matches:
            # Get minute
            current_minute = None
            if 'livescore' in match and isinstance(match['livescore'], dict):
                minute_str = match['livescore'].get('minute')
                if minute_str and isinstance(minute_str, str) and minute_str.isdigit():
                    current_minute = int(minute_str)
            elif 'liveStats' in match and isinstance(match['liveStats'], dict):
                current_minute = match['liveStats'].get('currentMinute')
                
            # Get current goals
            current_goals = None
            if 'livescore' in match and isinstance(match['livescore'], dict) and 'score' in match['livescore']:
                try:
                    score = match['livescore']['score']
                    if isinstance(score, str) and ' - ' in score:
                        parts = score.split(' - ')
                        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                            current_goals = int(parts[0]) + int(parts[1])
                except:
                    pass
            
            # Get shots on target data - NEW ANALYSIS
            shots_on_target = {
                'home': 0,
                'away': 0,
                'total': 0
            }
            shots_total = {
                'home': 0,
                'away': 0,
                'total': 0
            }
            
            # Extract shots data from livescore
            if 'livescore' in match and isinstance(match['livescore'], dict) and 'stats' in match['livescore']:
                stats = match['livescore']['stats']
                
                if isinstance(stats, dict):
                    # Get shots on target
                    if 'Shots On Target' in stats and isinstance(stats['Shots On Target'], dict):
                        shots_home = stats['Shots On Target'].get('home', '0')
                        shots_away = stats['Shots On Target'].get('away', '0')
                        
                        if isinstance(shots_home, str) and shots_home.isdigit():
                            shots_on_target['home'] = int(shots_home)
                        if isinstance(shots_away, str) and shots_away.isdigit():
                            shots_on_target['away'] = int(shots_away)
                            
                        shots_on_target['total'] = shots_on_target['home'] + shots_on_target['away']
                    
                    # Get total shots
                    if 'Shots Total' in stats and isinstance(stats['Shots Total'], dict):
                        shots_home = stats['Shots Total'].get('home', '0')
                        shots_away = stats['Shots Total'].get('away', '0')
                        
                        if isinstance(shots_home, str) and shots_home.isdigit():
                            shots_total['home'] = int(shots_home)
                        if isinstance(shots_away, str) and shots_away.isdigit():
                            shots_total['away'] = int(shots_away)
                            
                        shots_total['total'] = shots_total['home'] + shots_total['away']
                    
            # Check if match meets criteria
            if current_minute is not None and 52 <= current_minute <= 61 and current_goals is not None and 1 <= current_goals <= 3:
                # Calculate Under X recommendation
                recommended_under = current_goals + 4
                
                # Calculate risk level based on shots on target
                risk_level = "LOW"
                risk_factors = []
                
                # High shots on target relative to goals scored indicates potential for more goals
                if shots_on_target['total'] > current_goals * 3:
                    risk_level = "MEDIUM"
                    risk_factors.append(f"High shots on target ({shots_on_target['total']}) relative to goals ({current_goals})")
                
                if shots_on_target['total'] > current_goals * 4 or shots_on_target['total'] > 8:
                    risk_level = "HIGH"
                    risk_factors.append(f"Very high shots on target ({shots_on_target['total']})")
                
                # Calculate remaining shots to goals ratio (conversion efficiency)
                remaining_minutes = 90 - current_minute
                
                # Add to matches list with enhanced recommendation
                match_info = {
                    "game_id": str(match['_id']),
                    "match": match.get('match', 'Unknown Match'),
                    "current_minute": current_minute,
                    "current_goals": current_goals,
                    "recommendation": f"Bet on Under {recommended_under}.5",
                    "country": match.get('country'),
                    "league": match.get('league'),
                    "shots_data": {
                        "shots_on_target": shots_on_target,
                        "shots_total": shots_total
                    },
                    "risk_assessment": {
                        "level": risk_level,
                        "factors": risk_factors
                    }
                }
                
                # Add avg goals data if available
                if 'predictionStats' in match and isinstance(match['predictionStats'], dict) and 'avgTotalGoals' in match['predictionStats']:
                    match_info["avg_goals"] = match['predictionStats']['avgTotalGoals']
                
                under_x_matches.append(match_info)
                
        client.close()
        
        # Sort matches by risk level (LOW risk first)
        under_x_matches.sort(key=lambda x: 0 if x['risk_assessment']['level'] == "LOW" else 
                                          (1 if x['risk_assessment']['level'] == "MEDIUM" else 2))
        
        return jsonify({
            "count": len(under_x_matches),
            "matches": under_x_matches,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error finding Under X matches: {e}")
        traceback.print_exc()
        if 'client' in locals() and client:
            client.close()
        return jsonify({
            "error": f"Failed to find Under X matches: {str(e)}",
            "status": "error"
        }), 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint to verify the API is running"""
    return jsonify({
        "status": "ok",
        "message": "API is running"
    })

# --- Run Flask App ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    
    # Configure reloader to exclude virtual environment directory
    from werkzeug.serving import run_simple
    import re
    
    # Define regex patterns for files to exclude from reloading
    # This will exclude any changes in the virtual environment directory
    exclude_patterns = [
        r'^.*/venv/.*$',  # Exclude anything in venv directory
        r'^.*/site-packages/.*$',  # Exclude site-packages
        r'^.*/lib/python.*/.*$',  # Exclude Python lib directories
    ]
    
    if app.debug:
        # If in debug mode, use custom run function with exclusions
        run_simple(
            '0.0.0.0', 
            port, 
            app,
            use_reloader=True,
            use_debugger=True,
            threaded=True,
            reloader_interval=1,
            reloader_type='stat',
            static_files=None,
            exclude_patterns=exclude_patterns
        )
    else:
        # Normal run for production
        app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
