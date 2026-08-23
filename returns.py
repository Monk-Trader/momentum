import pandas as pd
import config
from universe import UniverseLoader

class ReturnEngine:
    def __init__(self):
        self.loader = UniverseLoader()
        self.cache_dir = config.CACHE_DIR

    def load_stock(self, ticker: str):
        file_path = self.cache_dir / f"{ticker}.parquet"
        if not file_path.exists():
            return None
        df = pd.read_parquet(file_path)
        return df.sort_values("date") if not df.empty else None

    def calculate_returns(self, df: pd.DataFrame):
        close = df["close"].values
        if len(close) < config.TRADING_DAYS_12M:
            return None

        try:
            p0 = close[-1]
            return {
                "3M_Return": (p0 / close[-config.TRADING_DAYS_3M] - 1) * 100,
                "6M_Return": (p0 / close[-config.TRADING_DAYS_6M] - 1) * 100,
                "9M_Return": (p0 / close[-config.TRADING_DAYS_9M] - 1) * 100,
                "12M_Return": (p0 / close[-config.TRADING_DAYS_12M] - 1) * 100
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
        results = []
        print(f"Processing momentum for {len(tickers)} stocks...")

        for ticker in tickers:
            df = self.load_stock(ticker)
            if df is None:
                continue

            r = self.calculate_returns(df)
            if r is None:
                continue

            w = self.weighted_return(r)
            results.append({
                "Ticker": ticker,
                "3M_Return": r["3M_Return"],
                "6M_Return": r["6M_Return"],
                "9M_Return": r["9M_Return"],
                "12M_Return": r["12M_Return"],
                "Weighted_Return": w
            })

        return pd.DataFrame(results)

if __name__ == "__main__":
    engine = ReturnEngine()
    print(engine.run().head())
