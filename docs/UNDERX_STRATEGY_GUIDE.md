# UnderX In-Play Strategy Implementation Guide

This document outlines the steps to run and manage the automated UnderX In-Play betting strategy system.

## Prerequisites

Before running the system, ensure you have:

1. **MongoDB** running with access to the `footystats_ev` database and `underxmatches` collection
2. **Redis** server running
3. Python 3.8+ with the required packages installed
4. Properly configured `.env` file with MongoDB and Redis credentials

## Required Python Packages

Install the following packages:

```bash
pip install pymongo redis schedule python-dotenv
```

## System Components

The system consists of three main components:

1. **Redis Handler** - Manages storage of live game IDs in Redis
2. **UnderX Match Handler** - Retrieves and processes match data from MongoDB
3. **UnderX Strategy Scheduler** - Runs analysis on live games every 60 seconds
4. **Cron Live Games** - Finds today's live games and stores their IDs in Redis

## Running the System

### Step 1: Find and Store Live Games

The first script identifies today's live games based on their timestamps and stores them in Redis.

```bash
cd /home/daniel/Projects/football_ml
python scripts/cron_live_games.py
```

This script should be run periodically (e.g., every 2 minutes) to keep the Redis database updated with current live games. You can set up an actual cron job for this:

```bash
# Add to crontab (run 'crontab -e')
*/2 * * * * cd /home/daniel/Projects/football_ml && python scripts/cron_live_games.py >> logs/cron_live_games.log 2>&1
```

### Step 2: Run the Strategy Scheduler

The strategy scheduler continuously analyzes live games every 60 seconds:

```bash
cd /home/daniel/Projects/football_ml
python scripts/underx_strategy_scheduler.py
```

This process should run continuously while you want to monitor games. You can run it in a screen or tmux session, or as a systemd service.

### Step 3: Monitor Results

The scheduler outputs results to the console, showing which games meet the UnderX betting criteria. In the testing phase, bets won't be placed automatically - you'll just see messages indicating suitable matches:

```text
===============================================================================
ANALYZING LIVE MATCHES WITH UNDER X IN-PLAY STRATEGY
-------------------------------------------------------------------------------
Found 3 live matches for analysis
✅ MATCH FOUND: Manchester United vs Chelsea
  - Score: 2 - 1
  - Minute: 53
  - Recommendation: PLACE BET
  - Market: under_6.5
  - Odds: 1.25
  - Risk: MEDIUM
-------------------------------------------------------------------------------
Analysis complete: 1 out of 3 matches are suitable for betting
===============================================================================
```

## High-Risk Game Monitoring & Emergency Cashout

After a bet is placed, the system continues to monitor the match for high-risk scenarios that may require an emergency cashout. This is handled by a dedicated monitoring script.

### How It Works

- **Skip Already Cashed Out Games:** The monitor checks MongoDB and skips games where the `cashout` property is `true`.
- **Emergency Cashout (2 goals before 70th minute):** If 2 goals are scored after the bet and before the 70th minute, an emergency cashout signal is sent to RabbitMQ after a 2-minute delay.
- **High-Risk Tracking (2 goals between 70 and 82):** If 2 goals are scored after the bet between the 70th and 82nd minute, the game is tracked as high risk in Redis.
- **Third Goal Before 82:** If a third goal is scored before the 82nd minute, a cashout signal is sent.
- **Third Goal After 82 but before 85:** If a third goal is scored after the 82nd but before the 85th minute, a cashout signal is sent.
- **Continued Monitoring:** The script continues to monitor high-risk games for further goals and triggers cashout as needed.

### Running the High-Risk Monitor

Start the monitor in a separate process or terminal:

```bash
cd /home/daniel/Projects/football_ml
python scripts/run_high_risk_monitor.py
```

This script will call the main high-risk monitoring logic and should be kept running alongside the main strategy scheduler.

### Integration

- The monitor script interacts with Redis and MongoDB to track and manage high-risk games.
- Emergency cashout signals are sent to RabbitMQ for immediate action.

## Odds Update Monitoring

To maximize bet success, the system continuously monitors odds for active bet games and requests updated information from bookmakers through a dedicated RabbitMQ queue.

### How Odds Monitoring Works

- **Live Bet Identification:** Every minute, the system checks Redis and MongoDB to identify matches with active bets
- **Skip Already Cashed Out Games:** The monitor skips games where the `cashout` property is `true`
- **Request Odds Updates:** For each active bet game, it sends a request to the `betfair_bets` RabbitMQ queue
- **Message Format:** Requests are sent in a standardized JSON format containing the match ID and type:

  ```json
  {
    "type": "get_odds",
    "matchType": "underXmatch",
    "matchId": "68336ebaeddf24a76ec32931"
  }
  ```

- **Real-time Updates:** The betting service processes these requests to provide fresh odds data for better cashout decisions

### Running the Odds Monitor

Start the odds monitor in a separate process or terminal:

```bash
cd /home/daniel/Projects/football_ml
python scripts/run_odds_monitor.py
```

This script runs the odds monitoring functionality and should be kept running alongside the main strategy scheduler and high-risk monitor.

### Odds Monitor Integration

- The odds monitor connects to RabbitMQ to send update requests
- The external betting service processes these requests and updates odds in MongoDB
- Updated odds are used for cashout decisions and profit calculations

## Advanced Setup

### Running as System Services

For production environments, you can create systemd services:

Create `/etc/systemd/system/underx-cron.service`:

```ini
[Unit]
Description=UnderX Live Games Finder
After=network.target

[Service]
User=your_user
WorkingDirectory=/home/daniel/Projects/football_ml
ExecStart=/usr/bin/python scripts/cron_live_games.py
Restart=always
RestartSec=120

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/underx-strategy.service`:

