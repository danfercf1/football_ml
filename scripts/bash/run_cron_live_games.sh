#!/bin/bash

# Set up logging
LOG_DIR="/home/daniel/Projects/football_ml/logs"
LOG_FILE="$LOG_DIR/cron_live_games.log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

echo "$(date): Starting cron job script" >> "$LOG_FILE" 2>&1

# Path to the virtual environment
VENV_PATH="/home/daniel/Projects/football_ml/venv"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "$(date): ERROR - Virtual environment not found at $VENV_PATH" >> "$LOG_FILE" 2>&1
    exit 1
fi

# Path to the python script
SCRIPT_PATH="/home/daniel/Projects/football_ml/scripts/cron_live_games.py"

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "$(date): ERROR - Script not found at $SCRIPT_PATH" >> "$LOG_FILE" 2>&1
    exit 1
fi

# Activate virtual environment
echo "$(date): Activating virtual environment" >> "$LOG_FILE" 2>&1
source "$VENV_PATH/bin/activate" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "$(date): ERROR - Failed to activate virtual environment" >> "$LOG_FILE" 2>&1
    exit 1
fi

# Print Python path for debugging
echo "$(date): Using Python: $(which python)" >> "$LOG_FILE" 2>&1

# Run the script
echo "$(date): Running script $SCRIPT_PATH" >> "$LOG_FILE" 2>&1
python "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1

# Check if script executed successfully
if [ $? -ne 0 ]; then
    echo "$(date): ERROR - Script execution failed" >> "$LOG_FILE" 2>&1
    deactivate >> "$LOG_FILE" 2>&1
    exit 1
fi

# Deactivate virtual environment
echo "$(date): Deactivating virtual environment" >> "$LOG_FILE" 2>&1
deactivate >> "$LOG_FILE" 2>&1

echo "$(date): Cron job completed successfully" >> "$LOG_FILE" 2>&1
