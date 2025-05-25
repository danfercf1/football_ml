# Real Match Data Analysis Guide

This guide explains how to use the football_ml system to analyze real soccer match data like the sample document provided.

## Data Format

The system can process detailed match documents with the following structure:

- Basic match info (teams, league, country)
- Team statistics and form data
- Live match stats (shots, possession, corners, etc.)
- Odds information from multiple bookmakers
- Expected goals (xG) data
- Historical performance data
- Prediction statistics

## Using the Match Analysis Tool

### Analyzing a Specific Match

To analyze a match document saved in a file:

```bash
# From the project root
python scripts/analyze_match.py data/fluminense_match.json
```

You can also paste a match document directly when prompted:

```bash
python scripts/analyze_match.py
```

### Output

The analysis tool will:

1. Process the match document to extract relevant features
2. Apply specialized rules to identify betting opportunities
3. Display key statistics and potential bets
4. Send bet signals to RabbitMQ if any opportunities are found

## Adding Specialized Rules

To add specialized rules for soccer analysis to MongoDB:

```bash
python scripts/create_soccer_rules.py
```

This script will:
1. Connect to the MongoDB database
2. Insert specialized soccer rules
3. Display the inserted rules

## Available Rule Types

The system includes several specialized rules for soccer analysis:

- `soccer_first_half_shots`: Identifies matches where the home team is dominating with shots in the first half
- `soccer_home_win_strong`: Detects strong home team performance with high possession and dangerous attacks
- `soccer_corner_frenzy`: Identifies matches with high corner potential
- `soccer_btts_potential`: Spots matches with good potential for both teams to score
- `soccer_copa_sudamericana_home_advantage`: Specialized for Copa Sudamericana matches with strong home advantage

## Testing with Sample Data

A sample match document is provided in `data/fluminense_match.json` which you can use to test the system.

## Example Analysis

The system will analyze the match and identify betting opportunities based on:

1. The current match state (minute, score, stats)
2. Team performance indicators (shots, possession, attacks)
3. Historical data (xG, team form, head-to-head)
4. Odds information from bookmakers

For every match, the system will produce a detailed analysis indicating which markets offer value, with confidence levels for each recommendation.
