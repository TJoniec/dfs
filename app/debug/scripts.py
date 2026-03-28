#scripts.py
from dash import Input, Output, State, callback

def register_debug_callbacks(app):
    @app.callback(
        Output("debug-df2", "children"),
        Input("global-store-df2", "data")
    )
    def show_df2_status(data):
        if not data:
            return "⚠️ No historical results loaded"
        return f"✅ Historical results (df2): {len(data)} records"

    @app.callback(
        Output("debug-df1", "children"),
        Input("global-store-df1", "data")
    )
    def show_df1_status(data):
        if not data:
            return "⚠️ No player master data loaded"
        return f"✅ Player master data (df1): {len(data)} records"
