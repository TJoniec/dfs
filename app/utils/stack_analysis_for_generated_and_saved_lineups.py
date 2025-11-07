from dash import html, Input, Output

def register_stack_analysis(app):
    @app.callback(
        Output("generated-stacks", "children"),
        Output("saved-stacks", "children"),
        Input("global-store-df3", "data"),
        Input("saved-lineups-store", "data"),
        prevent_initial_call=False
    )
    def render_stacks(all_lineups, saved_lineups):
        slots = ['QB1','RB1','RB2','WR1','WR2','WR3','TE1','FLEX','DST1']

        def get_pos(row, slot):
            for key in (f"{slot} Pos", f"{slot} Position", "Pos", f"{slot}_Pos"):
                val = row.get(key)
                if val:
                    return val
            if slot.startswith("QB"): return "QB"
            if slot.startswith("RB"): return "RB"
            if slot.startswith("WR"): return "WR"
            if slot.startswith("TE"): return "TE"
            if slot.startswith("DST"): return "DST"
            return "Unknown"

        def get_team(row, slot):
            return row.get(f"{slot} Team") or row.get(f"{slot}_Team") or row.get("Team")

        def get_rank(row, slot):
            for key in (f"{slot} FPTS_Rank", "FPTS_Rank", f"{slot}_FPTS_Rank"):
                val = row.get(key)
                if val not in (None, "N/A", ""):
                    return val
            return None

        def get_salary(row, slot):
            for key in (f"{slot} Salary", f"{slot}_Salary", "Salary"):
                val = row.get(key)
                if val not in (None, "N/A", ""):
                    try:
                        return float(val)
                    except Exception:
                        return None
            return None

        def team_grouped_report(lineups):
            team_to_lineups = {}

            for lu in (lineups or []):
                lineup_id = lu.get("Lineup ID", "?")
                lineup_fpts = lu.get("Total Lineup FPTS", None)
                per_team = {}

                for slot in slots:
                    player = lu.get(slot)
                    if not player or player == "None":
                        continue
                    team = get_team(lu, slot)
                    if not team:
                        continue
                    pos = get_pos(lu, slot)
                    rank = get_rank(lu, slot)
                    sal = get_salary(lu, slot)
                    per_team.setdefault(team, []).append((player, pos, rank, sal))

                for team, plist in per_team.items():
                    uniq = []
                    seen = set()
                    for p, pos, rank, sal in plist:
                        if p not in seen:
                            seen.add(p)
                            uniq.append((p, pos, rank, sal))
                    if len(uniq) >= 2:
                        team_to_lineups.setdefault(team, {})[lineup_id] = {
                            "players": uniq,
                            "lineup_fpts": lineup_fpts
                        }

            if not team_to_lineups:
                return html.Pre("No stacks found.",
                                style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "fontSize": "0.9rem"})

            lines = []
            for team in sorted(team_to_lineups.keys()):
                lineup_dict = team_to_lineups[team]
                lines.append(f"{team} — stacks in {len(lineup_dict)} lineup(s)")

                def _id_key(x):
                    try: return int(x)
                    except: return str(x)

                for lid in sorted(lineup_dict.keys(), key=_id_key):
                    entry = lineup_dict[lid]
                    players = entry["players"]
                    stack_salary = sum([s for *_, s in players if isinstance(s, (int, float)) and s is not None])
                    lfpts = entry.get("lineup_fpts")
                    lfpts_txt = f"{float(lfpts):.2f}" if lfpts is not None else "N/A"
                    salary_txt = f"${int(stack_salary):,}" if stack_salary else "$0"

                    # Build players line with Pos and Rank
                    players_txt = ", ".join(
                        f"{name} ({pos}-{rank})" if rank not in (None, "", "N/A") else f"{name} ({pos})"
                        for (name, pos, rank, _sal) in players
                    )

                    # ---- Two-line format per lineup
                    lines.append(f"  • Lineup #{lid} — Total FPTS: {lfpts_txt} — Stack Salary: {salary_txt}")
                    lines.append(f"    {players_txt}")
                lines.append("")  # blank line between teams

            text = "\n".join(lines).rstrip()
            return html.Pre(text, style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "fontSize": "0.9rem"})

        generated_view = team_grouped_report(all_lineups)
        saved_view = team_grouped_report(saved_lineups)
        return generated_view, saved_view
