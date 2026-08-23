import os
from pathlib import Path

# =========================================================
# PROJECT PATHS
# =========================================================
# If running in GitHub Actions, use the absolute workspace root environment variable
if os.environ.get("GITHUB_WORKSPACE"):
    BASE_DIR = Path(os.environ.get("GITHUB_WORKSPACE"))
else:
    BASE_DIR = Path(__file__).resolve().parent

CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
RESOURCE_DIR = BASE_DIR / "resources"

# Ensure all structural directories exist immediately
for directory in [CACHE_DIR, OUTPUT_DIR, LOG_DIR, RESOURCE_DIR]:
    directory.mkdir(exist_ok=True)

# =========================================================
# DATA & ENGINE SETTINGS
# =========================================================
HISTORY_PERIOD = "3y"
INTERVAL = "1d"
MAX_THREADS = 10
MAX_RETRIES = 3

# Momentum Lookbacks (Trading Days)
TRADING_DAYS_3M = 63
TRADING_DAYS_6M = 126
TRADING_DAYS_9M = 189
TRADING_DAYS_12M = 252

# Momentum Weights (Must sum up to 1.0)
WEIGHT_3M = 0.40
WEIGHT_6M = 0.20
WEIGHT_9M = 0.20
WEIGHT_12M = 0.20

# Filters
LIQUIDITY_LOOKBACK = 50
MIN_ADTV_CRORE = 10
MIN_RS_RANK = 90

# =========================================================
# DATA STRINGS & PERSISTENCE
# =========================================================
YAHOO_SUFFIX = ".NS"
UNIVERSE_FILE = RESOURCE_DIR / "universe.csv"
ALL_STOCKS_FILE = OUTPUT_DIR / "all_stocks.csv"
STRONG_STOCKS_FILE = OUTPUT_DIR / "strong_stocks.csv"
LOG_FILE = LOG_DIR / "scanner.log"
