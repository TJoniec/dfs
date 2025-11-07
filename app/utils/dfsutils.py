import pandas as pd
import re
from fuzzywuzzy import fuzz, process
import re

rank_thresholds = [12, 24, 36, 448, 60] # Including 66 to catch everyone below 48

def fill_nan_in_column(df, column_name, fill_value):
  """
  Replaces NaN values in a specified DataFrame column with a given value.

  Args:
    df (pd.DataFrame): The input DataFrame.
    column_name (str): The name of the column to modify.
    fill_value: The value to replace NaN with.

  Returns:
    pd.DataFrame: The DataFrame with NaN values filled in the specified column.
  """
  if column_name not in df.columns:
    print(f"Warning: Column '{column_name}' not found in the DataFrame.")
    return df

  df[column_name] = df[column_name].fillna(fill_value)
  return df

# Create df_wr_prep from df_projections with specified columns and conditions
def prepare_wr_data(df_projections, df_wr):
    """
    Prepares WR data by merging projections and matchup information.

    Args:
        df_projections (pd.DataFrame): DataFrame containing player projections.
        df_wr (pd.DataFrame): DataFrame containing WR matchup data.

    Returns:
        pd.DataFrame: Processed DataFrame with combined data.
    """
    df_wr_prep = df_projections[df_projections['position'] == 'te'].copy()
    df_wr_prep = df_wr_prep[[
        'playerName',
        'teamName',
        'position',
        'fantasyPoints',
        'recvTargets',
        'recvReceptions',
        'recvTd'
    ]]

    # Ensure unique player entries
    df_wr_prep = df_wr_prep.drop_duplicates(subset=['playerName'])

    # Ensure position is uppercase
    df_wr_prep['position'] = df_wr_prep['position'].str.upper()

    # Select relevant columns from df_wr and rename 'Matchup Score' for merging
    wr_matchup = df_wr[['Name', 'Matchup Score']].rename(columns={'Name': 'playerName', 'Matchup Score': 'MatchupScore'})

    # Ensure unique player entries in wr_matchup dataframe
    wr_matchup = wr_matchup.drop_duplicates(subset=['playerName'])

    # Merge df_wr_prep with wr_matchup on 'playerName', using a left merge to keep all players from df_wr_prep
    df_wr_prep = pd.merge(df_wr_prep, wr_matchup, on='playerName', how='left')

    # Apply the classify_matchup_grade_wr function to the 'MatchupScore' column
    df_wr_prep['MatchupGrade'] = df_wr_prep['MatchupScore'].apply(classify_matchup_grade_wr)

    # Ensure that only unique playerName exists in df_wr_prep after merge
    df_wr_prep = df_wr_prep.drop_duplicates(subset=['playerName'])

    return df_wr_prep


# Example usage (optional - can be removed if you just want the function definition)
# df_wr_prep = prepare_wr_data(df_projections, df_wr)
# print("WR Prep Data with Matchup Scores and Grades:")
# display(df_wr_prep)

# Example usage:
# df_with_nan_filled = fill_nan_in_column(my_dataframe, 'MyColumn', 0)
# display(df_with_nan_filled)

#import re
#import pandas as pd
#from fuzzywuzzy import fuzz, process

