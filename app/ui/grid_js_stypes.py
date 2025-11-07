# grid_styles.py

#Ensure that original field name not the header name is used
# Reusable styling rules for AG Grid

# Compare two rank columns and apply text color classes
RANK_DIFFERENCE_ROW_CLASSES = {
    # FPTS_Rank exceeds fantasyPointsRank by > 4
    "row-better": "params.data && (params.data.FPTS_Rank*1 - params.data.fantasyPointsRank*1) < - 4",

    # fantasyPointsRank exceeds FPTS_Rank by > 4
    "row-worse":  "params.data && (params.data.FPTS_Rank*1 - params.data.fantasyPointsRank*1)  > 4",
}




