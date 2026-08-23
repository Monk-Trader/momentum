import pandas as pd
import config
from downloader import DataDownloader
from returns import ReturnEngine
from liquidity import LiquidityEngine
from ranking import RankingEngine
import yfinance as yf


class MomentumScanner:
    def __init__(self):
        self.downloader = DataDownloader()
        self.return_engine = ReturnEngine()
        self.liquidity_engine = LiquidityEngine()
        self.ranking_engine = RankingEngine()

    def run(self):
        print("\n🚀 MOMENTUM SCANNER PRO ONLINE\n")

        # Step 1: Sync local historical data
        print("==============================")
        print("STEP 1: DATA DOWNLOAD CHECK")
        print("==============================")
        self.downloader.run()

        # Step 2: Calculate historical momentum ranges
        print("\n==============================")
        print("STEP 2: MOMENTUM CALCULATION")
        print("==============================")
        returns_df = self.return_engine.run()
        print(f"Returns computed for {len(returns_df)} stocks")

        # Step 3: Run liquid flow checks
        print("\n==============================")
        print("STEP 3: LIQUIDITY FILTER")
        print("==============================")
        liquidity_df = self.liquidity_engine.run()
        print(f"Liquidity computed for {len(liquidity_df)} stocks")

        # Step 4: Run percentile sorting matrices
        print("\n==============================")
        print("STEP 4: RANKING ENGINE")
        print("==============================")
        final_df = self.ranking_engine.run(returns_df, liquidity_df)
        print(f"Final stocks after filtering: {len(final_df)}")

        # Step 5: Save files to output directory
        print("\n==============================")
        print("STEP 5: SAVING OUTPUTS")
        print("==============================")
        if not final_df.empty:
            config.OUTPUT_DIR.mkdir(exist_ok=True)

            all_file = config.ALL_STOCKS_FILE
            final_df.to_csv(all_file, index=False)

            strong_df = final_df[final_df["Strong_Stock"] == True]
            strong_file = config.STRONG_STOCKS_FILE
            strong_df.to_csv(strong_file, index=False)

            print(f"Saved all stocks → {all_file}")
            print(f"Saved strong stocks → {strong_file}")
            print("\n==============================")
            print("SCAN COMPLETE")
            print("==============================")
            print(f"\nStrong Stocks Found: {len(strong_df)}")
        else:
            print("Warning: No matching stocks found across criteria.")


if __name__ == "__main__":
    try:
        scanner = MomentumScanner()
        scanner.run()
    except Exception as e:
        print(f"Execution failed: {e}")
        raise e
