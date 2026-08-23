import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Momentum Scanner", layout="wide")

st.title("🚀 Daily Momentum Stock Screener")
st.write("Welcome to the automated momentum stock scanner!")

# Look in both root and output folder as fallback
data_file = Path("strong_stocks.csv")
if not data_file.exists():
    data_file = Path("output/strong_stocks.csv")

if data_file.exists():
    df = pd.read_csv(data_file)
    st.metric("Total Strong Stocks Found", len(df))
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("No generated scanner output found yet.")
