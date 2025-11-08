import zipfile
import os
import pandas as pd

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.dfsutils import TEAMS, normalize_field, fuzzy_match_and_merge



import logging

# Set up logging to file
logging.basicConfig(
    filename='merge_log.txt',
    filemode='w',  # Overwrite each run; use 'a' to append
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)



# Define ZIP file path using os.path.join for cross-platform compatibility
ZIP_FILE_PATH = os.path.join('.', 'source', 'Week9MilliMakerREsults.zip')
EXTRACTED_CSV_NAME = 'DKResults.csv'
OPTIMIZER_PREP_FINAL_PATH = os.path.join('.', 'source', 'nfl_Week9_final_with_lambda_and_Salary.xlsx')

def post_process():
    extract_path = os.path.dirname(ZIP_FILE_PATH)
    extracted_csv_path = os.path.join(extract_path, EXTRACTED_CSV_NAME)

    try:
        # Open and inspect the ZIP file
        with zipfile.ZipFile(ZIP_FILE_PATH, 'r') as zip_ref:
            namelist = zip_ref.namelist()
            if not namelist:
                raise IndexError("ZIP archive is empty.")

            csv_in_zip = namelist[0]
            zip_ref.extract(csv_in_zip, extract_path)

            # Rename the extracted file
            original_csv_path = os.path.join(extract_path, csv_in_zip)
            os.rename(original_csv_path, extracted_csv_path)

        # Load and process the CSV
        results_df = pd.read_csv(extracted_csv_path, encoding='utf-8')
        results_df = results_df[['Player', '%Drafted', 'FPTS']]
        results_df = results_df.rename(columns={
            'Player': 'ResultsPlayer',
            'FPTS': 'ActualFPTS',
            '%Drafted': 'ActualDrafted'
        })



        # Optional: clean up extracted file
        os.remove(extracted_csv_path)

    except FileNotFoundError:
        print(f"Error: Zip file not found at {ZIP_FILE_PATH}")
    except IndexError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print("Rows in results_df is :", results_df.shape)
    print(results_df.head())
    return results_df

def optimizer_files():
    # Read this weeks projected file into a dataframe
    try:
        df_optimizer_prep_final = pd.read_excel(OPTIMIZER_PREP_FINAL_PATH)
    except FileNotFoundError:
        print(f"Error: Zip file not found at {OPTIMIZER_PREP_FINAL_PATH}")
    except IndexError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    print("Rows in sf_optimizer_prep_final is  :", df_optimizer_prep_final.shape)
    print(df_optimizer_prep_final)
    return df_optimizer_prep_final

def remove_nans_from_results_file(results_df):
    results_df = results_df.dropna(subset=['ResultsPlayer'])
    print("Rows in results_df after NaN removal is  :", results_df.shape)
    return results_df

def log_dst_matches(df_optimizer_prep_final, results_df):
    import logging

    # Filter DST rows
    dst_df = df_optimizer_prep_final[df_optimizer_prep_final["Pos"] == "DST"].copy()

    # Normalize ResultsPlayer for comparison
    results_players = set(results_df["ResultsPlayer"].dropna().unique())

    matched = []
    unmatched = []

    for _, row in dst_df.iterrows():
        player = row.get("Player")
        team = row.get("Team")
        if player in results_players:
            matched.append((player, team))
            logging.info(f"DST MATCHED: Player='{player}', Team='{team}' found in ResultsPlayer")
        else:
            unmatched.append((player, team))
            logging.warning(f"DST UNMATCHED: Player='{player}', Team='{team}' NOT found in ResultsPlayer")

    # Summary
    logging.info(f"DST Summary: Total={len(dst_df)}, Matched={len(matched)}, Unmatched={len(unmatched)}")
    logging.info(f"Matched DSTs: {[p for p, _ in matched]}")
    logging.info(f"Unmatched DSTs: {[p for p, _ in unmatched]}")


def make_team_names_consistent(results_df, df_optimizer_prep_final):
    # Run an inline update on Nand where Pos = DST, and TeamName for consistency
    df_optimizer_prep_final = normalize_field(df_optimizer_prep_final, "Team", TEAMS)
    results_df = normalize_field(results_df, "ResultsPlayer", TEAMS)

    print("ResultsPlayer keys:", results_df["ResultsPlayer"].unique())
    print("Player keys:", df_optimizer_prep_final["Player"].unique())


    return results_df, df_optimizer_prep_final

def merge_week_files(results_df, df_optimizer_prep_final):
    # results_df is the dribing file
    df_final = fuzzy_match_and_merge(
        results_df,
        df_optimizer_prep_final,
        "ResultsPlayer",
        "Player",
        min_score=90
    )

    # Log unmatched records (_score is NaN)
    unmatched = df_final[df_final["_score"].notna()]
    for _, row in unmatched.iterrows():
        logging.info(f"UNMATCHED: ResultsPlayer='{row.get('ResultsPlayer')}', Player='{row.get('Player')}', _score=NaN")

    # Log matched records (_score is not NaN)
    matched = df_final[df_final["_score"].isna()]
    for _, row in matched.iterrows():
        logging.info(f"MATCHED: ResultsPlayer='{row.get('ResultsPlayer')}', Player='{row.get('Player')}', _score={row['_score']:.2f}")

    # Optional summary
    logging.info(f"Merge Summary: Total={len(df_final)}, Matched={len(matched)}, Unmatched={len(unmatched)}")
    logging.info(f"df_final columns: {list(df_final.columns)}")

    # Log unmatched into a csv
    #pd.DataFrame(unmatched, columns=["ResultsPlayer", "Player", "Team"]).to_csv("unmatched_dsts.csv", index=False)
    # pd.DataFrame(unmatched, columns=["ResultsPlayer", "Player", "Team"]).to_csv("matched_dsts.csv", index=False)
    print(df_final.columns)

    # If the Salary is NaN, then most likely DK did not have them listed or there was issue with df_optimizer_prep_final
    
    df_final = df_final[df_final["Salary"].notna()]

    df_final.to_excel("df_final.audit.xlsx")

    return df_final
    

    
def final_processing_current_week():
    #Add Week numver and generate actual ranks
    pass


def combine_curnent_with_historical():
    # Verically concatenate current and historicalfiless and save
    pass

if __name__ == "__main__":
    results_df = post_process()
    df_optimizer_prep_final = optimizer_files()
    results_df = remove_nans_from_results_file(results_df)
    results_df, df_optimizer_prep_final = make_team_names_consistent(results_df, df_optimizer_prep_final)
    log_dst_matches(df_optimizer_prep_final, results_df)
    df_final = merge_week_files(results_df, df_optimizer_prep_final)
    # final_processing_current_week()
    # combine_curnent_with_historical()

