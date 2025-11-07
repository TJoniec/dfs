# ui/handbuilt.py

from dash import dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import uuid as _uuid
import json

# Reuse your existing card renderer
from app.ui.cards_movement_working_backup import generate_card_layout

SLOTS = ['QB1', 'RB1', 'RB2', 'WR1', 'WR2', 'WR3', 'TE1', 'FLEX', 'DST1']


def make_handbuild_section(
    component_id: str = "handbuild",
    preview_container_id: str | None = "handbuilt_preview_container"
):
    """
    Hand-build lineup UI (Card + Store).
    - preview_container_id: where the preview card will render.
      Pass None to avoid creating an internal preview container (e.g., if you have an external "Preview Pane").
    """
    dd_style = {
        "width": "100%",
        "backgroundColor": "#111",
        "color": "#fff",
        "border": "1px solid #444",
        "borderRadius": "6px",
    }

    children = [
        # Holds the currently constructed hand-built lineup record (only persisted when valid)
        dcc.Store(id="handbuilt-lineup-store", data=None),

        dbc.Card([
            dbc.CardHeader("Hand-build Lineup"),
            dbc.CardBody([
                # Salary indicator (live)
                html.Div(id="hb-salary-indicator",
                         style={"fontWeight": "600", "marginBottom": "0.5rem"}),

                # Vertically stacked, full-width dropdowns (each with className="hb-dd" for CSS)
                dbc.Row(dbc.Col([
                    html.Label("QB1"),
                    dcc.Dropdown(id="hb-QB1", options=[], value=None,
                                 placeholder="Select QB", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("RB1"),
                    dcc.Dropdown(id="hb-RB1", options=[], value=None,
                                 placeholder="Select RB", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("RB2"),
                    dcc.Dropdown(id="hb-RB2", options=[], value=None,
                                 placeholder="Select RB", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("WR1"),
                    dcc.Dropdown(id="hb-WR1", options=[], value=None,
                                 placeholder="Select WR", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("WR2"),
                    dcc.Dropdown(id="hb-WR2", options=[], value=None,
                                 placeholder="Select WR", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("WR3"),
                    dcc.Dropdown(id="hb-WR3", options=[], value=None,
                                 placeholder="Select WR", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("TE1"),
                    dcc.Dropdown(id="hb-TE1", options=[], value=None,
                                 placeholder="Select TE", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("FLEX"),
                    dcc.Dropdown(id="hb-FLEX", options=[], value=None,
                                 placeholder="Select RB/WR/TE", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                dbc.Row(dbc.Col([
                    html.Label("DST1"),
                    dcc.Dropdown(id="hb-DST1", options=[], value=None,
                                 placeholder="Select DST", style=dd_style, className="hb-dd")
                ], width=12), className="g-2"),

                html.Hr(),
                html.Div(id="hb-validation", className="text-danger", style={"minHeight": "1.2rem"}),

                # Preview lineup card (optional here; you can render to an external pane)
                *( [html.Div(id=preview_container_id)] if preview_container_id else [] ),
            ])
        ], id=component_id, className="mb-3"),
    ]

    return html.Div(children)


# --------------------------
# Option building helpers
# --------------------------

def _encode_value(name, pos, team, sal, fpts, rank):
    value_obj = {
        "Name": name,
        "Pos": pos,
        "Team": team,
        "Salary": int(sal or 0),
        "FPTS": float(fpts) if fpts is not None else None,
        "FPTS_Rank": rank if rank is not None else "N/A",
    }
    return json.dumps(value_obj)

def _decode_value(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return v or {}

def _player_key_from_value(vdict):
    """Unique key for duplicate prevention: (Name, Team)."""
    return (vdict.get("Name") or "", vdict.get("Team") or "")

def _make_options_from_df(df: pd.DataFrame, pos_filters, *, exclude_keys: set[tuple], keep_value):
    """
    Build Dropdown options for given positions while excluding already selected players.
    exclude_keys: set of (Name, Team) pairs to remove from options.
    keep_value: JSON string currently selected in this dropdown —
                if excluded, we still keep it in the options so it doesn't disappear.
    """
    # Decode current value (if present) and compute its key
    keep_key = None
    if keep_value not in (None, "", {}):
        keep_key = _player_key_from_value(_decode_value(keep_value))

    sub = df[df["Pos"].str.upper().isin([p.upper() for p in pos_filters])].copy()
    sub["Salary"] = pd.to_numeric(sub.get("Salary"), errors="coerce").fillna(0).astype(int)
    if "FPTS" in sub.columns:
        sub["FPTS"] = pd.to_numeric(sub["FPTS"], errors="coerce")

    opts = []
    for _, r in sub.iterrows():
        name = (r.get("Player") or r.get("Name") or "").strip()
        pos = r.get("Pos", "")
        team = r.get("Team", "")
        sal = int(r.get("Salary", 0) or 0)
        rank = r.get("FPTS_Rank", r.get("fantasyPointsRank", "N/A"))
        fpts = r.get("FPTS", None)

        if pos and str(pos).upper() == "DST" and (name == "" or pd.isna(name)):
            name = f"{team} DST"

        key = (name, team)
        # Exclude if selected elsewhere, unless this is the current value for this dropdown
        if key in exclude_keys and (keep_key is None or key != keep_key):
            continue

        label = f"{name} ({pos} ${sal:,}, Rank {rank})"
        opts.append({
            "label": label,
            "value": _encode_value(name, pos, team, sal, fpts, rank)
        })
    return opts


def register_handbuild_options(app):
    """
    Populate slot options from global-store-df1 and prevent duplicate selections
    by removing already-chosen players from other dropdowns.
    """
    @app.callback(
        Output("hb-QB1", "options"),
        Output("hb-RB1", "options"),
        Output("hb-RB2", "options"),
        Output("hb-WR1", "options"),
        Output("hb-WR2", "options"),
        Output("hb-WR3", "options"),
        Output("hb-TE1", "options"),
        Output("hb-FLEX", "options"),
        Output("hb-DST1", "options"),
        Input("global-store-df1", "data"),
        # current selections (to filter options)
        Input("hb-QB1", "value"),
        Input("hb-RB1", "value"),
        Input("hb-RB2", "value"),
        Input("hb-WR1", "value"),
        Input("hb-WR2", "value"),
        Input("hb-WR3", "value"),
        Input("hb-TE1", "value"),
        Input("hb-FLEX", "value"),
        Input("hb-DST1", "value"),
        prevent_initial_call=False
    )
    def populate_options(pool, qb1, rb1, rb2, wr1, wr2, wr3, te1, flex, dst1):
        if not pool:
            empty = []
            return empty, empty, empty, empty, empty, empty, empty, empty, empty

        df = pd.DataFrame(pool)
        for col in ["Player", "Pos", "Team", "Salary"]:
            if col not in df.columns:
                df[col] = None

        # Build exclusion set from current selections (Name, Team)
        selected_values = [qb1, rb1, rb2, wr1, wr2, wr3, te1, flex, dst1]
        selected_keys = set()
        for v in selected_values:
            vd = _decode_value(v)
            if vd:
                selected_keys.add(_player_key_from_value(vd))

        qb_opts   = _make_options_from_df(df, ["QB"],           exclude_keys=selected_keys, keep_value=qb1)
        rb_opts   = _make_options_from_df(df, ["RB"],           exclude_keys=selected_keys, keep_value=rb1)
        rb2_opts  = _make_options_from_df(df, ["RB"],           exclude_keys=selected_keys, keep_value=rb2)
        wr_opts   = _make_options_from_df(df, ["WR"],           exclude_keys=selected_keys, keep_value=wr1)
        wr2_opts  = _make_options_from_df(df, ["WR"],           exclude_keys=selected_keys, keep_value=wr2)
        wr3_opts  = _make_options_from_df(df, ["WR"],           exclude_keys=selected_keys, keep_value=wr3)
        te_opts   = _make_options_from_df(df, ["TE"],           exclude_keys=selected_keys, keep_value=te1)
        flex_opts = _make_options_from_df(df, ["RB","WR","TE"], exclude_keys=selected_keys, keep_value=flex)
        dst_opts  = _make_options_from_df(df, ["DST"],          exclude_keys=selected_keys, keep_value=dst1)

        return qb_opts, rb_opts, rb2_opts, wr_opts, wr2_opts, wr3_opts, te_opts, flex_opts, dst_opts


# --------------------------
# Preview building callback
# --------------------------

def _get_field(v, k, default=None):
    """
    Read a field from a dropdown 'value' that may be a JSON string or a dict.
    """
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return default
    return (v or {}).get(k, default)


def register_handbuild_preview(
    app,
    *,
    preview_container_id: str = "handbuilt_preview_container",
    salary_cap: int = 50000
):
    """
    Builds a hand-built lineup record from the selected dropdowns, validates the salary cap,
    updates a live salary indicator, and renders a preview card using generate_card_layout.
    Preview is NOT rendered unless all slots are chosen and salary <= cap.
    """
    @app.callback(
        Output("handbuilt-lineup-store", "data"),
        Output(preview_container_id, "children"),
        Output("hb-validation", "children"),
        Output("hb-salary-indicator", "children"),
        Output("hb-salary-indicator", "style"),
        Input("hb-QB1", "value"),
        Input("hb-RB1", "value"),
        Input("hb-RB2", "value"),
        Input("hb-WR1", "value"),
        Input("hb-WR2", "value"),
        Input("hb-WR3", "value"),
        Input("hb-TE1", "value"),
        Input("hb-FLEX", "value"),
        Input("hb-DST1", "value"),
        State("saved-lineups-store", "data"),
        prevent_initial_call=False
    )
    def preview_lineup(qb1, rb1, rb2, wr1, wr2, wr3, te1, flex, dst1, saved_data):
        selections = {
            "QB1": qb1, "RB1": rb1, "RB2": rb2,
            "WR1": wr1, "WR2": wr2, "WR3": wr3,
            "TE1": te1, "FLEX": flex, "DST1": dst1
        }

        # Live salary indicator (partial total)
        partial_salary = sum(int(_get_field(v, "Salary", 0) or 0)
                             for v in selections.values()
                             if v not in (None, "", {}))
        over_cap_now = partial_salary > salary_cap
        indicator_text = f"Salary: ${partial_salary:,} / {salary_cap:,}"
        indicator_style = {
            "fontWeight": "700",
            "color": ("#16a34a" if not over_cap_now else "#dc2626")  # green/red
        }

        # Require all slots before building record/preview
        if any(v in (None, "", {}) for v in selections.values()):
            return None, html.Div(), "", indicator_text, indicator_style

        # At this point all slots are filled
        total_salary = partial_salary
        fpts_vals = [_get_field(v, "FPTS") for v in selections.values()
                     if _get_field(v, "FPTS") is not None]
        total_fpts = round(sum(fpts_vals), 2) if fpts_vals else 0.0

        # Duplicate guard (hard stop)
        names = [_get_field(v, "Name", "") for v in selections.values()]
        if len(names) != len(set(names)):
            return None, html.Div(), "Duplicate player selected in multiple slots.", indicator_text, indicator_style

        # Salary guard (hard stop)
        if total_salary > salary_cap:
            warn = f"Salary cap exceeded: ${total_salary:,} > ${salary_cap:,}"
            return None, html.Div(), warn, indicator_text, indicator_style

        # Stable UUID based on selected players
        key = "|".join(f"{slot}:{_get_field(val, 'Name', '')}-{_get_field(val, 'Team', '')}"
                       for slot, val in selections.items())
        uid = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, f"handbuild:{key}"))
        lineup_id = f"HB-{uid.split('-')[0]}"

        # Build lineup record in the same schema your cards expect
        rec = {
            "uuid-index": uid,
            "Lineup ID": lineup_id,
            "Total Lineup FPTS": total_fpts,
            "Total Lineup Salary": total_salary,
        }
        for slot, val in selections.items():
            rec[slot] = _get_field(val, "Name", "None")
            rec[f"{slot} Team"] = _get_field(val, "Team", "N/A")
            rec[f"{slot} Salary"] = int(_get_field(val, "Salary", 0) or 0)
            rec[f"{slot} FPTS"] = float(_get_field(val, "FPTS", 0.0) or 0.0)
            rec[f"{slot} FPTS_Rank"] = _get_field(val, "FPTS_Rank", "N/A")
            rec[f"{slot} Pos"] = _get_field(val, "Pos", "Unknown")

        ok_msg = f"OK — Salary ${total_salary:,} / {salary_cap:,} — Total FPTS {total_fpts:.2f}"

        # Render preview card; checkbox reflects saved state (and saving remains guarded elsewhere)
        saved_uuids = {x.get("uuid-index") for x in (saved_data or [])}
        df = pd.DataFrame([rec])

        # If your generate_card_layout supports disabled_uuids, we pass none here since under cap.
        try:
            preview = generate_card_layout(df, saved_uuids=saved_uuids, disabled_uuids=set())
        except TypeError:
            preview = generate_card_layout(df, saved_uuids=saved_uuids)

        # Persist only when valid (so save callback won't find invalid/over-cap records)
        return rec, preview, ok_msg, indicator_text, indicator_style
