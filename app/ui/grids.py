# grids.py

from dash_ag_grid import AgGrid
from dash.dependencies import Input, Output

# Rename the headers at callback for the grid
RENAME_MAP_DF1 = {
    "Player" : "Name",
    "Salary" : "Salary",
    "Team" : "Team",
    "ProjectedFPTS" : "PublicFPTS",
    "fantasyPointsRank" : "PublicRank",
    "FPTS" : "TonyFPTS",
    "BiasApplied" : "BiasAdj",
    "Lambda" : "Lambda",
    "Sample_count" : "Samples",
    "FPTS_Rank" : "TonyRank"
}

ORDER_DF1 = ["Player", "Team", "Pos", "Salary", "ProjectedFPTS", "fantasyPointsRank",
              "BiasApplied", "FPTS", "FPTS_Rank", "Lambda", "Sample_count"]

EXCLUDE_DISPLAY_KEYS = ["Unnamed: 0", "Depth", "AdjustmentPercent",  "k"]

def _build_coldefs(data_keys, rename_map, order=None):
    """Build AgGrid columnDefs from data keys with header renames and optional ordering."""
    keys = order if order else list(data_keys)
    # keep only keys actually present
    keys = [k for k in keys if k in data_keys]

    # also include any remaining keys unless explicitly excluded not in the order (preserve input order)
    if order:
        keys += [k for k in data_keys if k not in keys and k not in EXCLUDE_DISPLAY_KEYS]

    # Add a checkbox to the grid.
    checkbox_col = [
        {
            "field" : "global-aggrid-df1-checkbox",
            "headerName" : "",
            "checkboxSelection" : True,
            "headerCheckboxSelection" : True,
            "width" : 50
        }
    ]


    other_cols = [
        {
            "field": k,                          # must match the data key
            "headerName": rename_map.get(k, k),  # display label
        }
        for k in keys
    ]

    return checkbox_col + other_cols

# Register the callback so that tha app object is visible
def register_callbacks_grid(app):
    @app.callback(
        Output("global-aggrid-df1", "rowData"),
        Output("global-aggrid-df1", "columnDefs"),
        Input("global-store-df1", "data")
    )
    def populate_grid_df1(data):
        if not data:
            return [], []

        # Extract column names from the first row.
        # Algorithm, take the first row of the dcc.Store(dict), and extract the key from the key-value pair
        # eg {"Name": "Smith", "Team": "BUF"} will return "Name", "Team"
        data_keys = list(data[0].keys())

        # Add the checkbox to to each row
        for row in data:
            row["global-aggrid-df1-checkbox"] = False

        columns = _build_coldefs(data_keys, RENAME_MAP_DF1, ORDER_DF1)

        return data, columns
    
 #   @app.callback(
  #      Output("global-aggrid-df2", "rowData"),
  #      Output("global-aggrid-df2", "columnDefs"),
  #      Input("global-store-df2", "data")
 #   )
   # def populate_grid_df2(data):
#    if not data:
  #          return [], []

        # Extract column names from the first row
   #     columns = [{"headerName": col, "field": col} for col in data[0].keys()]
   #     return data, columns
