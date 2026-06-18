import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime
from dotenv import load_dotenv
from notifier import notify_signal, notify_order, notify_no_signals, notify_daily_summary
import logging
import os

load_dotenv()

API_KEY    = os.getenv("ALPACA_KEY")
API_SECRET = os.getenv("ALPACA_SECRET")
PAPER      = True

CAPITAL          = 100000
POSITION_SIZE    = 0.10
STOP_LOSS_PCT    = 0.02
TAKE_PROFIT_PCT  = 0.05
SIGNAL_THRESHOLD = 0.60

EXCLUDED = ["BTC-USD", "GC=F", "CL=F"]


def connect(api_key, api_secret, paper=True):
    print("Connecting to Alpaca...")
    client  = TradingClient(api_key, api_secret, paper=paper)
    account = client.get_account()
    print(f"  connected — buying power: ${float(account.buying_power):,.2f}")
    return client


def get_latest_signals(path="data/signals.csv"):
    print("\nLoading signals...")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    latest = df.groupby("ticker").last().reset_index()
    buys = latest[
        (latest["signal_achat"] == 1) &
        (latest["signal_proba"] > SIGNAL_THRESHOLD) &
        (~latest["ticker"].isin(EXCLUDED))
    ].copy()
    print(f"  {len(buys)} buy signals found")
    for _, row in buys.iterrows():
        print(f"  -> {row['ticker']}  {row['signal_proba']*100:.1f}%  ${row['Close']:.2f}")
    return buys


def get_open_positions(client):
    positions = client.get_all_positions()
    return {p.symbol: p for p in positions}


def place_order(client, ticker, price, capital):
    size = capital * POSITION_SIZE
    qty  = int(size / price)

    if qty < 1:
        print(f"  {ticker} — not enough capital for 1 share, skipping")
        return None

    stop_price   = round(price * (1 - STOP_LOSS_PCT), 2)
    target_price = round(price * (1 + TAKE_PROFIT_PCT), 2)

    print(f"\n  Placing order: BUY {qty} {ticker} @ ${price:.2f}")
    print(f"  stop loss: ${stop_price:.2f} | take profit: ${target_price:.2f}")

    notify_signal(ticker, SIGNAL_THRESHOLD, price, stop_price, target_price)

    try:
        # simple market order — SL/TP checked at close by position manager
        order = client.submit_order(MarketOrderRequest(
            symbol        = ticker,
            qty           = qty,
            side          = OrderSide.BUY,
            time_in_force = TimeInForce.DAY,
        ))
        print(f"  order placed — id: {order.id}")
        notify_order(ticker, qty, price, str(order.id))
        return order

    except Exception as e:
        print(f"  ERROR placing order for {ticker}: {e}")
        return None


def run_trader():
    print("=" * 40)
    print(f"Signal Alpha Engine — Trader")
    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 40)

    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        filename=f"logs/trader_{datetime.now().strftime('%Y%m%d')}.log",
        level=logging.INFO,
        format="%(asctime)s — %(message)s"
    )

    client    = connect(API_KEY, API_SECRET, paper=PAPER)
    account   = client.get_account()
    capital   = float(account.buying_power)
    positions = get_open_positions(client)

    print(f"\n  open positions: {list(positions.keys()) or 'none'}")

    signals = get_latest_signals()

    if signals.empty:
        print("\n  no buy signals today — nothing to trade")
        notify_no_signals()
        return

    orders_placed = 0
    for _, signal in signals.iterrows():
        ticker = signal["ticker"]
        price  = signal["Close"]

        if ticker in positions:
            print(f"\n  {ticker} — already in position, skipping")
            continue

        order = place_order(client, ticker, price, capital)
        if order:
            orders_placed += 1
            logging.info(f"BUY {ticker} @ ${price:.2f}")

    print(f"\n{'='*40}")
    print(f"Done — {orders_placed} orders placed")
    print(f"{'='*40}")

    notify_daily_summary(orders_placed, capital)


if __name__ == "__main__":
    run_trader()