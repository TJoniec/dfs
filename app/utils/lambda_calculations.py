import pandas as pd


def process_all_players_with_bias_adjustment(
    full_df: pd.DataFrame,
    k: float = 5.0,
    clip_bias: float = 10.0,
    outlier_threshold: float = 2.5
) -> (pd.DataFrame, pd.DataFrame):
    """
    Process a fantasy football dataset to compute forward-looking, shrinkage-adjusted projections
    with outlier removal, per-player weekly adjustments, and player-level summary for future use.

    Parameters:
    - full_df (pd.DataFrame): Must contain columns:
        - 'Name', 'Week', 'ProjectedFPTS', 'ActualFPTS'
    - k (float): Shrinkage parameter
    - clip_bias (float): Max absolute value of applied bias
    - outlier_threshold (float): Z-score threshold to remove outlier biases

    Returns:
    - Tuple:
        1. Weekly-level DataFrame: all original columns + Bias, AppliedBias, AdjustedFPTS
        2. Player-level summary DataFrame:
            - Name, PlayerBiasMean, FinalAppliedBias, SampleCount
    """

    all_adjusted_rows = []
    player_bias_summary = []

    for player_name, player_data in full_df.groupby("Name"):
        player_df = player_data.sort_values("Week").reset_index(drop=True).copy()

        # Step 1: Calculate raw bias
        player_df["Bias"] = player_df["ActualFPTS"] - player_df["ProjectedFPTS"]

        # Step 2: Remove outliers based on Z-score
        bias_std = player_df["Bias"].std()
        bias_mean = player_df["Bias"].mean()

        if bias_std > 0:
            z_scores = (player_df["Bias"] - bias_mean) / bias_std
            player_df = player_df[(z_scores >= -outlier_threshold) & (z_scores <= outlier_threshold)].copy()

        # Step 3: Sort again
        player_df = player_df.sort_values("Week").reset_index(drop=True)

        adjusted_rows = []
        last_shrunken_bias = 0.0

        for i in range(len(player_df)):
            current_proj = player_df.loc[i, "ProjectedFPTS"]
            current_actual = player_df.loc[i, "ActualFPTS"]
            current_week = player_df.loc[i, "Week"]

            past_data = player_df.iloc[:i]

            if past_data.empty:
                applied_bias = 0.0
            else:
                past_data = past_data.copy()
                past_data["Bias"] = past_data["ActualFPTS"] - past_data["ProjectedFPTS"]
                player_bias_mean = past_data["Bias"].mean()
                group_bias_mean = player_bias_mean  # placeholder for group-level
                n = len(past_data)
                lambda_ = n / (n + k)
                shrunk_bias = lambda_ * player_bias_mean + (1 - lambda_) * group_bias_mean
                applied_bias = max(min(shrunk_bias, clip_bias), -clip_bias)
                last_shrunken_bias = applied_bias

            adjusted_fpts = max(0, current_proj + applied_bias)

            # Merge new values into row
            row = player_df.loc[i].to_dict()
            row.update({
                "AppliedBias": round(applied_bias, 2),
                "AdjustedFPTS": round(adjusted_fpts, 2)
            })
            adjusted_rows.append(row)

        all_adjusted_rows.extend(adjusted_rows)

        # Add player-level summary with sample count
        player_bias_summary.append({
            "Name": player_name,
            'Team': player_df['Team'].iloc[0],
            'Position': player_df['Position'].iloc[0],
            "PlayerBiasMean": round(player_df["Bias"].mean(), 2),
            "FinalAppliedBias": round(last_shrunken_bias, 2),
            "SampleCount": len(player_df)
        })

    # Compile results
    adjusted_df = pd.DataFrame(all_adjusted_rows)
    player_bias_df = pd.DataFrame(player_bias_summary)

    return adjusted_df, player_bias_df

