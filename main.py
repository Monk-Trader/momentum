import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import config
from downloader import DataDownloader
from returns import ReturnEngine
from liquidity import LiquidityEngine
from ranking import RankingEngine

# The RS rank is relative (top ~10% of the liquid pool), so the strong-stock count should stay
# roughly stable from day to day. Far fewer means the data is broken, not that the market is weak.
MIN_STRONG_EXPECTED = getattr(config, "MIN_STRONG_EXPECTED", 20)
MAX_LAG_DAYS = getattr(config, "MAX_LAG_DAYS", 4)        # calendar days behind the expected last session
MAX_STALE_PCT = getattr(config, "MAX_STALE_PCT", 10.0)   # % of universe allowed beyond that lag


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

        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        metadata_file = config.OUTPUT_DIR / "last_updated.json"

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=4)

        print(f"Timestamp updated → {timestamp_str}")

    def run(self):
        print("\n🚀 MOMENTUM SCANNER PRO ONLINE\n")

        print("==============================")
        print("STEP 1: DATA DOWNLOAD CHECK")
        print("==============================")
        dl = self.downloader.run()

        # Freshness guard: stop before publishing if the price feed is dead or many tickers are stale.
        # One session of lag (Yahoo not yet final for the latest close) is normal and does not trip this.
        fresh = dl.get("freshness", {}) if isinstance(dl, dict) else {}
        if fresh:
            if fresh["newest_lag_days"] > MAX_LAG_DAYS or fresh["stale_pct"] > MAX_STALE_PCT:
                print(
                    f"ERROR: stale data. Freshest bar is {fresh['newest_lag_days']} day(s) behind {fresh['expected']} "
                    f"and {fresh['stale_pct']:.1f}% of tickers are more than {MAX_LAG_DAYS} days behind "
                    f"(limits: {MAX_LAG_DAYS} days / {MAX_STALE_PCT:.0f}%). Outputs were NOT overwritten."
                )
                sys.exit(1)

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

        liq_pass = int(liquidity_df["Liquidity_Pass"].sum()) if not liquidity_df.empty else 0
        n_strong = int((final_df["Strong_Stock"] == True).sum()) if not final_df.empty else 0
        print(
            f"[Pipeline] returns computed={len(returns_df)} | liquidity rows={len(liquidity_df)} (pass={liq_pass}) "
            f"| ranked={len(final_df)} | strong={n_strong}"
        )

        print("\n==============================")
        print("STEP 5: SAVING OUTPUTS")
        print("==============================")
        if final_df.empty or n_strong < MIN_STRONG_EXPECTED:
            print(
                f"ERROR: only {n_strong} strong stocks (expected at least {MIN_STRONG_EXPECTED}). "
                "Outputs were NOT overwritten so the app keeps the last good result. Check the counts above."
            )
            sys.exit(1)

        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


if __name__ == "__main__":
    try:
        scanner = MomentumScanner()
        scanner.run()
    except Exception as e:
        print(f"Execution failed: {e}")
        raise e
