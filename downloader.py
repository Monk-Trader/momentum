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

        # Batch size for bulk yfinance downloads (safe for cloud IPs)
        self.batch_size = 40
        self.max_threads = 1
        self.batch_delay = 2.0      # Seconds to wait between batch requests

    def get_cache_path(self, ticker: str):
        return self.cache_dir / f"{ticker}.parquet"

    def process_and_save_batch(self, multi_df: pd.DataFrame, tickers: list) -> dict:
        """Processes and saves multi-index or single-index dataframe chunks into individual parquet files."""
        results = {"ok": [], "fail": [], "update": []}
        
        if multi_df is None or multi_df.empty:
            for t in tickers:
                results["fail"].append(t)
            return results

        for ticker in tickers:
            try:
                # Extract individual stock data from multi-ticker download result
                if isinstance(multi_df.columns, pd.MultiIndex):
                    # FIX: group_by="ticker" puts tickers at Level 0 and attributes at Level 1
                    if ticker in multi_df.columns.levels[0]:
                        df = multi_df.xs(ticker, level=0, axis=1).dropna(how="all")
                    else:
                        results["fail"].append(ticker)
                        continue
                else:
                    # Single ticker fallback
                    df = multi_df.copy()

                if df is None or df.empty:
                    results["fail"].append(ticker)
                    continue

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
                    results["fail"].append(ticker)
                    continue

                required_cols = [date_col, "open", "high", "low", close_col, "volume"]
                available_cols = [c for c in required_cols if c in df.columns]
                df = df[available_cols]
                
                rename_map = {date_col: "date", close_col: "close"}
                df = df.rename(columns=rename_map)
                df["date"] = pd.to_datetime(df["date"])

                file_path = self.get_cache_path(ticker)

                if file_path.exists():
                    existing_df = pd.read_parquet(file_path)
                    existing_df["date"] = pd.to_datetime(existing_df["date"])
                    combined_df = pd.concat([existing_df, df]).drop_duplicates(subset=["date"]).sort_values("date")
                    combined_df.to_parquet(file_path, index=False)
                    results["update"].append(ticker)
                else:
                    df.to_parquet(file_path, index=False)
                    results["ok"].append(ticker)

            except Exception:
                results["fail"].append(ticker)

        return results

    def download_batch(self, batch_tickers: list) -> dict:
        """Downloads a batch of tickers in a single yfinance call to prevent IP blocks."""
        batch_results = {"ok": [], "fail": [], "skip": [], "update": []}
        
        tickers_to_fetch = []
        today = pd.Timestamp.today().normalize()

        # Check cache status first
        for ticker in batch_tickers:
            file_path = self.get_cache_path(ticker)
            if file_path.exists():
                try:
                    cached_df = pd.read_parquet(file_path)
                    cached_df["date"] = pd.to_datetime(cached_df["date"])
                    last_date = cached_df["date"].max()
                    
                    # Skip if up to date within the last 3 days
                    if last_date >= (today - pd.Timedelta(days=3)):
                        batch_results["skip"].append(ticker)
                        continue
                except Exception:
                    pass
            tickers_to_fetch.append(ticker)

        if not tickers_to_fetch:
            return batch_results

        # Attempt batch download with retries
        success = False
        for attempt in range(config.MAX_RETRIES):
            try:
                time.sleep(1.0 * (attempt + 1))
                multi_df = yf.download(
                    tickers_to_fetch,
                    period=config.HISTORY_PERIOD,
                    interval=config.INTERVAL,
                    group_by="ticker",
                    progress=False,
                    auto_adjust=False,
                    threads=True
                )

                if multi_df is not None and not multi_df.empty:
                    res = self.process_and_save_batch(multi_df, tickers_to_fetch)
                    batch_results["ok"].extend(res["ok"])
                    batch_results["update"].extend(res["update"])
                    batch_results["fail"].extend(res["fail"])
                    success = True
                    break
            except Exception:
                continue

        # If batch download fails completely, mark all as failed
        if not success:
            for ticker in tickers_to_fetch:
                batch_results["fail"].append(ticker)

        return batch_results

    def run(self) -> dict:
        print(f"⚡ Rate-Limit Safe Downloader Active. Total items: {len(self.tickers)}")

        batches = [self.tickers[i:i + self.batch_size] for i in range(0, len(self.tickers), self.batch_size)]
        results = {"ok": [], "fail": [], "skip": [], "update": []}

        # Sequential processing with a polite delay prevents Yahoo Finance IP bans
        for idx, batch in enumerate(batches, 1):
            print(f"Processing batch {idx}/{len(batches)} ({len(batch)} tickers)...")
            try:
                chunk_res = self.download_batch(batch)
                results["ok"].extend(chunk_res["ok"])
                results["fail"].extend(chunk_res["fail"])
                results["skip"].extend(chunk_res["skip"])
                results["update"].extend(chunk_res["update"])
                
                # Polite sleep between batches to respect rate limits
                time.sleep(self.batch_delay)
            except Exception as e:
                print(f"Batch {idx} execution error: {e}")

        print(f"Completed -> New: {len(results['ok'])}, Updated: {len(results['update'])}, Skipped: {len(results['skip'])}, Failed: {len(results['fail'])}")
        return results
    

if __name__ == "__main__":
    downloader = DataDownloader()
    downloader.run()
