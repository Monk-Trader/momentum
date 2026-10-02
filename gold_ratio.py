import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


def fetch_ticker_data(ticker, start_date="2008-01-01"):
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


@st.cache_data(ttl=14400)  # Cache results for 4 hours to keep page reloads fast
def get_gold_ratio_data():
    """Fetch Nifty 500 (in USD) and Gold (in USD) to compute daily ratio and valuation bands."""
    start_date = "2008-01-01"

    # Fetch Nifty 500 (^CRSLDX), USD/INR (INR=X), and Gold Futures (GC=F)
    try:
        nifty = fetch_ticker_data("^CRSLDX", start_date)
        index_label = "Nifty 500"
    except Exception:
        nifty = fetch_ticker_data("^NSEI", start_date)
        index_label = "Nifty 50"

    usdinr = fetch_ticker_data("INR=X", start_date)
    gold = fetch_ticker_data("GC=F", start_date)

    # Align dates across US/Indian market holidays
    df = pd.DataFrame({"Nifty": nifty, "USDINR": usdinr, "Gold": gold})
    df = df.ffill().bfill().dropna()

    # Calculate USD-denominated Nifty and Ratio
    df["Nifty_USD"] = df["Nifty"] / df["USDINR"]
    df["Ratio"] = df["Nifty_USD"] / df["Gold"]

    # Calculate Valuation Bands
    mean_val = df["Ratio"].mean()
    std_val = df["Ratio"].std()

    bands = {
        "Upper_2SD": mean_val + (2 * std_val),
        "Upper_1SD": mean_val + std_val,
        "Mean": mean_val,
        "Lower_1SD": mean_val - std_val,
        "Lower_2SD": mean_val - (2 * std_val),
    }

    return df, bands, index_label


def render_gold_ratio_widget():
    """Renders the Gold Ratio Analysis Card inside Streamlit."""
    try:
        df, bands, index_label = get_gold_ratio_data()

        latest_ratio = df["Ratio"].iloc[-1]
        latest_date = df.index[-1].strftime("%b %d, %Y")

        # Determine regime signal
        if latest_ratio >= bands["Upper_2SD"]:
            status_text, status_color = "Extreme Bubble (Rotate to Gold)", "#d62728"
        elif latest_ratio >= bands["Upper_1SD"]:
            status_text, status_color = "Overvalued Equities", "#ff7f0e"
        elif latest_ratio >= bands["Lower_1SD"]:
            status_text, status_color = "Fair Value Zone", "#2ca02c"
        elif latest_ratio >= bands["Lower_2SD"]:
            status_text, status_color = "Undervalued Equities", "#2196F3"
        else:
            status_text, status_color = (
                "Deep Value (Rotate to Equities)",
                "#9467bd",
            )

        # Container Header
        st.subheader("Gold Ratio Charts")
        st.caption(f"{index_label} (USD) / Gold Futures (USD/Oz)")

        # Metric Card
        st.metric(label="Latest USD Ratio", value=f"{latest_ratio:.4f}")
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
                name="Ratio",
                line=dict(color="#1f77b4", width=1.8),
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
            **Valuation Bands:**
            - **+2 SD (Extreme):** `{bands['Upper_2SD']:.4f}`
            - **+1 SD (Overvalued):** `{bands['Upper_1SD']:.4f}`
            - **Mean (Fair Value):** `{bands['Mean']:.4f}`
            - **-1 SD (Undervalued):** `{bands['Lower_1SD']:.4f}`
            - **-2 SD (Deep Value):** `{bands['Lower_2SD']:.4f}`
            
            *Updated: {latest_date}*
            """
        )
    except Exception as e:
        st.error(f"Unable to load Gold Ratio chart: {e}")
