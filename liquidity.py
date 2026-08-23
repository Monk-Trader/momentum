import pandas as pd
import config
from universe import UniverseLoader

class LiquidityEngine:
    def __init__(self):
        self.loader = UniverseLoader()
        self.cache_dir = config.CACHE_DIR

    def load_stock(self, ticker: str):
        file_path = self.cache_dir / f"{ticker}.parquet"
        if not file_path.exists():
            return None
        df = pd.read_parquet(file_path)
        return df.sort_values("date") if not df.empty else None

    def compute_adtv(self, df: pd.DataFrame):
        if len(df) < config.LIQUIDITY_LOOKBACK:
            return None
        recent = df.tail(config.LIQUIDITY_LOOKBACK)
        return (recent["volume"].mean() * recent["close"].mean()) / 1e7

    def process_stock(self, ticker: str):
        df = self.load_stock(ticker)
        if df is None:
            return None
        adtv = self.compute_adtv(df)
        if adtv is None:
            return None

        return {
            "Ticker": ticker,
            "ADTV_Crore": adtv,
            "Liquidity_Pass": adtv >= config.MIN_ADTV_CRORE
        }

    def run(self):
        tickers = self.loader.get_tickers()
        results = []
        print(f"Checking liquidity for {len(tickers)} stocks...")

        for ticker in tickers:
            res = self.process_stock(ticker)
            if res is not None:
                results.append(res)

        return pd.DataFrame(results)

if __name__ == "__main__":
    engine = LiquidityEngine()
    print(engine.run().head())
