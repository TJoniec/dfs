# app.pypos
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
from dash_ag_grid import AgGrid

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



# Constants
FILE_NAME_1 = ('./data/Week9_optimizer_Prep_final.xlsx') # Master
FILE_NAME_2 = ('./data/Week1to8_results_cleaned.xlsx') # Detail
FILE_NAME_3 = ('./data/sample_week9_optimal_lineups_with_exposure.xlsx') # Testing of cards

#Define the app variable and define the style sheeet, using one for dark contrast
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

def read_data_source_1(FILE_NAME_1):
    df = pd.read_excel(FILE_NAME_1)
    df= force_numeric(df, ["FPTS_Rank", "fantasyPointsRank"])
    return df

def read_data_source_2(FILE_NAME_2):
    df = pd.read_excel(FILE_NAME_2)
    return df

def read_data_source_3(FILE_NAME_3):
    df = pd.read_excel(FILE_NAME_3)
    # Add uuid for use in cards
    df["uuid-index"] = [str(uuid.uuid4()) for _ in range(len(df))]
    return df

df1 = read_data_source_1(FILE_NAME_1)
df2 = read_data_source_2(FILE_NAME_2)
df3 = read_data_source_3(FILE_NAME_3)

# Define callbacks.  This callback is triggerred automatically upon data load
@app.callback(
    Output("debug-df3", "children"),
    Input("global-store-df1", "data")
)
def show_store_contents(data):
    if not data:
        return "No data loaded"
    return f"Records loaded for global-store-df1: {len(data)}"

@app.callback(
    Output("debug-df4", "children"),
    Input("global-store-df2", "data")
)
def show_store_contents(data):
    if not data:
        return "No data loaded"
    return f"Records loaded for global-store-df2: {len(data)}"

@app.callback(
    Output("debug-df5", "children"),
    Input("global-store-df3", "data")
)
def show_store_contents(data):
    if not data:
        return "No data loaded"
    return f"Records loaded for global-store-df3 (Orig Lineups): {len(data)}"

@app.callback(
    Output("debug-df6", "children"),
    Input("saved-lineups-store", "data")
)
def show_store_contents(data):
    if not data:
        return "No data loaded"
    return f"Records loaded for saved-lineups-store: {len(data)}"


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
    dcc.Store(id="global-store-df3", data=df3.to_dict("records")),
    dcc.Store(id="saved-lineups-store", data=[], storage_type="session"),
    html.Pre(id="debug-df2"),
    html.Pre(id="debug-df1"),
    html.Pre(id="debug-df3"),
    html.Pre(id="debug-df4"),
    html.Pre(id="debug-df5"),
    html.Pre(id="debug-df6"),

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
            generate_card_layout(df3),  # ← This is where you run it
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
    ], width=12, lg=4)
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
], fluid=True )


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8050)

    
