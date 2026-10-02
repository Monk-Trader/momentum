import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


# --- EXISTING HELPERS & FUNCTIONS (fetch_ticker_data, get_gold_nifty_ratio_data, etc.) ---
def fetch_ticker_data(ticker, start_date="1985-01-01"):
    """Safely fetch daily Close price for a ticker."""
    data = yf.download(ticker, start=start_date, progress=False)
    if data.empty:
        raise ValueError(f"No data returned for ticker: {ticker}")

    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            series = data["Close"].iloc[:, 0]
        else:
            series = data.iloc[:, 0]
    else:
        series = data["Close"] if "Close" in data else data.iloc[:, 0]

    return series.dropna()


# ... [Keep your existing get_gold_nifty_ratio_data & render_gold_nifty_widget] ...
# ... [Keep your existing get_gold_copper_ratio_data & render_gold_copper_widget] ...


# --- GOLD / SILVER RATIO MODULE ---
@st.cache_data(ttl=14400)
def get_gold_silver_ratio_data():
    """Fetch Gold Futures (GC=F) and Silver Futures (SI=F) over 40 years

    to compute daily ratio and valuation bands.
    """
    start_date = "1985-01-01"

    gold = fetch_ticker_data("GC=F", start_date)
    silver = fetch_ticker_data("SI=F", start_date)

    df = pd.DataFrame({"Gold": gold, "Silver": silver})
    df = df.ffill().bfill().dropna()

    # Ratio = Gold Price ($/Oz) / Silver Price ($/Oz)
    df["Ratio"] = df["Gold"] / df["Silver"]

    mean_val = df["Ratio"].mean()
    std_val = df["Ratio"].std()

    bands = {
        "Upper_2SD": mean_val + (2 * std_val),
        "Upper_1SD": mean_val + std_val,
        "Mean": mean_val,
        "Lower_1SD": mean_val - std_val,
        "Lower_2SD": mean_val - (2 * std_val),
    }

    return df, bands


def render_gold_silver_widget():
    """Renders the 40-Year Gold / Silver Ratio Card inside Streamlit."""
    try:
        df, bands = get_gold_silver_ratio_data()

        latest_ratio = df["Ratio"].iloc[-1]
        latest_date = df.index[-1].strftime("%b %d, %Y")

        # Determine metals regime signal
        if latest_ratio >= bands["Upper_2SD"]:
            status_text, status_color = (
                "Extreme Gold Premium (Rotate to Silver)",
                "#d62728",
            )
        elif latest_ratio >= bands["Upper_1SD"]:
            status_text, status_color = (
                "High GSR (Silver Undervalued)",
                "#ff7f0e",
            )
        elif latest_ratio >= bands["Lower_1SD"]:
            status_text, status_color = "Fair Value Zone", "#2ca02c"
        elif latest_ratio >= bands["Lower_2SD"]:
            status_text, status_color = (
                "Low GSR (Silver Outperforming)",
                "#2196F3",
            )
        else:
            status_text, status_color = (
                "Extreme Silver Bubble (Rotate to Gold)",
                "#9467bd",
            )

        st.caption(
            "Gold Futures (USD/Oz) vs. Silver Futures (USD/Oz) — 40-Year History"
        )
        st.metric(
            label="Latest Gold/Silver Ratio",
            value=f"{latest_ratio:.2f}",
            help="Ounces of Silver needed to buy 1 ounce of Gold",
        )
        st.markdown(
            f"""<div style="background-color: {status_color}; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; text-align: center; margin-bottom: 12px;">{status_text}</div>""",
            unsafe_allow_html=True,
        )

        fig = go.Figure()

        # Ratio Line
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Ratio"],
                mode="lines",
                name="Gold / Silver",
                line=dict(color="#94a3b8", width=1.8),  # Silver tone
            )
        )

        # Valuation Band Lines
        fig.add_hline(
            y=bands["Upper_2SD"],
            line_dash="dashdot",
            line_color="#d62728",
            annotation_text="+2 SD",
            annotation_position="top right",
        )
        fig.add_hline(
            y=bands["Upper_1SD"],
            line_dash="dash",
            line_color="#ff7f0e",
            annotation_text="+1 SD",
            annotation_position="top right",
        )
        fig.add_hline(
            y=bands["Mean"],
            line_dash="dash",
            line_color="#333333",
            annotation_text="Mean",
            annotation_position="top right",
        )
        fig.add_hline(
            y=bands["Lower_1SD"],
            line_dash="dash",
            line_color="#2ca02c",
            annotation_text="-1 SD",
            annotation_position="bottom right",
        )
        fig.add_hline(
            y=bands["Lower_2SD"],
            line_dash="dashdot",
            line_color="#9467bd",
            annotation_text="-2 SD",
            annotation_position="bottom right",
        )

        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
            template="plotly_white",
            showlegend=False,
            xaxis=dict(showgrid=True),
            yaxis=dict(showgrid=True),
        )

        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            f"""
            **40-Year Valuation Bands:**
            - **+2 SD (Extreme High):** `{bands['Upper_2SD']:.2f}`
            - **+1 SD (Overvalued Gold):** `{bands['Upper_1SD']:.2f}`
            - **Mean (Historical Average):** `{bands['Mean']:.2f}`
            - **-1 SD (Overvalued Silver):** `{bands['Lower_1SD']:.2f}`
            - **-2 SD (Extreme Low):** `{bands['Lower_2SD']:.2f}`
            
            *Updated: {latest_date}*
            """
        )
    except Exception as e:
        st.error(f"Unable to load Gold / Silver chart: {e}")
