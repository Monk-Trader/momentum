import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Momentum Scanner", layout="wide")

# Add header and visitor counter badge
col1, col2 = st.columns([4, 1])

with col1:
    st.title(" Momentum Screener")
    st.write("Welcome to the automated momentum scanner!")

with col2:
    # Free auto-incrementing visitor counter SVG
    st.markdown(
        """
        <div style="text-align: right; padding-top: 10px;">
            <img src="https://visitor-badge.laobi.icu/badge?page_id=monk-trader.momentum" alt="Visitor Count">
        </div>
        """,
        unsafe_allow_html=True
    )

st.divider()

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
