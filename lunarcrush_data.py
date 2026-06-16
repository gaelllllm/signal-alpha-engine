import requests
import pandas as pd
from datetime import datetime, timedelta

# ============================================================
# LUNARCRUSH API
# ============================================================
API_KEY = "65dhfr1y6f4rq1uxbju9i8zv8cmqgiiakceyfwxe"
BASE_URL = "https://lunarcrush.com/api4/public"

# mapping entre nos tickers et les topics LunarCrush
TICKER_TO_TOPIC = {
    "AAPL":  "apple",
    "MSFT":  "microsoft",
    "NVDA":  "nvidia",
    "GOOGL": "google",
    "META":  "meta",
    "JPM":   "jpmorgan",
    "GS":    "goldman sachs",
    "AMD":   "amd",
    "PLTR":  "palantir",
    "ARM":   "arm holdings",
    "SPY":   "spy etf",
    "QQQ":   "qqq etf",
}

HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def get_topic_sentiment(topic):
    """Get current sentiment data for a topic."""
    try:
        url = f"{BASE_URL}/topic/{topic}/v1"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "sentiment":    data.get("sentiment", 50),
                "galaxy_score": data.get("galaxy_score", 50),
                "num_posts":    data.get("num_posts", 0),
                "interactions": data.get("interactions_24h", 0),
            }
    except Exception as e:
        print(f"  error fetching {topic}: {e}")
    return None


def get_topic_timeseries(topic, days=365):
    """Get historical sentiment time series for a topic."""
    try:
        # calculate start timestamp
        start = int((datetime.now() - timedelta(days=days)).timestamp())
        url   = f"{BASE_URL}/topic/{topic}/time-series/v1"
        params = {
            "interval": "1d",
            "start":    start,
        }
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                df = pd.DataFrame(data["data"])
                df["time"] = pd.to_datetime(df["time"], unit="s")
                df = df.set_index("time")
                return df
    except Exception as e:
        print(f"  error fetching timeseries for {topic}: {e}")
    return pd.DataFrame()


def download_lunarcrush_features(tickers, days=365):
    """
    Download social sentiment features for all tickers.
    Returns a DataFrame with sentiment and galaxy_score per ticker per day.
    """
    print("\nDownloading LunarCrush social sentiment...")

    all_data = {}

    for ticker in tickers:
        topic = TICKER_TO_TOPIC.get(ticker)
        if not topic:
            print(f"  {ticker} — no LunarCrush mapping, skipping")
            continue

        print(f"  -> {ticker} ({topic})")
        ts = get_topic_timeseries(topic, days=days)

        if ts.empty:
            print(f"     no data available")
            continue

        # keep only relevant columns
        cols = []
        if "sentiment" in ts.columns:
            ts[f"{ticker}_sentiment"]    = ts["sentiment"]
            cols.append(f"{ticker}_sentiment")
        if "galaxy_score" in ts.columns:
            ts[f"{ticker}_galaxy_score"] = ts["galaxy_score"]
            cols.append(f"{ticker}_galaxy_score")
        if "num_posts" in ts.columns:
            ts[f"{ticker}_num_posts"]    = ts["num_posts"]
            cols.append(f"{ticker}_num_posts")

        if cols:
            all_data[ticker] = ts[cols]
            print(f"     {len(ts)} days downloaded")

    if not all_data:
        print("  no LunarCrush data available")
        return pd.DataFrame()

    # combine all tickers into one DataFrame
    combined = pd.concat(all_data.values(), axis=1)
    combined.index = pd.to_datetime(combined.index).tz_localize(None)

    print(f"  LunarCrush data ready — {len(combined)} days x {len(combined.columns)} columns")
    return combined


def get_current_signals(tickers):
    """Get today's sentiment signals for dashboard display."""
    print("\nFetching current LunarCrush signals...")
    signals = []

    for ticker in tickers:
        topic = TICKER_TO_TOPIC.get(ticker)
        if not topic:
            continue

        data = get_topic_sentiment(topic)
        if data:
            signals.append({
                "ticker":       ticker,
                "sentiment":    data["sentiment"],
                "galaxy_score": data["galaxy_score"],
                "num_posts":    data["num_posts"],
            })
            print(f"  {ticker:<6} sentiment: {data['sentiment']:.0f}  galaxy: {data['galaxy_score']:.0f}")

    return pd.DataFrame(signals)


if __name__ == "__main__":
    print("LunarCrush Data — Test")
    print("=" * 40)

    # test current signals
    tickers = ["NVDA", "PLTR", "AMD", "ARM", "SPY", "QQQ"]
    signals = get_current_signals(tickers)

    if not signals.empty:
        print("\nCurrent social sentiment:")
        print(signals.to_string(index=False))
    else:
        print("No data available")