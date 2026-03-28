# import zipfile
import os
import pandas as pd

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.dfsutils import TEAMS, normalize_field, fuzzy_match_and_merge
from utils.lambda_calculations import process_all_players_with_bias_adjustment, adjust_future_projections_dataframe, compute_position_level_bias_summary


import logging

# Set up logging to file
logging.basicConfig(
    filename='optimizer_prep_log.txt',
    filemode='w',  # Overwrite each run; use 'a' to append
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

NFL_WEEK = 11
HISTORICAL_DATA_FILE = os.path.join('.', 'source', 'Week1to10_results_cleaned.xlsx')
DF_PROJECTIONS = os.path.join('.', 'source', 'PFFprojectionsWeek11.csv')
DF_SALARIES = os.path.join('.', 'source', 'DKSalariesWeek11.csv')

REQUIRED_DK_SALARIES_FIELDS = ["Name", "Salary", "TeamAbbrev", "Roster Position"]
REQUIRED_DF_OPTIMIZER_PREP_FIELDS = ["Name", "Salary", "teamName", "position", "fantasyPoints"]

DEBUG_LAMBDA_CALC = False
USING_ADJUSTED_FLAG = True

OUTPUT_OPTIMIZER_PREP_FINAL = os.path.join('.', 'generated', 'Week11_optimizer_prep_final.xlsx')

def phase1_cleanup_and_merge():
    df_projections = pd.read_csv(DF_PROJECTIONS)
    df_salaries = pd.read_csv(DF_SALARIES)  

    # Data cleanup and refactoring for df_projections
    df_projections['position'] = df_projections['position'].str.upper()
    df_projections.loc[df_projections['position'] == 'DST', 'playerName'] = df_projections.loc[df_projections['position'] == 'DST', 'teamName']
    df_projections.drop(columns=['passComp',
       'passAtt', 'passYds', 'passTd', 'passInt', 'passSacked', 'rushAtt',
       'rushYds', 'rushTd', 'recvTargets', 'recvReceptions', 'recvYds', 'recvTd'], inplace=True)
    
    # Data cleanup and refactoring for df_salaries
    
    # df_salaries.rename(columns={'Roster Position': 'Position'}, inplace=True)
    df_salaries = df_salaries[REQUIRED_DK_SALARIES_FIELDS]
    
    # Safe normalize PFFProjection.teamName and PFFProjection.Name.  
    df_projections = normalize_field(df_projections, "teamName", TEAMS)
    df_projections = normalize_field(df_projections, "playerName", TEAMS)

    #Safe normalize df_salaries.  Name and teamAbbrev
    df_salaries = normalize_field(df_salaries, "TeamAbbrev", TEAMS)

    #Create a dataframe of unique TeamAbbrev from df_salaries.  Perform slate specific cleaning vs. 
    # Week specific for projections
    
    df_salaries_unique_teams = df_salaries['TeamAbbrev'].unique()
    df_projections = df_projections[df_projections["teamName"].isin(df_salaries_unique_teams)]
 
   # In df_salaries, make Name be equal to teamAbbrev where position = 'DST
    df_salaries.loc[df_salaries['Roster Position'] == 'DST', 'Name'] = df_salaries.loc[df_salaries['Roster Position'] == 'DST', 'TeamAbbrev']

    logging.info(f"Unique TeamAbbrev values in df_salaries: {df_salaries_unique_teams}")
    df_projections_unique_team_names = df_projections['teamName'].unique()
    logging.info(f"Unique teamName values in df_projections: {df_projections_unique_team_names}")

    df_optimizer_prep = fuzzy_match_and_merge(
        df_salaries,
        df_projections,
        'Name',  # Pass column names as strings
        'playerName' # Pass column names as strings
    )

    # Remove extraneous columns
    df_optimizer_prep=df_optimizer_prep[REQUIRED_DF_OPTIMIZER_PREP_FIELDS]
    
    # Add in the ranks, grouping by position after renaming fields

    # Rename fields
    OPTIMIZER_PREP_RENAMES = {
        "position" : "Pos",
        "fantasyPoints" : "ProjectedFPTS",
        "teamName" : "Team",
        "Name" : "Player"
    }

    df_optimizer_prep = df_optimizer_prep.rename(columns=OPTIMIZER_PREP_RENAMES)

    df_optimizer_prep['ProjectedFPTS_Rank'] = df_optimizer_prep.groupby('Pos')['ProjectedFPTS'].rank(ascending=False, method='min')
    
    # Remove players where there is no value in ProjectedFPTS, useless
    df_optimizer_prep = df_optimizer_prep.dropna(subset=['ProjectedFPTS'])

    df_optimizer_prep.to_excel("debug_salary.xlsx")
  
    return df_optimizer_prep

def phase2_introduce_lambda(HISTORICAL_DATA_FILE, df_optimizer_prep):
    df_historical = pd.read_excel(HISTORICAL_DATA_FILE)

    #  Reurns weekly level dataframe
    # Player level dataframe, Name , Bias Mean, Applied bias and Sample count
    adjusted_df, player_bias_df = process_all_players_with_bias_adjustment(df_historical)

    # Run with optional FPTS threshold (e.g., filter out samples with ProjectedFPTS < 5.0)
    position_bias_df = compute_position_level_bias_summary(df_historical, min_projected_fpts=5.0)


    # Rename df_future_projections names to have 'Name', 'Team, 'Postion' 
    RENAME_DICT = {
        "Player" : "Name",
        "Pos" : "Position"
    }
    df_optimizer_prep = df_optimizer_prep.rename(columns=RENAME_DICT)

    df_optimizer_prep_final = adjust_future_projections_dataframe(
        df_future_projections=df_optimizer_prep,
        player_bias_df=player_bias_df,
        position_bias_df=position_bias_df,
        k = 5.0)
    
    # Create the ranks
    df_optimizer_prep_final['ProjectedFPTS_Rank'] = df_optimizer_prep_final.groupby('Position')['ProjectedFPTS'].rank(ascending=False, method='min')
    df_optimizer_prep_final['AdjustedFPTS_Rank'] = df_optimizer_prep_final.groupby('Position')['AdjustedFPTS'].rank(ascending=False, method='min' )
    
    if USING_ADJUSTED_FLAG:
        df_optimizer_prep_final['FPTS'] = df_optimizer_prep_final['AdjustedFPTS']
        df_optimizer_prep_final['FPTS_Rank'] = df_optimizer_prep_final['AdjustedFPTS_Rank']

    df_optimizer_prep_final.to_excel(OUTPUT_OPTIMIZER_PREP_FINAL)
    
                                                                                                                                                                                                                                                     

if __name__ == "__main__":
    df_optimizer_prep = phase1_cleanup_and_merge()
    # df_optimizer_prep.to_excel("test_optimizer_prep.xlsx")
    phase2_introduce_lambda(HISTORICAL_DATA_FILE, df_optimizer_prep)
    

"""
Key fiels:
projectedPoints (from df_projections typically PFF) -> ProjectedFPTS
ProjectedFPTS_Rank based upon Week, Position, ProjectedFPTS

AdjustedFPTS is the result of lambda calculations
AdjustedFPTS_Rank is ranks of above

Set the field for the optimizer to use:
Set the USING_ADJUSTED_FLAG to TRUE
Create the FPTS, FPTS_Rank fields from lambda generated AdjustedFPTS and AdjustedFPTS_Rank


"""