def fuzzy_match_and_merge(
    optimizer_df: pd.DataFrame,
    millimaker_df: pd.DataFrame,
    name_col: str = "playerName",
    mm_name_col: str = "Player",
    min_score: int = 90,           # tighten/loosen as needed
    use_pool: list[str] | None = None,   # optionally restrict optimizer rows to a set/list of names
    keep_cols_from_mm: list[str] | None = None  # e.g., ["ActualFPTS", "%Drafted"]
):
    """
    Merge optimizer_df with millimaker_df by player name with a robust exact+fuzzy pipeline.
    Returns (merged_df, diagnostics_dict).
    """

    def _norm(s: str) -> str:
        if pd.isna(s): return ""
        s = s.lower().strip()
        s = re.sub(r"[^a-z0-9 ]+", "", s)   # drop punctuation
        s = re.sub(r"\s+", " ", s)
        return s

    odf = optimizer_df.copy()
    mdf = millimaker_df.copy()

    if use_pool is not None:
        pool_set = set(use_pool)
        odf = odf[odf[name_col].isin(pool_set)].copy()

    # Normalize names
    odf["_name_norm"] = odf[name_col].map(_norm)
    mdf["_name_norm"] = mdf[mm_name_col].map(_norm)

    # Columns to keep from millimaker side - Define AFTER _name_norm is added
    if keep_cols_from_mm is None:
        keep_cols_from_mm = [c for c in mdf.columns if c not in {mm_name_col, "_name_norm"}]
    mm_keep = [mm_name_col, "_name_norm"] + keep_cols_from_mm

    # 1) Exact join on normalized name
    exact = odf.merge(mdf[mm_keep], on="_name_norm", how="left", suffixes=("", "_mm"))
    exact_hit_mask = exact[mm_name_col].notna()
    exact_hits = exact[exact_hit_mask].copy()
    exact_misses = exact[~exact_hit_mask].copy()

    # 2) Fuzzy match remaining optimizer rows to remaining MM candidates
    #    Exclude already-used MM names to improve 1-1 mapping.
    used_mm = set(exact_hits[mm_name_col].dropna().tolist())
    # Ensure _name_norm is included in the columns when creating cand
    cand = mdf[~mdf[mm_name_col].isin(used_mm)][mm_keep].copy()

    # --- Debugging prints ---
    # print("--- Debugging cand DataFrame ---")
    # print("cand columns:", cand.columns)
    # print("cand head:", cand.head())
    # print("mm_keep:", mm_keep)
    # print("--- End Debugging ---")

    # Build quick lookups - Alternative approach avoiding set_index
    choices = cand["_name_norm"].tolist()
    # Check if _name_norm is in cand before proceeding
    if "_name_norm" not in cand.columns:
         # This should not happen based on previous debugging, but as a safeguard:
         raise KeyError("'_name_norm' column is unexpectedly missing from 'cand' DataFrame.")
    norm_to_mmrow = {row["_name_norm"]: row.drop("_name_norm").to_dict() for _, row in cand[mm_keep].iterrows()}


    fuzzy_rows = []
    for idx, row in exact_misses.iterrows():
        query = row["_name_norm"]
        if not query:
            continue
        # scorer: WRatio is robust; token_set_ratio is also fine
        match = process.extractOne(query, choices, scorer=fuzz.WRatio)
        if match is None:
            continue
        best_norm, score = match[0], match[1]
        if score >= min_score:
            mm_info = norm_to_mmrow.get(best_norm, None)
            if mm_info:
                fuzzy_rows.append({
                    "_opt_idx": idx,
                    "_mm_norm": best_norm,
                    "_score": score,
                    **mm_info
                })

    # 3) Greedy de-dup: highest score first; do not reuse optimizer row or MM name
    fuzzy_df = pd.DataFrame(fuzzy_rows)
    greedy_picks = []
    used_opt = set()
    used_mm2 = set()
    if not fuzzy_df.empty:
        for _, r in fuzzy_df.sort_values("_score", ascending=False).iterrows():
            if r["_opt_idx"] in used_opt:
                continue
            if r[mm_name_col] in used_mm2:
                continue
            greedy_picks.append(r)
            used_opt.add(r["_opt_idx"])
            used_mm2.add(r[mm_name_col])
    greedy_df = pd.DataFrame(greedy_picks)

    # 4) Attach fuzzy selections back to the exact_misses
    if not greedy_df.empty:
        # Map by original optimizer row index
        # Need to re-add _name_norm to greedy_df before joining if needed for other steps
        attach_cols = [c for c in mm_keep if c != "_name_norm"] + ["_score", "_mm_norm"]
        attach = greedy_df.set_index("_opt_idx")[attach_cols]

        # Use join for attaching, specify suffixes for overlapping columns
        exact_misses = exact_misses.join(attach, how="left", lsuffix="_left", rsuffix="_right")

        # Fill columns from joined data (handle renamed _mm_norm)
        # Prioritize the right side (from fuzzy match) if available
        for col in attach_cols:
            if col in exact_misses.columns and col + "_right" in exact_misses.columns:
                 exact_misses[col] = exact_misses[col + "_right"].fillna(exact_misses[col])
                 exact_misses = exact_misses.drop(columns=[col + "_right"]) # drop the temporary join column
            elif col + "_right" in exact_misses.columns:
                 exact_misses[col] = exact_misses[col + "_right"]
                 exact_misses = exact_misses.drop(columns=[col + "_right"]) # drop the temporary join column

        if "_mm_norm" in exact_misses.columns:
             exact_misses["_name_norm"] = exact_misses["_name_norm"].fillna(exact_misses["_mm_norm"])
             exact_misses = exact_misses.drop(columns=["_mm_norm"]) # drop the temporary join column


        # Fill mm columns for rows that got a fuzzy match
        for col in keep_cols_from_mm + [mm_name_col]: # Use original keep_cols_from_mm and mm_name_col
            if col + "_mm" in exact_misses.columns:
                 exact_misses[col] = exact_misses[col].fillna(exact_misses[col + "_mm"])
                 exact_misses = exact_misses.drop(columns=[col + "_mm"]) # drop the temporary join column


    else:
        exact_misses["_score"] = pd.NA


    # 5) Combine exact hits + (misses with/without fuzzy)
    # Drop _mm cols from exact_hits before concat to avoid duplicates
    cols_to_drop_from_exact_hits = [c + "_mm" for c in keep_cols_from_mm + [mm_name_col] if c + "_mm" in exact_hits.columns]
    exact_hits_cleaned = exact_hits.drop(columns=cols_to_drop_from_exact_hits)

    combined = pd.concat([exact_hits_cleaned, exact_misses], axis=0, ignore_index=True)

    # 6) Clean helpers; keep original optimizer name & the MM fields
    # Drop columns with suffixes and the temporary _name_norm if it wasn't needed
    drop_cols = [c for c in combined.columns if c.endswith(("_mm", "_left", "_right"))]
    # Only drop _name_norm if it's not in the original mm_keep list (meaning we don't want to keep it)
    if "_name_norm" not in mm_keep:
         drop_cols.append("_name_norm")

    merged_df = combined.drop(columns=list(set(drop_cols))) # Use set to avoid dropping same col multiple times


    # 7) Diagnostics
    diag = {
        "optimizer_rows_in": int(len(optimizer_df)),
        "optimizer_rows_after_pool": int(len(odf)),
        "exact_matches": int(exact_hits.shape[0]),
        "fuzzy_candidates": int(len(fuzzy_rows)),
        "fuzzy_accepted": int(greedy_df.shape[0]),
        "min_score": int(min_score),
        "unmatched_after_all": int(merged_df[mm_name_col].isna().sum())
    }

    # Ensure final merged_df contains the columns that were intended to be kept from mm_keep
    # This is a safeguard in case the dropping logic was too aggressive
    final_mm_cols = [c for c in keep_cols_from_mm + [mm_name_col] if c in merged_df.columns] # Only include if they exist
    # Ensure original optimizer_df columns are also in the output
    original_opt_cols = [c for c in optimizer_df.columns if c != "_name_norm"]
    # Combine and get unique columns in desired order (optimizer cols first, then final mm cols)
    final_cols_order = original_opt_cols + [col for col in final_mm_cols if col not in original_opt_cols]

    # Add _score column if it exists
    if "_score" in merged_df.columns and "_score" not in final_cols_order:
        final_cols_order.append("_score")


    # Reindex the dataframe to ensure column order and presence
    merged_df = merged_df.reindex(columns=final_cols_order)


    return merged_df


