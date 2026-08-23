import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Momentum Scanner", layout="wide")

# Header section with visitor counter badge
col1, col2 = st.columns([4, 1])

with col1:
    st.title("🚀 Daily Momentum Stock Screener")
    st.write("Welcome to the automated momentum stock scanner!")

with col2:
    st.markdown(
        """
        <div style="text-align: right; padding-top: 10px;">
            <img src="https://visitor-badge.laobi.icu/badge?page_id=monk-trader.momentum" alt="Visitor Count">
        </div>
        """,
        unsafe_allow_html=True
    )

st.divider()

# Look for universe.csv in resources/ folder or root folder
universe_file = Path("resources/universe.csv")
if not universe_file.exists():
    universe_file = Path("universe.csv")

total_universe = "N/A"

if universe_file.exists():
    try:
        universe_df = pd.read_csv(universe_file)
        if not universe_df.empty:
            total_universe = len(universe_df)
    except Exception:
        total_universe = "N/A"

# Locate scanner output data file
data_file = Path("strong_stocks.csv")
if not data_file.exists():
    data_file = Path("output/strong_stocks.csv")

# Display metrics side by side
m_col1, m_col2 = st.columns(2)

with m_col1:
    st.metric("Total Stock Universe", total_universe)

with m_col2:
    if data_file.exists():
        try:
            df = pd.read_csv(data_file)
            st.metric("Total Strong Stocks Found", len(df))
        except Exception:
            df = pd.DataFrame()
            st.metric("Total Strong Stocks Found", 0)
    else:
        df = pd.DataFrame()
        st.metric("Total Strong Stocks Found", 0)

st.write("")

# Display interactive data table
if not df.empty:
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("No generated scanner output found yet.")
