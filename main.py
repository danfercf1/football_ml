import os
import pandas as pd
from bson import ObjectId
import traceback
from pycaret_analyzer import analyze_with_pycaret
import db_connector

# --- Fix Preprocessing Function ---
def preprocess_data(df, target_col='success', is_target_game=False):
    """Preprocesses the DataFrame for PyCaret with enhanced feature extraction."""
    print(f"Starting preprocessing with {len(df)} rows.")

    # Handle empty DataFrame
    if df.empty:
        print("DataFrame is empty, returning empty DataFrame")
        return pd.DataFrame()

    # Handle potential ObjectId column if not already string
    if '_id' in df.columns:
        df['_id'] = df['_id'].astype(str)

    # Define basic features for backward compatibility
    basic_features = ['homeForm', 'awayForm', 'under25Probability']
    all_features = []  # We'll build this list as we go
    
    # Create a new DataFrame to hold our flattened features
    processed_df = pd.DataFrame(index=df.index)
    
    # Add ID column if it exists
    if '_id' in df.columns:
        processed_df['_id'] = df['_id']
    
    # Direct transfer of simple numeric fields
    for col in basic_features:
        if col in df.columns:
            try:
                # Handle percentage values
                if col == 'under25Probability':
                    processed_df[col] = df[col].astype(str).str.replace('%', '').apply(
                        lambda x: float(x)/100 if x and x.strip() and x.strip().replace('.', '', 1).isdigit() else None
                    )
                else:
                    processed_df[col] = pd.to_numeric(df[col], errors='coerce')
                
                all_features.append(col)
                print(f"Added feature {col} directly")
            except Exception as e:
                print(f"Error processing basic feature {col}: {e}")
    
    # Add team positions as numeric features
    for pos_col in ['homePosition', 'awayPosition']:
        if pos_col in df.columns:
            try:
                processed_df[pos_col] = pd.to_numeric(df[pos_col], errors='coerce')
                all_features.append(pos_col)
                print(f"Added team position feature {pos_col}")
            except Exception as e:
                print(f"Error processing position column {pos_col}: {e}")
    
    # Process prediction stats (nested dictionary field)
    if 'predictionStats' in df.columns:
        print("Processing predictionStats field")
        for idx, row in df.iterrows():
            try:
                pred_stats = row.get('predictionStats', {})
                if pred_stats and isinstance(pred_stats, dict):
                    # Key prediction metrics
                    prediction_features = [
                        ('pred_over15', 'predictedOver1_5', True),  # (column_name, source_key, is_percent)
                        ('pred_over25', 'predictedOver2_5', True),
                        ('pred_btts', 'predictedBTTS', True),
                        ('pred_goals', 'avgTotalGoals', False),
                        ('pred_corners', 'avgCorners', False)
                    ]
                    
                    for feature_name, source_key, is_percent in prediction_features:
                        if source_key in pred_stats:
                            try:
                                value = pred_stats.get(source_key)
                                # Percentage conversion if needed
                                if is_percent and isinstance(value, (int, float)):
                                    value = value / 100
                                elif is_percent and isinstance(value, str) and '%' in value:
                                    value = float(value.replace('%', '')) / 100
                                
                                if feature_name not in processed_df.columns:
                                    processed_df[feature_name] = None
                                    all_features.append(feature_name)
                                    print(f"Added prediction feature {feature_name}")
                                
                                processed_df.at[idx, feature_name] = value
                            except Exception as e:
                                print(f"Error extracting {source_key}: {e}")
            except Exception as e:
                print(f"Error processing predictionStats for row {idx}: {e}")
    
    # Process H2H stats (nested dictionary field)
    if 'h2hStats' in df.columns:
        print("Processing h2hStats field")
        for idx, row in df.iterrows():
            try:
                h2h = row.get('h2hStats', {})
                if h2h and isinstance(h2h, dict):
                    # Key H2H metrics
                    h2h_features = [
                        ('h2h_homeWin', 'h2hHomeWinPercentage', True),
                        ('h2h_awayWin', 'h2hAwayWinPercentage', True),
                        ('h2h_over25', 'h2hOver2_5', True),
                        ('h2h_btts', 'h2hBTTS', True)
                    ]
                    
                    for feature_name, source_key, is_percent in h2h_features:
                        if source_key in h2h:
                            try:
                                value = h2h.get(source_key)
                                if is_percent and isinstance(value, (int, float)):
                                    value = value / 100
                                    
                                if feature_name not in processed_df.columns:
                                    processed_df[feature_name] = None
                                    all_features.append(feature_name)
                                    print(f"Added H2H feature {feature_name}")
                                
                                processed_df.at[idx, feature_name] = value
                            except Exception as e:
                                print(f"Error extracting {source_key}: {e}")
            except Exception as e:
                print(f"Error processing h2hStats for row {idx}: {e}")
    
    # Add team form indicators from currentForm if available
    if 'currentForm' in df.columns:
        print("Processing currentForm field")
        for idx, row in df.iterrows():
            try:
                form_data = row.get('currentForm', {})
                if isinstance(form_data, dict):
                    # Calculate recent form metrics
                    if 'homeCurrentForm' in form_data and isinstance(form_data['homeCurrentForm'], list):
                        home_wins = sum(1 for match in form_data['homeCurrentForm'] 
                                      if isinstance(match, dict) and 'score' in match
                                      and match['score'].split(' - ')[0] > match['score'].split(' - ')[1])
                        if 'home_recent_wins' not in processed_df.columns:
                            processed_df['home_recent_wins'] = None
                            all_features.append('home_recent_wins')
                        processed_df.at[idx, 'home_recent_wins'] = home_wins
                    
                    if 'awayCurrentForm' in form_data and isinstance(form_data['awayCurrentForm'], list):
                        away_wins = sum(1 for match in form_data['awayCurrentForm']
                                      if isinstance(match, dict) and 'score' in match
                                      and match['score'].split(' - ')[1] > match['score'].split(' - ')[0])
                        if 'away_recent_wins' not in processed_df.columns:
                            processed_df['away_recent_wins'] = None
                            all_features.append('away_recent_wins')
                        processed_df.at[idx, 'away_recent_wins'] = away_wins
            except Exception as e:
                print(f"Error processing currentForm for row {idx}: {e}")
    
    # Add target column for training data
    if not is_target_game and target_col in df.columns:
        print(f"Adding target column {target_col}")
        try:
            # First, simply copy the target column
            processed_df[target_col] = df[target_col]
            
            # Then convert to boolean if it's not already
            if processed_df[target_col].dtype != bool:
                # For mixed data types, try converting to numeric first, then boolean
                processed_df[target_col] = pd.to_numeric(processed_df[target_col], errors='coerce')
                # Replace NaN values with False to avoid losing rows
                processed_df.loc[processed_df[target_col].isna(), target_col] = False
                # Convert to boolean
                processed_df[target_col] = processed_df[target_col].astype(bool)
                print(f"Converted {target_col} to boolean")
        except Exception as e:
            print(f"Error processing target column: {e}")
            # If conversion fails, create a dummy target column with all False values
            # This is better than losing all the data
            print(f"Creating dummy {target_col} column with False values")
            processed_df[target_col] = False
    
    # Fill missing values with median or 0
    for col in all_features:
        if col in processed_df.columns and processed_df[col].isnull().any():
            non_null_count = processed_df[col].count()
            null_count = processed_df[col].isnull().sum()
            print(f"Column {col} has {null_count} null values out of {len(processed_df)}")
            
            # Only use median if we have enough non-null values
            if non_null_count > 5:
                median_val = processed_df[col].median()
                if pd.notnull(median_val):
                    processed_df[col].fillna(median_val, inplace=True)
                    print(f"Filled {col} nulls with median: {median_val}")
                else:
                    processed_df[col].fillna(0, inplace=True)
                    print(f"Filled {col} nulls with 0 (median was null)")
            else:
                # Default to 0 if we have very few values
                processed_df[col].fillna(0, inplace=True)
                print(f"Filled {col} nulls with 0 (too few values for median)")
    
    # Final check for any remaining NaN values
    print(f"Final processed DataFrame has {len(processed_df)} rows and {len(all_features)} features")
    nan_counts = processed_df[all_features].isna().sum().sum()
    if nan_counts > 0:
        print(f"WARNING: Still have {nan_counts} NaN values in features. Filling with 0...")
        processed_df[all_features] = processed_df[all_features].fillna(0)
    
    # For historical data, check if we have any valid target values
    if not is_target_game and target_col in processed_df.columns:
        true_count = processed_df[target_col].sum()
        false_count = len(processed_df) - true_count
        print(f"Target distribution: {true_count} True, {false_count} False")
    
    # NOTE: This function currently does NOT flatten or extract features from nested 'liveStats', 'livescore', or similar fields.
    # It only copies 'currentMinute' from 'livescore' to 'liveStats' if 'liveStats' is missing.
    # All advanced feature extraction from 'liveStats', 'livescore', etc. is handled in pycaret_analyzer.extract_advanced_features,
    # which is called later in the pipeline.

    return processed_df