```ini
[Unit]
Description=UnderX Strategy Scheduler
After=network.target

[Service]
User=your_user
WorkingDirectory=/home/daniel/Projects/football_ml
ExecStart=/usr/bin/python scripts/underx_strategy_scheduler.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the services:

```bash
sudo systemctl enable underx-cron.service
sudo systemctl start underx-cron.service
sudo systemctl enable underx-strategy.service
sudo systemctl start underx-strategy.service
```

## Machine Learning Model Setup

The UnderX strategy includes a machine learning component that can enhance the rule-based betting decisions. Here's how to set it up:

### 1. Collect Historical Match Data

The ML model learns from historical betting outcomes. It requires matches where:

- The `bet` property is set to `true` (matches where the strategy placed a bet)
- The `profitLoss` property indicates the outcome (`profitLoss > 0` for successful bets)

The data is stored in the `underxmatches` collection in MongoDB.

### 2. Train the ML Model

You can train the ML model using the provided MLPredictor class. Here's how to train it manually:

```python
from src.betting_rules import get_ml_predictor

# Get the ML predictor instance
ml_predictor = get_ml_predictor()

# Train the model (this reads data from MongoDB)
success = ml_predictor.train_model(save_model=True)

if success:
    print("Model trained and saved successfully!")
else:
    print("Model training failed.")
```

Or use the command-line script:

```bash
cd /home/daniel/Projects/football_ml
python scripts/train_ml_model.py
```

### 3. Model Training Details

The training process:

1. Queries the `underxmatches` collection for matches with `bet: true`
2. Extracts features from each match, including:
   - Match time
   - Current score
   - Team statistics
   - Shots, corners, and other match stats
3. Labels matches as successful (1) if `profitLoss > 0`, or unsuccessful (0) if `profitLoss < 0`
4. Trains a RandomForest classifier with balanced class weights
5. Evaluates model performance and saves the model to disk

### 4. Scheduled Retraining

As you collect more betting data, regularly retrain the model to improve its performance. Set up a weekly cron job:

```bash
# Add to crontab
0 2 * * MON cd /home/daniel/Projects/football_ml && python scripts/train_ml_model.py >> logs/ml_training.log 2>&1
```

Make the script executable:

```bash
chmod +x scripts/train_ml_model.py
```

### 5. ML Model Integration

The ML model integrates with the rule-based system in these ways:

1. **Validation**: ML validates rule-based decisions and can override them if it strongly disagrees
2. **Risk Assessment**: ML predictions can adjust stake sizes based on confidence levels
3. **Feature Importance**: The model can help identify which factors most strongly influence successful bets

To view ML feature importance:

```python
from src.betting_rules import get_ml_predictor
import matplotlib.pyplot as plt
import numpy as np

ml_predictor = get_ml_predictor()
model = ml_predictor.model

if model is not None and hasattr(model, 'feature_importances_'):
    # Define feature names (must match the feature extraction order)
    feature_names = [
        'minute', 'home_goals', 'away_goals', 'total_goals', 'goal_diff',
        'home_avg_goals', 'away_avg_goals', 'home_shots', 'away_shots',
        'home_shots_on_target', 'away_shots_on_target', 'home_corners',
        'away_corners', 'home_fouls', 'away_fouls', 'home_dangerous_attacks',
        'away_dangerous_attacks', 'goals_per_minute', 'shots_per_minute',
        'shots_on_target_per_minute'
    ]
    
    # Sort features by importance
    indices = np.argsort(model.feature_importances_)[::-1]
    
    # Print feature ranking
    print("Feature ranking:")
    for f in range(min(10, len(feature_names))):
        print(f"{f+1}. {feature_names[indices[f]]}: {model.feature_importances_[indices[f]]:.4f}")
```

## Troubleshooting

### Configuration Issues

If you see errors about missing configuration attributes:

- Check that `src/config.py` is properly loading all required environment variables
- Make sure your `.env` file contains all the required settings
- For Redis-specific errors like `module 'src.config' has no attribute 'REDIS_HOST'`, ensure that:

  ```python
  # Redis Configuration
  REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
  REDIS_PORT = os.getenv('REDIS_PORT', 6379)
  REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
  REDIS_DB = os.getenv('REDIS_DB', 0)
  REDIS_TTL = os.getenv('REDIS_TTL', 120)
  LIVE_GAMES_KEY = os.getenv('LIVE_GAMES_KEY', 'live_games')
  ```

  exists in your `src/config.py` file

### Redis Connection Issues

If you're experiencing Redis connection issues:

- Verify Redis is running: `redis-cli ping`
- Check connection parameters in `.env`
- Ensure Redis is not protected by a password or firewall

### MongoDB Connection Issues

If MongoDB connections fail:

- Verify MongoDB is running: `mongosh`
- Check connection string and credentials in `.env`
- Ensure the `underxmatches` collection exists and contains documents

### No Live Games Found

If no live games are detected:

- Check if there are games scheduled for today in the `underxmatches` collection
- Verify the game timestamps are in the correct format (milliseconds since epoch)
- Run the cron script with DEBUG logging to see more details

## Moving to Production

When you're ready to enable actual bet signals:

1. Edit the `UnderXInPlayStrategy.analyze_live_matches` method
2. Uncomment the code that sends bet signals to RabbitMQ
3. Update the `.env` file with proper RabbitMQ credentials
4. Run tests with small stakes before going live

## Logs and Monitoring

All system logs are output to the console. For permanent logging:

```bash
python scripts/underx_strategy_scheduler.py > logs/strategy.log 2>&1
```

You can use tools like `logrotate` to manage log files and prevent them from growing too large.
