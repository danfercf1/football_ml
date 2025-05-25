#!/usr/bin/env bash
# Script to test the match analysis with the Fluminense FC vs Unión Española match
# This version includes the special Under X In-Play betting strategy

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored messages
print_msg() {
  echo -e "${2}${1}${NC}"
}

# Create Python virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  print_msg "Creating Python virtual environment..." "$BLUE"
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

# Display the Under X In-Play Strategy
print_msg "=============================================================" "$PURPLE"
print_msg "           UNDER X IN-PLAY BETTING STRATEGY                  " "$PURPLE"
print_msg "=============================================================" "$PURPLE"
print_msg "Strategy criteria:" "$YELLOW"
print_msg "1. Find matches between minutes 52-61" "$YELLOW"
print_msg "2. Match should have 1-3 goals already scored" "$YELLOW"
print_msg "3. Teams should have low average total goal counts" "$YELLOW"
print_msg "4. Bet on Under (current goals + 4) market" "$YELLOW"
print_msg "5. Cash out if 2+ more goals before minute 82" "$YELLOW"
print_msg "=============================================================" "$PURPLE"

print_msg "\nRunning match analysis on Fluminense FC vs Unión Española match..." "$BLUE"

# First run the standard analysis
print_msg "\n1. Standard analysis:" "$GREEN"
python scripts/analyze_match.py data/fluminense_match.json

# Now run the Under X In-Play strategy-specific analysis
print_msg "\n2. Under X In-Play strategy analysis:" "$GREEN"
python scripts/under_x_inplay.py data/fluminense_match.json

# Print a completion message
print_msg "\nAnalysis complete!" "$GREEN"
print_msg "To add specialized soccer rules to MongoDB, use:" "$YELLOW"
print_msg "python scripts/create_soccer_rules.py" "$NC"
