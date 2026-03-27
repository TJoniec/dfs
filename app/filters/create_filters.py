from dash import Input, Output, State, callback
# create_filters.py
# "SelectedRows gives full row data for each selected checkbox
# Match by Name into a global-store-df2
#  Return the filtered list to populate global-aggrid-df2
# "selectedRows" is a callback input that returns a full list of dictionaries for each selected row.
# AgGrid handles selection atuomatically and already affects what checked.  The selectedrows list already 
# reflects whats been selected

# use row.get to get a key from a dictionary when unsure if the field exists.
# row,get('fienldname') is safer that row['fieldname]

EXCLUDED_COLUMNS = {"internalId", "debugFlag", "global-aggrid-df1-checkbox"}
#EXCLUDED_COLUMNS = set()

def register_callbacks_master_detail(app):
    @app.callback(
        Output("global-aggrid-df2", "rowData"),
        Output("global-aggrid-df2", "columnDefs"),
        Input("global-aggrid-df1", "selectedRows"),
        State("global-store-df2", "data")
    )
    def update_detail_grid(selected_rows, df2_data):
        if not selected_rows or not df2_data:
            return [], []

        selected_players = {row["Player"] for row in selected_rows if "Player" in row}
        filtered = [row for row in df2_data if row.get("Player") in selected_players]

        if not filtered:
            return [], []

        column_defs = [
            {"headerName": col, "field": col, "sortable": True, "filter": True}
            for col in filtered[0].keys()
            if col not in EXCLUDED_COLUMNS
        ]

        return filtered, column_defs

