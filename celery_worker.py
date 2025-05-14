import os
from celery import Celery
from main import analyze_game
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery
# Use the correct Redis hostname for Docker networking
redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
print(f"[celery_worker] REDIS_URL = {redis_url}")
celery_app = Celery('football_ml', broker=redis_url, backend=redis_url)

# Configure Celery task settings
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max runtime
    broker_connection_retry_on_startup=True,
)

@celery_app.task(name='analyze_game_task')
def analyze_game_task(game_id):
    """
    Background task to analyze a game using PyCaret.
    This function runs in the background, allowing the API to respond immediately.
    
    Args:
        game_id (str): MongoDB ObjectId as string
        
    Returns:
        dict: Analysis results
    """
    print(f"Starting background analysis for game: {game_id}")
    try:
        result = analyze_game(game_id)
        return result
    except Exception as e:
        import traceback
        print(f"Error in background task: {e}")
        traceback.print_exc()
        return {
            "game_id": game_id,
            "error": f"Background task error: {str(e)}",
            "final_decision": "ERROR",
            "status": "failed"
        }
