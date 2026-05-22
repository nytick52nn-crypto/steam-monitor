import pandas as pd


def add_indicators(df):

    df["ema20"] = df["price"].ewm(span=20).mean()

    delta = df["price"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["rsi"] = 100 - (100 / (1 + rs))

    df["ma20"] = df["price"].rolling(20).mean()

    df["std20"] = df["price"].rolling(20).std()

    df["upper_band"] = df["ma20"] + 2 * df["std20"]
    df["lower_band"] = df["ma20"] - 2 * df["std20"]

    return df