# Classify WR Matchup Grades - Corrected function to handle individual scores
def classify_matchup_grade_wr(score):
    """Classifies matchup scores into 'GREAT', 'GOOD', 'POOR', or 'UNRANKED'."""
    # Check if the score is a single numerical value or NaN
    if pd.isna(score):
        return "UNRANKED"
    # Ensure score is treated as an integer for comparison
    try:
        score_int = int(score)
        if score_int in [4, 5]:
            return "GREAT"
        elif score_int == 3:
            return "GOOD"
        elif score_int in [1, 2]:
            return "POOR"
        else:
            return "UNRANKED" # Handle any unexpected score values
    except (ValueError, TypeError):
        return "UNRANKED" # Handle non-numeric scores

def remove_players_by_name(df, player_names_to_remove, name_col='Name'):
      """
      Removes players from a DataFrame based on a list of names.

      Args:
          df (pd.DataFrame): The input DataFrame.
          player_names_to_remove (list): A list of player names to remove.
          name_col (str): The name of the column containing player names.

      Returns:
          pd.DataFrame: A new DataFrame with the specified players removed.
      """
      return df[~df[name_col].isin(player_names_to_remove)].copy()

# Example usage (you can uncomment and modify this to test the function)
# players_to_remove = ['Player A', 'Player B']
# df_oppScore_prep_filtered = remove_players_by_name(df_oppScore_prep, players_to_remove, name_col='Name')
# display(df_oppScore_prep_filtered)

