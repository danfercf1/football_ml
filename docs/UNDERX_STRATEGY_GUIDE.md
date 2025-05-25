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
