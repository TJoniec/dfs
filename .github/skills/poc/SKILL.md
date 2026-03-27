---
name: poc
description: A simple proof-of-concept skill that demonstrates basic agent workflows. Use when: testing skills, generating hello world examples, or answering questions about Excel data and player stats.
---

# Simple POC Skill

This skill provides a basic demonstration of agent capabilities.

## Workflow
1. Greet the user with a "Hello World" message including the current date.
2. Read the Excel file at C:\Users\tonyj\OneDrive\Documents\VSCode\BasicDash\app\data\Week1to10_results_cleaned.xlsx and report the number of rows and columns, including semantic meanings from column_descriptions.json.
3. Generate a simple Python code snippet as an example.

## Instructions
- When invoked, respond with: "[POC Skill Invoked] Hello World! This is a POC skill." Include the current date and time in the greeting.
- Read the Excel file at C:\Users\tonyj\OneDrive\Documents\VSCode\BasicDash\app\data\Week1to10_results_cleaned.xlsx using pandas, and report the number of rows and columns.
- Read column_descriptions.json in the skill directory to get semantic descriptions for each column, and include them in the response.
- Then, provide a basic Python print statement snippet.
- Keep responses short and focused.