def calculate_spearman_correlation(df, col1, col2):
  """
  Calculates the Spearman correlation coefficient between two columns in a DataFrame.

  Args:
    df (pd.DataFrame): The input DataFrame.
    col1 (str): The name of the first column.
    col2 (str): The name of the second column.

  Returns:
    float: The Spearman correlation coefficient. Returns NaN if calculation is not possible.
  """
  if col1 not in df.columns:
    print(f"Warning: Column '{col1}' not found in the DataFrame.")
    return float('nan')
  if col2 not in df.columns:
    print(f"Warning: Column '{col2}' not found in the DataFrame.")
    return float('nan')

  # Drop rows with NaN values in either column before calculating correlation
  df_clean = df[[col1, col2]].dropna()

  if len(df_clean) < 2:
      print("Warning: Not enough non-NaN data points to calculate correlation.")
      return float('nan')

  correlation = df_clean[col1].corr(df_clean[col2], method='spearman')
  return correlation

# Example usage with df_new
# spearman_corr = calculate_spearman_correlation(df_new, 'OppScore', 'ActualFPTS')
# print(f"Spearman correlation between OppScore and ActualFPTS: {spearman_corr}")



# Create OppScore_Bucket column
def assign_oppscore_bucket(rank):
    if pd.isna(rank):
        return 'UNRANKED'
    if rank <= rank_thresholds[0]:
        return f'Top {rank_thresholds[0]}'
    for i in range(1, len(rank_thresholds)):
        if rank <= rank_thresholds[i]:
            return f'Top {rank_thresholds[i]}'
    return f'Below Top {rank_thresholds[-2]}' # Assign players below the last threshold to a "Below Top XX" bucket


def are_in_same_bucket(oppscore_rank, actualfpts_rank, thresholds):
  if pd.isna(oppscore_rank) or pd.isna(actualfpts_rank):
    return False

  oppscore_bucket = None
  actualfpts_bucket = None

  # Determine OppScore bucket
  if oppscore_rank <= thresholds[0]:
    oppscore_bucket = f'Top {thresholds[0]}'
  else:
    for i in range(1, len(thresholds)):
      if oppscore_rank <= thresholds[i]:
        oppscore_bucket = f'Top {thresholds[i]}'
        break
    if oppscore_bucket is None:  # Handle ranks below the last threshold
      oppscore_bucket = f'Below Top {thresholds[-2]}'

  # Determine ActualFPTS bucket
  if actualfpts_rank <= thresholds[0]:
    actualfpts_bucket = f'Top {thresholds[0]}'
  else:
    for i in range(1, len(thresholds)):
      if actualfpts_rank <= thresholds[i]:
        actualfpts_bucket = f'Top {thresholds[i]}'
        break
    if actualfpts_bucket is None:  # Handle ranks below the last threshold
      actualfpts_bucket = f'Below Top {thresholds[-2]}'

  return oppscore_bucket == actualfpts_bucket

def assign_actualfpts_bucket(rank):
  if pd.isna(rank):
    return 'UNRANKED'
  if rank <= rank_thresholds[0]:
    return f'Top {rank_thresholds[0]}'
  for i in range(1, len(rank_thresholds)):
    if rank <= rank_thresholds[i]:
      return f'Top {rank_thresholds[i]}'
  # Handle ranks below the last threshold, similar to OppScore_Bucket logic
  return f'Below Top {rank_thresholds[-2]}'  # Assuming 'Below Top 48' is the appropriate label

