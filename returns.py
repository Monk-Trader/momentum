import pandas as pd
import config
from universe import UniverseLoader

# A ticker whose last valid bar is more than this many calendar days older than the
# freshest ticker is treated as suspended/delisted and left out of the ranking.
MAX_STALE_DAYS = 5


class ReturnEngine:
    def __init__(self):
        self.loader = UniverseLoader()
        self.cache_dir = config.CACHE_DIR

    def load_stock(self, ticker: str):
        file_path = self.cache_dir / f"{ticker}.parquet"
        if not file_path.exists():
            return None
        df = pd.read_parquet(file_path, columns=["date", "close"])
        # Bars without a close (e.g. Yahoo's not-yet-final latest bar) must never be used as the
        # current price: with close[-1] = NaN every return becomes NaN and the stock disappears.
        df = df.dropna(subset=["close"])
        if df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date")

    def calculate_returns(self, df: pd.DataFrame):
        close = df["close"].values
        if len(close) < config.TRADING_DAYS_12M:
            return None

        try:
            p0 = close[-1]
            return {
                "CMP": round(float(p0), 2),
                "3M_Return": (p0 / close[-config.TRADING_DAYS_3M] - 1) * 100,
                "6M_Return": (p0 / close[-config.TRADING_DAYS_6M] - 1) * 100,
                "9M_Return": (p0 / close[-config.TRADING_DAYS_9M] - 1) * 100,
                "12M_Return": (p0 / close[-config.TRADING_DAYS_12M] - 1) * 100,
            }
        except Exception:
            return None

    def weighted_return(self, r):
        return (
            config.WEIGHT_3M * r["3M_Return"] +
            config.WEIGHT_6M * r["6M_Return"] +
            config.WEIGHT_9M * r["9M_Return"] +
            config.WEIGHT_12M * r["12M_Return"]
        )

    def run(self):
        tickers = self.loader.get_tickers()
        print(f"Processing momentum for {len(tickers)} stocks...")

        loaded, no_data = {}, 0
        for ticker in tickers:
            df = self.load_stock(ticker)
            if df is None:
                no_data += 1
            else:
                loaded[ticker] = df

        if not loaded:
            print("[Returns] No usable price data found in the cache.")
            return pd.DataFrame()

        latest = max(df["date"].iloc[-1] for df in loaded.values())
        cutoff = latest - pd.Timedelta(days=MAX_STALE_DAYS)

        results, stale, too_short, bad = [], 0, 0, 0
        for ticker, df in loaded.items():
            if df["date"].iloc[-1] < cutoff:
                stale += 1
                continue
            r = self.calculate_returns(df)
            if r is None:
                too_short += 1
                continue
            w = self.weighted_return(r)
            if pd.isna(w):
                bad += 1
                continue
            results.append({
                "Ticker": ticker,
                "CMP": r["CMP"],
                "3M_Return": r["3M_Return"],
                "6M_Return": r["6M_Return"],
                "9M_Return": r["9M_Return"],
                "12M_Return": r["12M_Return"],
                "Weighted_Return": w,
            })

        print(
            f"[Returns] universe={len(tickers)} | no cache data={no_data} | stale (>{MAX_STALE_DAYS}d behind {latest.date()})={stale} "
            f"| fewer than {config.TRADING_DAYS_12M} bars={too_short} | NaN return={bad} | computed={len(results)}"
        )
        return pd.DataFrame(results)


if __name__ == "__main__":
    engine = ReturnEngine()
    print(engine.run().head())