def compute_position_level_bias_summary(
    full_df: pd.DataFrame,
    min_projected_fpts: float = 0.0,
    outlier_threshold: float = 2.5
) -> pd.DataFrame:
    """
    Compute position-level bias summary statistics from a full fantasy dataset,
    with optional filtering by minimum projected FPTS and outlier removal via z-score.

    Parameters:
    ----------
    full_df : pd.DataFrame
        Must include 'Position', 'ProjectedFPTS', 'ActualFPTS'
    min_projected_fpts : float
        Minimum ProjectedFPTS required to include a row in the analysis
    outlier_threshold : float
        Z-score threshold for outlier removal (default = 2.5)

    Returns:
    -------
    pd.DataFrame
        Grouped by Position with:
        - SampleCount
        - MeanBias
        - StdBias
        - MinBias
        - MaxBias
    """

    df = full_df.copy()

    # Step 1: Filter by ProjectedFPTS threshold
    df = df[df["ProjectedFPTS"] >= min_projected_fpts]

    # Step 2: Compute Bias
    df["Bias"] = df["ActualFPTS"] - df["ProjectedFPTS"]

    # Step 3: Remove outliers using Z-score filtering
    bias_mean = df["Bias"].mean()
    bias_std = df["Bias"].std()

    if bias_std > 0:
        z_scores = (df["Bias"] - bias_mean) / bias_std
        df = df[(z_scores >= -outlier_threshold) & (z_scores <= outlier_threshold)]

    # Step 4: Aggregate by Position
    summary_df = (
        df.groupby("Position")["Bias"]
        .agg([
            ("SampleCount", "count"),
            ("MeanBias", "mean"),
            ("StdBias", "std"),
            ("MinBias", "min"),
            ("MaxBias", "max")
        ])
        .reset_index()
    )

    return summary_df

def adjust_future_projections_dataframe(
    df_future_projections: pd.DataFrame,
    player_bias_df: pd.DataFrame,
    position_bias_df: pd.DataFrame,
    k: float = 5.0
) -> pd.DataFrame:
    """
    Adjust future projected fantasy points using a blend of player and position-level biases,
    and include lambda (shrinkage weight) in the output.

    Parameters:
    ----------
    df_future_projections : pd.DataFrame
        Must contain 'Name', 'Team', 'Position', 'ProjectedFPTS'
    player_bias_df : pd.DataFrame
        Must contain 'Name', 'PlayerBiasMean', 'SampleCount'
    position_bias_df : pd.DataFrame
        Must contain 'Position', 'MeanBias'
    k : float
        Shrinkage hyperparameter

     - The k parameter controls the trust level you place on a players personal bias compared to their positioj averag
    - If a player has few games, their bias is noisy - we do not want to overcorrect
    - If they have lots of history we can trust their personal bias more
    - K lets you smooth out volitality for players with little history
    - Personalize projections for well known heavily played players.
    - For GPP k should be lower than for cash (k-2 to 5)

    - Interpretation of k.
    - Using the formula lambda = .5 amd n = 6   n / n + k then lambda = .67, means that 67% of basis adjustment is on the player
    - Same above but with an n or 3, then lambda = .33, means that 33% of basis adjustment is on the player

    - Lambda is always between 0 and 1 and this is by design, it's the foundation of empirical Bayes-style shrinkage.
    - The value of lambda is the basis of how much of the bias adjustmnt is based upon the player.

    - Lambda smooths out the small sample noise.

    Returns:
    -------
    pd.DataFrame
        With columns:
        - Name, Team, Position, ProjectedFPTS, AdjustedFPTS, BiasApplied,
          AdjustmentPercent, Lambda, Sample_count, k
    """

    def lookup_and_adjust(row):
        name = row["Name"]
        position = row["Position"]
        proj = row["ProjectedFPTS"]

        # Get player bias and sample count
        player_row = player_bias_df[player_bias_df["Name"] == name]
        player_bias = player_row["PlayerBiasMean"].values[0] if not player_row.empty else 0.0
        sample_count = player_row["SampleCount"].values[0] if not player_row.empty else 0

        # Get position bias
        pos_row = position_bias_df[position_bias_df["Position"] == position]
        position_bias = pos_row["MeanBias"].values[0] if not pos_row.empty else 0.0

        # Compute lambda
        lambda_ = sample_count / (sample_count + k) if sample_count > 0 else 0.0

        # Compute adjusted bias and adjusted FPTS
        adjusted_bias = lambda_ * player_bias + (1 - lambda_) * position_bias
        adjusted_fpts = max(0.0, proj + adjusted_bias)

        bias_applied = round(adjusted_fpts - proj, 2)
        adjustment_percent = round((bias_applied / proj) * 100, 2) if proj != 0 else 0.0

        return pd.Series({
            "AdjustedFPTS": round(adjusted_fpts, 2),
            "BiasApplied": bias_applied,
            "AdjustmentPercent": adjustment_percent,
            "Lambda": round(lambda_, 3),
            'Sample_count': sample_count,
            'k': k
        })

    # Apply adjustments to each row
    results = df_future_projections.copy()
    adjustments = results.apply(lookup_and_adjust, axis=1)

    # Combine original and adjustment data
    results = pd.concat([results, adjustments], axis=1)

    return results[[
        "Name", 'Team', "Position", "ProjectedFPTS",
        "AdjustedFPTS", "BiasApplied", "AdjustmentPercent", "Lambda", 'Sample_count', 'k'
    ]]