import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Allow imports from project root when Streamlit runs web/dashboard.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import STEAM_MARKET_FEE_PCT
from app.paper_trading import get_closed_positions, get_open_positions
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


def _total_closed_pnl() -> float:
    """Sum of realized PnL across all closed positions."""
    closed = get_closed_positions()
    return sum(p["pnl_rub"] for p in closed if p["pnl_rub"] is not None)


def render_wallet_section() -> None:
    st.subheader("Virtual wallet")
    snap = get_wallet_snapshot()
    realized_pnl = _total_closed_pnl()
    pnl_delta = f"{realized_pnl:+.2f} \u20bd" if realized_pnl != 0 else "0.00 \u20bd"

    col1, col2, col3 = st.columns(3)
    col1.metric("Current balance", f"{snap['balance']:,.2f} \u20bd".replace(",", " "))
    col2.metric("Starting balance", f"{snap['starting_balance']:,.2f} \u20bd".replace(",", " "))
    col3.metric("Total PnL (realized)", f"{realized_pnl:,.2f} \u20bd".replace(",", " "), delta=pnl_delta)
    st.caption(
        "Paper wallet \u2014 Total PnL shows sum of realized profits from closed positions."
    )

    with st.expander("Adjust balance (testing)"):
        c1, c2, c3 = st.columns([2, 2, 1])
        amount = c1.number_input("Amount (\u20bd)", min_value=0.01, value=100.0, step=10.0)
        note = c2.text_input("Note", value="")
        if c3.button("Deposit"):
            try:
                deposit(amount, note=note)
                st.success(f"Deposited {amount:.2f} \u20bd")
                st.cache_data.clear()
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if c3.button("Withdraw"):
            try:
                withdraw(amount, note=note)
                st.success(f"Withdrew {amount:.2f} \u20bd")
                st.cache_data.clear()
                st.rerun()
            except InsufficientBalanceError as exc:
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))


@st.cache_data(ttl=30)
def _load_latest_prices() -> dict[str, float]:
    """Load latest price per item from DB for unrealized PnL calculation."""
    if not DB_PATH.exists():
        return {}

    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(
            "SELECT item_name, price FROM price_history "
            "WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY item_name)",
            conn,
        )
    finally:
        conn.close()

    if df.empty:
        return {}
    return dict(zip(df["item_name"], df["price"]))


def render_open_positions_section() -> None:
    st.subheader("Open positions (paper)")
    positions = get_open_positions()
    if not positions:
        st.info("No open paper positions. BUY signals open positions when balance allows.")
        return

    latest_prices = _load_latest_prices()
    fee_mult = 1 - STEAM_MARKET_FEE_PCT / 100.0

    df = pd.DataFrame(positions)
    df["opened_at"] = pd.to_datetime(df["opened_at"], errors="coerce")

    df["current_price"] = df["item_name"].map(latest_prices)
    df["unrealized_pnl"] = df.apply(
        lambda r: round(
            (r["current_price"] * fee_mult - r["entry_price"]) * r["quantity"], 2
        )
        if pd.notna(r.get("current_price"))
        else None,
        axis=1,
    )

    display = df[
        ["item_name", "entry_price", "current_price", "unrealized_pnl",
         "quantity", "cost", "signal", "opened_at", "status"]
    ].copy()
    display.columns = [
        "Item",
        "Entry (\u20bd)",
        "Current (\u20bd)",
        "Unrealized PnL (\u20bd)",
        "Qty",
        "Cost (\u20bd)",
        "Signal",
        "Opened (UTC)",
        "Status",
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)

    total_unrealized = df["unrealized_pnl"].dropna().sum()
    st.caption(
        f"{len(positions)} open position(s). "
        f"Total unrealized PnL: {total_unrealized:+.2f} \u20bd (after {STEAM_MARKET_FEE_PCT:.0f}% fee)"
    )


def render_closed_positions_section() -> None:
    st.subheader("Closed positions (paper)")
    closed = get_closed_positions()
    if not closed:
        st.info("No closed positions yet. SELL signals will close open positions.")
        return

    df = pd.DataFrame(closed)
    df["opened_at"] = pd.to_datetime(df["opened_at"], errors="coerce")
    df["closed_at"] = pd.to_datetime(df["closed_at"], errors="coerce")

    display = df[
        ["item_name", "entry_price", "exit_price", "pnl_rub", "pnl_pct",
         "quantity", "opened_at", "closed_at"]
    ].copy()
    display.columns = [
        "Item",
        "Entry (\u20bd)",
        "Exit (\u20bd)",
        "PnL (\u20bd)",
        "PnL (%)",
        "Qty",
        "Opened (UTC)",
        "Closed (UTC)",
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)

    total_pnl = sum(p["pnl_rub"] for p in closed if p["pnl_rub"] is not None)
    wins = sum(1 for p in closed if p["pnl_rub"] is not None and p["pnl_rub"] > 0)
    win_rate = (wins / len(closed) * 100) if closed else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total realized PnL", f"{total_pnl:+.2f} \u20bd")
    c2.metric("Trades", str(len(closed)))
    c3.metric("Win rate", f"{win_rate:.0f}%")


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
    col3.metric("Latest price (avg)", f"{latest['price'].mean():.2f} \u20bd" if not latest.empty else "\u2014")
    col4.metric("Last update", df["created_at"].max().strftime("%H:%M:%S") if not df.empty else "\u2014")


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
        title=f"{item_name} \u2014 price history (\u20bd)",
        labels={"created_at": "Time", "price": "Price (\u20bd)"},
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
        "No price history yet. The monitor is collecting data \u2014 "
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
    f"**Latest:** {latest_row['price']:.2f} \u20bd | "
    f"**Volume:** {int(latest_row['volume'])} | "
    f"**At:** {latest_row['created_at']}"
)

if auto_refresh:
    st.markdown(f'<meta http-equiv="refresh" content="{refresh_sec}">', unsafe_allow_html=True)
