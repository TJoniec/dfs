import pandas as pd

# Ensure numerics BEFORE putting into dcc.Store
def force_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = (
                df[c].astype(str)
                      .str.replace(r"[,\$]", "", regex=True)
                      .str.strip()
            )
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


