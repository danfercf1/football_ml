"""
Module for generating mock live soccer match data for testing purposes.
"""
import random
import time
import uuid
from typing import Dict, Any


class MockDataGenerator:
    """
    Generates mock live soccer match data for testing the analysis system.
    """
    
    def __init__(self, league: str = "premier_league"):
        """
        Initialize the mock data generator.
        
        Args:
            league: The league to generate data for
        """
        self.match_id = str(uuid.uuid4())
        self.minute = 0
        self.league = league
        self.home_team = "Home Team"
        self.away_team = "Away Team"
        
        # Initial match statistics
        self.home_shots = 0
        self.away_shots = 0
        self.possession_home = 50
        self.xg_home = 0.0
        self.xg_away = 0.0
        self.odds = {
            "over_2.5": 1.8,
            "under_2.5": 2.0,
            "home_win": 2.2,
            "draw": 3.2,
            "away_win": 3.0
        }
        
    def update_match_state(self) -> Dict[str, Any]:
        """
        Update the match state to simulate progression of the game.
        
        Returns:
            Dict with updated match statistics
        """
        # Simulate time passing
        self.minute += 1
        if self.minute > 90:
            self.minute = 1
            self.match_id = str(uuid.uuid4())
            self.reset_match()
        
        # Update shots
        if random.random() < 0.1:  # 10% chance of a shot per minute
            if random.random() < 0.6:  # 60% chance it's from home team
                self.home_shots += 1
                self.xg_home += random.uniform(0.01, 0.2)
            else:
                self.away_shots += 1
                self.xg_away += random.uniform(0.01, 0.2)
        
        # Update possession
        possession_change = random.uniform(-3, 3)
        self.possession_home = max(30, min(70, self.possession_home + possession_change))
        
        # Update odds based on match progress
        self._update_odds()
        
        return self.get_current_state()
    
    def _update_odds(self):
        """Update the odds based on the current match state."""
        # Simplistic odds update based on xG
        total_xg = self.xg_home + self.xg_away
        
        # Update over/under odds
        if total_xg > 2.0:
            self.odds["over_2.5"] = max(1.1, self.odds["over_2.5"] * 0.98)
            self.odds["under_2.5"] = min(4.0, self.odds["under_2.5"] * 1.02)
        else:
            self.odds["over_2.5"] = min(3.0, self.odds["over_2.5"] * 1.01)
            self.odds["under_2.5"] = max(1.2, self.odds["under_2.5"] * 0.99)
            
        # Update match outcome odds
        if self.xg_home > self.xg_away + 0.5:
            self.odds["home_win"] = max(1.2, self.odds["home_win"] * 0.99)
            self.odds["away_win"] = min(5.0, self.odds["away_win"] * 1.02)
        elif self.xg_away > self.xg_home + 0.5:
            self.odds["away_win"] = max(1.2, self.odds["away_win"] * 0.99)
            self.odds["home_win"] = min(5.0, self.odds["home_win"] * 1.02)
        
    def reset_match(self):
        """Reset match statistics for a new match."""
        self.home_shots = 0
        self.away_shots = 0
        self.possession_home = 50
        self.xg_home = 0.0
        self.xg_away = 0.0
        self.odds = {
            "over_2.5": 1.8,
            "under_2.5": 2.0,
            "home_win": 2.2,
            "draw": 3.2,
            "away_win": 3.0
        }
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        Get the current match state.
        
        Returns:
            Dict with all current match statistics
        """
        return {
            "match_id": self.match_id,
            "minute": self.minute,
            "league": self.league,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_shots": self.home_shots,
            "away_shots": self.away_shots,
            "possession_home": self.possession_home,
            "xg_home": self.xg_home,
            "xg_away": self.xg_away,
            "total_xg": self.xg_home + self.xg_away,
            "odds": self.odds
        }


def get_mock_match_generator(league: str = "premier_league") -> MockDataGenerator:
    """
    Create and return a new mock data generator.
    
    Args:
        league: The league to generate data for
        
    Returns:
        A configured MockDataGenerator instance
    """
    return MockDataGenerator(league=league)


def simulate_live_match(duration_seconds: int = 90, delay: float = 1.0) -> None:
    """
    Simulate a live match for a specified duration.
    
    Args:
        duration_seconds: How long to run the simulation for
        delay: Delay between updates in seconds
    """
    generator = get_mock_match_generator()
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        match_data = generator.update_match_state()
        print(f"Minute {match_data['minute']}: "
              f"Shots {match_data['home_shots']}-{match_data['away_shots']}, "
              f"xG {match_data['xg_home']:.2f}-{match_data['xg_away']:.2f}, "
              f"Odds over 2.5: {match_data['odds']['over_2.5']:.2f}")
        time.sleep(delay)


if __name__ == "__main__":
    # Example usage
    simulate_live_match(duration_seconds=30, delay=0.5)
