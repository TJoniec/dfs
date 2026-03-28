# DFS Optimizer

A Daily Fantasy Sports lineup optimizer built with Python and Dash.

## Project Structure

```
app/
├── app.py              # Main Dash application entry point
├── assets/             # Static assets (CSS, images)
├── data/               # Input data files
├── debug/              # Debug utilities
├── documentation/      # Developer notes and documentation
├── filters/            # Player/lineup filter logic
├── optimizer/          # Core lineup optimization logic
├── process_data/       # Data ingestion and preprocessing
├── solvers/            # CBC/COIN-OR optimization solvers
├── ui/                 # Dash UI components and layout
└── utils/              # Shared utility functions
```

## Getting Started

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the app

```bash
python app/app.py
```

## Syncing Your Local Branch with Remote

If files exist on GitHub but not on your local machine, run:

```bash
git fetch origin
git pull origin main
```

If `git status` shows your branch is already up to date but files are still missing, your local branch may not be tracking the latest remote state. To force your local `main` to exactly match the remote:

```bash
git fetch origin
git reset --hard origin/main
```

> **Note:** `git reset --hard` will discard any uncommitted local changes. Make sure to stash or commit anything you want to keep first:
> ```bash
> git stash
> git fetch origin
> git reset --hard origin/main
> git stash pop   # re-apply your saved changes if needed
> ```