def create_bucket_movement_matrix(df):
  """
  Creates a matrix showing the count of players moving from OppScore_Bucket
  to ActualFPTS_Bucket.

  Args:
    df (pd.DataFrame): The input DataFrame containing 'OppScore_Bucket'
                       and 'ActualFPTS_Bucket' columns.

  Returns:
    pd.DataFrame: A pivot table showing the count of players in each
                  OppScore_Bucket vs. ActualFPTS_Bucket cell.
                  Returns None if required columns are missing.
  """
  if 'OppScore_Bucket' not in df.columns or 'ActualFPTS_Bucket' not in df.columns:
    print("Error: Required columns ('OppScore_Bucket', 'ActualFPTS_Bucket') not found in the DataFrame.")
    return None

  # Create the pivot table
  movement_matrix = pd.pivot_table(df,
                                   index='OppScore_Bucket',
                                   columns='ActualFPTS_Bucket',
                                   aggfunc='size', # Count the number of players in each group
                                   fill_value=0)   # Fill missing values with 0

  # Define the desired order of columns and index based on rank thresholds
  # Assuming the buckets are 'Top 12', 'Top 24', 'Top 36', 'Top 44', 'Below Top 36' based on your thresholds [12, 24, 36, 44]
  rank_thresholds = [12, 24, 36, 44]
  bucket_order = [f'Top {threshold}' for threshold in rank_thresholds]
  # Remove the "Below Top" bucket from the desired order if it exists
  if f'Below Top {rank_thresholds[-2]}' in bucket_order:
      bucket_order.remove(f'Below Top {rank_thresholds[-2]}')

  # Reindex the matrix to ensure the desired order and include all potential buckets
  # Only include buckets that are actually present in the data to avoid errors if a bucket is empty
  present_index = [b for b in bucket_order if b in movement_matrix.index]
  present_columns = [b for b in bucket_order if b in movement_matrix.columns]

  # Include all buckets from bucket_order during reindexing, not just present ones
  movement_matrix = movement_matrix.reindex(index=bucket_order, columns=bucket_order, fill_value=0)


  return movement_matrix

def remove_duplicate_players(df, name_column='Name'):
  """
  Removes duplicate player entries from a DataFrame based on a specified name column.

  Args:
    df (pd.DataFrame): The input DataFrame.
    name_column (str): The name of the column containing player names.

  Returns:
    pd.DataFrame: A new DataFrame with duplicate player entries removed.
  """
  return df.drop_duplicates(subset=[name_column]).copy()

# Example usage:
# df_unique_players = remove_duplicate_players(my_dataframe, 'playerName')
# display(df_unique_players)

def _norm(s: str) -> str:
    # lower, strip, remove all non-alphanumerics
    return re.sub(r'[^a-z0-9]', '', s.strip().lower())

