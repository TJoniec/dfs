# Sunday Morning Working Copy
# ------------------FINAL WORKING CODPY ------------------------
# ------------------WINNING ONE -------------------------------
#-----------------USE THIS---------------------
import os
import pandas as pd
import pulp
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, LpBinary, PulpSolverError
from itertools import combinations
from pulp import LpStatus
from collections import Counter
from pathlib import Path




def generate_optimal_lineups_nfl(nfl_df, min_fpts=None, max_lineups=20, save_to_excel_each=False, bucket_name=None, rank_constraints=None, global_max_exposure=None, player_max_exposures=None):
    """
    Generates optimal NFL DraftKings lineups using linear programming, with optional
    minimum FPTS threshold, maximum lineup count, individual lineup saving, and
    rank-based player filtering, and exposure controls.

    Exposure Control:
    - Global Maximum Exposure: Limits the total percentage (0-100) of lineups
      a player can appear in across all generated lineups.
    - Player-Specific Maximum Exposures: A dictionary where keys are player
      names (str) and values are their maximum exposure percentages (float, 0-100).
      These override the global limit for specified players.
    - The exposure constraints are iteratively added to the LP problem after
      each valid lineup is found, limiting the total number of times a player
      can be selected in future lineups based on their allowed occurrences in
      the already generated lineups.
    - Basic validation is performed on exposure percentage inputs to ensure they
      are within the 0-100 range. Invalid values are ignored.

    Args:
        nfl_df (pd.DataFrame): DataFrame containing NFL player data with columns
                               'Player', 'Team', 'Pos', 'Salary', 'FPTS', 'Depth', 'FPTS_Rank'.
        min_fpts (float, optional): Minimum total projected FPTS for a lineup to be considered.
                                    Defaults to None (no minimum).
        max_lineups (int, optional): Maximum number of unique optimal lineups to generate.
                                     Defaults to 20. Set to None for no limit.
        save_to_excel_each (bool, optional): If True, saves each generated lineup to a
                                             separate Excel file. Defaults to False.
        bucket_name (str, optional): Google Cloud Storage bucket name for uploading
                                     lineups (if using GCS). Defaults to None.
        rank_constraints (dict, optional): A dictionary specifying rank constraints
                                           for positions.
                                           Format: {'POS': [(min_rank, max_rank, num_players, constraint_type), ...]}
                                           constraint_type can be 'exact', 'min', or 'max'.
                                           Example: {'RB': [(1, 6, 1, 'exact'), (7, 12, 2, 'min')]}
                                           Defaults to None (no rank constraints).
        global_max_exposure (float, optional): The maximum percentage (0-100) of lineups
                                               a player can appear in globally across all
                                               generated lineups. Defaults to None (no global limit).
        player_max_exposures (dict, optional): A dictionary where keys are player
                                               names (str) and values are their
                                               maximum exposure percentages (float, 0-100).
                                               These override the global limit for specified players.
                                               Defaults to None (no player-specific limits).


    Returns:
        pd.DataFrame: A DataFrame containing the generated optimal lineups.
    """
    # NFL specific parameters
    salary_cap = 50000 # Example NFL salary cap, adjust as needed
    nfl_roster_spots = 9 # NFL Draftkings roster spots: QB, RB, RB, WR, WR, WR, TE, FLEX, DST

    slate = nfl_df.copy() # Use the entire DataFrame provided

    if slate.empty:
        print(f"⚠️ Input DataFrame is empty.")
        return pd.DataFrame()

    # Drop rows with NaN in 'FPTS' or 'Salary' as Pulp cannot handle them in the objective function or constraints
    initial_rows = slate.shape[0]
    slate.dropna(subset=['FPTS', 'Salary', 'FPTS_Rank'], inplace=True)
    rows_after_drop = slate.shape[0]
    if initial_rows > rows_after_drop:
        print(f"ℹ️ Dropped {initial_rows - rows_after_drop} players with missing FPTS, Salary, or FPTS_Rank.")

    # Ensure necessary columns exist
    required_cols = ['Player', 'Team', 'Pos', 'Salary', 'FPTS', 'Depth', 'FPTS_Rank']
    if not all(col in slate.columns for col in required_cols):
        missing = [col for col in required_cols if col not in slate.columns]
        print(f"❌ Missing required columns in data: {missing}")
        return pd.DataFrame()

    # Create a dictionary of players with their attributes
    players = slate.set_index('Player').T.to_dict('dict')

    valid_lineups = []
    lineup_id = 1
    generated_lineup_count = 0

    # Calculate maximum allowed occurrences for each player based on exposure limits
    player_max_occurrences = {}
    if max_lineups is not None and max_lineups > 0:
        for player_name in players:
            # Validate exposure percentages
            global_exposure = global_max_exposure if global_max_exposure is not None else 101 # Use a value > 100 if no global limit
            player_exposure = player_max_exposures.get(player_name, global_exposure)

            if not (0 <= player_exposure <= 100):
                 print(f"⚠️ Warning: Invalid exposure percentage for player '{player_name}': {player_exposure}. Must be between 0 and 100. Ignoring exposure constraint for this player.")
                 player_max_occurrences[player_name] = float('inf') # Treat as no limit if invalid
            else:
                max_occurrences = (player_exposure / 100) * max_lineups
                player_max_occurrences[player_name] = max_occurrences
    else:
        # If max_lineups is None or 0, exposure limits are not meaningful
        for player_name in players:
            player_max_occurrences[player_name] = float('inf')


    # Keep track of players for whom exposure constraints have already been added to the LP problem
    # This set prevents adding duplicate constraints for the same player.
    exposure_constrained_players = set()

    print("\nSolving LP problem to generate lineups...")

    try:
        # The LP problem and variables are re-created inside the loop to allow adding constraints
        # based on previously found lineups.
        # This is an iterative approach to handling exposure constraints.
        prob = LpProblem(f"NFL Optimal Lineup", LpMaximize)
        player_vars = LpVariable.dicts("Select", players.keys(), cat=LpBinary)

        # Objective function: Maximize total projected points (using FPTS)
        prob += lpSum([players[i]['FPTS'] * player_vars[i] for i in players]), "Total Projected Points"

        # Constraint 1: Stay under the salary cap
        prob += lpSum([players[i]['Salary'] * player_vars[i] for i in players]) <= salary_cap, "Salary Cap"

        # Constraint 2: Exactly nfl_roster_spots players in the lineup
        prob += lpSum([player_vars[i] for i in players]) == nfl_roster_spots, "Roster Spots"

        # Constraint 3: Position requirements for NFL DraftKings
        prob += lpSum([player_vars[i] for i in players if players[i]['Pos'] == 'QB']) == 1, "One QB"
        prob += lpSum([player_vars[i] for i in players if players[i]['Pos'] == 'RB']) >= 2, "At least two RBs"
        prob += lpSum([player_vars[i] for i in players if players[i]['Pos'] == 'WR']) >= 3, "At least three WRs"
        prob += lpSum([player_vars[i] for i in players if players[i]['Pos'] == 'TE']) >= 1, "At least one TE"
        prob += lpSum([player_vars[i] for i in players if players[i]['Pos'] == 'DST']) == 1, "One DST"

        # Constraint 4: FLEX spot (additional RB, WR, or TE)
        prob += lpSum([player_vars[i] for i in players if players[i]['Pos'] in ['RB', 'WR', 'TE']]) >= 7, "RB, WR, TE and FLEX spots"

        # Debugging print: Check rank constraints received
        print("\n--- Applying Rank Constraints ---")
        print(f"Received rank_constraints: {rank_constraints}")

        # Rank constraints - Modified to handle the constraint type
        if rank_constraints:
             for pos, constraints in rank_constraints.items():
                  for i, constraint_tuple in enumerate(constraints):
                      if len(constraint_tuple) == 4:
                          min_rank, max_rank, num_players_in_range, constraint_type = constraint_tuple
                          # Debugging print: Print constraint details
                          print(f"Processing constraint for {pos}: Rank {min_rank}-{max_rank}, Players: {num_players_in_range}, Type: {constraint_type}")
                          players_in_range = [
                                player for player, details in players.items()
                                if details['Pos'] == pos and isinstance(details['FPTS_Rank'], (int, float)) and min_rank <= details['FPTS_Rank'] <= max_rank # <-- Added type check
                           ]
                          # Debugging print: Print players found for this constraint
                          print(f"Players found in rank range for {pos} ({min_rank}-{max_rank}): {[p for p in players_in_range]}")

                          if players_in_range:
                              if constraint_type == 'exact':
                                   prob += lpSum([player_vars[p] for p in players_in_range]) == num_players_in_range, f"{pos}_Rank_{min_rank}-{max_rank}_{i}_Exact" # Added unique name
                              elif constraint_type == 'min':
                                   prob += lpSum([player_vars[p] for p in players_in_range]) >= num_players_in_range, f"{pos}_Rank_{min_rank}-{max_rank}_{i}_Min" # Added unique name
                              elif constraint_type == 'max':
                                   prob += lpSum([player_vars[p] for p in players_in_range]) <= num_players_in_range, f"{pos}_Rank_{min_rank}-{max_rank}_{i}_Max" # Added unique name
                              else:
                                  print(f"⚠️ Warning: Unknown constraint type '{constraint_type}' for {pos} rank constraint ({min_rank}-{max_rank}). Skipping this constraint.")
                          else:
                               print(f"⚠️ Warning: No players found for {pos} with FPTS_Rank between {min_rank} and {max_rank}.")
                      else:
                          print(f"⚠️ Warning: Invalid rank constraint tuple format for {pos}: {constraint_tuple}. Expected 4 elements (min_rank, max_rank, num_players, constraint_type). Skipping this constraint.")
        print("--- Finished Applying Rank Constraints ---")
        # Debugging print: Print all constraints added to the problem
        # print("\n--- All LP Problem Constraints ---")
        # for name, constraint in prob.constraints.items():
        #     print(f"{name}: {constraint}")
        # print("--- End of LP Problem Constraints ---")


        # --- Loop to generate multiple lineups ---
        while True:
            if max_lineups is not None and generated_lineup_count >= max_lineups:
                print(f"\n✅ Reached maximum requested lineups ({max_lineups}). Stopping.")
                break

            # Solve the problem - Added time limit
            # Explicitly specify the path to the cbc solver
            # solver = pulp.COIN_CMD(msg=1, timeLimit=60, path="/usr/bin/cbc") # Added path
            # prob.solve(solver)
            status = prob.solve()

            if LpStatus[prob.status] == "Optimal":
                selected_players = [player for player, var in player_vars.items() if var.varValue > 0.5]
                total_fpts = sum(players[p]['FPTS'] for p in selected_players)
                total_salary = sum(players[p]['Salary'] for p in selected_players)

                # Debugging print: Print players in the potential lineup before checking duplication/exposure
                # print(f"\nPotential Lineup {lineup_id} players: {selected_players}")
                # print(f"Potential Lineup {lineup_id} FPTS: {total_fpts:.2f}, Salary: {total_salary}")


                if min_fpts is None or total_fpts >= min_fpts:
                    # Check for duplication across ALL found lineups
                    lineup_players_sorted = tuple(sorted(selected_players))
                    # Create a simplified representation of the new lineup for comparison
                    new_lineup_representation = tuple(sorted([p for p in selected_players]))

                    # Check if this exact combination of players is already in valid_lineups
                    is_duplicate = False
                    for existing_lineup_dict in valid_lineups:
                        player_cols = [col for col in existing_lineup_dict.keys() if 'Team' not in col and 'Pos' not in col and 'Depth' not in col and 'Salary' not in col and 'FPTS' not in col and col not in ['Lineup ID', 'Total Lineup FPTS', 'Total Lineup Salary']]
                        existing_lineup_players = [existing_lineup_dict[col] for col in player_cols if pd.notna(existing_lineup_dict[col]) and existing_lineup_dict[col] != 'None']
                        existing_lineup_representation = tuple(sorted(existing_lineup_players))
                        if new_lineup_representation == existing_lineup_representation:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        # --- Check Global and Player-Specific Exposure Limits ---
                        # Calculate current player counts in valid_lineups (including the newly added one)
                        temp_lineup_counts = Counter()
                        for lineup in valid_lineups:
                            player_cols = [col for col in lineup.keys() if 'Team' not in col and 'Pos' not in col and 'Depth' not in col and 'Salary' not in col and 'FPTS' not in col and col not in ['Lineup ID', 'Total Lineup FPTS', 'Total Lineup Salary']]
                            players_in_lineup = [lineup[col] for col in player_cols if pd.notna(lineup[col]) and lineup[col] != 'None']
                            temp_lineup_counts.update(players_in_lineup)

                        # Add players from the potential new lineup
                        temp_lineup_counts.update(selected_players)

                        # Check if adding this lineup violates any exposure limits
                        exposure_violated = False
                        for player, count in temp_lineup_counts.items():
                            # Check against calculated max occurrences
                            if player in player_max_occurrences and count > player_max_occurrences[player]:
                                print(f"🚫 Skipping Lineup {lineup_id}: Adding player '{player}' would exceed exposure limit ({count:.0f} > {player_max_occurrences[player]:.0f}).")
                                exposure_violated = True
                                break # No need to check other players in this lineup

                        if not exposure_violated:
                            print(f"✅ Found Lineup {lineup_id}: Total FPTS = {total_fpts:.2f}, Total Salary = {total_salary}")

                            # --- Extract Lineup Info ---
                            lineup_details = {'Lineup ID': lineup_id}
                            lineup_details['Total Lineup FPTS'] = total_fpts
                            lineup_details['Total Lineup Salary'] = total_salary

                            lineup_pos_players = {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'DST': []}
                            for player_name in selected_players:
                                pos = players[player_name]['Pos']
                                if pos in lineup_pos_players:
                                    lineup_pos_players[pos].append({
                                        'Player': player_name,
                                        'Team': players[player_name]['Team'],
                                        'Pos': players[player_name]['Pos'],
                                        'Depth': players[player_name]['Depth'],
                                        'Salary': players[player_name]['Salary'],
                                        'FPTS': players[player_name]['FPTS'],
                                        'FPTS_Rank': players[player_name]['FPTS_Rank']
                                    })

                            for pos in lineup_pos_players:
                                lineup_pos_players[pos].sort(key=lambda x: x['FPTS'], reverse=True)

                            for pos_key, players_list in lineup_pos_players.items():
                                for i, player_info in enumerate(players_list):
                                    slot_name = None
                                    if pos_key == 'QB' and i == 0: slot_name = 'QB1'
                                    elif pos_key == 'RB' and i == 0: slot_name = 'RB1'
                                    elif pos_key == 'RB' and i == 1: slot_name = 'RB2'
                                    elif pos_key == 'WR' and i == 0: slot_name = 'WR1'
                                    elif pos_key == 'WR' and i == 1: slot_name = 'WR2'
                                    elif pos_key == 'WR' and i == 2: slot_name = 'WR3'
                                    elif pos_key == 'TE' and i == 0: slot_name = 'TE1'
                                    elif pos_key == 'DST' and i == 0: slot_name = 'DST1'

                                    if slot_name:
                                        lineup_details[slot_name] = player_info['Player']
                                        lineup_details[f'{slot_name} Team'] = player_info['Team']
                                        lineup_details[f'{slot_name} Pos'] = player_info['Pos']
                                        lineup_details[f'{slot_name} Depth'] = player_info['Depth']
                                        lineup_details[f'{slot_name} Salary'] = player_info['Salary']
                                        lineup_details[f'{slot_name} FPTS'] = player_info['FPTS']
                                        lineup_details[f'{slot_name} FPTS_Rank'] = player_info['FPTS_Rank']

                            flex_player_name = 'None'
                            flex_team = 'None'
                            flex_pos = 'None'
                            flex_depth = 'None'
                            flex_salary = 0
                            flex_fpts = 0
                            flex_fpts_rank = 0

                            rb_count_total = len(lineup_pos_players.get('RB', []))
                            wr_count_total = len(lineup_pos_players.get('WR', []))
                            te_count_total = len(lineup_pos_players.get('TE', []))

                            extra_players = []
                            if rb_count_total > 2:
                                extra_players.extend(lineup_pos_players['RB'][2:])
                            if wr_count_total > 3:
                                extra_players.extend(lineup_pos_players['WR'][3:])
                            if te_count_total > 1:
                                extra_players.extend(lineup_pos_players['TE'][1:])

                            if extra_players:
                                # Sort extra players by FPTS to pick the highest for FLEX
                                extra_players.sort(key=lambda x: x['FPTS'], reverse=True)
                                flex_player_info = extra_players[0] # Select the top FPTS player as FLEX
                                flex_player_name = flex_player_info['Player']
                                flex_team = flex_player_info['Team']
                                flex_pos = flex_player_info['Pos']
                                flex_depth = flex_player_info['Depth']
                                flex_salary = flex_player_info['Salary']
                                flex_fpts = flex_player_info['FPTS']
                                flex_fpts_rank = flex_player_info['FPTS_Rank']

                            lineup_details['FLEX'] = flex_player_name
                            lineup_details['FLEX Team'] = flex_team
                            lineup_details['FLEX Pos'] = flex_pos
                            lineup_details['FLEX Depth'] = flex_depth
                            lineup_details['FLEX Salary'] = flex_salary
                            lineup_details['FLEX FPTS'] = flex_fpts
                            lineup_details['FLEX FPTS_Rank'] = flex_fpts_rank

                            all_slots = ['QB1', 'RB1', 'RB2', 'WR1', 'WR2', 'WR3', 'TE1', 'DST1', 'FLEX']
                            for slot in all_slots:
                                if slot not in lineup_details:
                                    lineup_details[slot] = 'None'
                                    lineup_details[f'{slot} Team'] = 'None'
                                    lineup_details[f'{slot} Pos'] = 'None'
                                    lineup_details[f'{slot} Depth'] = 'None'
                                    if f'{slot} Salary' not in lineup_details:
                                        lineup_details[f'{slot} Salary'] = 0
                                    if f'{slot} FPTS' not in lineup_details:
                                        lineup_details[f'{slot} FPTS'] = 0
                                    if f'{slot} FPTS_Rank' not in lineup_details:
                                        lineup_details[f'{slot} FPTS_Rank'] = 0


                            valid_lineups.append(lineup_details)
                            lineup_id += 1
                            generated_lineup_count += 1

                            if save_to_excel_each:
                                lineup_df = pd.DataFrame([lineup_details])
                                output_filename = f"NFL_Lineup_ID_{lineup_details['Lineup ID']}.xlsx"
                                lineup_df.to_excel(output_filename, index=False)
                                print(f"💾 Saved lineup {lineup_details['Lineup ID']} to {output_filename}")

                            # --- Iterative Exposure Constraint Addition ---
                            # Count current player occurrences in valid_lineups (including the newly added one)
                            current_player_counts = Counter()
                            for lineup in valid_lineups:
                                player_cols = [col for col in lineup.keys() if 'Team' not in col and 'Pos' not in col and 'Depth' not in col and 'Salary' not in col and 'FPTS' not in col and col not in ['Lineup ID', 'Total Lineup FPTS', 'Total Lineup Salary']]
                                players_in_lineup = [lineup[col] for col in player_cols if pd.notna(lineup[col]) and lineup[col] != 'None']
                                current_player_counts.update(players_in_lineup)

                            # Add constraints for players whose maximum occurrences are reached or exceeded
                            # Check against calculated max occurrences
                            for player_name, max_count in player_max_occurrences.items():
                                # Only add the constraint if it hasn't been added before and the limit is reached
                                # Using a small tolerance (0.001) for float comparison
                                if player_name in current_player_counts and current_player_counts[player_name] >= max_count - 0.001 and player_name not in exposure_constrained_players:
                                    if player_name in player_vars: # Ensure player_name exists as a variable key
                                        # Use a unique constraint name for each player's exclusion
                                        constraint_name = f"Exclude_{player_name.replace(' ', '_').replace('-', '_')}_Exposure_Limit_Reached"
                                        prob += player_vars[player_name] == 0, constraint_name
                                        # Mark as constrained to prevent adding this constraint again
                                        exposure_constrained_players.add(player_name)

                            # Add a constraint to exclude the *exact* current lineup to ensure uniqueness.
                            # This is crucial even with exposure constraints, as different combinations
                            # of low-exposure players could still form duplicate lineups.
                            # Use a unique constraint name for each lineup exclusion
                            lineup_exclusion_constraint_name = f"Exclude_Lineup_{lineup_id - 1}"
                            # The constraint is: sum of variables for players in the current lineup <= number of players - 1
                            # This forces at least one player from the current lineup to be excluded in future solutions.
                            prob += lpSum([player_vars[player] for player in selected_players]) <= len(selected_players) - 1, lineup_exclusion_constraint_name


                else:
                    # Stop generating lineups if the score is below the threshold
                    print(f"🚫 Found optimal lineup below minimum FPTS threshold ({total_fpts:.2f} < {min_fpts}). Stopping.")
                    break # Stop if the optimal score drops below the threshold


            else:
                print(f"⚠️ No more optimal lineups found. Solver status: {LpStatus[prob.status]}")
                break # Stop generating lineups if no more optimal solutions are found

    except PulpSolverError as e:
        print(f"❌ Solver Error: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")


    # Convert the list of all valid lineups to a DataFrame
    optimal_lineups_df = pd.DataFrame(valid_lineups)

    # Reorder columns for better readability (optional)
    ordered_cols = ['Lineup ID', 'Total Lineup FPTS', 'Total Lineup Salary',
                    'QB1', 'QB1 Team', 'QB1 Pos', 'QB1 Depth', 'QB1 Salary', 'QB1 FPTS', 'QB1 FPTS_Rank',
                    'RB1', 'RB1 Team', 'RB1 Pos', 'RB1 Depth', 'RB1 Salary', 'RB1 FPTS', 'RB1 FPTS_Rank',
                    'RB2', 'RB2 Team', 'RB2 Pos', 'RB2 Depth', 'RB2 Salary', 'RB2 FPTS', 'RB2 FPTS_Rank',
                    'WR1', 'WR1 Team', 'WR1 Pos', 'WR1 Depth', 'WR1 Salary', 'WR1 FPTS', 'WR1 FPTS_Rank',
                    'WR2', 'WR2 Team', 'WR2 Pos', 'WR2 Depth', 'WR2 Salary', 'WR2 FPTS', 'WR2 FPTS_Rank',
                    'WR3', 'WR3 Team', 'WR3 Pos', 'WR3 Depth', 'WR3 Salary', 'WR3 FPTS', 'WR3 FPTS_Rank',
                    'TE1', 'TE1 Team', 'TE1 Pos', 'TE1 Depth', 'TE1 Salary', 'TE1 FPTS', 'TE1 FPTS_Rank',
                    'FLEX', 'FLEX Team', 'FLEX Pos', 'FLEX Depth', 'FLEX Salary', 'FLEX FPTS', 'FLEX FPTS_Rank',
                    'DST1', 'DST1 Team', 'DST1 Pos', 'DST1 Depth', 'DST1 Salary', 'DST1 FPTS', 'DST1 FPTS_Rank'
                   ]

    existing_ordered_cols = [col for col in optimal_lineups_df.columns if col in ordered_cols]
    remaining_cols = [col for col in optimal_lineups_df.columns if col not in existing_ordered_cols]
    final_cols_order = existing_ordered_cols + remaining_cols

    if not optimal_lineups_df.empty:
        optimal_lineups_df = optimal_lineups_df[final_cols_order]

    return optimal_lineups_df