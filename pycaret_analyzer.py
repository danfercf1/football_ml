import pandas as pd
import numpy as np
from pycaret.classification import setup, compare_models, predict_model, ClassificationExperiment, create_model
import traceback
import warnings
warnings.filterwarnings('ignore')

def extract_advanced_features(df):
    """
    Extract rich features from the match document structure
    
    Args:
        df (pd.DataFrame): DataFrame containing match documents
        
    Returns:
        pd.DataFrame: DataFrame with additional extracted features
    """
    features_df = df.copy()
    
    # List to store new features
    new_features = []
    
    # DEBUG: Show columns and content of incoming DataFrame
    print(f"extract_advanced_features: DataFrame columns: {list(df.columns)}")
    print(f"DEBUG: Check if liveStats exists in any row: {any('liveStats' in row for idx, row in df.iterrows())}")
    print(f"DEBUG: Check if livescore exists in any row: {any('livescore' in row for idx, row in df.iterrows())}")
    
    # Add default current_minute column to ensure it always exists
    has_live_data = False
    
    for idx, row in df.iterrows():
        features = {}
        
        # Basic features - already being used
        features['homeForm'] = float(row.get('homeForm', 0)) if pd.notna(row.get('homeForm')) else 0
        features['awayForm'] = float(row.get('awayForm', 0)) if pd.notna(row.get('awayForm')) else 0
        features['under25Probability'] = float(str(row.get('under25Probability', '0')).replace('%', '')) / 100 if pd.notna(row.get('under25Probability')) else 0
        
        # Always initialize current_minute to ensure column exists
        features['current_minute'] = 0
        
        # Extract game status, defaulting to what's in the data
        features['game_status'] = row.get('status', 'upcoming')
        
        # DEBUG: Deep inspection of raw data for live information
        print(f"DEBUG: Row keys: {list(row.keys())}")
        if 'liveStats' in row:
            print(f"DEBUG: liveStats content type: {type(row['liveStats'])}")
            if isinstance(row['liveStats'], dict):
                print(f"DEBUG: liveStats keys: {list(row['liveStats'].keys())}")
        if 'livescore' in row:
            print(f"DEBUG: livescore content type: {type(row['livescore'])}")
            if isinstance(row['livescore'], dict):
                print(f"DEBUG: livescore keys: {list(row['livescore'].keys())}")
        
        # --- PATCH: Prefer liveStats over livescore for current_minute and status ---
        if 'liveStats' in row and isinstance(row['liveStats'], dict):
            has_live_data = True
            # Try both 'minute' and 'currentMinute' keys for robustness
            minute_val = None
            if 'minute' in liveStats:
                minute_val = liveStats['minute']
            elif 'currentMinute' in liveStats:
                minute_val = liveStats['currentMinute']
            # Debug print to help trace
            print(f"Analyzing live stats from liveStats... minute_val={minute_val!r}")
            # Handle int, str, or None
            if isinstance(minute_val, int):
                features['current_minute'] = minute_val
                features['game_status'] = 'live'
            elif isinstance(minute_val, str):
                if minute_val.isdigit():
                    features['current_minute'] = int(minute_val)
                    features['game_status'] = 'live'
                elif minute_val == 'HT':
                    features['current_minute'] = 45
                    features['game_status'] = 'live'
                elif minute_val == 'FT':
                    features['current_minute'] = 90
                    features['game_status'] = 'finished'
                else:
                    import re
                    numbers = re.findall(r'\d+', minute_val)
                    if numbers:
                        features['current_minute'] = int(numbers[0])
                        if features['current_minute'] < 90:
                            features['game_status'] = 'live'
                    else:
                        print("  Could not determine current minute from liveStats")
            else:
                print("  Could not determine current minute from liveStats")
            # If liveStats has isLive flag, respect it
            if liveStats.get('isLive') is True:
                features['game_status'] = 'live'
            elif liveStats.get('isCompleted') is True:
                features['game_status'] = 'finished'
            # ...existing code for extracting stats from liveStats...
        # --- END PATCH ---

        # If no liveStats, fallback to livescore
        elif 'livescore' in row and isinstance(row['livescore'], dict):
            has_live_data = True
            
            # Current minute
            minute_str = livescore.get('minute')
            features['current_minute'] = int(minute_str) if minute_str and isinstance(minute_str, str) and minute_str.isdigit() else 0
            
            # Handle special minute values like "HT" (Half Time)
            if minute_str == 'HT':
                features['current_minute'] = 45
                features['game_status'] = 'live'  # Mark HT as live
            elif minute_str == 'FT':
                features['current_minute'] = 90
                features['game_status'] = 'finished'  # Mark FT as finished
            else:
                # If minute is available and < 90, and not FT, consider it live
                if features['current_minute'] > 0 and features['current_minute'] < 90:
                    features['game_status'] = 'live'
            
            # Current score
            if 'score' in livescore:
                try:
                    home_score, away_score = livescore['score'].split(' - ')
                    features['home_score'] = int(home_score)
                    features['away_score'] = int(away_score)
                    features['total_score'] = features['home_score'] + features['away_score']
                    features['score_difference'] = features['home_score'] - features['away_score']
                except:
                    features['home_score'] = features['away_score'] = features['total_score'] = features['score_difference'] = 0
            
            # Extract live game stats
            if 'stats' in livescore and isinstance(livescore['stats'], dict):
                try:
                    stats = livescore['stats']
                    
                    # Shots
                    if 'Shots Total' in stats:
                        try:
                            features['home_shots'] = int(stats['Shots Total'].get('home', 0)) if stats['Shots Total'].get('home', '').isdigit() else 0
                            features['away_shots'] = int(stats['Shots Total'].get('away', 0)) if stats['Shots Total'].get('away', '').isdigit() else 0
                            features['total_shots'] = features['home_shots'] + features['away_shots']
                            features['shots_difference'] = features['home_shots'] - features['away_shots']
                        except Exception as e:
                            print(f"Error extracting Shots Total: {e}")
                    
                    # Shots on target
                    if 'Shots On Target' in stats:
                        try:
                            features['home_shots_on_target'] = int(stats['Shots On Target'].get('home', 0)) if stats['Shots On Target'].get('home', '').isdigit() else 0
                            features['away_shots_on_target'] = int(stats['Shots On Target'].get('away', 0)) if stats['Shots On Target'].get('away', '').isdigit() else 0
                            features['total_shots_on_target'] = features['home_shots_on_target'] + features['away_shots_on_target']
                        except Exception as e:
                            print(f"Error extracting Shots On Target: {e}")
                    
                    # Corners
                    if 'Corners' in stats:
                        try:
                            features['home_corners'] = int(stats['Corners'].get('home', 0)) if stats['Corners'].get('home', '').isdigit() else 0
                            features['away_corners'] = int(stats['Corners'].get('away', 0)) if stats['Corners'].get('away', '').isdigit() else 0
                            features['total_corners'] = features['home_corners'] + features['away_corners']
                        except Exception as e:
                            print(f"Error extracting Corners: {e}")
                    
                    # Attacks
                    if 'Attacks' in stats:
                        try:
                            features['home_attacks'] = int(stats['Attacks'].get('home', 0)) if stats['Attacks'].get('home', '').isdigit() else 0
                            features['away_attacks'] = int(stats['Attacks'].get('away', 0)) if stats['Attacks'].get('away', '').isdigit() else 0
                            features['total_attacks'] = features['home_attacks'] + features['away_attacks']
                        except Exception as e:
                            print(f"Error extracting Attacks: {e}")
                    
                    # Dangerous attacks
                    if 'Dangerous Attacks' in stats:
                        try:
                            features['home_dangerous'] = int(stats['Dangerous Attacks'].get('home', 0)) if stats['Dangerous Attacks'].get('home', '').isdigit() else 0
                            features['away_dangerous'] = int(stats['Dangerous Attacks'].get('away', 0)) if stats['Dangerous Attacks'].get('away', '').isdigit() else 0
                            features['total_dangerous'] = features['home_dangerous'] + features['away_dangerous']
                        except Exception as e:
                            print(f"Error extracting Dangerous Attacks: {e}")
                            
                except Exception as e:
                    print(f"Error processing livescore stats: {e}")
                    # Ensure basic features are still available even if stats processing fails
                    if 'home_shots' not in features: features['home_shots'] = 0
                    if 'away_shots' not in features: features['away_shots'] = 0
                    if 'total_shots' not in features: features['total_shots'] = 0
                    if 'shots_difference' not in features: features['shots_difference'] = 0
                    
        # Handle liveStats (which has a different structure)
        elif 'liveStats' in row and isinstance(row['liveStats'], dict):
            liveStats = row['liveStats']
            
            # Current minute - fixed to look for 'minute' instead of 'currentMinute'
            minute_str = liveStats.get('minute')
            if minute_str:
                if isinstance(minute_str, str) and minute_str.isdigit():
                    features['current_minute'] = int(minute_str)
                    features['game_status'] = 'live'  # If minute is present in liveStats, game is live
                # Handle special minute values
                elif minute_str == 'HT':
                    features['current_minute'] = 45
                    features['game_status'] = 'live'  # Mark HT as live
                elif minute_str == 'FT':
                    features['current_minute'] = 90
                    features['game_status'] = 'finished'  # Mark FT as finished
                else:
                    # Try to extract numbers from strings like "45+2" or "2nd half"
                    import re
                    numbers = re.findall(r'\d+', minute_str)
                    if numbers:
                        features['current_minute'] = int(numbers[0])
                        # If detected minute is < 90, consider game live
                        if features['current_minute'] < 90:
                            features['game_status'] = 'live'
            
            # If liveStats has isLive flag, respect it
            if liveStats.get('isLive') == True:
                features['game_status'] = 'live'
            elif liveStats.get('isCompleted') == True:
                features['game_status'] = 'finished'
            
            # Get current goals from liveStats
            if 'score' in liveStats:
                try:
                    score = liveStats['score']
                    if isinstance(score, str) and ' - ' in score:
                        home_score, away_score = score.split(' - ')
                        features['home_score'] = int(home_score)
                        features['away_score'] = int(away_score)
                        features['total_score'] = features['home_score'] + features['away_score']
                        features['score_difference'] = features['home_score'] - features['away_score'] 
                except:
                    features['home_score'] = features['away_score'] = features['total_score'] = features['score_difference'] = 0
            
            # Extract stats from liveStats if available
            if 'stats' in liveStats and isinstance(liveStats['stats'], dict):
                stats = liveStats['stats']
                
                # Shots on target
                if 'Shots On Target' in stats and isinstance(stats['Shots On Target'], dict):
                    shots_home = stats['Shots On Target'].get('home', '0')
                    shots_away = stats['Shots On Target'].get('away', '0')
                    
                    if isinstance(shots_home, str) and shots_home.isdigit():
                        features['home_shots_on_target'] = int(shots_home)
                    if isinstance(shots_away, str) and shots_away.isdigit():
                        features['away_shots_on_target'] = int(shots_away)
                    
                    features['total_shots_on_target'] = features.get('home_shots_on_target', 0) + features.get('away_shots_on_target', 0)
                
                # Total shots
                if 'Shots Total' in stats and isinstance(stats['Shots Total'], dict):
                    shots_home = stats['Shots Total'].get('home', '0')
                    shots_away = stats['Shots Total'].get('away', '0')
                    
                    if isinstance(shots_home, str) and shots_home.isdigit():
                        features['home_shots'] = int(shots_home)
                    if isinstance(shots_away, str) and shots_away.isdigit():
                        features['away_shots'] = int(shots_away)
                    
                    features['total_shots'] = features.get('home_shots', 0) + features.get('away_shots', 0)

        # Include additional check for liveStats at the root level
        if 'liveStats' in row and not features.get('current_minute') and isinstance(row['liveStats'], dict):
            is_live = row['liveStats'].get('isLive')
            if is_live:
                features['game_status'] = 'live'

        # Team stats
        if 'teamOverviews' in row and isinstance(row['teamOverviews'], dict):
            try:
                print(f"Processing teamOverviews for game {idx}")  # Debug info
                
                home_team = row['teamOverviews'].get('home', {})
                away_team = row['teamOverviews'].get('away', {})
                
                # Win percentages
                try:
                    if home_team and isinstance(home_team, dict) and home_team.get('stats', {}).get('winPercent'):
                        win_percent_str = str(home_team['stats']['winPercent'].get('home', '0%'))
                        features['home_win_pct'] = float(win_percent_str.replace('%', '')) / 100
                    else:
                        features['home_win_pct'] = 0
                except Exception as e:
                    print(f"Error extracting home win percentage: {e}")
                    features['home_win_pct'] = 0
                
                try:
                    if away_team and isinstance(away_team, dict) and away_team.get('stats', {}).get('winPercent'):
                        win_percent_str = str(away_team['stats']['winPercent'].get('away', '0%'))
                        features['away_win_pct'] = float(win_percent_str.replace('%', '')) / 100
                    else:
                        features['away_win_pct'] = 0
                except Exception as e:
                    print(f"Error extracting away win percentage: {e}")
                    features['away_win_pct'] = 0
                
                # Expected goals
                try:
                    if home_team and isinstance(home_team, dict) and home_team.get('stats', {}).get('xg'):
                        home_xg_val = home_team['stats']['xg'].get('home', 0)
                        features['home_xg'] = float(home_xg_val) if home_xg_val else 0
                    else:
                        features['home_xg'] = 0
                except Exception as e:
                    print(f"Error extracting home xG: {e}")
                    features['home_xg'] = 0
                
                try:
                    if away_team and isinstance(away_team, dict) and away_team.get('stats', {}).get('xg'):
                        away_xg_val = away_team['stats']['xg'].get('away', 0)
                        features['away_xg'] = float(away_xg_val) if away_xg_val else 0
                    else:
                        features['away_xg'] = 0
                except Exception as e:
                    print(f"Error extracting away xG: {e}")
                    features['away_xg'] = 0
                    
                # Clean sheets
                try:
                    if home_team and isinstance(home_team, dict) and home_team.get('stats', {}).get('cs'):
                        cs_str = str(home_team['stats']['cs'].get('home', '0%'))
                        features['home_cleansheet_pct'] = float(cs_str.replace('%', '')) / 100
                    else:
                        features['home_cleansheet_pct'] = 0
                except Exception as e:
                    print(f"Error extracting home clean sheet percentage: {e}")
                    features['home_cleansheet_pct'] = 0
                
                try:
                    if away_team and isinstance(away_team, dict) and away_team.get('stats', {}).get('cs'):
                        cs_str = str(away_team['stats']['cs'].get('away', '0%'))
                        features['away_cleansheet_pct'] = float(cs_str.replace('%', '')) / 100
                    else:
                        features['away_cleansheet_pct'] = 0
                except Exception as e:
                    print(f"Error extracting away clean sheet percentage: {e}")
                    features['away_cleansheet_pct'] = 0
                
            except Exception as e:
                print(f"Error processing teamOverviews: {e}")
                # Ensure all team stats features have default values
                features['home_win_pct'] = features.get('home_win_pct', 0)
                features['away_win_pct'] = features.get('away_win_pct', 0)
                features['home_xg'] = features.get('home_xg', 0)
                features['away_xg'] = features.get('away_xg', 0)
                features['home_cleansheet_pct'] = features.get('home_cleansheet_pct', 0)
                features['away_cleansheet_pct'] = features.get('away_cleansheet_pct', 0)
        
        # Prediction stats
        if 'predictionStats' in row and isinstance(row['predictionStats'], dict):
            pred_stats = row['predictionStats']
            
            features['pred_avg_goals'] = float(pred_stats.get('avgTotalGoals', 0))
            features['pred_avg_corners'] = float(pred_stats.get('avgCorners', 0))
            features['pred_over25_pct'] = float(pred_stats.get('predictedOver2_5', 0)) / 100
            features['pred_btts_pct'] = float(pred_stats.get('predictedBTTS', 0)) / 100
            
        # Goals by minute data
        if 'goalsByMinute' in row and isinstance(row['goalsByMinute'], dict) and 'teams' in row['goalsByMinute']:
            teams = row['goalsByMinute']['teams']
            
            # Late goals tendency (61-90 mins)
            for team_name, team_data in teams.items():
                if team_name == row.get('homeTeam') and 'scored_15_min' in team_data:
                    late_goals = float(str(team_data['scored_15_min'].get('61 - 75 Mins', '0%')).replace('%', '')) / 100
                    late_goals += float(str(team_data['scored_15_min'].get('76 - 90 Mins', '0%')).replace('%', '')) / 100
                    features['home_late_goals_tendency'] = late_goals / 2  # average of the two periods
                
                if team_name == row.get('awayTeam') and 'scored_15_min' in team_data:
                    late_goals = float(str(team_data['scored_15_min'].get('61 - 75 Mins', '0%')).replace('%', '')) / 100
                    late_goals += float(str(team_data['scored_15_min'].get('76 - 90 Mins', '0%')).replace('%', '')) / 100
                    features['away_late_goals_tendency'] = late_goals / 2  # average of the two periods
        
        # Ensure only numeric features are added for modeling
        # Remove or skip any feature that is not numeric (e.g., 'game_status')
        # Add this after all feature extraction, before appending to new_features:
        # Remove non-numeric features (like 'game_status') for modeling
        features_clean = {k: v for k, v in features.items() if isinstance(v, (int, float, np.integer, np.floating))}
        # Optionally, keep 'game_status' for diagnostics, but not for modeling
        features_clean['game_status'] = features.get('game_status', None)
        new_features.append(features_clean)
    
    # Convert list of dictionaries to DataFrame
    features_df = pd.DataFrame(new_features)
    
    # Fill any NaN values
    features_df = features_df.fillna(0)
    
    # DEBUG: Final check of features created
    print(f"DEBUG: Final feature columns: {list(features_df.columns)}")
    print(f"DEBUG: Has current_minute column: {'current_minute' in features_df.columns}")
    print(f"DEBUG: Has live data in any row: {has_live_data}")
    
    return features_df

