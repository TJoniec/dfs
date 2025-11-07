# ui/handbuild.py

from dash import dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import uuid as _uuid
import json

# Import the live card renderer (no leading "app." when running python app.py from app/)
from ui.cards_movement import generate_card_layout

SLOTS = ['QB1', 'RB1', 'RB2', 'WR1', 'WR2', 'WR3', 'TE1', 'FLEX', 'DST1']


def make_handbuild_section(
    component_id: str = "handbuild",
    preview_container_id=None,
):
    """
    Hand-build lineup UI (Card + Store).
    If preview_container_id is None, no internal preview div is rendered (so you can use an external Preview Pane).
    """
    dd_style = {
        "width": "100%",
        "backgroundColor": "#111",
        "color": "#fff",
        "border": "1px solid #444",
        "borderRadius": "6px",
    }

    body_children = [
        # Salary indicator (live)
        html.Div(id="hb-salary-indicator",
                 style={"fontWeight": "600", "marginBottom": "0.5rem"}),

        # Vertically stacked, full-width dropdowns (dark-styled)
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
    ]

    if preview_container_id:
        body_children.append(html.Div(id=preview_container_id))

    return html.Div([
        # Holds the currently constructed hand-built lineup record (only when valid)
        dcc.Store(id="handbuilt-lineup-store", data=None),

        dbc.Card([
            dbc.CardHeader("Hand-build Lineup"),
            dbc.CardBody(body_children),
        ], id=component_id, className="mb-3"),
    ])


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

def _make_options_from_df(df: pd.DataFrame, pos_filters, *, exclude_keys, keep_value):
    """Build Dropdown options for given positions while excluding already selected players."""
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
        if key in exclude_keys and (keep_key is None or key != keep_key):
            continue

        label = f"{name} ({pos} ${sal:,}, Rank {rank})"
        opts.append({"label": label, "value": _encode_value(name, pos, team, sal, fpts, rank)})
    return opts


def register_handbuild_options(app):
    """Populate slot options from global-store-df1 and prevent duplicate selections across slots."""
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
    """Read a field from a dropdown 'value' that may be a JSON string or a dict."""
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
    Builds a hand-built lineup record from the selected dropdowns, validates the cap,
    updates live salary, renders preview card to the preview_container_id, and stores the
    current record to handbuilt-lineup-store (when valid).
    """
    @app.callback(
        Output("handbuilt-lineup-store", "data"),
        Output(preview_container_id, "children"),
        Output("hb-validation", "children"),
        Output("hb-salary-indicator", "children"),
        Output("hb-salary-indicator", "style"),
        Input("saved-lineups-store", "data"),  # watch saved list to clear preview when unsaved
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
    def preview_lineup(saved_data, qb1, rb1, rb2, wr1, wr2, wr3, te1, flex, dst1):
        selections = {"QB1": qb1, "RB1": rb1, "RB2": rb2,
                      "WR1": wr1, "WR2": wr2, "WR3": wr3,
                      "TE1": te1, "FLEX": flex, "DST1": dst1}

        # Live salary indicator (partial)
        partial_salary = sum(int(_get_field(v, "Salary", 0) or 0)
                             for v in selections.values() if v not in (None, "", {}))
        over_cap_now = partial_salary > salary_cap
        indicator_text = f"Salary: ${partial_salary:,} / {salary_cap:,}"
        indicator_style = {"fontWeight": "700", "color": ("#16a34a" if not over_cap_now else "#dc2626")}

        # If not all slots chosen, just show indicator; no preview, no store
        if any(v in (None, "", {}) for v in selections.values()):
            return None, html.Div(), "", indicator_text, indicator_style

        # Deterministic UUID for current selection
        key = "|".join(f"{slot}:{_get_field(val,'Name','')}-{_get_field(val,'Team','')}"
                       for slot, val in selections.items())
        uid = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, f"handbuild:{key}"))
        lineup_id = f"HB-{uid.split('-')[0]}"

        # If trigger is saved store and this uid was removed, clear preview
        if ctx.triggered_id == "saved-lineups-store":
            saved_uuids = {x.get("uuid-index") for x in (saved_data or [])}
            if uid not in saved_uuids:
                return None, html.Div(), "", indicator_text, indicator_style

        # Compute totals
        total_salary = partial_salary
        fpts_vals = [_get_field(v, "FPTS") for v in selections.values()
                     if _get_field(v, "FPTS") is not None]
        total_fpts = round(sum(fpts_vals), 2) if fpts_vals else 0.0

        # Duplicate guard
        names = [_get_field(v, "Name", "") for v in selections.values()]
        if len(names) != len(set(names)):
            return None, html.Div(), "Duplicate player selected in multiple slots.", indicator_text, indicator_style

        # Salary guard
        if total_salary > salary_cap:
            warn = f"Salary cap exceeded: ${total_salary:,} > ${salary_cap:,}"
            return None, html.Div(), warn, indicator_text, indicator_style

        # Build lineup record
        rec = {"uuid-index": uid, "Lineup ID": lineup_id,
               "Total Lineup FPTS": total_fpts, "Total Lineup Salary": total_salary}
        for slot, val in selections.items():
            rec[slot] = _get_field(val, "Name", "None")
            rec[f"{slot} Team"] = _get_field(val, "Team", "N/A")
            rec[f"{slot} Salary"] = int(_get_field(val, "Salary", 0) or 0)
            rec[f"{slot} FPTS"] = float(_get_field(val, "FPTS", 0.0) or 0.0)
            rec[f"{slot} FPTS_Rank"] = _get_field(val, "FPTS_Rank", "N/A")
            rec[f"{slot} Pos"] = _get_field(val, "Pos", "Unknown")

        ok_msg = f"OK — Salary ${total_salary:,} / {salary_cap:,} — Total FPTS {total_fpts:.2f}"

        # Render preview card with a DIFFERENT checkbox id type to avoid collisions
        saved_uuids = {x.get("uuid-index") for x in (saved_data or [])}
        df = pd.DataFrame([rec])
        try:
            preview = generate_card_layout(
                df,
                saved_uuids=saved_uuids,
                disabled_uuids=set(),
                checkbox_id_type="preview-save-toggle"  # <-- key change
            )
        except TypeError:
            # Backward-compat if older signature is loaded
            preview = generate_card_layout(df, saved_uuids=saved_uuids)

        # Persist current valid handbuilt so preview save/unsave can add/remove it
        return rec, preview, ok_msg, indicator_text, indicator_style