# Abbreviations (NFL-style)
TEAMS = {
    'ARI': ['Arizona Cardinals', 'Cardinals', 'Arizona', 'ARI'],
    'ATL': ['Atlanta Falcons', 'Falcons', 'Atlanta', 'ATL'],
    'BAL': ['Baltimore Ravens', 'Ravens', 'Baltimore', 'BAL'],
    'BUF': ['Buffalo Bills', 'Bills', 'Buffalo', 'BUF'],
    'CAR': ['Carolina Panthers', 'Panthers', 'Carolina', 'CAR'],
    'CHI': ['Chicago Bears', 'Bears', 'Chicago', 'CHI'],
    'CIN': ['Cincinnati Bengals', 'Bengals', 'Cincinnati', 'CIN'],
    'CLE': ['Cleveland Browns', 'Browns', 'Cleveland', 'CLE'],
    'DAL': ['Dallas Cowboys', 'Cowboys', 'Dallas', 'DAL'],
    'DEN': ['Denver Broncos', 'Broncos', 'Denver', 'DEN'],
    'DET': ['Detroit Lions', 'Lions', 'Detroit', 'DET'],
    'GB' : ['Green Bay Packers', 'Packers', 'Green Bay', 'GB'],
    'HOU': ['Houston Texans', 'Texans', 'Houston', 'HOU'],
    'IND': ['Indianapolis Colts', 'Colts', 'Indianapolis', 'IND'],
    'JAX': ['Jacksonville Jaguars', 'Jaguars', 'Jacksonville', 'JAX'],
    'KC' : ['Kansas City Chiefs', 'Chiefs', 'Kansas City', 'KC'],
    'LAC': ['Los Angeles Chargers', 'Chargers', 'LA Chargers', 'LAC'],
    'LAR': ['Los Angeles Rams', 'Rams', 'LA Rams', 'LAR'],
    'LV' : ['Las Vegas Raiders', 'Raiders', 'Las Vegas', 'LV'],
    'MIA': ['Miami Dolphins', 'Dolphins', 'Miami', 'MIA'],
    'MIN': ['Minnesota Vikings', 'Vikings', 'Minnesota', 'MIN'],
    'NE' : ['New England Patriots', 'Patriots', 'New England', 'NE'],
    'NO' : ['New Orleans Saints', 'Saints', 'New Orleans', 'NO'],
    'NYG': ['New York Giants', 'Giants', 'NY Giants', 'NYG'],
    'NYJ': ['New York Jets', 'Jets', 'NY Jets', 'NYJ'],
    'PHI': ['Philadelphia Eagles', 'Eagles', 'Philadelphia', 'PHI'],
    'PIT': ['Pittsburgh Steelers', 'Steelers', 'Pittsburgh', 'PIT'],
    'SEA': ['Seattle Seahawks', 'Seahawks', 'Seattle', 'SEA'],
    'SF' : ['San Francisco 49ers', '49ers', 'Niners', 'San Francisco', 'SF'],
    'TB' : ['Tampa Bay Buccaneers', 'Buccaneers', 'Bucs', 'Tampa Bay', 'TB'],
    'TEN': ['Tennessee Titans', 'Titans', 'Tennessee', 'TEN'],
    'WAS': ['Washington Commanders', 'Commanders', 'Washington', 'WAS', 'WSH'],
}

# Build a normalized alias map
_ALIAS = {}
for abbr, aliases in TEAMS.items():
    for alias in aliases:
        _ALIAS[_norm(alias)] = abbr

def get_team_abbreviation(team_name):
    if team_name is None or (isinstance(team_name, float) and pd.isna(team_name)):
        return team_name
    key = _norm(str(team_name))
    return _ALIAS.get(key, team_name)  # fall back to original if not found


# Merge removed
def calculate_percentile_and_grade(df, column_name, positions=None, grade_map=None):
    """
    Calculates percentiles and ranks for a column within each position group,
    optionally filters by position, and maps percentiles to categorical grades.
    The calculations are performed directly on the input DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.
        column_name (str): The name of the column to calculate percentiles and ranks for.
        positions (str or list, optional): A single position or a list of positions
                                           to include in the calculation. If None,
                                           calculations are performed for all positions.
                                           Defaults to None.
        grade_map (dict, optional): A dictionary mapping percentile thresholds
                                     (inclusive lower bound) to categorical grades.
                                     Example: {80: "80 Plus", 60: "60 Plus",
                                               40: "40 Plus", 0: "Below 40"}.
                                     If None, no grading is applied. Defaults to None.

    Returns:
        pd.DataFrame: The DataFrame with new columns named f'{column_name}_Percentile',
                      f'{column_name}_Rank', and optionally f'{column_name}_Grade',
                      calculated within each position group. Returns the original
                      DataFrame if the specified column does not exist or if 'position'
                      column is missing.
    """
    if column_name not in df.columns:
        print(f"Error: Column '{column_name}' not found in the DataFrame.")
        return df

    if 'position' not in df.columns:
        print("Error: 'position' column not found in the DataFrame.")
        return df

    # Create a copy to avoid modifying the original DataFrame directly if filtering
    df_processed = df.copy()

    # Filter by position if specified
    if positions:
        if isinstance(positions, str):
            positions = [positions]
        df_processed = df_processed[df_processed['position'].isin(positions)]

    # Calculate percentile and rank within each position group
    # Apply calculations to the original df and not the filtered df_processed
    # Ensure calculations are done on the filtered or full dataframe based on 'positions'
    if positions:
      df.loc[df['position'].isin(positions), f'{column_name}_Percentile'] = df_processed.groupby('position')[column_name].rank(pct=True, method='average') * 100
      df.loc[df['position'].isin(positions), f'{column_name}_Rank'] = df_processed.groupby('position')[column_name].rank(ascending=False, method='average')
    else:
      df[f'{column_name}_Percentile'] = df.groupby('position')[column_name].rank(pct=True, method='average') * 100
      df[f'{column_name}_Rank'] = df.groupby('position')[column_name].rank(ascending=False, method='average')


    # Map percentile to categorical grade if grade_map is provided
    if grade_map:
        def assign_grade(percentile):
            if pd.isna(percentile):
                return None
            for threshold in sorted(grade_map.keys(), reverse=True):
                if percentile >= threshold:
                    return grade_map[threshold]
            return None # Should not happen if 0 is in grade_map keys

        # Apply grade assignment to the original df, only for rows that were processed
        if positions:
          df.loc[df['position'].isin(positions), f'{column_name}_Grade'] = df.loc[df['position'].isin(positions), f'{column_name}_Percentile'].apply(assign_grade)
        else:
          df[f'{column_name}_Grade'] = df[f'{column_name}_Percentile'].apply(assign_grade)


    return df

