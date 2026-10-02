import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


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


@st.cache_data(ttl=14400)  # Cache results for 4 hours
def get_gold_copper_ratio_data():
    """Fetch Gold Futures (GC=F in USD/Oz) and Copper Futures (HG=F in USD/lb)

    over a 40-year horizon to calculate the Gold/Copper ratio and valuation bands.
    """
    start_date = "1985-01-01"

    # Fetch Gold Futures (GC=F) and Copper Futures (HG=F)
    gold = fetch_ticker_data("GC=F", start_date)
    copper = fetch_ticker_data("HG=F", start_date)

    # Align dates across commodity exchange calendar gaps
    df = pd.DataFrame({"Gold": gold, "Copper": copper})
    df = df.ffill().bfill().dropna()

    # Ratio = Gold Price ($/Oz) / Copper Price ($/lb)
    df["Ratio"] = df["Gold"] / df["Copper"]

    # Calculate 40-Year Valuation Bands
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


def render_gold_copper_widget():
    """Renders the 40-Year Gold / Copper Ratio Card inside Streamlit."""
    try:
        df, bands = get_gold_copper_ratio_data()

        latest_ratio = df["Ratio"].iloc[-1]
        latest_date = df.index[-1].strftime("%b %d, %Y")

        # Determine regime signal
        if latest_ratio >= bands["Upper_2SD"]:
            status_text, status_color = (
                "Extreme Slowdown / Risk-Off Panic",
                "#d62728",
            )
        elif latest_ratio >= bands["Upper_1SD"]:
            status_text, status_color = "Economic Slowdown / Defensive", "#ff7f0e"
        elif latest_ratio >= bands["Lower_1SD"]:
            status_text, status_color = "Normal Economic Growth", "#2ca02c"
        elif latest_ratio >= bands["Lower_2SD"]:
            status_text, status_color = "Strong Reflation / Growth", "#2196F3"
        else:
            status_text, status_color = (
                "Extreme Economic Expansion / Commodity Boom",
                "#9467bd",
            )

        # Header Details
        st.caption("Gold Futures (USD/Oz) vs. Copper Futures (USD/lb) — 40-Year History")

        # Metric Card
        st.metric(
            label="Latest Gold/Copper Ratio",
            value=f"{latest_ratio:.2f}",
            help="Ounces of Gold needed to buy 1 pound of Copper",
        )
        st.markdown(
            f"""
            <div style="background-color: {status_color}; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; text-align: center; margin-bottom: 12px;">
                {status_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Plotly Interactive Chart
        fig = go.Figure()

        # Ratio Line
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Ratio"],
                mode="lines",
                name="Gold / Copper",
                line=dict(color="#d97706", width=1.8),  # Amber color for commodities
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

        # Summary Metrics Table
        st.markdown(
            f"""
            **40-Year Valuation Bands:**
            - **+2 SD (Extreme Risk-Off):** `{bands['Upper_2SD']:.2f}`
            - **+1 SD (Slowdown):** `{bands['Upper_1SD']:.2f}`
            - **Mean (Historical Average):** `{bands['Mean']:.2f}`
            - **-1 SD (Reflation Growth):** `{bands['Lower_1SD']:.2f}`
            - **-2 SD (Boom / Commodity Peak):** `{bands['Lower_2SD']:.2f}`
            
            *Updated: {latest_date}*
            """
        )
    except Exception as e:
        st.error(f"Unable to load Gold / Copper chart: {e}")
