from dash import html
import dash_bootstrap_components as dbc
from dash import Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
import pandas as pd
import uuid

# ALL used for pattern matching
# ctx used to detect which input triggerred the callback


# <<< CHANGED: accept saved_uuids and reflect checkbox value based on saved state
def generate_card_layout(df: pd.DataFrame, saved_uuids: set | None = None) -> html.Div:
    saved_uuids = saved_uuids or set()

    if df.empty:
        return html.Div("No lineups generated.")

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
        uid = row["uuid-index"]  # <<< CHANGED: cache uid

        return dbc.Card([
            dbc.CardHeader([
                html.Div(header_text, style={"display": "inline-block"}),
                dbc.Checkbox(
                    id={"type": "save-toggle", "index": uid},
                    className="float-end",
                    style={"marginLeft": "10px"},
                    value=(uid in saved_uuids)  # <<< CHANGED: reflect saved state
                )
            ]),
            dbc.CardBody(html.Ul(player_items, style={"fontSize": "0.85rem"}))
        ],
        id={"type": "optimizer-lineup-card-initial-uuid", "index": uid},
        className="mb-3 shadow-sm")

    # Generate all cards
    cards = [build_card(row) for _, row in df.iterrows()]
    return html.Div(cards)


# Callback to save/unsave lineups (works from both columns)
def register_save_lineups_functionality(app):
    @app.callback(
        Output("saved-lineups-store", "data"),
        Input({"type": "save-toggle", "index": ALL}, "value"),
        State({"type": "save-toggle", "index": ALL}, "id"),  # <<< CHANGED: map values <-> ids
        State("saved-lineups-store", "data"),
        State("global-store-df3", "data"),  # assuming df3 is stored here
        prevent_initial_call=True  # <<< CHANGED: avoids firing on first render
    )
    def update_saved_lineups(toggle_values, toggle_ids, saved_data, all_lineups):
        triggered = ctx.triggered_id
        if not triggered:
            raise PreventUpdate

        saved_data = saved_data or []
        all_lineups = all_lineups or []

        fired_uuid = triggered["index"]

        # <<< CHANGED: get the correct value for the fired checkbox by matching id lists
        try:
            i = next(i for i, cid in enumerate(toggle_ids) if cid["index"] == fired_uuid)
        except StopIteration:
            raise PreventUpdate
        toggled_on = bool(toggle_values[i])

        if toggled_on:
            lineup = next((x for x in all_lineups if x["uuid-index"] == fired_uuid), None)
            if lineup and not any(x["uuid-index"] == fired_uuid for x in saved_data):
                saved_data.append(lineup)
        else:
            saved_data = [x for x in saved_data if x["uuid-index"] != fired_uuid]

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

        saved_uuids = set(df["uuid-index"])  # <<< CHANGED
        return generate_card_layout(df, saved_uuids=saved_uuids)  # <<< CHANGED


def register_render_original_lineups(app):
    @app.callback(
        Output("initial_lineup_card_container", "children"),
        Input("global-store-df3", "data"),
        Input("saved-lineups-store", "data")
    )
    def render_original_lineups(all_lineups, saved_data):
        if not all_lineups:
            return html.Div("No lineups generated.")

        saved_uuids = {x["uuid-index"] for x in (saved_data or [])}
        filtered = [x for x in all_lineups if x["uuid-index"] not in saved_uuids]

        df = pd.DataFrame(filtered)

        # Defensive: ensure UUIDs exist
        if "uuid-index" not in df.columns:
            df["uuid-index"] = [str(uuid.uuid4()) for _ in range(len(df))]

        return generate_card_layout(df, saved_uuids=saved_uuids)  # <<< CHANGED
