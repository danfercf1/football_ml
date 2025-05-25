# Football ML - Live Soccer Game Analysis System

A real-time soccer match analysis service that processes live statistics and makes betting decisions based on predefined rules or ML predictions.

## Features

- Real-time processing of match statistics (shots, possession, xG, etc.)
- Rule-based analysis engine with rules stored in MongoDB
- Machine learning prediction integration
- RabbitMQ messaging for bet execution
- Adaptive rule reloading via MongoDB change streams

## Project Structure

```
football_ml/
├── src/
│   ├── __init__.py
│   ├── analyzer.py           # Main analyzer service
│   ├── rule_engine.py        # Rule-based analysis logic
│   ├── ml_predictor.py       # ML model integration
│   ├── mongo_handler.py      # MongoDB integration
│   ├── rabbitmq_publisher.py # RabbitMQ integration
│   ├── mock_data.py          # Mock live data for testing
│   ├── match_processor.py    # Real match data processing
│   ├── specialized_rules.py  # Advanced soccer rules
│   └── config.py             # Configuration settings
├── models/                   # Folder to store ML models
│   └── betting_model.pkl     # Sample pre-trained model
├── data/                     # Sample match data
│   └── fluminense_match.json # Example real match document
├── docs/                     # Documentation
│   └── MATCH_ANALYSIS.md     # Guide for real match analysis
├── tests/                    # Unit tests
├── scripts/                  # Utility scripts
│   ├── create_model.py       # Script to generate sample ML model
│   ├── bet_viewer.py         # Script to view bet signals in RabbitMQ
│   ├── analyze_match.py      # Real match analysis tool
│   └── create_soccer_rules.py # Soccer rules creation
├── docker-compose.yml        # Docker Compose configuration
├── run.sh                    # Setup and run script
├── test_match_analysis.sh    # Test script for real match analysis
├── .env.example              # Example environment variables
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

## Setup

### Quick Start with Docker

The easiest way to get started is using the provided run script, which sets up everything for you:

```bash
./run.sh
```

This script will:

1. Check for Docker and Docker Compose
2. Create a Python virtual environment and install dependencies
3. Start MongoDB and RabbitMQ containers
4. Create a sample ML model
5. Start a bet viewer service
6. Run basic tests
7. Start the analyzer

### Manual Setup

If you prefer to set up the components manually:

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your MongoDB and RabbitMQ credentials.

4. Start MongoDB and RabbitMQ (using Docker):

```bash
docker-compose up -d mongodb rabbitmq
```

5. Generate a sample ML model:

```bash
python scripts/create_model.py
```

6. Run the analyzer:

```bash
python -m src.analyzer
```

### Running Tests

To run the basic tests:

```bash
python -m tests.test_basic
```

## MongoDB Structure

The system uses a collection called `rules` with documents like:

```json
{
  "type": "shots",
  "league": "premier_league",
  "conditions": {
    "home_shots": {"$gt": 10},
    "minute": {"$gt": 60}
  },
  "market": "over_2.5",
  "enabled": true
}
```

## Adding New Rules

Rules can be added directly to the MongoDB collection and will be picked up automatically by the system (if change streams are enabled).

## Machine Learning

The system can load pre-trained models from the `models/` directory to make predictions based on live match data.

## Docker Compose Environment

The project includes a Docker Compose configuration with the following services:

- **MongoDB**: Stores the analysis rules
- **RabbitMQ**: Message queue for bet signals
- **Bet Viewer**: Simple service that displays bet signals from the queue

To start the Docker services:

```bash
docker-compose up -d
```

You can view the RabbitMQ management console at <http://localhost:15672> (username/password: guest/guest).

To view bet signals from the viewer:

```bash
docker-compose logs -f bet_viewer
```

## Real Match Data Analysis

The system has been enhanced to process detailed real match data from sports APIs or databases. This functionality provides more sophisticated analysis using:

- Advanced match statistics (shots, possession, corners, dangerous attacks)
- Team performance indicators (xG, form, win percentages)
- Odds from multiple bookmakers
- League-specific analysis

### Analyzing Real Match Data

To analyze a real match document:

```bash
# Analyze a specific match from a JSON file
python scripts/analyze_match.py data/fluminense_match.json

# Or run the test script to analyze the sample match
./test_match_analysis.sh
```

### Creating Specialized Soccer Rules

To add advanced soccer-specific rules to MongoDB:

```bash
python scripts/create_soccer_rules.py
```

For more details on real match data analysis, see [Match Analysis Guide](docs/MATCH_ANALYSIS.md).

## Specialized Betting Strategies

### Under X In-Play Strategy

This strategy focuses on betting on under goals markets during live matches:

- **Target window:** Matches between minutes 52-61
- **Current state:** Match should have 1-3 goals already scored
- **Team profile:** Teams should have low average goal counts
- **Market:** Bet on Under (current goals + 4)
- **Odds range:** Typically 1.01-1.03
- **Cash-out trigger:** If 2+ more goals are scored before minute 82

Run this specialized strategy:

```bash
# Analyze a match specifically for the Under X In-Play strategy
python scripts/under_x_inplay.py data/fluminense_match.json

# The test script already includes running this analysis
./test_match_analysis.sh
```

Features of the Under X In-Play analysis:

- Risk scoring based on team goal rates and match momentum
- Live monitoring simulation to demonstrate when to cash out
- Integration with RabbitMQ for automatic bet signals
- Specialized MongoDB rule for automated detection
