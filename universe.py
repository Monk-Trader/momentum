import os
from pathlib import Path
import pandas as pd
import config


class UniverseLoader:
    """Loads, cleans, and standardizes the user's local stock universe CSV file."""

    def __init__(self):
        # Dynamically locate the baseline directory inside GitHub Actions or Local
        github_workspace = os.environ.get("GITHUB_WORKSPACE")

        if github_workspace:
            base_path = Path(github_workspace)
        else:
            base_path = Path(__file__).resolve().parent

        self.universe_file = base_path / "resources" / "universe.csv"

        # Dictionary mapping for common NSE ticker discrepancies on Yahoo Finance
        self.ticker_corrections = {
            "SBI": "SBIN",
            "M&M": "M&M",
        }

    def load(self) -> pd.DataFrame:
        if not self.universe_file.exists():
            # Emergency fallback: check root folder
            root_fallback = Path(__file__).resolve().parent / "universe.csv"
            if root_fallback.exists():
                self.universe_file = root_fallback
            else:
                raise FileNotFoundError(
                    f"Could not find your stock list CSV file!\n"
                    f"Attempted Path: {self.universe_file}"
                )

        df = pd.read_csv(self.universe_file)

        # Standardize column headers
        df.columns = [c.strip() for c in df.columns]

        # Find the symbol column regardless of case variations
        symbol_col = next((col for col in df.columns if col.lower() in ["symbol", "ticker", "code"]), None)
        if not symbol_col:
            raise ValueError("Your CSV file must contain a column named 'Symbol'.")

        df = df.rename(columns={symbol_col: "Symbol"})
        df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()

        # --- SANITIZATION FIX ---
        def clean_raw_symbol(sym: str) -> str:
            if ":" in sym:
                sym = sym.split(":")[-1]
            if sym.endswith(".NS"):
                sym = sym[:-3]
            return sym.strip()

        df["Symbol"] = df["Symbol"].apply(clean_raw_symbol)

        if "Company" not in df.columns:
            df["Company"] = df["Symbol"]

        df["YahooSymbol"] = df["Symbol"].apply(
            lambda sym: self.ticker_corrections.get(sym, sym) + config.YAHOO_SUFFIX
        )

        df = df.dropna(subset=["Symbol"]).drop_duplicates(subset=["Symbol"]).reset_index(drop=True)
        return df

    def get_tickers(self) -> list:
        """Returns the fully qualified list of Yahoo Finance ticker symbols."""
        return self.load()["YahooSymbol"].tolist()


if __name__ == "__main__":
    try:
        loader = UniverseLoader()
        df = loader.load()
        print("✅ Local universe file successfully loaded and parsed:")
        print(df.head())
        print(f"\nTotal Tickers Found: {len(df)}")
    except Exception as e:
        print(f"❌ Error: {e}")
