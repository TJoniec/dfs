# app.pypos
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
from dash_ag_grid import AgGrid
from dash.exceptions import PreventUpdate
from dash import callback_context as ctx


import pandas as pd
import json
import uuid

from ui.grids import register_callbacks_grid
from ui.grid_js_stypes import RANK_DIFFERENCE_ROW_CLASSES
from utils.pre_processing import force_numeric
from filters.create_filters import register_callbacks_master_detail
from debug.scripts import register_debug_callbacks
from ui.cards_movement import generate_card_layout, register_save_lineups_functionality, register_render_saved_lineups, register_render_original_lineups
from utils.frequency_analysis_by_pos import register_frequency_analysis
from utils.stack_analysis_for_generated_and_saved_lineups import register_stack_analysis
#from app.utils.handbuild_backup import make_handbuild_section, register_handbuild_options, register_handbuild_preview
from utils.handbuild import make_handbuild_section, register_handbuild_options, register_handbuild_preview

from optimizer.optimizer_original import generate_optimal_lineups_nfl

# app.py (very top, after stdlib imports)
import os, shutil
from pathlib import Path

# Point PATH at your bundled CBC
CBC_DIR = (Path(__file__).resolve().parent / "solvers" / "bin")
os.environ["PATH"] = str(CBC_DIR) + os.pathsep + os.environ.get("PATH", "")

# Optional: sanity check
print("CBC found at:", shutil.which("cbc") or shutil.which("cbc.exe"))

# Constants
FILE_NAME_1 = ('./data/Week11_optimizer_prep_final.xlsx') # Master
FILE_NAME_2 = ('./data/Week1to10_results_cleaned.xlsx') # Detail
FILE_NAME_3 = ('./data/sample_week9_optimal_lineups_with_exposure.xlsx') # Testing of cards

#Define the app variable and define the style sheeet, using one for dark contrast
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

def read_data_source_1(FILE_NAME_1):
    df = pd.read_excel(FILE_NAME_1)
    df= force_numeric(df, ["FPTS_Rank", "fantasyPointsRank"])
    df.rename(columns={"Name" : "Player", "Position" : "Pos"}, inplace=True)
    df["Depth"]= 1
    return df

def read_data_source_2(FILE_NAME_2):
    df = pd.read_excel(FILE_NAME_2)
    df.rename(columns={"Name" : "Player"}, inplace=True)
    return df

def read_data_source_3(FILE_NAME_3):
    df = pd.read_excel(FILE_NAME_3)
    # Add uuid for use in cards
    df["uuid-index"] = [str(uuid.uuid4()) for _ in range(len(df))]
    return df

df1 = read_data_source_1(FILE_NAME_1)
df2 = read_data_source_2(FILE_NAME_2)
# df3 = read_data_source_3(FILE_NAME_3)

from dash.exceptions import PreventUpdate  # add once at top if not present

# Shared style for monitoring status elements
_STATUS_PRE_STYLE = {"fontSize": "0.85rem", "marginBottom": 0}

# Define callbacks.  This callback is triggered automatically upon data load
@app.callback(
    Output("debug-df3", "children"),
    Input("global-store-df1", "data")
)
def show_df1_status(data):
    if not data:
        return "⚠️ No player data"
    return f"✅ Players loaded: {len(data)}"

@app.callback(
    Output("debug-df4", "children"),
    Input("global-store-df2", "data")
)
def show_df2_status(data):
    if not data:
        return "⚠️ No historical data"
    return f"✅ Historical records: {len(data)}"

@app.callback(
    Output("debug-df5", "children"),
    Input("global-store-df3", "data")
)
def show_generated_lineups_status(data):
    if not data:
        return "⏳ No lineups generated yet"
    return f"✅ Generated lineups: {len(data)}"

@app.callback(
    Output("debug-df6", "children"),
    Input("saved-lineups-store", "data")
)
def show_saved_lineups_status(data):
    if not data:
        return "⏳ No lineups saved yet"
    return f"✅ Saved lineups: {len(data)}"

