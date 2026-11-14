import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

import config
from universe import UniverseLoader

IST = ZoneInfo("Asia/Kolkata")
KEEP_COLS = ["date", "open", "high", "low", "close", "volume"]


def expected_last_session() -> pd.Timestamp:
    """Most recent weekday whose daily bar should be final (IST, after ~16:00).
    Exchange holidays are not modelled: on a holiday every ticker is simply re-checked."""
    now = datetime.now(IST)
    d = now.date()
    if now.hour < 16:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return pd.Timestamp(d)


class DataDownloader:
    def __init__(self):
        self.loader = UniverseLoader()
        self.cache_dir = config.CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        self.tickers = list(dict.fromkeys(self.loader.get_tickers()))  # de-duplicated, order kept

        self.batch_size = 25
        self.batch_delay = 3.0
        self.max_rounds = 4             # full passes over still-missing tickers
        self.round_backoff = 30.0       # seconds * round number, lets a rate limit cool off
        self.fail_warn_pct = 10.0
        self.max_lag_days = 4           # calendar days a ticker may trail the expected bar before it counts as stale
        self.errors = {}                # ticker -> last reason, written to failed_tickers.txt

    # ---------- cache helpers ----------
    def get_cache_path(self, ticker: str):
        return self.cache_dir / f"{ticker}.parquet"

    def _last_cached_date(self, ticker: str):
        path = self.get_cache_path(ticker)
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path, columns=["date", "close"])
            # a bar with NaN close is not a usable bar: only count dates that have a real close
            d = pd.to_datetime(df.loc[df["close"].notna(), "date"])
            return d.max().normalize() if len(d) else None
        except Exception:
            return None

    def _clean_cache(self) -> int:
        """One-off repair: remove rows with NaN close that earlier runs saved and never fixed."""
        cleaned = 0
        for path in self.cache_dir.glob("*.parquet"):
            try:
                df = pd.read_parquet(path)
                if "close" not in df.columns:
                    continue
                good = df.dropna(subset=["close"])
                if len(good) != len(df):
                    good.to_parquet(path, index=False)
                    cleaned += 1
            except Exception:
                continue
        return cleaned

    def _needs_update(self, ticker: str, expected: pd.Timestamp) -> bool:
        last = self._last_cached_date(ticker)
        return last is None or last < expected

    def _save(self, ticker: str, df: pd.DataFrame):
        path = self.get_cache_path(ticker)
        if path.exists():
            try:
                old = pd.read_parquet(path)
                old["date"] = pd.to_datetime(old["date"]).dt.normalize()
                # The pull covers the full history window: if it reaches back as far as the cache,
                # replace instead of merge so split/bonus adjustments never leave jumps in old rows.
                if df["date"].min() > old["date"].min():
                    df = pd.concat([old, df])
            except Exception:
                pass
        # keep="last": fresh data must override an old partial or NaN bar (original kept the stale one)
        df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        df = df.dropna(subset=["close"])
        df.to_parquet(path, index=False)

    # ---------- download helpers ----------
    def _extract(self, raw, ticker: str, n_requested: int):
        if raw is None or raw.empty:
            self.errors[ticker] = "empty download"
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            level = None
            for i in range(raw.columns.nlevels):
                if ticker in raw.columns.get_level_values(i):
                    level = i
                    break
            if level is None:
                self.errors[ticker] = "ticker missing from result"
                return None
            df = raw.xs(ticker, level=level, axis=1)
        else:
            if n_requested != 1:
                self.errors[ticker] = "flat result for multi-ticker request"
                return None
            df = raw.copy()

        df = df.dropna(how="all").reset_index()
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
        if "date" not in df.columns and "datetime" in df.columns:
            df = df.rename(columns={"datetime": "date"})
        if "date" not in df.columns or "close" not in df.columns:
            self.errors[ticker] = "no date/close column"
            return None

        df = df.dropna(subset=["close"])
        if df.empty:
            self.errors[ticker] = "all close values NaN"
            return None
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
        return df[[c for c in KEEP_COLS if c in df.columns]]

    def _download(self, tickers: list):
        try:
            return yf.download(
                tickers,
                period=config.HISTORY_PERIOD,
                interval=config.INTERVAL,
                group_by="ticker",
                progress=False,
                auto_adjust=False,
                threads=True,
                timeout=30,
            )
        except Exception as e:
            for t in tickers:
                self.errors[t] = f"{type(e).__name__}: {e}"[:200]
            return None

    def _single_fallback(self, ticker: str):
        try:
            raw = yf.Ticker(ticker).history(
                period=config.HISTORY_PERIOD, interval=config.INTERVAL, auto_adjust=False
            )
            return self._extract(raw, ticker, 1)
        except Exception as e:
            self.errors[ticker] = f"{type(e).__name__}: {e}"[:200]
            return None

    # ---------- main ----------
    def run(self) -> dict:
        expected = expected_last_session()
        print(f"Downloader active. Universe: {len(self.tickers)} | expected last bar: {expected.date()}")

        n_clean = self._clean_cache()
        print(f"Cache repair: removed NaN-close rows from {n_clean} files")

        pending = [t for t in self.tickers if self._needs_update(t, expected)]
        skipped = len(self.tickers) - len(pending)
        updated = []

        for rnd in range(1, self.max_rounds + 1):
            if not pending:
                break
            print(f"Round {rnd}/{self.max_rounds}: {len(pending)} tickers to fetch")
            still = []
            for i in range(0, len(pending), self.batch_size):
                batch = pending[i:i + self.batch_size]
                raw = self._download(batch)
                for t in batch:
                    df = self._extract(raw, t, len(batch))
                    if df is None:
                        still.append(t)       # retry only what actually failed
                    else:
                        self._save(t, df)
                        updated.append(t)
                time.sleep(self.batch_delay)
            pending = still
            if pending and rnd < self.max_rounds:
                wait = self.round_backoff * rnd
                print(f"  {len(pending)} failed, waiting {wait:.0f}s before retrying")
                time.sleep(wait)

        if pending:
            print(f"Per-ticker fallback for {len(pending)} tickers")
            remaining = []
            for t in pending:
                df = self._single_fallback(t)
                if df is None:
                    remaining.append(t)
                else:
                    self._save(t, df)
                    updated.append(t)
                time.sleep(1.0)
            pending = remaining

        freshness = self._report(expected, skipped, updated, pending)
        return {"updated": updated, "skipped": skipped, "failed": pending, "freshness": freshness}

    def _report(self, expected, skipped, updated, failed):
        total = len(self.tickers)
        last_dates = {t: self._last_cached_date(t) for t in self.tickers}

        # Yahoo often has no final close for the latest session on many NSE tickers (weekends, right
        # after the close), so a ticker one session behind is normal. Only a gap of more than
        # max_lag_days calendar days counts as stale.
        current = lagging = 0
        for d in last_dates.values():
            if d is None:
                continue
            behind = (expected - d).days
            if behind <= 0:
                current += 1
            elif behind <= self.max_lag_days:
                lagging += 1
        stale = total - current - lagging
        stale_pct = 100.0 * stale / max(total, 1)

        valid_dates = [d for d in last_dates.values() if d is not None]
        newest = max(valid_dates) if valid_dates else None
        newest_lag = max((expected - newest).days, 0) if newest is not None else 9999

        print("\n===== DOWNLOAD SUMMARY =====")
        print(f"Updated: {len(updated)} | Already fresh: {skipped} | Failed: {len(failed)}")
        print(f"Bar for {expected.date()}: {current}/{total} | "
              f"1-session lag (<= {self.max_lag_days}d behind, normal when Yahoo has not finalized the close): {lagging} | "
              f"Stale (> {self.max_lag_days}d behind or no data): {stale} ({stale_pct:.1f}%)")
        counts = pd.Series(valid_dates).value_counts().head(5)
        print("Most common last dates in cache:")
        for d, n in counts.items():
            print(f"  {d.date()}: {n}")

        if failed:
            out = self.cache_dir / "failed_tickers.txt"
            out.write_text("\n".join(f"{t}\t{self.errors.get(t, '')}" for t in failed))
            print(f"Failed list with reasons saved to {out}")

        if stale_pct > self.fail_warn_pct:
            print(f"WARNING: {stale_pct:.0f}% of the universe is more than {self.max_lag_days} days behind. "
                  f"Screener output will be unreliable until this is fixed.")

        return {
            "total": total, "current": current, "lagging": lagging, "stale": stale,
            "stale_pct": stale_pct, "newest_lag_days": newest_lag, "expected": str(expected.date()),
        }


if __name__ == "__main__":
    DataDownloader().run()
