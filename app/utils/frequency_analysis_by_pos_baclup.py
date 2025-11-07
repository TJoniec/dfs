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
        if not saved_data:
            return html.Div("No saved lineups yet. Save some to see player exposures.")

        slots = ['QB1','RB1','RB2','WR1','WR2','WR3','TE1','FLEX','DST1']
        rows = []

        def get_pos(row, slot):
            # Try slot-specific key first, then generic 'Pos'
            for key in (f"{slot} Pos", f"{slot} Position", "Pos", f"{slot}_Pos"):
                if key in row and row[key]:
                    return row[key]
            # Fallback inference from slot
            if slot.startswith("QB"): return "QB"
            if slot.startswith("RB"): return "RB"
            if slot.startswith("WR"): return "WR"
            if slot.startswith("TE"): return "TE"
            if slot.startswith("DST"): return "DST"
            return "Unknown"  # e.g., FLEX without explicit Pos

        for lineup in saved_data:
            for slot in slots:
                player = lineup.get(slot, 'None')
                if player and player != 'None':
                    rows.append({
                        "player": player,
                        "team": lineup.get(f"{slot} Team", "N/A"),
                        "salary": lineup.get(f"{slot} Salary", None),
                        "fpts": lineup.get(f"{slot} FPTS", None),
                        "pos": get_pos(lineup, slot),  # <-- group by this
                    })

        if not rows:
            return html.Div("No players found in saved lineups.")

        import pandas as pd
        df = pd.DataFrame(rows)
        n_lineups = len(saved_data)

        # Overall exposure by player
        overall = (
            df.groupby(["player","team"], dropna=False)
              .size()
              .reset_index(name="count")
              .sort_values(["count","player"], ascending=[False, True])
        )
        overall["exposure_%"] = (overall["count"] / n_lineups * 100).round(1)

        # Avg FPTS when player appears (optional)
        if "fpts" in df.columns:
            avg_fpts = (df.dropna(subset=["fpts"])
                          .groupby(["player","team"])["fpts"]
                          .mean().round(2)
                          .reset_index(name="avg_fpts"))
            overall = overall.merge(avg_fpts, on=["player","team"], how="left")

        # Exposure grouped by position (Pos), show top players per position
        by_pos = (
            df.groupby(["pos","player","team"], dropna=False)
              .size()
              .reset_index(name="count")
        )
        by_pos["exposure_%"] = (by_pos["count"] / n_lineups * 100).round(1)
        by_pos = by_pos.sort_values(["pos","count","player"], ascending=[True, False, True])

        # Pretty text
        def tabulate(df, cols, headers):
            data = df[cols].astype(str).fillna("")
            widths = [max(len(h), data[c].map(len).max()) for c, h in zip(cols, headers)]
            line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
            sep  = "  ".join("-"*w for w in widths)
            body = [
                "  ".join(str(v).ljust(w) for v, w in zip(row, widths))
                for row in data.itertuples(index=False, name=None)
            ]
            return "\n".join([line, sep] + body)

        lines = []
        lines.append(f"Saved Lineups: {n_lineups}")
        lines.append("")

        # Overall (top 25)
        top_overall = overall.head(25).copy()
        cols = ["player","team","count","exposure_%"]
        headers = ["Player","Team","Count","Exposure %"]
        if "avg_fpts" in top_overall.columns:
            cols += ["avg_fpts"]; headers += ["Avg FPTS"]
        lines.append("== Overall Exposure (Top 25) ==")
        lines.append(tabulate(top_overall, cols, headers))
        lines.append("")

        # By-Pos (top 5 per position)
        for pos_value in by_pos["pos"].dropna().unique():
            pos_df = by_pos[by_pos["pos"] == pos_value].head(5).copy()
            if pos_df.empty:
                continue
            lines.append(f"== {pos_value} Exposure (Top 5) ==")
            lines.append(tabulate(pos_df, ["player","team","count","exposure_%"],
                                  ["Player","Team","Count","Exposure %"]))
            lines.append("")

        text_block = "\n".join(lines)
        return html.Pre(
            text_block,
            style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "fontSize": "0.9rem"}
        )