from dash import Input, Output, State

# Optimizer: Global dictionary to store player exposures
from dash import callback_context as ctx

# Global dict (you already have this)
player_exposures = {}

# Player exposures
from dash import callback_context as ctx

player_exposures = {}

@app.callback(
    Output("player-exposure-list", "children"),
    Output("dropdown-player-name", "value"),
    Output("input-player-exposure", "value"),
    Input("add-player-exposure-btn", "n_clicks"),
    Input("clear-player-exposures-btn", "n_clicks"),
    State("dropdown-player-name", "value"),
    State("input-player-exposure", "value"),
    prevent_initial_call=True
)
def handle_player_exposures(add_clicks, clear_clicks, name, exposure):
    trig = (ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None)

    if trig == "clear-player-exposures-btn":
        player_exposures.clear()
        return [], None, None

    if name and exposure is not None:
        player_exposures[name] = exposure

    items = [html.Div(f"{p}: {exp}") for p, exp in sorted(player_exposures.items())]
    return items, None, None



# Rank exposures
rank_constraints = {}

@app.callback(
    Output("rank-constraint-list", "children"),
    Output("dropdown-position", "value"),
    Output("input-start-rank", "value"),
    Output("input-end-rank", "value"),
    Output("input-count", "value"),
    Output("dropdown-type", "value"),
    Input("add-rank-constraint-btn", "n_clicks"),
    Input("clear-rank-constraints-btn", "n_clicks"),
    State("dropdown-position", "value"),
    State("input-start-rank", "value"),
    State("input-end-rank", "value"),
    State("input-count", "value"),
    State("dropdown-type", "value"),
    State("global-store-df1", "data"),
    prevent_initial_call=True
)
def handle_rank_constraints(add_clicks, clear_clicks,
                            position, start, end, count, ctype, df1_data):
    trig = (ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None)

    if trig == "clear-rank-constraints-btn":
        rank_constraints.clear()
        return [], None, None, None, None, None

    if all(v is not None for v in [position, start, end, count, ctype]):
        rank_constraints.setdefault(position, []).append([start, end, count, ctype])

    df_local = pd.DataFrame(df1_data or [])
    if "FPTS_Rank" in df_local:
        df_local["FPTS_Rank"] = pd.to_numeric(df_local["FPTS_Rank"], errors="coerce")

    display = []
    for pos, cons in rank_constraints.items():
        for s, e, _, _ in cons:
            matching = []
            if not df_local.empty and {"Pos","FPTS_Rank","Player"}.issubset(df_local.columns):
                mask = (df_local["Pos"] == pos) & (df_local["FPTS_Rank"].between(s, e, inclusive="both"))
                matching = df_local.loc[mask, "Player"].dropna().tolist()
            display.append(
                html.Div([
                    html.Strong(f"{pos} [{s}, {e}]"),
                    html.Ul([html.Li(n) for n in matching]) if matching else html.Div("No matching players")
                ])
            )

    return display, None, None, None, None, None


# Optimizer callback
@app.callback(
    Output("global-store-df3", "data"),
    Output("optimizer-status", "children"),
    Input("run-optimizer-btn", "n_clicks"),
    prevent_initial_call=True
)
def run_optimizer_and_store(n_clicks):
    if not n_clicks:
        raise PreventUpdate

    # Run optimizer using df1
    print("\n--- Player Exposure Constraints ---")
    if not player_exposures:
        print("No per-player exposure limits set.")
    else:
        for name, limit in player_exposures.items():
            print(f"{name}: <= {limit} lineups")

    optimal_lineups = generate_optimal_lineups_nfl(
        df1,  # ← this is your master dataset
        min_fpts=0,
        max_lineups=100,
        save_to_excel_each=False,
        global_max_exposure=10.0,
        player_max_exposures=player_exposures,
        rank_constraints=rank_constraints
        )

    # Add UUIDs for card rendering
    optimal_lineups["uuid-index"] = [str(uuid.uuid4()) for _ in range(len(optimal_lineups))]

    return optimal_lineups.to_dict("records"), "✅ Optimizer complete. Lineups updated."

