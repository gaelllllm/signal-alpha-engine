import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime, timezone
from notifier import notify
import logging
import os

# ============================================================
# ALPACA API KEYS
# ============================================================
API_KEY    = "PK2RWLSFLFIQ3BU2O3THLG5IH7"
API_SECRET = "5Ltwkpn4ey5eV1q9jbkYRY9bD4V85CWJeFwT2r2bVBtD"
PAPER      = True

# close position after this many trading days
MAX_HOLDING_DAYS = 5


def connect():
    print("Connecting to Alpaca...")
    client  = TradingClient(API_KEY, API_SECRET, paper=PAPER)
    account = client.get_account()
    print(f"  connected — buying power: ${float(account.buying_power):,.2f}")
    return client


def get_open_positions(client):
    """Get all open positions with their age."""
    positions = client.get_all_positions()
    print(f"\n  open positions: {len(positions)}")
    return positions


def get_position_age(position):
    """
    Estimate position age from Alpaca.
    Alpaca doesn't give entry date directly so we use the cost basis date
    from orders history.
    """
    # we'll use a simple approach — check if unrealized PnL suggests old position
    return None


def close_position(client, symbol, qty):
    """Close a position by selling all shares."""
    print(f"\n  Closing {symbol} — {qty} shares")
    try:
        order = client.submit_order(MarketOrderRequest(
            symbol        = symbol,
            qty           = qty,
            side          = OrderSide.SELL,
            time_in_force = TimeInForce.DAY,
        ))
        print(f"  closed — order id: {order.id}")
        return order
    except Exception as e:
        print(f"  ERROR closing {symbol}: {e}")
        return None


def check_and_close_old_positions(client):
    """
    Check all open positions and close those held too long.
    Since Alpaca paper trading doesn't give entry date easily,
    we cross-reference with our trades.csv file.
    """
    print("\nChecking positions age...")

    # load our trade history
    try:
        trades = pd.read_csv("data/trades.csv", parse_dates=["date_entree"])
    except:
        print("  no trades.csv found")
        return

    today     = pd.Timestamp.now().normalize()
    positions = get_open_positions(client)

    if not positions:
        print("  no open positions")
        return

    closed = 0
    for position in positions:
        symbol = position.symbol
        qty    = abs(int(float(position.qty)))

        # find the most recent entry for this symbol in our trades
        symbol_trades = trades[trades["ticker"] == symbol]
        if symbol_trades.empty:
            print(f"  {symbol} — no entry in trades.csv, skipping")
            continue

        last_entry = symbol_trades["date_entree"].max()
        days_held  = (today - last_entry).days

        print(f"  {symbol} — held {days_held} days (entry: {last_entry.date()})")

        if days_held >= MAX_HOLDING_DAYS:
            print(f"  -> {symbol} exceeded {MAX_HOLDING_DAYS} days — closing")
            order = close_position(client, symbol, qty)
            if order:
                closed += 1
                notify(
                    f"<b>🔴 Position Closed</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"Ticker    : <b>{symbol}</b>\n"
                    f"Held      : <b>{days_held} days</b>\n"
                    f"Reason    : max holding period\n"
                    f"PnL       : <b>${float(position.unrealized_pl):.2f}</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
                )
        else:
            remaining = MAX_HOLDING_DAYS - days_held
            print(f"  -> {symbol} OK — {remaining} days remaining")

    print(f"\n  {closed} positions closed")


def run_position_manager():
    print("=" * 40)
    print(f"Signal Alpha Engine — Position Manager")
    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 40)

    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        filename=f"logs/positions_{datetime.now().strftime('%Y%m%d')}.log",
        level=logging.INFO,
        format="%(asctime)s — %(message)s"
    )

    client = connect()
    check_and_close_old_positions(client)

    print("\nDone.")


if __name__ == "__main__":
    run_position_manager()