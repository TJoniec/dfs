import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
from dash_ag_grid import AgGrid

import pandas as pd

def register_frequency_analysis(app):
    @app.callback(
        Output("frequency_analysis_container", "children"),
        Input("saved-lineups-store", "data"),
        prevent_initial_call=False
    )
    def render_frequency(saved_data):
        # 1) No saved lineups yet
        if not saved_data:
            return html.Div("No saved lineups yet. Save some to see player exposures.")

        # 2) Flatten players across all saved lineups
        slots = ['QB1','RB1','RB2','WR1','WR2','WR3','TE1','FLEX','DST1']
        rows = []
        for row in saved_data:
            for slot in slots:
                player = row.get(slot, 'None')
                if player and player != 'None':
                    rows.append({
                        "slot": slot,
                        "player": player,
                        "team": row.get(f"{slot} Team", "N/A"),
                        "salary": row.get(f"{slot} Salary", None),
                        "fpts": row.get(f"{slot} FPTS", None),
                    })

        if not rows:
            return html.Div("No players found in saved lineups.")

        df = pd.DataFrame(rows)
        n_lineups = len(saved_data)

        # 3) Overall exposure by player
        overall = (
            df.groupby(["player","team"], dropna=False)
              .size()
              .reset_index(name="count")
              .sort_values(["count","player"], ascending=[False, True])
        )
        overall["exposure_%"] = (overall["count"] / n_lineups * 100).round(1)

        # 4) By-slot exposure (top 5 per slot)
        by_slot = (
            df.groupby(["slot","player","team"], dropna=False)
              .size()
              .reset_index(name="count")
        )
        by_slot["exposure_%"] = (by_slot["count"] / n_lineups * 100).round(1)
        by_slot = by_slot.sort_values(["slot","count","player"], ascending=[True, False, True])

        # 5) Optional: avg FPTS when player appears (overall)
        if "fpts" in df.columns:
            avg_fpts = (df.dropna(subset=["fpts"])
                          .groupby(["player","team"])["fpts"]
                          .mean().round(2)
                          .reset_index(name="avg_fpts"))
            overall = overall.merge(avg_fpts, on=["player","team"], how="left")

        # ---- Pretty text formatting helpers
        def tabulate(df, cols, headers):
            # compute column widths
            data = df[cols].astype(str).fillna("")
            widths = [max(len(h), data[c].map(len).max()) for c, h in zip(cols, headers)]
            # header
            line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
            sep  = "  ".join("-"*w for w in widths)
            # rows
            body = [
                "  ".join(str(v).ljust(w) for v, w in zip(row, widths))
                for row in data.itertuples(index=False, name=None)
            ]
            return "\n".join([line, sep] + body)

        # 6) Build final text block
        lines = []
        lines.append(f"Saved Lineups: {n_lineups}")
        lines.append("")

        # Overall table (top 25)
        top_overall = overall.head(25).copy()
        cols = ["player","team","count","exposure_%"]
        headers = ["Player","Team","Count","Exposure %"]
        if "avg_fpts" in top_overall.columns:
            cols += ["avg_fpts"]
            headers += ["Avg FPTS"]
        lines.append("== Overall Exposure (Top 25) ==")
        lines.append(tabulate(top_overall, cols, headers))
        lines.append("")

        # By-slot tables (top 5 each)
        for slot in ['QB1','RB1','RB2','WR1','WR2','WR3','TE1','FLEX','DST1']:
            slot_df = by_slot[by_slot["slot"] == slot].head(5).copy()
            if slot_df.empty:
                continue
            lines.append(f"== {slot} Exposure (Top 5) ==")
            lines.append(tabulate(slot_df, ["player","team","count","exposure_%"],
                                  ["Player","Team","Count","Exposure %"]))
            lines.append("")

        text_block = "\n".join(lines)

        # 7) Return as preformatted text
        return html.Pre(
            text_block,
            style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "fontSize": "0.9rem"}
        )