# Call the optimizer.  REMOVED
#@app.callback(
#    Output("initial_lineup_card_container", "children"),
#   Input("global-store-df3", "data")
#)
#def update_generated_lineups(data):
#    if not data:
#        return html.Div("No lineups generated yet.")
 #   df = pd.DataFrame(data)
 #   return generate_card_layout(df)




# App callback registration
register_callbacks_grid(app)
register_callbacks_master_detail(app)
register_debug_callbacks(app)
register_save_lineups_functionality(app)
register_render_saved_lineups(app)
register_render_original_lineups(app)
register_frequency_analysis(app)
register_stack_analysis(app)
register_handbuild_options(app)
register_handbuild_preview(app, preview_container_id="handbuilt_preview_container", salary_cap=50000)
# register_preview_save_toggle(app)

# load records into a public property of a dcc.Store
app.layout = dbc.Container([
    dcc.Store(id= "global-store-df1", data=df1.to_dict('records')),
    dcc.Store(id="global-store-df2", data=df2.to_dict("records")),
    #dcc.Store(id="global-store-df3", data=df3.to_dict("records")),
    dcc.Store(id="global-store-df3", data = []),
    dcc.Store(id="saved-lineups-store", data=[], storage_type="session"),

    dbc.Card([
        dbc.CardHeader(html.H5("📊 System Status", className="mb-0")),
        dbc.CardBody([
            dbc.Row([
                dbc.Col(html.Pre(id="debug-df1", style=_STATUS_PRE_STYLE), width=12, lg=4),
                dbc.Col(html.Pre(id="debug-df2", style=_STATUS_PRE_STYLE), width=12, lg=4),
                dbc.Col(html.Pre(id="debug-df3", style=_STATUS_PRE_STYLE), width=12, lg=4),
            ], className="mb-1"),
            dbc.Row([
                dbc.Col(html.Pre(id="debug-df4", style=_STATUS_PRE_STYLE), width=12, lg=4),
                dbc.Col(html.Pre(id="debug-df5", style=_STATUS_PRE_STYLE), width=12, lg=4),
                dbc.Col(html.Pre(id="debug-df6", style=_STATUS_PRE_STYLE), width=12, lg=4),
            ]),
        ])
    ], className="mb-4"),

    AgGrid(id="global-aggrid-df1", 
           className="ag-theme-alpine-dark",
           columnDefs=[],
           rowData=[],
           dashGridOptions = {
              "rowSelection" : "multiple",
              "suppressFieldDotNotation" : True 
           },
           # getRowStyle=BETTER_THAN_PROJ, 
           rowClassRules = RANK_DIFFERENCE_ROW_CLASSES,
           defaultColDef={"sortable" : True, "filter" : True, "resizable": True},
           style = {"height": "500px", "width": "100%"}),
    AgGrid(id="global-aggrid-df2", className="ag-theme-alpine-dark", columnDefs=[], rowData=[]),

    dbc.Row([
    dbc.Col([
        html.H4("Generated Lineups"),
        html.Div(
            # generate_card_layout(df3),  # ← This is where you run it
            id="initial_lineup_card_container",
            style={"overflowY": "auto", "maxHeight": "80vh"}
        )
    ], width=12, lg=4),

    dbc.Col([
        html.H4("Saved Lineups"),
        html.Div(id="saved_lineup_card_container", style={"overflowY": "auto", "maxHeight": "80vh"})
    ], width=12, lg=4),

    dbc.Col([
        html.H4("Player Frequency Analysis"),
        html.Div(id="frequency_analysis_container", style={"overflowY": "auto", "maxHeight": "80vh"})
    ], width=12, lg=4),
]),


dbc.Row([
    dbc.Col([
        html.H4("Generated Stacks"),
        html.Div(id="generated-stacks", style={"overflowY": "auto", "maxHeight": "80vh"})
    ], width=12, lg=6),
    dbc.Col([
        html.H4("Saved Stacks"), 
        html.Div(id="saved-stacks", style={"overflowY": "auto", "maxHeight": "80vh"}) 
], width=12, lg=6)
]),
dbc.Row([
    dbc.Col([
        html.H4("Handbuild"),
        make_handbuild_section(),
    ], width=12, lg=4), # End dbc column
    dbc.Col([
       html.H4("Preview Pane") ,
       html.Div(id="handbuilt_preview_container", style={"overflowY": "auto", "maxHeight": "80vh"})
    ], width=12, lg=4)
], className= "g-3"), # End dbc row

# Player exposure cards
dbc.Card([
    dbc.CardHeader("Player Exposure Constraints"),
    dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.Label("Select Player"),
                dcc.Dropdown(
                    id="dropdown-player-name",
                    options=[{"label": name, "value": name} for name in df1["Player"].unique()],
                    placeholder="Choose a player",
                    className="mb-2 dropdown-contrast"
                )
            ], width=8),
            dbc.Col([
                html.Label("Max Exposure"),
                dcc.Input(
                    id="input-player-exposure",
                    type="number",
                    min=0,
                    step=1,
                    placeholder="e.g. 2",
                    className="mb-2 input-contrast",
                    style={"width": "100%"}
                )
            ], width=4),
        ]),
        dbc.ButtonGroup([
            dbc.Button("Add Player Exposure", id="add-player-exposure-btn", color="info"),
            dbc.Button("Clear", id="clear-player-exposures-btn", color="secondary", outline=True),
        ], className="mb-3 gap-2"),
        html.Div(id="player-exposure-list", children=[])
    ])
], className="mb-4"),

