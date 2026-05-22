def analyze_signal(df):

    latest = df.iloc[-1]

    buy_signal = (
        latest["rsi"] < 30
        and latest["price"] < latest["lower_band"]
    )

    sell_signal = (
        latest["rsi"] > 70
        and latest["price"] > latest["upper_band"]
    )

    if buy_signal:
        return "BUY"

    if sell_signal:
        return "SELL"

    return "HOLD"