import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import os

TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META",
    "JPM", "GS",
    "GC=F", "CL=F",
    "AMD",
    "PLTR",
    "ARM",
    "SPY", "QQQ",
]

MACRO_TICKERS = ["^VIX", "^TNX", "DX-Y.NYB"]


def download_data(tickers, period="5y"):
    print(f"Downloading data for {len(tickers)} assets...")
    frames = []
    for ticker in tickers:
        print(f"  -> {ticker}")
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if df.empty:
            print(f"     no data for {ticker}, skipping")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df["ticker"] = ticker
        frames.append(df)
    data = pd.concat(frames)
    print(f"  {len(data)} rows downloaded")
    return data


def download_macro(period="5y"):
    print("\nDownloading macro data...")
    macro = pd.DataFrame()
    for ticker in MACRO_TICKERS:
        print(f"  -> {ticker}")
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        name = ticker.replace("^", "").replace("-", "_").replace(".", "_")
        macro[name] = df["Close"]
    print(f"  macro columns: {list(macro.columns)}")
    return macro


def download_fear_greed(days=365*5):
    """Download Fear & Greed Index — no API key needed, 100% free."""
    print("\nDownloading Fear & Greed Index...")
    try:
        url      = f"https://api.alternative.me/fng/?limit={days}&format=json"
        response = requests.get(url, timeout=10)
        data     = response.json()["data"]

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="s")
        df = df.set_index("timestamp")
        df = df.sort_index()

        # keep only numeric value
        df["fear_greed"] = df["value"].astype(int)
        df = df[["fear_greed"]]

        print(f"  {len(df)} days downloaded — current: {df['fear_greed'].iloc[-1]}")
        return df

    except Exception as e:
        print(f"  error: {e}")
        return pd.DataFrame()


def clean_data(data):
    print("\nCleaning data...")
    before = len(data)
    data = data.dropna(subset=["Close"])
    data = data[data["Volume"] > 0]
    data = data[data["Close"] > 0]
    print(f"  removed {before - len(data)} rows, kept {len(data)}")
    return data


def compute_features(data, macro, fear_greed):
    print("\nComputing features...")
    results = []

    for ticker in data["ticker"].unique():
        df = data[data["ticker"] == ticker].copy()
        df = df.sort_index()

        # momentum
        df["momentum_5"]  = df["Close"].pct_change(5)
        df["momentum_20"] = df["Close"].pct_change(20)
        df["momentum_60"] = df["Close"].pct_change(60)

        # RSI
        df["rsi_14"] = ta.rsi(df["Close"], length=14)

        # MACD
        macd = ta.macd(df["Close"])
        if macd is not None:
            df["macd"]        = macd["MACD_12_26_9"]
            df["macd_signal"] = macd["MACDs_12_26_9"]
            df["macd_hist"]   = macd["MACDh_12_26_9"]

        # Bollinger Bands
        bb = ta.bbands(df["Close"], length=20)
        if bb is not None:
            df["bb_upper"]    = bb["BBU_20_2.0_2.0"]
            df["bb_lower"]    = bb["BBL_20_2.0_2.0"]
            df["bb_position"] = (df["Close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        # ATR
        df["atr_14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        # volume
        df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
        df["volume_trend"] = df["Volume"].rolling(5).mean() / df["Volume"].rolling(20).mean()

        # moving averages
        df["sma_20"]  = ta.sma(df["Close"], length=20)
        df["sma_50"]  = ta.sma(df["Close"], length=50)
        df["sma_200"] = ta.sma(df["Close"], length=200)
        df["price_vs_sma20"]  = df["Close"] / df["sma_20"]
        df["price_vs_sma200"] = df["Close"] / df["sma_200"]

        # 52-week high/low distance
        df["dist_52w_high"] = df["Close"] / df["High"].rolling(252).max()
        df["dist_52w_low"]  = df["Close"] / df["Low"].rolling(252).min()

        # realized volatility
        df["vol_5"]     = df["Close"].pct_change().rolling(5).std()
        df["vol_20"]    = df["Close"].pct_change().rolling(20).std()
        df["vol_ratio"] = df["vol_5"] / df["vol_20"]

        # day of week
        df["day_of_week"] = df.index.dayofweek

        # macro features
        if not macro.empty:
            df = df.join(macro, how="left")
            df = df.ffill()
            if "VIX" in df.columns:
                df["vix_level"]  = df["VIX"]
                df["vix_change"] = df["VIX"].pct_change(5)
            if "TNX" in df.columns:
                df["taux_change"] = df["TNX"].pct_change(5)
            if "DX_Y_NYB" in df.columns:
                df["dollar_change"] = df["DX_Y_NYB"].pct_change(5)

        # fear & greed index
        if not fear_greed.empty:
            df = df.join(fear_greed, how="left")
            df = df.ffill()
            if "fear_greed" in df.columns:
                # variation sur 5 jours — est-ce que la peur monte ou baisse ?
                df["fear_greed_change"] = df["fear_greed"].pct_change(5)

        results.append(df)

    out = pd.concat(results)
    n = len([c for c in out.columns if c not in ["Open","High","Low","Close","Volume","ticker"]])
    print(f"  {n} features computed")
    return out


def create_target(data, horizon=5, threshold=0.02):
    print("\nCreating target variable...")
    results = []
    for ticker in data["ticker"].unique():
        df = data[data["ticker"] == ticker].copy()
        df = df.sort_index()
        df["future_price"]  = df["Close"].shift(-horizon)
        df["future_return"] = (df["future_price"] - df["Close"]) / df["Close"]
        df["target"]        = (df["future_return"] > threshold).astype(int)
        results.append(df)
    out = pd.concat(results).dropna(subset=["target"])
    print(f"  positive signals: {out['target'].mean()*100:.1f}%")
    return out


def save_data(data, path="data/features.csv"):
    os.makedirs("data", exist_ok=True)
    data.to_csv(path)
    print(f"\n  saved to '{path}' — {data.shape[0]} rows x {data.shape[1]} cols")


if __name__ == "__main__":
    print("Signal Alpha Engine — Data Pipeline")
    print("=" * 40)

    data       = download_data(TICKERS)
    macro      = download_macro()
    fear_greed = download_fear_greed()
    data       = clean_data(data)
    data       = compute_features(data, macro, fear_greed)
    data       = create_target(data)
    save_data(data)

    print("\nDone. Ready for model training.")