# Rank constraint cards
dbc.Card([
    dbc.CardHeader("Rank Constraints"),
    dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.Label("Position"),
                dcc.Dropdown(
                    id="dropdown-position",
                    options=[{"label": pos, "value": pos} for pos in ["QB", "RB", "WR", "TE", "DST"]],
                    placeholder="Select position",
                    className="mb-2 dropdown-contrast"
                )
            ], width=3),
            dbc.Col([
                html.Label("Start Rank"),
                dcc.Input(id="input-start-rank", type="number", placeholder="e.g. 1", className="mb-2 input-contrast", style={"width": "100%"})
            ], width=2),
            dbc.Col([
                html.Label("End Rank"),
                dcc.Input(id="input-end-rank", type="number", placeholder="e.g. 6", className="mb-2 input-contrast", style={"width": "100%"})
            ], width=2),
            dbc.Col([
                html.Label("Count"),
                dcc.Input(id="input-count", type="number", placeholder="e.g. 1", className="mb-2 input-contrast", style={"width": "100%"})
            ], width=2),
            dbc.Col([
                html.Label("Type"),
                dcc.Dropdown(
                    id="dropdown-type",
                    options=[{"label": "exact", "value": "exact"}, {"label": "min", "value": "min"}, {"label": "max", "value": "max"}],
                    placeholder="Constraint type",
                    className="mb-2 dropdown-contrast"
                )
            ], width=3),
        ]),
        dbc.ButtonGroup([
            dbc.Button("Add Rank Constraint", id="add-rank-constraint-btn", color="info"),
            dbc.Button("Clear", id="clear-rank-constraints-btn", color="secondary", outline=True),
        ], className="mb-3 gap-2"),
        html.Div(id="rank-constraint-list", children=[])
    ])
], className="mb-4"),


# Run optimizer button
dbc.Card([
    dbc.CardHeader("Run Optimizer"),
    dbc.CardBody([
        dcc.Loading(
            type="circle",
            color="#0d6efd",  # Bootstrap primary blue
            children=[
                dbc.Button("Run Optimizer", id="run-optimizer-btn", color="primary", className="mb-3"),
                html.Div(id="optimizer-status", children="Click the button to generate lineups.")
            ]
        )
    ])
], className="mb-4")



], fluid=True )


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8050)

    
