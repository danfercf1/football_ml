#!/usr/bin/env python3
"""
Wrapper script to run the high-risk game monitor in a managed way.
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    from scripts.monitor_high_risk_games import main as monitor_main
    monitor_main()
