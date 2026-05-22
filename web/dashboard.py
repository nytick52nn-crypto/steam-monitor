import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Allow imports from project root when Streamlit runs web/dashboard.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.paper_trading import get_open_positions, get_closed_positions
from app.wallet import (
    InsufficientBalanceError,
    deposit,
    get_wallet_snapshot,
    withdraw,
)

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA_DIR / "steam_cards.db"

st.set_page_config(
    page_title="Steam Monitor",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Steam Market Monitor")
st.caption("Live prices from Steam Community Market API")


def render_wallet_section() -> None:
    st.subheader("Virtual wallet")
    snap = get_wallet_snapshot()
    pnl = snap["pnl_placeholder"]
    pnl_delta = f"{pnl:+.2f} ₽" if pnl != 0 else "0.00 ₽"

    closed_positions = get_closed_positions()
    realized_pnl = sum(float(p.get("pnl_rub") or 0) for p in closed_positions)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current balance", f"{snap['balance']:,.2f} ₽".replace(",", " "))
    col2.metric("Starting balance", f"{snap['starting_balance']:,.2f} ₽".replace(",", " "))
    col3.metric("Realized PnL", f"{realized_pnl:+,.2f} ₽".replace(",", " "))
    col4.metric("Total PnL", f"{pnl:+,.2f} ₽".replace(",", " "), delta=pnl_delta)
    st.caption(
        "Paper wallet — Realized PnL from closed trades. "
        "Total PnL = current balance − starting balance."
    )

    with st.expander("Adjust balance (testing)"):
        c1, c2, c3 = st.columns([2, 2, 1])
        amount = c1.number_input("Amount (₽)", min_value=0.01, value=100.0, step=10.0)
        note = c2.text_input("Note", value="")
        if c3.button("Deposit"):
            try:
                deposit(amount, note=note)
                st.success(f"Deposited {amount:.2f} ₽")
                st.cache_data.clear()
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if c3.button("Withdraw"):
            try:
                withdraw(amount, note=note)
                st.success(f"Withdrew {amount:.2f} ₽")
                st.cache_data.clear()
                st.rerun()
            except InsufficientBalanceError as exc:
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))


@st.cache_data(ttl=10)
def get_latest_prices() -> dict:
    """Get latest price for each item from price_history."""
    if not DB_PATH.exists():
        return {}

    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(
            "SELECT item_name, price FROM price_history ORDER BY created_at DESC",
            conn,
        )
    finally:
        conn.close()

    if df.empty:
        return {}

    return df.drop_duplicates(subset=["item_name"], keep="first").set_index("item_name")["price"].to_dict()


def render_open_positions_section() -> None:
    st.subheader("Open positions (paper)")
    positions = get_open_positions()
    if not positions:
        st.info("No open paper positions. BUY signals open positions when balance allows.")
        return

    latest_prices = get_latest_prices()
    fee_net_pct = 0.85

    df = pd.DataFrame(positions)
    df["opened_at"] = pd.to_datetime(df["opened_at"], errors="coerce")

    df["current_price"] = df["item_name"].map(lambda x: latest_prices.get(x, None))
    df["unrealized_pnl"] = df.apply(
        lambda row: (row["current_price"] - row["entry_price"]) * fee_net_pct * row["quantity"]
        if row["current_price"] is not None
        else None,
        axis=1,
    )

    display = df[
        ["item_name", "entry_price", "current_price", "quantity", "cost", "unrealized_pnl", "signal", "opened_at", "status"]
    ].copy()
    display.columns = [
        "Item",
        "Entry (₽)",
        "Current (₽)",
        "Qty",
        "Cost (₽)",
        "Unrealized PnL (₽)",
        "Signal",
        "Opened (UTC)",
        "Status",
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption(f"{len(positions)} open position(s). SELL signals close positions and realize PnL.")


def render_closed_positions_section() -> None:
    st.subheader("Closed positions (paper)")
    positions = get_closed_positions()
    if not positions:
        st.info("No closed positions yet. Closed trades will appear here.")
        return

    df = pd.DataFrame(positions)
    df["closed_at"] = pd.to_datetime(df["closed_at"], errors="coerce")

    display = df[
        ["item_name", "entry_price", "exit_price", "quantity", "pnl_rub", "pnl_pct", "closed_at", "status"]
    ].copy()
    display.columns = [
        "Item",
        "Entry (₽)",
        "Exit (₽)",
        "Qty",
        "PnL (₽)",
        "PnL (%)",
        "Closed (UTC)",
        "Status",
    ]

    st.dataframe(display, use_container_width=True, hide_index=True)
    total_pnl = df["pnl_rub"].sum()
    st.caption(f"{len(positions)} closed position(s). Total realized PnL: {total_pnl:+,.2f} ₽".replace(",", " "))


@st.cache_data(ttl=30)
def load_prices() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()

    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(
            "SELECT id, item_name, price, volume, created_at "
            "FROM price_history ORDER BY created_at DESC",
            conn,
        )
    finally:
        conn.close()

    if df.empty:
        return df

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["price", "created_at"])
    return df[df["price"] < 100_000]


def render_metrics(df: pd.DataFrame) -> None:
    latest = df.sort_values("created_at").groupby("item_name").tail(1)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tracked items", df["item_name"].nunique())
    col2.metric("Total records", len(df))
    col3.metric("Latest price (avg)", f"{latest['price'].mean():.2f} ₽" if not latest.empty else "—")
    col4.metric("Last update", df["created_at"].max().strftime("%H:%M:%S") if not df.empty else "—")


def render_chart(card_df: pd.DataFrame, item_name: str) -> None:
    if card_df.empty:
        st.info("No data for this item yet.")
        return

    card_df = card_df.sort_values("created_at")
    fig = px.line(
        card_df,
        x="created_at",
        y="price",
        markers=True,
        title=f"{item_name} — price history (₽)",
        labels={"created_at": "Time", "price": "Price (₽)"},
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)


refresh_sec = st.sidebar.slider("Auto-refresh (seconds)", 10, 120, 30, 10)
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)

if st.sidebar.button("Refresh now"):
    st.cache_data.clear()
    st.rerun()

render_wallet_section()
render_open_positions_section()
render_closed_positions_section()
st.divider()

df = load_prices()

if df.empty:
    st.warning(
        "No price history yet. The monitor is collecting data — "
        "check back in about a minute after the first scan cycle."
    )
    st.info(f"Database path: `{DB_PATH.resolve()}`")
    if auto_refresh:
        st.markdown(f'<meta http-equiv="refresh" content="{refresh_sec}">', unsafe_allow_html=True)
    st.stop()

render_metrics(df)

st.subheader("Recent records")
st.dataframe(
    df.head(100)[["created_at", "item_name", "price", "volume"]],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Price chart")

cards = sorted(df["item_name"].unique())
selected = st.selectbox("Select item", cards)

card_df = df[df["item_name"] == selected]
render_chart(card_df, selected)

latest_row = card_df.sort_values("created_at").iloc[-1]
st.write(
    f"**Latest:** {latest_row['price']:.2f} ₽ | "
    f"**Volume:** {int(latest_row['volume'])} | "
    f"**At:** {latest_row['created_at']}"
)

if auto_refresh:
    st.markdown(f'<meta http-equiv="refresh" content="{refresh_sec}">', unsafe_allow_html=True)
