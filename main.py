import json
from datetime import datetime
import pytz
import config
from downloader import DataDownloader
from returns import ReturnEngine
from liquidity import LiquidityEngine
from ranking import RankingEngine

class MomentumScanner:
    def __init__(self):
        self.downloader = DataDownloader()
        self.return_engine = ReturnEngine()
        self.liquidity_engine = LiquidityEngine()
        self.ranking_engine = RankingEngine()


    def save_last_updated_time(self):
        """Saves current timestamp in Indian Standard Time (IST)."""
        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        
        # Format example: "October 09, 2026 at 07:00 PM IST"
        timestamp_str = now_ist.strftime("%B %d, %Y at %I:%M %p IST")
        
        metadata = {
            "last_updated": timestamp_str,
            "iso_timestamp": now_ist.isoformat()
        }
        
        config.OUTPUT_DIR.mkdir(exist_ok=True)
        metadata_file = config.OUTPUT_DIR / "last_updated.json"
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=4)
            
        print(f"Timestamp updated → {timestamp_str}")
    def run(self):
        print("\n🚀 MOMENTUM SCANNER PRO ONLINE\n")

        print("==============================")
        print("STEP 1: DATA DOWNLOAD CHECK")
        print("==============================")
        self.downloader.run()

        print("\n==============================")
        print("STEP 2: MOMENTUM CALCULATION")
        print("==============================")
        returns_df = self.return_engine.run()

        print("\n==============================")
        print("STEP 3: LIQUIDITY FILTER")
        print("==============================")
        liquidity_df = self.liquidity_engine.run()

        print("\n==============================")
        print("STEP 4: RANKING ENGINE")
        print("==============================")
        final_df = self.ranking_engine.run(returns_df, liquidity_df)

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

            # Save execution timestamp
            self.save_last_updated_time()

            print(f"Saved all stocks → {all_file}")
            print(f"Saved strong stocks → {strong_file}")
            print("\n==============================")
            print("SCAN COMPLETE")
            print("==============================")
        else:
            print("Warning: No matching stocks found across criteria.")


if __name__ == "__main__":
    try:
        scanner = MomentumScanner()
        scanner.run()
    except Exception as e:
        print(f"Execution failed: {e}")
        raise e