# Example Usage (assuming df_optimizer_prep is your DataFrame after merging)
# Define the grade map
#custom_grade_map = {
#    80: "80 Plus",
#    60: "60 Plus",
#    40: "40 Plus",
#    0: "Below 40"
#}

# Apply the function to calculate percentiles, ranks, and grades for 'fantasyPoints' for RBs, QBs, WRs, TEs, and DSTs
# df_optimizer_prep_with_percentiles = calculate_percentile_and_grade(df_optimizer_prep,
#                                                                     'fantasyPoints',
#                                                                     positions=['rb', 'qb', 'wr', 'te', 'dst'],
#                                                                     grade_map=custom_grade_map)

# Display the updated DataFrame (optional)
# display(df_optimizer_prep_with_percentiles.head())

def debug_nan_rows(df, columns_to_display, query_column):
    """
    Displays specified columns for rows where a query column has NaN values.

    Args:
        df (pd.DataFrame): The input DataFrame.
        columns_to_display (list): A list of column names to display.
        query_column (str): The name of the column to check for NaN values.

    Returns:
        pd.DataFrame: A DataFrame containing the specified columns for rows
                      with NaN values in the query column. Returns an empty
                      DataFrame if no NaNs are found or if columns are missing.
    """
    if query_column not in df.columns:
        print(f"Error: Query column '{query_column}' not found in the DataFrame.")
        return pd.DataFrame()

    # Filter rows where the query column is NaN
    nan_rows_df = df[df[query_column].isna()]

    # Check if all columns to display exist
    if not all(col in df.columns for col in columns_to_display):
        missing_cols = [col for col in columns_to_display if col not in df.columns]
        print(f"Warning: The following display columns were not found and will be excluded: {missing_cols}")
        columns_to_display = [col for col in columns_to_display if col in df.columns]


    # Select the specified columns
    if columns_to_display:
      result_df = nan_rows_df[columns_to_display]
    else:
      # If no columns to display are specified or found after checking, return all columns of nan_rows_df
      result_df = nan_rows_df


    return result_df

# Example usage:
# Assuming df_final is your DataFrame
# columns_to_show = ['Name', 'teamName', 'position', 'fantasyPoints', 'ActualFPTS']
# nan_fantasy_points_rows = debug_nan_rows(df_final, columns_to_show, 'fantasyPoints')
# display(nan_fantasy_points_rows)

def drop_rows_with_nan_excluding(df, exclude_columns=None):
    """
    Deletes rows from a DataFrame that contain NaN values in any column,
    optionally excluding a specified list of columns from this check.

    Args:
        df (pd.DataFrame): The input DataFrame.
        exclude_columns (list, optional): A list of column names to exclude
                                         when checking for NaN values. Rows
                                         will not be deleted based on NaN values
                                         in these columns. Defaults to None.

    Returns:
        pd.DataFrame: The DataFrame with rows containing NaN values (outside
                      of excluded columns) removed.
    """
    if exclude_columns is None:
        exclude_columns = []

    # Determine the columns to check for NaN values
    columns_to_check = [col for col in df.columns if col not in exclude_columns]

    if not columns_to_check:
        print("Warning: All columns are excluded from NaN check. No rows will be dropped.")
        return df

    # Drop rows where any of the specified columns have NaN values
    df_cleaned = df.dropna(subset=columns_to_check).copy()

    return df_cleaned

