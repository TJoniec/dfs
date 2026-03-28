---
name: poc
description: A proof-of-concept skill for querying fantasy football player statistics and ownership data. Use when: reporting player stats, querying ownership percentages, comparing QBs, RBs or other positions, or answering questions about Excel data and player performance across weeks 1-10.
---

# Fantasy Football POC Skill

This skill reads fantasy football data from Excel files and answers questions about player statistics, ownership, and performance for weeks 1 through 10.

## Data Source
- File: `app/data/Week1to10_results_cleaned.xlsx`
- Column semantics: `.github/skills/poc/column_descriptions.json`
- Key columns: `Name`, `Team`, `Position`, `Week`, `Salary`, `ActualFPTS`, `ActualFPTS_Rank`, `ProjectedFPTS`, `ProjectedFPTS_Rank`, `ActualDrafted` (ownership %)

## Workflow
1. Greet the user with a "Hello World" message including the current date.
2. Read the Excel file at `app/data/Week1to10_results_cleaned.xlsx` using pandas, and report the number of rows and columns, including semantic meanings from `column_descriptions.json`.
3. Answer user queries about specific players, positions, teams, weeks, or ownership by filtering the data and returning relevant stats.

## Instructions
- When invoked, respond with: "[POC Skill Invoked] Hello World! This is a POC skill." Include the current date and time in the greeting.
- Read the Excel file at `app/data/Week1to10_results_cleaned.xlsx` using pandas.
- Read `.github/skills/poc/column_descriptions.json` to get semantic descriptions for each column.
- **Player stats query** (e.g., "What are Josh Allen's stats?"):
  - Filter the DataFrame where the `Name` column matches the player name (case-insensitive).
  - Return columns: `Name`, `Position`, `Team`, `Week`, `ActualFPTS`, `ProjectedFPTS`, `ActualDrafted`, `Salary`.
- **Team lookup by week** (e.g., "What team did Patrick Mahomes play for in Week 2?"):
  - Filter rows where `Name` matches the player (case-insensitive) AND `Week` equals the requested week.
  - Return the `Team` value for that row.
- **Position salary and ranking by week** (e.g., "Player names, salary and ranking for RB in week 1"):
  - Filter rows where `Position` matches the requested position AND `Week` equals the requested week.
  - Sort by `ActualFPTS_Rank` ascending (lower rank number = better performance).
  - Return columns: `Name`, `Salary`, `ActualFPTS_Rank`, `ProjectedFPTS_Rank`, `ActualFPTS`.
- **Ownership across multiple weeks** (e.g., "What was the ownership of Josh Allen in Weeks 1 through 5?"):
  - Filter rows where `Name` matches the player (case-insensitive) AND `Week` is within the requested range.
  - Return columns: `Name`, `Week`, `ActualDrafted`, `ActualFPTS`, `Salary`, sorted by `Week`.
  - Note: `ActualDrafted` is the actual ownership percentage (e.g., "12.46%").
- **Highest ownership query** (e.g., "Who has the highest ownership?"):
  - Convert `ActualDrafted` to numeric (strip the "%" suffix) and sort descending.
  - Return the top results with `Name`, `Position`, `Week`, `ActualDrafted`, `ActualFPTS`.
- **Position comparison** (e.g., "Show me all QBs" or "Compare RBs"):
  - Filter the DataFrame where `Position` equals the requested position.
  - Return a summary sorted by `ActualFPTS` descending, including `Name`, `Team`, `Week`, `ActualFPTS`, `Salary`.
- Keep responses concise and focused on the requested data.