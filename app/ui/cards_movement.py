# ui/cards_movement.py

from dash import html, Input, Output, State, ctx, ALL
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import pandas as pd
import uuid as _uuid

SLOTS = ['QB1', 'RB1', 'RB2', 'WR1', 'WR2', 'WR3', 'TE1', 'FLEX', 'DST1']


def _ensure_uuid_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure every row has a stable uuid-index; create if missing."""
    if "uuid-index" not in df.columns:
        df = df.copy()
        df["uuid-index"] = [str(_uuid.uuid4()) for _ in range(len(df))]
    return df


def _build_player_items(row: pd.Series) -> list:
    """Build bullet list of slot -> player lines with team/salary/fpts/rank."""
    items = []
    for slot in SLOTS:
        name = row.get(slot, "None")
        if name == "None" or name is None:
            continue
        team = row.get(f"{slot} Team", "N/A")
        sal = int(row.get(f"{slot} Salary", 0) or 0)
        fpts = float(row.get(f"{slot} FPTS", 0.0) or 0.0)
        rank = row.get(f"{slot} FPTS_Rank", "N/A")
        pos  = row.get(f"{slot} Pos", None)
        rank_str = f"({pos}-{rank})" if (pos and rank not in (None, "N/A")) else f"Rank: {rank}"
        items.append(html.Li(f"{slot}: {name} ({team}, ${sal:,}, {fpts:.2f} pts, {rank_str})"))
    return items


def generate_card_layout(
    df: pd.DataFrame,
    *,
    saved_uuids: set | None = None,
    disabled_uuids: set | None = None,
    checkbox_id_type: str = "save-toggle"  # default for Generated/Saved columns
) -> html.Div:
    """
    Render a list of lineup cards from a dataframe.
    Each row must contain:
      - 'uuid-index', 'Lineup ID', 'Total Lineup FPTS', 'Total Lineup Salary'
      - Slot fields per SLOTS plus per-slot Team/Salary/FPTS/FPTS_Rank (optional but used in display)
    """
    saved_uuids = saved_uuids or set()
    disabled_uuids = disabled_uuids or set()

    if df is None or len(df) == 0:
        return html.Div("No lineups generated.")

    df = _ensure_uuid_column(pd.DataFrame(df))
    cards = []

    for _, row in df.iterrows():
        uid = row["uuid-index"]
        header_text = (
            f"Lineup #{row.get('Lineup ID', '—')} — "
            f"FPTS: {float(row.get('Total Lineup FPTS', 0.0)):.2f}, "
            f"Salary: ${int(row.get('Total Lineup Salary', 0) or 0):,}"
        )
        player_items = _build_player_items(row)

        card = dbc.Card(
            [
                dbc.CardHeader(
                    [
                        html.Div(header_text, style={"display": "inline-block"}),
                        dbc.Checkbox(
                            id={"type": checkbox_id_type, "index": uid},
                            className="float-end",
                            style={"marginLeft": "10px"},
                            value=(uid in saved_uuids),
                            disabled=(uid in disabled_uuids),
                        ),
                    ]
                ),
                dbc.CardBody(html.Ul(player_items, style={"fontSize": "0.85rem"})),
            ],
            id={"type": "optimizer-lineup-card-initial-uuid", "index": uid},
            className="mb-3 shadow-sm",
        )
        cards.append(card)

    return html.Div(cards)


# =========================
# Save / Unsave lineups — single merged callback
# =========================

def register_save_lineups_functionality(app):
    """
    Single callback that handles both:
      - Cards in Generated/Saved columns: {"type":"save-toggle","index":...}
      - Preview pane card: {"type":"preview-save-toggle","index":...}

    Saves/unsaves into saved-lineups-store. Pulls lineups from:
      - global-store-df3 (generated pool)
      - handbuilt-lineup-store (current handbuilt preview)
    Blocks over-cap saves and dedupes by uuid-index.
    """
    @app.callback(
        Output("saved-lineups-store", "data"),
        # Cards (Generated/Saved columns)
        Input({"type": "save-toggle", "index": ALL}, "value"),
        State({"type": "save-toggle", "index": ALL}, "id"),
        # Preview pane
        Input({"type": "preview-save-toggle", "index": ALL}, "value"),
        State({"type": "preview-save-toggle", "index": ALL}, "id"),
        # Stores
        State("saved-lineups-store", "data"),
        State("global-store-df3", "data"),
        State("handbuilt-lineup-store", "data"),
        prevent_initial_call=True,
    )
    def update_saved_lineups(
        card_toggle_values, card_toggle_ids,
        preview_toggle_values, preview_toggle_ids,
        saved_data, generated, handbuilt_current
    ):
        if not ctx.triggered_id:
            raise PreventUpdate

        saved_data = saved_data or []
        generated = generated or []

        fired = ctx.triggered_id  # {"type": "...", "index": "..."}
        fired_uuid = fired.get("index")
        fired_type = fired.get("type")

        # determine toggled value depending on which list fired
        if fired_type == "save-toggle":
            try:
                i = next(i for i, cid in enumerate(card_toggle_ids) if cid["index"] == fired_uuid)
            except StopIteration:
                return saved_data
            toggled_on = bool(card_toggle_values[i])

        elif fired_type == "preview-save-toggle":
            try:
                i = next(i for i, cid in enumerate(preview_toggle_ids) if cid["index"] == fired_uuid)
            except StopIteration:
                return saved_data
            toggled_on = bool(preview_toggle_values[i])

        else:
            # unknown source
            return saved_data

        if toggled_on:
            # try generated pool first
            lineup = next((x for x in generated if x.get("uuid-index") == fired_uuid), None)
            # else take current handbuilt preview if ids match
            if lineup is None and handbuilt_current and handbuilt_current.get("uuid-index") == fired_uuid:
                lineup = handbuilt_current

            if (
                lineup
                and lineup.get("Total Lineup Salary", 0) <= 50000
                and not any(x.get("uuid-index") == fired_uuid for x in saved_data)
            ):
                saved_data.append(lineup)
            return saved_data

        # toggled OFF → remove by uuid
        return [x for x in saved_data if x.get("uuid-index") != fired_uuid]


# =========================
# Render Saved / Generated columns
# =========================

def register_render_saved_lineups(app):
    """Renders Saved Lineups column from saved-lineups-store."""
    @app.callback(
        Output("saved_lineup_card_container", "children"),
        Input("saved-lineups-store", "data"),
        prevent_initial_call=False,
    )
    def render_saved_cards(saved_data):
        if not saved_data:
            return html.Div("No saved lineups yet.")

        df = _ensure_uuid_column(pd.DataFrame(saved_data))
        saved_uuids = {x for x in df["uuid-index"].tolist()}
        return generate_card_layout(df, saved_uuids=saved_uuids, disabled_uuids=set())


def register_render_original_lineups(app):
    """Renders Generated Lineups column as (global-store-df3 − saved)."""
    @app.callback(
        Output("initial_lineup_card_container", "children"),
        Input("global-store-df3", "data"),
        Input("saved-lineups-store", "data"),
        prevent_initial_call=False,
    )
    def render_original_lineups(all_lineups, saved_data):
        if not all_lineups:
            return html.Div("No lineups generated.")

        saved_uuids = {x.get("uuid-index") for x in (saved_data or [])}
        filtered = [x for x in all_lineups if x.get("uuid-index") not in saved_uuids]

        if not filtered:
            return html.Div("All generated lineups are saved.")

        df = _ensure_uuid_column(pd.DataFrame(filtered))
        return generate_card_layout(df, saved_uuids=saved_uuids, disabled_uuids=set())
