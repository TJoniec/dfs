"""
POC Skill: Fantasy Football Player Stats Query
Reads historical fantasy football data and answers queries about player stats,
ownership, and performance.
"""

import json
import os
from datetime import datetime

import pandas as pd

# Paths relative to the app directory
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "Week1to10_results_cleaned.xlsx")
COLUMN_DESCRIPTIONS_FILE = os.path.join(
    os.path.dirname(__file__), "..", ".github", "skills", "poc", "column_descriptions.json"
)

QUERY_COLUMNS = ["Name", "Position", "Week", "ActualFPTS", "ProjectedFPTS", "ActualDrafted", "Salary"]


def load_data():
    """Load the Excel data file into a DataFrame."""
    df = pd.read_excel(DATA_FILE)
    return df


def load_column_descriptions():
    """Load semantic column descriptions from JSON."""
    with open(COLUMN_DESCRIPTIONS_FILE, "r") as f:
        return json.load(f)


def greet():
    """Print the POC skill greeting with current date/time."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[POC Skill Invoked] Hello World! This is a POC skill. Current date/time: {now}")


def report_data_summary(df, column_descriptions):
    """Report the number of rows, columns, and their semantic meanings."""
    print(f"\nData loaded: {df.shape[0]} rows x {df.shape[1]} columns")
    print("\nColumn descriptions:")
    for col in df.columns:
        desc = column_descriptions.get(col, "No description available")
        print(f"  {col}: {desc}")


def query_player(df, player_name):
    """Return stats for a specific player (case-insensitive match)."""
    mask = df["Name"].str.lower() == player_name.lower()
    result = df.loc[mask, [c for c in QUERY_COLUMNS if c in df.columns]]
    if result.empty:
        print(f"\nNo data found for player: {player_name}")
    else:
        print(f"\nStats for {player_name}:")
        print(result.to_string(index=False))
    return result


def query_top_ownership(df, top_n=10):
    """Return players with the highest actual ownership (ActualDrafted)."""
    cols = [c for c in QUERY_COLUMNS if c in df.columns]
    result = (
        df[cols]
        .sort_values("ActualDrafted", ascending=False)
        .drop_duplicates(subset=["Name"])
        .head(top_n)
    )
    print(f"\nTop {top_n} players by ownership (ActualDrafted):")
    print(result.to_string(index=False))
    return result


def query_position(df, position):
    """Return a summary of players at a specific position, sorted by ActualFPTS."""
    mask = df["Position"].str.upper() == position.upper()
    cols = [c for c in QUERY_COLUMNS if c in df.columns]
    result = (
        df.loc[mask, cols]
        .sort_values("ActualFPTS", ascending=False)
        .drop_duplicates(subset=["Name", "Week"])
    )
    if result.empty:
        print(f"\nNo data found for position: {position}")
    else:
        print(f"\nAll {position.upper()} players sorted by ActualFPTS:")
        print(result.to_string(index=False))
    return result


def main():
    greet()
    df = load_data()
    column_descriptions = load_column_descriptions()
    report_data_summary(df, column_descriptions)

    # Example queries demonstrating the POC
    print("\n--- Example: Josh Allen's stats ---")
    query_player(df, "Josh Allen")

    print("\n--- Example: Top 10 by ownership ---")
    query_top_ownership(df, top_n=10)

    print("\n--- Example: All QBs sorted by ActualFPTS ---")
    query_position(df, "QB")


if __name__ == "__main__":
    main()
