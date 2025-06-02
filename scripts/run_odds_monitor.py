#!/usr/bin/env python3
"""
Runner script for the live bet odds monitor.
This script calls the main monitoring functionality to request odds updates for active bet games.
"""
import sys
import os

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scripts.monitor_live_bet_odds import main

if __name__ == "__main__":
    main()
