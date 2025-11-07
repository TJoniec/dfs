import zipfile
import os
import pandas as pd

import sys
import os


# Define ZIP file path using os.path.join for cross-platform compatibility
ZIP_FILE_PATH = os.path.join('.', 'source', 'Week9MilliMakerREsults.zip')
EXTRACTED_CSV_NAME = 'DKResults.csv'
OPTIMIZER_PREP_FINAL_PATH = os.path.join('.', 'source', 'nfl_Week9_final_with_lambda_and_Salary).xlsx')

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

def remove_nans_from_results_file():
     results_df = results_df.dropna(subset=['ResultsPlayer'])
     print("Rows in results_df after NaN removal is  :", results_df.shape)

def make_team_names_consistent():
    # Run an inline update on Nand where Pos = DST, and TeamName for consistency
    pass

def merge_week_files():
    pass

def final_processing_current_week():
    #Add Week numver and generate actual ranks
    pass


def combine_curnent_with_historical():
    # Verically concatenate current and historicalfiless and save
    pass

if __name__ == "__main__":
    post_process()
    optimizer_files()
    remove_nans_from_results_file()
    make_team_names_consistent()
    merge_week_files()
    final_processing_current_week()
    combine_curnent_with_historical()