def analyze_game(target_game_id):
    """
    Main analysis function that can be called with a target game ID.
    Uses db_connector to retrieve data, performs analysis and returns results.
    
    Args:
        target_game_id (str): MongoDB ObjectId as string
        
    Returns:
        dict: Analysis results including prediction and decision
    """
    target_game_data = None
    historical_df = pd.DataFrame()
    target_variable = 'success'
    pycaret_prediction = None
    model_name = None
    current_minute = None
    avoid_game_live = False
    final_decision = "PROCEED (Default)"
    decision_reason = "No analysis performed"
    error_message = None
    
    try:
        # Fetch target game data using the DB connector
        print(f"Analyzing game with ID: {target_game_id}")
        target_game_data = db_connector.get_game_data(target_game_id)
        
        if not target_game_data:
            raise ValueError(f"No game found with _id: {target_game_id}")
        
        print(f"Target game loaded: {target_game_data.get('match', 'N/A')}")
        
        # Get historical data using the DB connector
        historical_data = db_connector.get_historical_games(target_game_data)
        
        if historical_data:
            historical_df = pd.DataFrame(historical_data)
            historical_df.drop_duplicates(subset=['_id'], inplace=True)
            print(f"Created historical DataFrame with {len(historical_df)} unique games.")
            
            # Check if we have success field in historical data
            if 'success' in historical_df.columns:
                success_count = historical_df['success'].sum()
                print(f"Found {success_count} successful entries in historical data")
            else:
                print("WARNING: 'success' column not found in historical data")
        else:
            print("No relevant historical data found for PyCaret analysis.")
            
        # Preprocess historical data
        print("\nPreprocessing historical data...")
        try:
            historical_df_processed = preprocess_data(historical_df.copy(), target_col=target_variable) if not historical_df.empty else pd.DataFrame()
            if historical_df_processed.empty and not historical_df.empty:
                print("WARNING: Historical data exists but preprocessing resulted in empty DataFrame")
        except Exception as e:
            print(f"Error preprocessing historical data: {e}")
            historical_df_processed = pd.DataFrame()
            traceback.print_exc()
        
        # Preprocess target game data
        print("\nPreprocessing target game features...")
        target_df = pd.DataFrame([target_game_data])

        # --- PATCH: Ensure target_df includes all raw fields for advanced feature extraction ---
        # Do NOT flatten or drop nested fields before passing to extract_advanced_features!
        # Pass the raw target_df to analyze_with_pycaret (which calls extract_advanced_features)
        target_df_features = target_df  # Pass raw DataFrame, not preprocessed/flattened

        # Call PyCaret analyzer if we have historical data
        if not historical_df_processed.empty:
            try:
                # --- ENHANCED PATCH: Better handling of non-numeric values ---
                def drop_non_numeric(df):
                    # First, explicitly print column types for debugging
                    print("\nColumn types before filtering:")
                    for col in df.columns:
                        print(f"  {col}: {df[col].dtype} (sample: {df[col].iloc[0] if len(df) > 0 else 'empty'})")
                    
                    # Drop columns that are not numeric (except for the target variable)
                    numeric_cols = []
                    for col in df.columns:
                        # Keep target variable regardless of type
                        if col == target_variable:
                            numeric_cols.append(col)
                            continue
                            
                        # For other columns, only keep numeric types
                        if pd.api.types.is_numeric_dtype(df[col]):
                            numeric_cols.append(col)
                        else:
                            print(f"  Dropping non-numeric column: {col} (type: {df[col].dtype})")
                    
                    # Always explicitly exclude troublesome columns
                    for exclude_col in ['status', 'game_status']:
                        if exclude_col in numeric_cols:
                            numeric_cols.remove(exclude_col)
                            print(f"  Explicitly removing {exclude_col} column")
                    
                    return df[numeric_cols]

                # Process the historical data frame
                print("\nFiltering historical DataFrame for numeric columns only")
                historical_df_numeric = drop_non_numeric(historical_df_processed)
                
                # Process the target data frame - ensuring nested fields are removed
                print("\nFiltering target DataFrame for numeric columns only")
                
                # First, extract only the simple columns from raw target data
                target_df_basic = pd.DataFrame()
                for col in target_df_features.columns:
                    # Skip any dict or list columns which might contain nested complex structures
                    if isinstance(target_df_features[col].iloc[0], (dict, list)) if len(target_df_features) > 0 else False:
                        print(f"  Skipping complex column: {col}")
                        continue
                    target_df_basic[col] = target_df_features[col]
                
                # Now filter for numeric columns only
                target_df_numeric = drop_non_numeric(target_df_basic)
                
                # Debug: Final check before sending to model
                print("\nFinal DataFrame structures:")
                print(f"  Historical: {historical_df_numeric.shape}, columns: {historical_df_numeric.columns.tolist()}")
                print(f"  Target: {target_df_numeric.shape}, columns: {target_df_numeric.columns.tolist()}")
                
                if target_df_numeric.empty or historical_df_numeric.empty:
                    print("ERROR: Empty DataFrames after processing! Cannot proceed with modeling.")
                    raise ValueError("Empty DataFrame after processing")

                # Finally, call PyCaret with clean, numeric-only DataFrames
                pycaret_prediction, _, model_name = analyze_with_pycaret(
                    historical_df_numeric, 
                    target_df_numeric,
                    target_variable
                )
                if pycaret_prediction is None:
                    print("PyCaret returned None prediction despite having historical data")
            except Exception as e:
                print(f"Error during PyCaret analysis: {e}")
                traceback.print_exc()
        
        # Live game analysis - check both liveStats and livescore fields
        live_data_source = None
        if 'liveStats' in target_game_data:
            live_stats = target_game_data['liveStats']
            current_minute = live_stats.get('currentMinute')
            live_data_source = 'liveStats'
        elif 'livescore' in target_game_data:
            live_stats = target_game_data['livescore']
            current_minute = live_stats.get('minute')
            live_data_source = 'livescore'
            
        if live_data_source:
            print(f"\nAnalyzing live stats from {live_data_source}...")
            if current_minute is not None:
                # Try to convert string minutes to int
                if isinstance(current_minute, str) and current_minute.isdigit():
                    current_minute = int(current_minute)
                
                print(f"  Current Minute: {current_minute} (type: {type(current_minute).__name__})")
                if isinstance(current_minute, (int, float)) and current_minute > 70:
                    avoid_game_live = True
                    print("  Live Decision: Avoid game (minute > 70)")
                else:
                    print("  Live Decision: Do not avoid game (minute <= 70 or not numeric)")
            else:
                print(f"  Could not determine current minute from {live_data_source}")
        else:
            print("\nNo live stats found for this game (neither liveStats nor livescore field found).")
        
        # Check game status even if no live data is available
        game_status = target_game_data.get('status', '').lower()
        print(f"Game status: {game_status}")
        
        # If game is in-progress but no live data, try to determine stage from status
        if not live_data_source and game_status in ['in-progress', 'live', 'playing']:
            print("Game appears to be in progress based on status field")
            
            # Check for a minute indicator in the status field
            # Some systems put minute in status like "45'" or "HT"
            if game_status.isdigit():
                current_minute = int(game_status)
                live_data_source = 'status'
            elif "'" in game_status:
                try:
                    # Extract minute from status like "45'"
                    current_minute = int(game_status.split("'")[0])
                    live_data_source = 'status'
                except:
                    pass
                
        # Enhanced live game analysis with minute inference
        if live_data_source:
            pass
        elif game_status in ['in-progress', 'live', 'playing']:
            print("\nGame appears to be live but no minute information available.")
        else:
            print("\nGame does not appear to be live based on available data.")
            
            # If this is a pre-game analysis, note that
            if game_status in ['scheduled', 'not-started', 'upcoming']:
                print("This appears to be a pre-game analysis.")
                decision_reason = "Pre-game analysis (no live data needed)"
                
        # Make final decision - enhanced with status awareness
        if avoid_game_live:
            final_decision = "AVOID"
            decision_reason = f"Live Minute ({current_minute}) > 70"
        elif game_status in ['in-progress', 'live', 'playing'] and current_minute is None:
            # If game is live but we don't know the minute, be cautious
            final_decision = "CAUTION"
            decision_reason = "Game is live but minute is unknown"
        elif pycaret_prediction is not None:
            if pycaret_prediction == False:
                final_decision = "AVOID"
                decision_reason = f"PyCaret ({model_name}) predicts {target_variable}=False"
            else:
                final_decision = "PROCEED"
                decision_reason = f"PyCaret ({model_name}) predicts {target_variable}=True"
        else:
            if game_status in ['scheduled', 'not-started', 'upcoming']:
                decision_reason = "Pre-game analysis - proceed unless model suggests otherwise"
            else:
                decision_reason = "No definitive signal (insufficient data or no prediction)"
        
    except ValueError as ve:
        error_message = str(ve)
        print(f"Value Error: {error_message}")
    except Exception as e:
        error_message = str(e)
        print(f"Error during analysis: {error_message}")
        traceback.print_exc()
    
    # Prepare and return results
    result = {
        "game_id": target_game_id,
        "match": target_game_data.get('match', 'N/A') if target_game_data else 'N/A',
        "current_minute": current_minute,
        "model_used": model_name,
        "prediction_target": target_variable if pycaret_prediction is not None else None,
        "prediction_value": pycaret_prediction,
        "final_decision": final_decision,
        "decision_reason": decision_reason,
        "error": error_message,
        "game_status": game_status if 'game_status' in locals() else None,
        "diagnostics": {
            "historical_games_count": len(historical_df) if not historical_df.empty else 0,
            "historical_processed_count": len(historical_df_processed) if not historical_df_processed.empty else 0,
            "live_data_source": live_data_source,
            "has_target_features": not target_df_features.empty,
            "available_fields": list(target_game_data.keys()) if target_game_data else [],
            "game_status": game_status if 'game_status' in locals() else None,
            "prediction_stats_available": 'predictionStats' in target_game_data if target_game_data else False,
            "h2h_stats_available": 'h2hStats' in target_game_data if target_game_data else False
        }
    }
    
    return result

# Test function - only for direct script execution
if __name__ == "__main__":
    # Example usage when running main.py directly
    test_id = "67fab4a1a6155bd60617b8f2"  # Example ID
    print(f"\nRunning test analysis with ID: {test_id}")
    result = analyze_game(test_id)
    print("\nAnalysis Result:")
    for key, value in result.items():
        print(f"{key}: {value}")
