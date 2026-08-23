import pandas as pd
import config


class RankingEngine:
    def run(self, returns_df: pd.DataFrame, liquidity_df: pd.DataFrame) -> pd.DataFrame:
        if returns_df.empty or liquidity_df.empty:
            print("[Ranking Engine] Warning: Empty metrics incoming. Check historical dataset profiles.")
            return pd.DataFrame()

        # Merge datasets
        df = pd.merge(returns_df, liquidity_df, on="Ticker", how="inner")

        # Hard liquidity screening filter
        df = df[df["Liquidity_Pass"] == True].copy()
        if df.empty:
            return df

        # Quantile metric processing matrix
        df["RS_Rank"] = df["Weighted_Return"].rank(pct=True) * 100

        # --- FIX: Drop any rows where RS_Rank is NaN before casting to int ---
        df = df.dropna(subset=["RS_Rank"]).copy()
        if df.empty:
            return df
        # ---------------------------------------------------------------------

        df["RS_Rank"] = df["RS_Rank"].round().clip(lower=1, upper=99).astype(int)

        # Apply absolute system flag signals
        df["Strong_Stock"] = (df["RS_Rank"] >= config.MIN_RS_RANK) & (df["ADTV_Crore"] >= config.MIN_ADTV_CRORE)

        return df.sort_values("RS_Rank", ascending=False).reset_index(drop=True)
