from dash import html
import dash_bootstrap_components as dbc
from dash import Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
import pandas as pd
import uuid

#ALL used for pattern matching
#ctx used to detect which input triggerred the callback


def generate_card_layout(df: pd.DataFrame) -> html.Div:
    if df.empty:
        return html.Div("No lineups generated.")

    # Ensure each row has a unique UUID
    #if "uuid-index" not in df.columns:
     #   df["uuid-index"] = [str(uuid.uuid4()) for _ in range(len(df))]

    def build_player_list(row) -> list:
        items = []
        slots = ['QB1', 'RB1', 'RB2', 'WR1', 'WR2', 'WR3', 'TE1', 'FLEX', 'DST1']
        for slot in slots:
            player = row.get(slot, 'None')
            team = row.get(f"{slot} Team", 'None')
            salary = row.get(f"{slot} Salary", 0)
            fpts = row.get(f"{slot} FPTS", 0.0)
            rank = row.get(f"{slot} FPTS_Rank", 'N/A')

            if player != 'None':
                items.append(html.Li(
                    f"{slot}: {player} ({team}, ${int(salary)}, {fpts:.2f} pts, Rank: {rank})"
                ))
        return items

    def build_card(row) -> dbc.Card:
        header_text = f"Lineup #{row['Lineup ID']} — FPTS: {row['Total Lineup FPTS']:.2f}, Salary: ${int(row['Total Lineup Salary'])}"
        player_items = build_player_list(row)

        return dbc.Card([
            dbc.CardHeader([
                html.Div(header_text, style={"display": "inline-block"}),
                dbc.Checkbox(
                    id={"type": "save-toggle", "index": row["uuid-index"]},
                    className="float-end",
                    style={"marginLeft": "10px"}
                )
            ]),
            dbc.CardBody(html.Ul(player_items, style={"fontSize": "0.85rem"}))
        ],
        id={"type": "optimizer-lineup-card-initial-uuid", "index": row["uuid-index"]},
        className="mb-3 shadow-sm")

    # Generate all cards
    cards = [build_card(row) for _, row in df.iterrows()]
    return html.Div(cards)

# Callback to save lineups old
def register_save_lineups_functionality(app):
    @app.callback(
        Output("saved-lineups-store", "data"),
        Input({"type": "save-toggle", "index": ALL}, "value"),
        State("saved-lineups-store", "data"),
        State("global-store-df3", "data")  # assuming df3 is stored here
    )
    def update_saved_lineups(toggle_values, saved_data, all_lineups):
        triggered = ctx.triggered_id
        if not triggered:
            raise PreventUpdate

        uuid = triggered["index"]
        toggled_on = toggle_values[
            next(i for i, row in enumerate(all_lineups) if row["uuid-index"] == uuid)
        ]

        if toggled_on:
            lineup = next((x for x in all_lineups if x["uuid-index"] == uuid), None)
            if lineup and lineup not in saved_data:
                saved_data.append(lineup)
        else:
            saved_data = [x for x in saved_data if x["uuid-index"] != uuid]

        return saved_data

   
def register_render_saved_lineups(app):
    @app.callback(
        Output("saved_lineup_card_container", "children"),
        Input("saved-lineups-store", "data")
    )
    def render_saved_cards(saved_data):
        if not saved_data or len(saved_data) == 0:
            return html.Div("No saved lineups yet.")

        df = pd.DataFrame(saved_data)

        # Defensive: ensure UUIDs exist for rendering
        if "uuid-index" not in df.columns:
            df["uuid-index"] = [str(uuid.uuid4()) for _ in range(len(df))]

        return generate_card_layout(df)
   
def register_render_original_lineups(app):
    @app.callback(
        Output("initial_lineup_card_container", "children"),
        Input("global-store-df3", "data"),
        Input("saved-lineups-store", "data")
    )
    def render_original_lineups(all_lineups, saved_data):
        if not all_lineups:
            return html.Div("No lineups generated.")

        saved_uuids = {x["uuid-index"] for x in saved_data or []}
        filtered = [x for x in all_lineups if x["uuid-index"] not in saved_uuids]

        df = pd.DataFrame(filtered)

        # Defensive: ensure UUIDs exist
        if "uuid-index" not in df.columns:
            df["uuid-index"] = [str(uuid.uuid4()) for _ in range(len(df))]

        return generate_card_layout(df)
    
# New 
