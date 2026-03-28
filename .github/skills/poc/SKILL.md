---
name: poc
description: A proof-of-concept skill for querying fantasy football player statistics and ownership data. Use when: reporting player stats, querying ownership percentages, comparing QBs, or answering questions about Excel data and player performance.
---

# Fantasy Football POC Skill

This skill reads fantasy football data from Excel files and answers questions about player statistics, ownership, and performance.

## Workflow
1. Greet the user with a "Hello World" message including the current date.
2. Read the Excel file at `app/data/Week1to10_results_cleaned.xlsx` using pandas, and report the number of rows and columns, including semantic meanings from `column_descriptions.json`.
3. Answer user queries about specific players (e.g., Josh Allen) or positions (e.g., QB) by filtering the data and returning relevant stats.

## Instructions
- When invoked, respond with: "[POC Skill Invoked] Hello World! This is a POC skill." Include the current date and time in the greeting.
- Read the Excel file at `app/data/Week1to10_results_cleaned.xlsx` using pandas.
- Read `column_descriptions.json` in the skill directory to get semantic descriptions for each column, and include them in the response.
- To query a specific player's stats (e.g., "What are Josh Allen's stats?"):
  - Filter the DataFrame where the `Name` column matches the player name (case-insensitive).
  - Return relevant columns: `Name`, `Position`, `Week`, `ActualFPTS`, `ProjectedFPTS`, `ActualDrafted`, `Salary`.
- To query ownership data (e.g., "Who has the highest ownership?"):
  - Sort by the `ActualDrafted` column descending and return the top results.
- To compare players at a position (e.g., "Show me all QBs"):
  - Filter the DataFrame where `Position` equals the requested position.
  - Return a summary sorted by `ActualFPTS` descending.
- Keep responses concise and focused on the requested data.