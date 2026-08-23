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

        # HIGH-SPEED OPTIMIZATION: Keep threads balanced to prevent API rate-limiting
        self.max_threads = 10
        # CHUNK SIZE: Moderate sizing ensures cleaner DataFrame index unpacking
        self.chunk_size = 25

    def is_cached(self, ticker: str) -> bool:
        return (self.cache_dir / f"{ticker}.parquet").exists()

    def download_chunk(self, ticker_chunk: list) -> dict:
        """Downloads a grouped chunk of tickers simultaneously to optimize network requests."""
        chunk_results = {"ok": [], "fail": [], "skip": []}

        # Filter out tickers in this chunk that are already cached locally
        tickers_to_download = [t for t in ticker_chunk if not self.is_cached(t)]
        skipped_tickers = [t for t in ticker_chunk if self.is_cached(t)]

        chunk_results["skip"].extend(skipped_tickers)

        if not tickers_to_download:
            return chunk_results

        last_error = "Unknown execution error"
        for attempt in range(config.MAX_RETRIES):
            try:
                # High-speed bulk download request
                df = yf.download(
                    tickers_to_download,
                    period=config.HISTORY_PERIOD,
                    interval=config.INTERVAL,
                    group_by="ticker",  # Structure columns by ticker name
                    progress=False,
                    auto_adjust=False,
                    threads=False,  # Set to False because we are already multi-threading chunk blocks
                )

                if df is None or df.empty:
                    raise ValueError("Empty data dataframe packet returned.")

                # Process each ticker from the returned batch data matrix
                for ticker in tickers_to_download:
                    try:
                        # Handle formatting differences between single and multiple tickers dynamically
                        if len(tickers_to_download) == 1:
                            ticker_df = df.copy()
                        else:
                            # Use cross-section (.xs) to safely isolate the ticker data without risking index mismatch errors
                            if ticker not in df.columns.get_level_values(0):
                                continue
                            ticker_df = df.xs(ticker, axis=1, level=0).copy()

                        ticker_df = ticker_df.reset_index()
                        ticker_df.columns = [str(c).lower().replace(" ", "_") for c in ticker_df.columns]

                        # Verify data content existence before caching
                        if "date" in ticker_df.columns and "close" in ticker_df.columns and not ticker_df["close"].dropna().empty:
                            required_cols = ["date", "open", "high", "low", "close", "volume"]
                            ticker_df = ticker_df[required_cols]

                            file_path = self.cache_dir / f"{ticker}.parquet"
                            ticker_df.to_parquet(file_path, index=False)
                            chunk_results["ok"].append(ticker)
                        else:
                            chunk_results["fail"].append(f"{ticker} | Empty pricing history rows")
                    except Exception as single_err:
                        chunk_results["fail"].append(f"{ticker} | Parsing error: {single_err}")

                return chunk_results  # Successfully processed the batch

            except Exception as e:
                last_error = e
                time.sleep(1 + attempt)  # Back off briefly before retrying the chunk

        # If the batch completely fails after retries, mark all remaining tickers in it as failed
        for t in tickers_to_download:
            if t not in chunk_results["ok"] and t not in chunk_results["fail"]:
                chunk_results["fail"].append(f"{t} | Batch level failure: {last_error}")

        return chunk_results

    def run(self) -> dict:
        print(f"⚡ Turbo Download Mode Active. Total items to verify: {len(self.tickers)}")

        if not self.tickers:
            print("❌ Error: No tickers were returned from the UniverseLoader.")
            return {"ok": [], "fail": [], "skip": []}

        # Split the massive ticker array into small chunks
        chunks = [self.tickers[i:i + self.chunk_size] for i in range(0, len(self.tickers), self.chunk_size)]

        results = {"ok": [], "fail": [], "skip": []}

        # Multi-thread across groups of chunks concurrently
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {executor.submit(self.download_chunk, chunk): chunk for chunk in chunks}

            with tqdm(total=len(self.tickers), desc="Accelerated Bulk Download Processing") as pbar:
                for future in as_completed(futures):
                    chunk_res = future.result()
                    results["ok"].extend(chunk_res["ok"])
                    results["fail"].extend(chunk_res["fail"])
                    results["skip"].extend(chunk_res["skip"])

                    # Advance progress bar by total size of processed group
                    pbar.update(len(futures[future]))

        print("\n==============================")
        print("⚡ HIGH-SPEED DOWNLOAD REPORT ⚡")
        print("==============================")
        print(f"SUCCESS DOWNLOADS : {len(results['ok'])}")
        print(f"FAILED TICKERS    : {len(results['fail'])}")
        print(f"SKIPPED (CACHED)  : {len(results['skip'])}")

        if results["fail"]:
            print("\n💡 Tip: If any tickers failed, double check their formatting mappings inside universe.py")

        return results


if __name__ == "__main__":
    downloader = DataDownloader()
    downloader.run()

