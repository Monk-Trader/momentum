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

        # Safe optimization to protect against rate-limits and IP blocks
        self.max_threads = 2
        self.chunk_size = 10  Smaller chunk size for safer batching

    def get_cache_path(self, ticker: str):
        return self.cache_dir / f"{ticker}.parquet"

    def process_and_save(self, ticker: str, df: pd.DataFrame, mode: str = "w") -> bool:
        """Cleans, formats, and saves/updates dataframe to parquet cache incrementally."""
        try:
            if df is None or df.empty:
                return False

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
        """Downloads chunks safely with incremental fetching and rate-limit protection."""
        chunk_results = {"ok": [], "fail": [], "skip": [], "update": []}

        tickers_to_fetch = []
        ticker_modes = {}
        ticker_start_dates = {}

        today = pd.Timestamp.today().normalize()

        for ticker in ticker_chunk:
            file_path = self.get_cache_path(ticker)
            if file_path.exists():
                try:
                    cached_df = pd.read_parquet(file_path)
                    cached_df["date"] = pd.to_datetime(cached_df["date"])
                    last_date = cached_df["date"].max()
                    
                    # Skip if data is already up to date (within last 3 days)
                    if last_date >= (today - pd.Timedelta(days=3)):
                        chunk_results["skip"].append(ticker)
                        continue
                    
                    # For append mode, fetch only from the last recorded date minus a 5-day overlap buffer
                    tickers_to_fetch.append(ticker)
                    ticker_modes[ticker] = "append"
                    ticker_start_dates[ticker] = (last_date - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
                except Exception:
                    tickers_to_fetch.append(ticker)
                    ticker_modes[ticker] = "w"
                    ticker_start_dates[ticker] = None
            else:
                tickers_to_fetch.append(ticker)
                ticker_modes[ticker] = "w"
                ticker_start_dates[ticker] = None

        if not tickers_to_fetch:
            return chunk_results

        # Initial pause before hitting chunk requests
        time.sleep(1.0)

        for ticker in tickers_to_fetch:
            success = False
            mode = ticker_modes.get(ticker, "w")
            start_date = ticker_start_dates.get(ticker)

            for attempt in range(config.MAX_RETRIES):
                try:
                    # Use incremental start date if updating, else full history period for new files
                    if mode == "append" and start_date:
                        df = yf.download(
                            ticker,
                            start=start_date,
                            interval=config.INTERVAL,
                            progress=False,
                            auto_adjust=False,
                            threads=False,
                            multi_level_index=False
                        )
                    else:
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

                    success = self.process_and_save(ticker, df, mode=mode)
                    if success:
                        if mode == "append":
                            chunk_results["update"].append(ticker)
                        else:
                            chunk_results["ok"].append(ticker)
                        break
                except Exception:
                    time.sleep(2 * (attempt + 1))  # Exponential backoff on failure
            
            if not success:
                chunk_results["fail"].append(ticker)

            # CRITICAL: Polite delay between individual tickers to prevent Yahoo IP blocks
            time.sleep(0.6)

        return chunk_results

    def run(self) -> dict:
        print(f"⚡ Robust Safe Mode Active. Total items: {len(self.tickers)}")

        chunks = [self.tickers[i:i + self.chunk_size] for i in range(0, len(self.tickers), self.chunk_size)]
        results = {"ok": [], "fail": [], "skip": [], "update": []}

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {executor.submit(self.download_chunk, chunk): chunk for chunk in chunks}

            for future in as_completed(futures):
                try:
                    chunk_res = future.result()
                    results["ok"].extend(chunk_res["ok"])
                    results["fail"].extend(chunk_res["fail"])
                    results["skip"].extend(chunk_res["skip"])
                    results["update"].extend(chunk_res["update"])
                except Exception as e:
                    print(f"Chunk execution error: {e}")

        print(f"Completed -> New: {len(results['ok'])}, Updated: {len(results['update'])}, Skipped: {len(results['skip'])}, Failed: {len(results['fail'])})")
        return results


if __name__ == "__main__":
    downloader = DataDownloader()
    downloader.run()
