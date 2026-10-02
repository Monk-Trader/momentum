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


# ==========================================
# 1. GOLD / NIFTY 500 RATIO
# ==========================================
@st.cache_data(ttl=14400)
def get_gold_nifty_ratio_data():
    start_date = "2008-01-01"
    try:
        nifty = fetch_ticker_data("^CRSLDX", start_date)
        index_label = "Nifty 500"
    except Exception:
        nifty = fetch_ticker_data("^NSEI", start_date)
        index_label = "Nifty 50"

    usdinr = fetch_ticker_data("INR=X", start_date)
    gold = fetch_ticker_data("GC=F", start_date)

    df = pd.DataFrame({"Nifty": nifty, "USDINR": usdinr, "Gold": gold})
    df = df.ffill().bfill().dropna()

    df["Nifty_USD"] = df["Nifty"] / df["USDINR"]
    df["Ratio"] = df["Nifty_USD"] / df["Gold"]

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


def render_gold_nifty_widget():
    try:
        df, bands, index_label = get_gold_nifty_ratio_data()
        latest_ratio = df["Ratio"].iloc[-1]
        latest_date = df.index[-1].strftime("%b %d, %Y")

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

        st.caption(f"{index_label} (USD) vs. Gold Futures (USD/Oz)")
        st.metric(label="Latest USD Ratio", value=f"{latest_ratio:.4f}")
        st.markdown(
            f"""<div style="background-color: {status_color}; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; text-align: center; margin-bottom: 12px;">{status_text}</div>""",
            unsafe_allow_html=True,
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Ratio"],
                mode="lines",
                name="Gold / Nifty 500",
                line=dict(color="#1f77b4", width=1.8),
            )
        )
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
        st.error(f"Unable to load Gold / Nifty 500 chart: {e}")


# ==========================================
# 2. GOLD / COPPER RATIO
# ==========================================
@st.cache_data(ttl=14400)
def get_gold_copper_ratio_data():
    start_date = "1985-01-01"
    gold = fetch_ticker_data("GC=F", start_date)
    copper = fetch_ticker_data("HG=F", start_date)

    df = pd.DataFrame({"Gold": gold, "Copper": copper})
    df = df.ffill().bfill().dropna()

    df["Ratio"] = df["Gold"] / df["Copper"]

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
    try:
        df, bands = get_gold_copper_ratio_data()
        latest_ratio = df["Ratio"].iloc[-1]
        latest_date = df.index[-1].strftime("%b %d, %Y")

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

        st.caption(
            "Gold Futures (USD/Oz) vs. Copper Futures (USD/lb) — 40-Year History"
        )
        st.metric(label="Latest Gold/Copper Ratio", value=f"{latest_ratio:.2f}")
        st.markdown(
            f"""<div style="background-color: {status_color}; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; text-align: center; margin-bottom: 12px;">{status_text}</div>""",
            unsafe_allow_html=True,
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Ratio"],
                mode="lines",
                name="Gold / Copper",
                line=dict(color="#d97706", width=1.8),
            )
        )
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


# ==========================================
# 3. GOLD / SILVER RATIO
# ==========================================
@st.cache_data(ttl=14400)
def get_gold_silver_ratio_data():
    start_date = "1985-01-01"
    gold = fetch_ticker_data("GC=F", start_date)
    silver = fetch_ticker_data("SI=F", start_date)

    df = pd.DataFrame({"Gold": gold, "Silver": silver})
    df = df.ffill().bfill().dropna()

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
    try:
        df, bands = get_gold_silver_ratio_data()
        latest_ratio = df["Ratio"].iloc[-1]
        latest_date = df.index[-1].strftime("%b %d, %Y")

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
        st.metric(label="Latest Gold/Silver Ratio", value=f"{latest_ratio:.2f}")
        st.markdown(
            f"""<div style="background-color: {status_color}; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; text-align: center; margin-bottom: 12px;">{status_text}</div>""",
            unsafe_allow_html=True,
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Ratio"],
                mode="lines",
                name="Gold / Silver",
                line=dict(color="#94a3b8", width=1.8),
            )
        )
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
