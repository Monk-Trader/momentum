import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import yfinance as yf
from tqdm import tqdm
import config
from universe import UniverseLoader


class DataDownloader:
    def __init__(self):
        self.loader = UniverseLoader()
        self.cache_dir = config.CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        self.tickers = self.loader.get_tickers()

        # CLOUD OPTIMIZATION: Reduced threads & chunk size to avoid Streamlit Cloud IP bans
        self.max_threads = 2
        self.chunk_size = 15

    def get_cache_path(self, ticker: str):
        return self.cache_dir / f"{ticker}.parquet"

    def process_and_save(self, ticker: str, df: pd.DataFrame, mode: str = "w") -> bool:
        """Cleans, formats, and saves/updates dataframe to parquet cache incrementally."""
        try:
            df = df.reset_index()
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

            date_col = "date" if "date" in df.columns else ("datetime" if "datetime" in df.columns else None)
            close_col = "close" if "close" in df.columns else None

            if not close_col:
                for col in df.columns:
                    if "close" in col:
                        close_col = col
                        break

            if not date_col or not close_col or df[close_col].dropna().empty:
                return False

            required_cols = [date_col, "open", "high", "low", close_col, "volume"]
            available_cols = [c for c in required_cols if c in df.columns]
            df = df[available_cols]
            
            rename_map = {date_col: "date", close_col: "close"}
            df = df.rename(columns=rename_map)
            df["date"] = pd.to_datetime(df["date"])

            file_path = self.get_cache_path(ticker)

            if mode == "append" and file_path.exists():
                existing_df = pd.read_parquet(file_path)
                existing_df["date"] = pd.to_datetime(existing_df["date"])
                
                # Combine, drop duplicate dates, and sort chronologically
                combined_df = pd.concat([existing_df, df]).drop_duplicates(subset=["date"]).sort_values("date")
                combined_df.to_parquet(file_path, index=False)
            else:
                df.to_parquet(file_path, index=False)

            return True
        except Exception:
            return False

    def download_chunk(self, ticker_chunk: list) -> dict:
        """Downloads chunks safely with individual fallback to prevent multi-index drop bugs."""
        chunk_results = {"ok": [], "fail": [], "skip": [], "update": []}

        tickers_to_fetch = []
        ticker_modes = {}

        for ticker in ticker_chunk:
            file_path = self.get_cache_path(ticker)
            if file_path.exists():
                try:
                    cached_df = pd.read_parquet(file_path)
                    cached_df["date"] = pd.to_datetime(cached_df["date"])
                    last_date = cached_df["date"].max()
                    
                    today = pd.Timestamp.today().normalize()
                    if last_date >= (today - pd.Timedelta(days=3)):
                        chunk_results["skip"].append(ticker)
                        continue
                    
                    tickers_to_fetch.append(ticker)
                    ticker_modes[ticker] = "append"
                except Exception:
                    tickers_to_fetch.append(ticker)
                    ticker_modes[ticker] = "w"
            else:
                tickers_to_fetch.append(ticker)
                ticker_modes[ticker] = "w"

        if not tickers_to_fetch:
            return chunk_results

        time.sleep(1.5)

        # Download tickers individually to ensure consistent single-level dataframes on cloud environments
        for ticker in tickers_to_fetch:
            success = False
            for attempt in range(config.MAX_RETRIES):
                try:
                    df = yf.download(
                        ticker,
                        period=config.HISTORY_PERIOD,
                        interval=config.INTERVAL,
                        progress=False,
                        auto_adjust=False,
                        threads=False,
                        multi_level_index=False
                    )

                    if df is None or df.empty:
                        raise ValueError("Empty data packet.")

                    mode = ticker_modes.get(ticker, "w")
                    success = self.process_and_save(ticker, df, mode=mode)
                    if success:
                        if mode == "append":
                            chunk_results["update"].append(ticker)
                        else:
                            chunk_results["ok"].append(ticker)
                        break
                except Exception:
                    time.sleep(1 * (attempt + 1))
            
            if not success:
                chunk_results["fail"].append(ticker)

        return chunk_results

    def run(self) -> dict:
        print(f"⚡ Streamlit Cloud Safe Mode Active. Total items: {len(self.tickers)}")

        chunks = [self.tickers[i:i + self.chunk_size] for i in range(0, len(self.tickers), self.chunk_size)]
        results = {"ok": [], "fail": [], "skip": [], "update": []}

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {executor.submit(self.download_chunk, chunk): chunk for chunk in chunks}

            for future in as_completed(futures):
                chunk_res = future.result()
                results["ok"].extend(chunk_res["ok"])
                results["fail"].extend(chunk_res["fail"])
                results["skip"].extend(chunk_res["skip"])
                results["update"].extend(chunk_res["update"])

        return results


if __name__ == "__main__":
    downloader = DataDownloader()
    downloader.run()
