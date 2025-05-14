# Football ML Analysis Project

A machine learning system that analyzes football matches using PyCaret and MongoDB data. This project provides an API for triggering analysis of specific matches, with real-time predictions and decisions about whether to avoid matches based on game statistics.

## Setup

### Prerequisites

- Python 3.7+
- MongoDB
- Docker and Docker Compose (for Redis)

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd /home/daniel/Projects/football_ml
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

The `.env` file should have the following configuration:

```
MONGO_URI="mongodb://daniel:daniel@127.0.0.1:27018/footystats_ev"
REDIS_URL="redis://localhost:6380/0"
```

## Running the Project

### 1. Start Redis with Docker Compose

The project uses Redis for message queuing with Celery. Start Redis using Docker Compose:

```bash
# Start Redis
docker-compose up -d redis
```

### 2. Start the Celery Worker

Celery workers perform the background processing of the ML tasks:

```bash
# In a separate terminal
cd /home/daniel/Projects/football_ml
celery -A celery_worker worker --loglevel=info
```

### 3. Run the Flask API Server

The API allows clients to request match analysis:

```bash
# In a separate terminal
cd /home/daniel/Projects/football_ml
python api.py
```

The API will be available at <http://localhost:5000>.

## API Usage

### Analyze a Game

```
GET /analyze/{game_id}
```

Example:

```bash
curl http://localhost:5000/analyze/67fab4a1a6155bd60617b8f2
```

Response:

```json
{
  "message": "Analysis started in background",
  "task_id": "abc123...",
  "game_id": "67fab4a1a6155bd60617b8f2",
  "status": "pending",
  "result_endpoint": "/results/abc123..."
}
```

For synchronous execution (useful for testing):

```bash
curl http://localhost:5000/analyze/67fab4a1a6155bd60617b8f2?sync=true
```

### Check Analysis Results

```
GET /results/{task_id}
```

Example:

```bash
curl http://localhost:5000/results/abc123...
```

Response:

```json
{
  "task_id": "abc123...",
  "status": "completed",
  "result": {
    "game_id": "67fab4a1a6155bd60617b8f2",
    "match": "Team A vs Team B",
    "current_minute": 75,
    "model_used": "RandomForestClassifier",
    "prediction_target": "success",
    "prediction_value": false,
    "final_decision": "AVOID",
    "decision_reason": "Live Minute (75) > 70"
  }
}
```

## Working with Historical Data

### Retrieving Historical Data

The system automatically fetches relevant historical matches when analyzing a game. This is handled by the `get_historical_games()` function in `db_connector.py`:

```python
# Retrieve historical data for a specific game
from db_connector import get_game_data, get_historical_games

# First get a specific game
target_game = get_game_data("67fab4a1a6155bd60617b8f2")  # Replace with actual game ID

# Then retrieve historical data relevant to this game
historical_matches = get_historical_games(target_game)

# Convert to DataFrame if needed
import pandas as pd
historical_df = pd.DataFrame(historical_matches)
```

### Loading New Historical Data

If you need to import new historical match data into MongoDB:

1. Prepare your data as JSON files or a compatible format
2. Use the MongoDB import utility or a Python script:

```python
# Example script to import historical data
from pymongo import MongoClient
import json
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

def import_historical_data(json_file_path):
    """Import historical match data from a JSON file"""
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()
    collection = db['underxmatches']
    
    with open(json_file_path, 'r') as file:
        data = json.load(file)
    
    # For single document
    if isinstance(data, dict):
        collection.insert_one(data)
        print(f"Imported 1 document")
    
    # For multiple documents
    elif isinstance(data, list):
        result = collection.insert_many(data)
        print(f"Imported {len(result.inserted_ids)} documents")
    
    client.close()

# Usage
import_historical_data('/path/to/historical_matches.json')
```

### Exporting Historical Data

To export your existing historical data:

```bash
# Using MongoDB's mongoexport utility
mongoexport --uri="mongodb://daniel:daniel@127.0.0.1:27018/footystats_ev" \
            --collection=underxmatches \
            --out=historical_matches.json \
            --jsonArray
```

### Historical Data API Endpoints

The API offers several endpoints to work with historical data:

#### Import Historical Data

```
POST /historical/import
```

Accepts a JSON payload with match data to import into the database.

Example:

```bash
curl -X POST http://localhost:5000/historical/import \
     -H "Content-Type: application/json" \
     -d @matches.json
```

Response:

```json
{
  "message": "Successfully imported 10 documents",
  "inserted_count": 10
}
```

#### Export Historical Data

```
GET /historical/export?league=SerieA&country=Italy&limit=50
```

Exports historical matches as a downloadable JSON file.

Query parameters:
- `league`: Filter by league name
- `country`: Filter by country name
- `team`: Filter by team name (matches either home or away team)
- `limit`: Maximum number of documents to export (default: 100)

#### Count Historical Data

```
GET /historical/count?league=SerieA&country=Italy
```

Returns a count of matching historical matches.

Example Response:

```json
{
  "count": 342,
  "query": {
    "league": "SerieA",
    "country": "Italy" 
  }
}
```

## Project Structure

- `api.py` - Flask API server
- `main.py` - Core analysis logic
- `celery_worker.py` - Background task processing
- `db_connector.py` - MongoDB connection handling
- `pycaret_analyzer.py` - ML model training and prediction

## Troubleshooting

### Redis Connection Issues

If you encounter Redis connection issues, verify:

1. Redis is running: `docker ps | grep redis`
2. The port in your `.env` file matches the port in `docker-compose.yml`
3. Try the default Redis port (6379) if 6380 is not working: `REDIS_URL="redis://localhost:6379/0"`

### MongoDB Connection Issues

If you encounter MongoDB connection issues, verify:

1. MongoDB is running and accessible
2. Connection string in `.env` is correct
3. Database and collections exist