# Example Usage:
# Assuming df_final is your DataFrame
# cleaned_df = drop_rows_with_nan_excluding(df_final, exclude_columns=['ActualFPTS_Grade', 'some_other_calculated_column'])
# display(cleaned_df.head())

def display_selected_columns(df, columns_to_display):
    """
    Displays only the specified columns of a DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.
        columns_to_display (list): A list of column names to display.
    """
    # Check if all columns to display exist in the DataFrame
    if not all(col in df.columns for col in columns_to_display):
        missing_cols = [col for col in columns_to_display if col not in df.columns]
        print(f"Warning: The following columns were not found in the DataFrame and will not be displayed: {missing_cols}")
        # Filter out missing columns from the list to display
        columns_to_display = [col for col in columns_to_display if col in df.columns]

    # Display the DataFrame with only the selected columns
    if columns_to_display:
        display(df[columns_to_display])
    else:
        print("No valid columns to display.")

# Example Usage:
# Assuming df_final is your DataFrame
# columns_to_show = ['Name', 'DKSalary', 'fantasyPoints']
# display_selected_columns(df_final, columns_to_show)

def state_transitions(df, column1, column2, position=None, order=None):
    """
    Calculates the state transitions between values in two columns of a DataFrame,
    optionally filtering by position and specifying the order of values in the output matrix.

    Args:
        df (pd.DataFrame): The input DataFrame.
        column1 (str): The name of the first column (initial state).
        column2 (str): The name of the second column (final state).
        position (str, optional): The position to filter by. If None, transitions
                                  are calculated for all rows. Defaults to None.
        order (list, optional): A list specifying the desired order of values
                                in the rows and columns of the output matrix.
                                If None, the order will be determined by pandas.
                                Defaults to None.

    Returns:
        pd.DataFrame: A cross-tabulation (matrix) showing the number of transitions
                      from each value in column1 to each value in column2 for the
                      specified position (or all if None), with the specified order.
                      Returns an empty DataFrame if columns are not found or if no
                      data matches the position filter.
    """
    if column1 not in df.columns:
        print(f"Error: Column '{column1}' not found in the DataFrame.")
        return pd.DataFrame()
    if column2 not in df.columns:
        print(f"Error: Column '{column2}' not found in the DataFrame.")
        return pd.DataFrame()
    if position is not None and 'position' not in df.columns:
         print("Error: 'position' column not found in the DataFrame to apply position filter.")
         return pd.DataFrame()


    df_filtered = df.copy()

    # Filter by position if specified
    if position is not None:
        df_filtered = df_filtered[df_filtered['position'] == position]

    # Apply specified order if provided
    if order is not None:
        # Convert columns to categorical type with specified order
        df_filtered[column1] = pd.Categorical(df_filtered[column1], categories=order, ordered=True)
        df_filtered[column2] = pd.Categorical(df_filtered[column2], categories=order, ordered=True)


    # Calculate the cross-tabulation of the two columns
    # Use df_filtered for crosstab calculation
    transition_matrix = pd.crosstab(df_filtered[column1], df_filtered[column2], dropna=False) # dropna=False to include categories with no data


    return transition_matrix

# Example Usage:
# Assuming df_final is your DataFrame with 'fantasyPoints_Grade' and 'ActualFPTS_Grade'
# movement_matrix_all = state_transitions(df_final, 'fantasyPoints_Grade', 'ActualFPTS_Grade')
# display(movement_matrix_all)

# Example Usage with position filter:
# movement_matrix_rb = state_transitions(df_final, 'fantasyPoints_Grade', 'ActualFPTS_Grade', position='RB')
# display(movement_matrix_rb)

# Example Usage with specified order:
# custom_order = ["Top", "Above Average", "Below Average", "Bottom"]
# movement_matrix_ordered = state_transitions(df_final, 'fantasyPoints_Grade', 'ActualFPTS_Grade', order=custom_order)
# display(movement_matrix_ordered)