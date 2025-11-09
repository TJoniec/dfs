
custom_player_exposures = {
    'Tyrone Tracy Jr.': 2,
    }


custom_rank_constraints = {
    'RB': [(1, 6, 1, 'exact'), (7, 24, 1, 'exact')], # Combined the two RB constraints - Example with 'exact'
    # 'WR': [(1, 36, 3, 'exact')],
    #'WR': [(7, 12, 1, 'exact')],
   # 'TE': [(1, 6, 1, 'exact')],
    'TE': [(7, 12, 1, 'exact')],
    'QB': [(1, 6, 1, 'exact')],
    #'WR': [(1, 1, 1, 'exact')],
    'DST': [(1, 6, 1, 'exact')],
   # 'FLEX': [(1, 1, 1)] # FLEX is handled by position constraints
}

# Generate optimal lineups with both global and player-specific exposure constraints
# Using nfl_df from previous cells
optimal_lineups_with_exposure = generate_optimal_lineups_nfl(
    nfl_df,
    min_fpts=0, # Set a low minimum FPTS to see results with the constraints
    max_lineups=100, # Generate a sufficient number of lineups to see exposure effects
    save_to_excel_each=False,
    global_max_exposure=10.0, # Increased global maximum exposure
    player_max_exposures=custom_player_exposures, # Pass the player-specific constraints
    rank_constraints=custom_rank_constraints # Pass the custom rank constraints

)