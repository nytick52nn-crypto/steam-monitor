from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def _safe_filename(item_name: str, signal: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in item_name)
    return f"{safe}_{signal}.png"


def chart_path_for(item_name: str, signal: str, charts_dir: Path) -> Path:
    charts_dir.mkdir(parents=True, exist_ok=True)
    return charts_dir / _safe_filename(item_name, signal)


def save_signal_chart(
    df,
    item_name: str,
    signal: str,
    charts_dir: Path,
) -> Path:
    path = chart_path_for(item_name, signal, charts_dir)

    fig, (ax_price, ax_rsi) = plt.subplots(
        2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    ax_price.plot(df["created_at"], df["price"], label="Price", color="#1f77b4", linewidth=2)
    ax_price.plot(df["created_at"], df["ema20"], label="EMA20", color="#ff7f0e", alpha=0.8)
    ax_price.plot(df["created_at"], df["upper_band"], label="Upper band", color="#2ca02c", linestyle="--", alpha=0.7)
    ax_price.plot(df["created_at"], df["lower_band"], label="Lower band", color="#d62728", linestyle="--", alpha=0.7)

    last = df.iloc[-1]
    marker_color = "#2ca02c" if signal == "BUY" else "#d62728"
    ax_price.scatter(
        [last["created_at"]],
        [last["price"]],
        color=marker_color,
        s=120,
        zorder=5,
        label=f"{signal} @ {last['price']:.2f}",
    )

    ax_price.set_title(f"{item_name} — {signal} signal")
    ax_price.set_ylabel("Price (₽)")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.grid(True, alpha=0.3)

    ax_rsi.plot(df["created_at"], df["rsi"], label="RSI", color="#9467bd", linewidth=1.5)
    ax_rsi.axhline(70, color="#d62728", linestyle=":", alpha=0.6)
    ax_rsi.axhline(30, color="#2ca02c", linestyle=":", alpha=0.6)
    ax_rsi.set_ylabel("RSI")
    ax_rsi.set_ylim(0, 100)
    ax_rsi.legend(loc="upper left", fontsize=8)
    ax_rsi.grid(True, alpha=0.3)

    ax_rsi.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    fig.autofmt_xdate(rotation=30)
    plt.tight_layout()
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return path
