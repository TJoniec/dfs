#scripts.py
from dash import Input, Output, State, callback
import json

def register_debug_callbacks(app):
    @app.callback(
        Output("debug-df2", "children"),
        Input("global-store-df2", "data")
    )
    def show_df2(data):
        if not data:
            return "No df2 data loaded"
        return "global-store-df2" + json.dumps(data[:1], indent=2)
    
    @app.callback(
        Output("debug-df1", "children"),
        Input("global-store-df1", "data")
    )
    def show_df1(data):
        if not data:
            return "No df1 data loaded"
        return "global-store-df1" + json.dumps(data[:1], indent=2)
