"""Explains why tickers fail the liquidity filter. Usage:
    python diagnose_cache.py [path/to/cache]
With no argument it uses config.CACHE_DIR."""
import sys
from pathlib import Path

import pandas as pd

LOOKBACK, MIN_ADTV = 50, 10.0

if len(sys.argv) > 1:
    cache = Path(sys.argv[1])
else:
    import config
    cache = config.CACHE_DIR
    LOOKBACK = getattr(config, "LIQUIDITY_LOOKBACK", LOOKBACK)
    MIN_ADTV = getattr(config, "MIN_ADTV_CRORE", MIN_ADTV)

files = sorted(cache.glob("*.parquet"))
print(f"Cache folder: {cache}\nParquet files: {len(files)} | lookback={LOOKBACK} | min ADTV={MIN_ADTV} Cr\n")

rows = []
for f in files:
    rec = {"ticker": f.stem, "rows": 0, "last_date": None, "adtv": None, "vol_dtype": None, "status": ""}
    try:
        df = pd.read_parquet(f)
    except Exception as e:
        rec["status"] = "unreadable"
        rows.append(rec)
        continue
    rec["rows"] = len(df)
    if "date" in df.columns and len(df):
        rec["last_date"] = pd.to_datetime(df["date"]).max().normalize()
    if "volume" not in df.columns or "close" not in df.columns:
        rec["status"] = "missing volume/close column"
    elif len(df) < LOOKBACK:
        rec["status"] = f"too short (<{LOOKBACK} rows)"
    else:
        rec["vol_dtype"] = str(df["volume"].dtype)
        recent = df.sort_values("date").tail(LOOKBACK)
        vol = pd.to_numeric(recent["volume"], errors="coerce")
        close = pd.to_numeric(recent["close"], errors="coerce")
        if vol.isna().all():
            rec["status"] = "volume all NaN"
        elif vol.fillna(0).sum() == 0:
            rec["status"] = "volume all zero"
        else:
            rec["adtv"] = vol.mean() * close.mean() / 1e7
            rec["status"] = "PASS" if rec["adtv"] >= MIN_ADTV else "ADTV below minimum"
    rows.append(rec)

res = pd.DataFrame(rows)
print("=== Status counts ===")
print(res["status"].value_counts().to_string())

adtv = res["adtv"].dropna()
if len(adtv):
    print("\n=== ADTV (Crore) percentiles, tickers with usable volume ===")
    print(adtv.quantile([.1, .25, .5, .75, .9, .99]).round(2).to_string())

print("\n=== Most common last dates ===")
print(res["last_date"].value_counts().head(5).to_string())
print("\n=== Volume dtypes ===")
print(res["vol_dtype"].value_counts(dropna=False).to_string())

print("\n=== Examples per non-PASS status (last 3 rows) ===")
for status in res["status"].unique():
    if status == "PASS":
        continue
    for t in res.loc[res["status"] == status, "ticker"].head(2):
        print(f"\n[{status}] {t}")
        try:
            print(pd.read_parquet(cache / f"{t}.parquet").tail(3).to_string(index=False))
        except Exception as e:
            print(f"  could not read: {e}")