def analyze_with_pycaret(historical_df, target_df, target_variable='success'):
    """
    Performs PyCaret analysis with historical data and predicts outcome for a target game.
    
    Args:
        historical_df (pd.DataFrame): DataFrame with historical games data
        target_df (pd.DataFrame): DataFrame with the target game data
        target_variable (str): Target column name to predict
        
    Returns:
        tuple: (prediction, best_model, model_name) or (None, None, None) on error
    """
    pycaret_prediction = None
    best_model = None
    model_name = None
    
    try:
        print(f"\n--- PyCaret Analysis ---")
        print(f"Historical data: {historical_df.shape[0]} rows, {historical_df.shape[1]} columns")
        print(f"Target data: {target_df.shape[0]} rows, {target_df.shape[1]} columns")
        
        if historical_df.empty:
            print("Historical DataFrame is empty. Cannot perform PyCaret analysis.")
            return None, None, None
        
        # ADDED: Extract advanced features from both historical and target data
        print("Extracting advanced features from historical data...")
        historical_features_df = extract_advanced_features(historical_df)
        print(f"Extracted {historical_features_df.shape[1]} features from historical data")
        
        print("Extracting advanced features from target data...")
        # --- PATCH: Always use extract_advanced_features on the RAW target_df (with all fields) ---
        # If target_df is already flattened/numeric, re-fetch the raw document or ensure liveStats is present
        # This ensures current_minute and other live features are extracted
        target_features_df = extract_advanced_features(target_df)
        print(f"Extracted {target_features_df.shape[1]} features from target data")
        
        # Add the target column to the historical features
        if target_variable in historical_df.columns:
            historical_features_df[target_variable] = historical_df[target_variable]
        else:
            print(f"ERROR: Target column '{target_variable}' not found in historical data.")
            print(f"Available columns: {historical_df.columns.tolist()}")
            return None, None, None
        
        # Check class distribution
        target_values = historical_features_df[target_variable].value_counts().to_dict()
        print(f"Target distribution: {target_values}")
        
        # Need both True and False values for binary classification
        if len(target_values) < 2:
            print(f"ERROR: Target variable has only one class: {target_values}")
            # Check if we have enough examples to create a dummy class
            if len(historical_features_df) >= 5:
                # ...existing code for synthetic examples...
                print("Creating synthetic examples to create a second class...")
                main_class = list(target_values.keys())[0]
                synthetic_class = not main_class
                synthetic_df = historical_features_df.iloc[:min(5, len(historical_features_df))].copy()
                synthetic_df[target_variable] = synthetic_class
                historical_features_df = pd.concat([historical_features_df, synthetic_df], ignore_index=True)
                print(f"New target distribution: {historical_features_df[target_variable].value_counts().to_dict()}")
            else:
                print("Not enough data to create synthetic examples.")
                return None, None, None
        
        # Check feature compatibility between the two feature sets
        try:
            # Ensure column compatibility - use only features present in both datasets
            historical_feature_cols = set(historical_features_df.columns) - {target_variable}
            target_feature_cols = set(target_features_df.columns)
            
            common_features = list(historical_feature_cols.intersection(target_feature_cols))
            print(f"Using {len(common_features)} common advanced features")
            
            # DEBUG: Check if current_minute survives feature selection
            print(f"DEBUG: current_minute in historical_features_df: {'current_minute' in historical_features_df.columns}")
            print(f"DEBUG: current_minute in target_features_df: {'current_minute' in target_features_df.columns}")
            print(f"DEBUG: current_minute in common_features: {'current_minute' in common_features}")
            
            if not common_features:
                print("ERROR: No common features between historical and target data")
                # Print some sample column names to help debug
                print(f"Historical feature columns (first 5): {list(historical_feature_cols)[:5]}")
                print(f"Target feature columns (first 5): {list(target_feature_cols)[:5]}")
                return None, None, None
            
            # Create clean copies with only common features (plus target for historical)
            historical_clean = historical_features_df[common_features + [target_variable]].copy()
            target_clean = target_features_df[common_features].copy()
            
            # Ensure no string columns are kept for modeling
            string_columns = []
            for col in historical_clean.columns:
                if col == target_variable:
                    continue
                if historical_clean[col].dtype == object or target_clean[col].dtype == object:
                    string_columns.append(col)
            
            if string_columns:
                print(f"WARNING: Removing string columns from modeling: {string_columns}")
                for col in string_columns:
                    if col in historical_clean.columns and col != target_variable:
                        historical_clean = historical_clean.drop(columns=[col])
                    if col in target_clean.columns:
                        target_clean = target_clean.drop(columns=[col])
            
            print(f"Final historical data shape for modeling: {historical_clean.shape}")
            print(f"Final target data shape for prediction: {target_clean.shape}")
            print(f"Final features being used: {[col for col in historical_clean.columns if col != target_variable]}")
        
        except Exception as e:
            print(f"Error during feature compatibility check: {e}")
            traceback.print_exc()
            return None, None, None
        
        # Final sanity check for NaN values
        hist_nan_count = historical_clean.isna().sum().sum()
        target_nan_count = target_clean.isna().sum().sum()
        
        if hist_nan_count > 0:
            print(f"WARNING: Historical data still has {hist_nan_count} NaN values. Filling with 0...")
            historical_clean = historical_clean.fillna(0)
            
        if target_nan_count > 0:
            print(f"WARNING: Target data still has {target_nan_count} NaN values. Filling with 0...")
            target_clean = target_clean.fillna(0)
        
        # Try methods in order until one works
        methods = ["experiment_api", "classic_api", "direct_model"]
        success = False
        
        for method in methods:
            if success:
                break
                
            print(f"\nTrying method: {method}")
            try:
                if method == "experiment_api":
                    # Explicitly create experiment for better control
                    exp = ClassificationExperiment()
                    # Remove 'silent' parameter which is causing errors
                    setup_results = exp.setup(
                        data=historical_clean, 
                        target=target_variable, 
                        session_id=456,
                        # silent=True,  # Remove this line
                        verbose=False,
                        n_jobs=-1,  # Use all cores
                        fold=5,      # 5-fold cross-validation
                        use_gpu=False,
                        html=False,
                        log_experiment=False,
                        fix_imbalance=True   # Handle class imbalance
                    )
                    
                    print(f"Setup complete. Features used: {len(exp.X_train.columns)}")
                    
                    # Compare models - with exception handling for each step
                    try:
                        best_model = exp.compare_models(n_select=1, exclude=['gbc', 'lightgbm', 'catboost'])
                        
                        # Handle case of multiple models vs single model
                        if isinstance(best_model, list):
                            best_model = best_model[0]
                            
                        model_name = type(best_model).__name__
                        print(f"Best model: {model_name}")
                    except Exception as model_error:
                        print(f"Error comparing models: {model_error}")
                        print("Trying to create a simple model instead...")
                        try:
                            # Try a simple model like Random Forest
                            best_model = exp.create_model('rf')
                            model_name = "RandomForestClassifier (fallback)"
                            print(f"Created fallback model: {model_name}")
                        except Exception as simple_error:
                            print(f"Error creating simple model: {simple_error}")
                            raise  # Re-raise to try next method
                    
                    # Prediction
                    prediction_df = exp.predict_model(best_model, data=target_clean)
                    
                    # Extract prediction 
                    pred_col = next((col for col in prediction_df.columns if 'prediction' in col.lower() or col == 'Label'), None)
                    
                    if pred_col:
                        pycaret_prediction = prediction_df[pred_col].iloc[0]
                        if hasattr(pycaret_prediction, 'item'):
                            pycaret_prediction = pycaret_prediction.item()
                        print(f"PyCaret Prediction: {pycaret_prediction}")
                        success = True
                    else:
                        print("Could not find prediction column in output")
                        raise ValueError("Prediction column not found")
                        
                elif method == "classic_api":
                    # Try the classic setup API
                    print("Using classic PyCaret API...")
                    # Remove 'silent' parameter which is causing errors
                    setup_classic = setup(
                        data=historical_clean,
                        target=target_variable,
                        session_id=123,
                        # silent=True,  # Remove this line
                        verbose=False,
                        fix_imbalance=True
                    )
                    
                    # Try simpler models first
                    for model_name in ['lr', 'dt', 'rf']:
                        try:
                            print(f"Creating model: {model_name}")
                            best_model = create_model(model_name)
                            model_name = f"{model_name}_classic"
                            
                            # Predict
                            prediction_df = predict_model(best_model, data=target_clean)
                            pred_col = next((col for col in prediction_df.columns if 'prediction' in col.lower() or col == 'Label'), None)
                            
                            if pred_col:
                                pycaret_prediction = prediction_df[pred_col].iloc[0]
                                if hasattr(pycaret_prediction, 'item'):
                                    pycaret_prediction = pycaret_prediction.item()
                                print(f"PyCaret Prediction: {pycaret_prediction}")
                                success = True
                                break
                            else:
                                print(f"No prediction column for {model_name}")
                        except Exception as model_error:
                            print(f"Error with {model_name}: {model_error}")
                
                elif method == "direct_model":
                    # Last resort: Skip PyCaret and use scikit-learn directly
                    print("Using scikit-learn directly...")
                    from sklearn.ensemble import RandomForestClassifier
                    from sklearn.preprocessing import StandardScaler
                    
                    # Prepare data
                    X_train = historical_clean.drop(columns=[target_variable])
                    y_train = historical_clean[target_variable]
                    X_test = target_clean
                    
                    # ADDED: Check for Under X In-Play System criteria
                    meets_under_x_criteria = False
                    under_x_recommendation = ""
                    
                    print("Checking for Under X In-Play System criteria...")
                    print(f"Target data columns: {target_clean.columns.tolist()}")
                    print(f"Target features columns: {target_features_df.columns.tolist()}")
                    print(f"Current time: {target_features_df.get('current_time', None)}")
                    
                    # --- PATCH: More robust handling of current_minute ---
                    current_minute = None
                    
                    # Try different possible sources for current_minute
                    if 'current_minute' in target_features_df.columns:
                        current_minute = target_features_df['current_minute'].iloc[0]
                        print(f"Found current_minute in target_features_df: {current_minute}")
                    elif 'current_minute' in target_clean.columns:
                        current_minute = target_clean['current_minute'].iloc[0]
                        print(f"Found current_minute in target_clean: {current_minute}")
                    else:
                        # Try to get minute from original raw data if available
                        try:
                            if len(target_df) > 0:
                                row = target_df.iloc[0]
                                if 'liveStats' in row and isinstance(row['liveStats'], dict):
                                    minute_val = row['liveStats'].get('minute') or row['liveStats'].get('currentMinute')
                                    if isinstance(minute_val, int):
                                        current_minute = minute_val
                                    elif isinstance(minute_val, str) and minute_val.isdigit():
                                        current_minute = int(minute_val)
                                    print(f"Found current_minute in raw liveStats: {current_minute}")
                                elif 'livescore' in row and isinstance(row['livescore'], dict):
                                    minute_str = row['livescore'].get('minute')
                                    if isinstance(minute_str, str) and minute_str.isdigit():
                                        current_minute = int(minute_str)
                                    print(f"Found current_minute in raw livescore: {current_minute}")
                        except Exception as e:
                            print(f"Error extracting current_minute from raw data: {e}")
                    
                    # Rest of the Under X system criteria check
                    if current_minute is not None:
                        # Check if match is between minute 52-61
                        if 52 <= current_minute <= 61:
                            print(f"✓ Match is in target minute range: {current_minute}")
                            # ... existing code ...
                    else:
                        print("✗ Not a live match or minute not available")
                    # ... existing code ...
                    
                    # Scale features
                    scaler = StandardScaler()
                    X_train_scaled = scaler.fit_transform(X_train)
                    X_test_scaled = scaler.transform(X_test)
                    
                    # Train model with class_weight='balanced' to handle imbalance
                    rf = RandomForestClassifier(
                        n_estimators=100,
                        random_state=42,
                        class_weight='balanced',
                        n_jobs=-1  # Use all CPU cores
                    )
                    rf.fit(X_train_scaled, y_train)
                    
                    # Add more weight to the Under X criteria in the model
                    if meets_under_x_criteria:
                        # If match meets our specific Under X criteria, we want to favor a positive prediction
                        # Override prediction if it meets our specific requirements
                        pycaret_prediction = True
                        print("✅ PREDICTION OVERRIDE: Match meets Under X System criteria")
                    else:
                        # Otherwise use the model's prediction
                        pycaret_prediction = rf.predict(X_test_scaled)[0]
                        if hasattr(pycaret_prediction, 'item'):
                            pycaret_prediction = pycaret_prediction.item()
                    
                    # Get prediction probabilities
                    probabilities = rf.predict_proba(X_test_scaled)[0]
                    # Get probability for predicted class
                    class_idx = 1 if pycaret_prediction else 0  # Will be 0 for False, 1 for True
                    probability = probabilities[class_idx]
                    
                    # Adjust probability if we overrode the prediction
                    if meets_under_x_criteria and not rf.predict(X_test_scaled)[0]:
                        probability = 0.8  # High confidence due to specific system match
                    
                    print(f"Direct Scikit-learn prediction: {pycaret_prediction} with probability: {probability:.2f}")
                    
                    # Store Under X recommendation in model_name if applicable
                    if meets_under_x_criteria:
                        model_name = f"Under X System: {under_x_recommendation}"
                    else:
                        model_name = "RandomForestClassifier (direct)"
                    
                    print(f"Final decision: {'PROCEED' if pycaret_prediction else 'AVOID'} " + 
                          f"- probability {probability:.2f}")
                    success = True
                    
                    # Print feature importance, but abbreviated since we've added Under X system info
                    if len(rf.feature_importances_) > 0 and not meets_under_x_criteria:
                        feature_importance = dict(zip(X_train.columns, rf.feature_importances_))
                        sorted_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5])
                        print("Top 5 important features:")
                        for feature, importance in sorted_importance.items():
                            print(f"  {feature}: {importance:.4f}")
                            
                            # For the top features, show the target game's value
                            if feature in target_clean.columns:
                                value = target_clean[feature].iloc[0]
                                print(f"    Value for target game: {value}")
                    
            except Exception as method_error:
                print(f"Method '{method}' failed: {method_error}")
                # Continue to next method
        
        if not success:
            print("All methods failed. No prediction available.")
            return None, None, None
            
    except Exception as e:
        print(f"\nError during PyCaret analysis: {e}")
        traceback.print_exc()
        return None, None, None
        
    return pycaret_prediction, best_model, model_name
