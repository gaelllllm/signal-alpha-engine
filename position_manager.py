import pandas as pd
import time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime
from dotenv import load_dotenv
from notifier import notify
import logging
import os

load_dotenv()

API_KEY          = os.getenv("ALPACA_KEY")
API_SECRET       = os.getenv("ALPACA_SECRET")
PAPER            = True
MAX_HOLDING_DAYS = 5
STOP_LOSS_PCT    = 0.02
TAKE_PROFIT_PCT  = 0.05


def connect():
    print("Connecting to Alpaca...")
    client  = TradingClient(API_KEY, API_SECRET, paper=PAPER)
    account = client.get_account()
    print(f"  connected — buying power: ${float(account.buying_power):,.2f}")
    return client


def get_open_positions(client):
    positions = client.get_all_positions()
    print(f"\n  open positions: {len(positions)}")
    return positions


def close_position(client, symbol, qty, reason):
    """Submit a sell order and check its real status before reporting success."""
    print(f"\n  Closing {symbol} — {qty} shares — reason: {reason}")
    try:
        order = client.submit_order(MarketOrderRequest(
            symbol        = symbol,
            qty           = qty,
            side          = OrderSide.SELL,
            time_in_force = TimeInForce.DAY,
        ))

        # give the market a moment to fill it if it's open
        time.sleep(2)
        refreshed = client.get_order_by_id(order.id)
        status    = refreshed.status.value

        if status == "filled":
            fill_price = float(refreshed.filled_avg_price)
            print(f"  FILLED — order id: {order.id} — avg price: ${fill_price:.2f}")
            return refreshed, "filled", fill_price
        else:
            print(f"  PENDING — order id: {order.id} — status: {status} (market likely closed)")
            return refreshed, status, None

    except Exception as e:
        print(f"  ERROR closing {symbol}: {e}")
        return None, "error", None


def check_positions(client):
    print("\nChecking positions...")

    today     = pd.Timestamp.now().normalize()
    positions = get_open_positions(client)

    if not positions:
        print("  no open positions")
        notify(
            f"<b>🌙 Evening Check</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"No open positions tonight.\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
        )
        return

    # get real entry dates from Alpaca orders history
    orders      = client.get_orders()
    entry_dates = {}
    for order in orders:
        if order.filled_at and order.side.value == "buy":
            symbol = order.symbol
            filled = pd.Timestamp(order.filled_at).tz_localize(None).normalize()
            if symbol not in entry_dates or filled < entry_dates[symbol]:
                entry_dates[symbol] = filled

    closed     = 0
    pending    = 0
    still_open = []

    for position in positions:
        symbol  = position.symbol
        qty     = abs(int(float(position.qty)))
        pnl_pct = float(position.unrealized_plpc)
        pnl_usd = float(position.unrealized_pl)
        entry   = float(position.avg_entry_price)
        current = float(position.current_price)

        last_entry = entry_dates.get(symbol, today)
        days_held  = (today - last_entry).days

        print(f"\n  {symbol}")
        print(f"    entry: ${entry:.2f} | current: ${current:.2f}")
        print(f"    PnL: ${pnl_usd:.2f} ({pnl_pct*100:.2f}%)")
        print(f"    held: {days_held} days")

        reason = None

        # stop loss at -2%
        if pnl_pct <= -STOP_LOSS_PCT:
            reason = f"stop_loss ({pnl_pct*100:.1f}%)"

        # take profit +5% days 1-3
        elif days_held < 4 and pnl_pct >= TAKE_PROFIT_PCT:
            reason = f"take_profit ({pnl_pct*100:.1f}%)"

        # take profit +4% from day 4
        elif days_held >= 4 and pnl_pct >= 0.04:
            reason = f"take_profit_day4 ({pnl_pct*100:.1f}%)"

        # max holding period
        elif days_held >= MAX_HOLDING_DAYS:
            reason = f"max_horizon ({days_held} days)"

        if reason:
            order, status, fill_price = close_position(client, symbol, qty, reason)

            if status == "filled":
                closed += 1
                notify(
                    f"<b>🔴 Position Closed</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"Ticker  : <b>{symbol}</b>\n"
                    f"Reason  : <b>{reason}</b>\n"
                    f"Fill    : <b>${fill_price:.2f}</b>\n"
                    f"PnL     : <b>${pnl_usd:.2f} ({pnl_pct*100:.1f}%)</b>\n"
                    f"Held    : <b>{days_held} days</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
                )
            elif order is not None:
                pending += 1
                notify(
                    f"<b>⏳ Sell Order Pending</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"Ticker  : <b>{symbol}</b>\n"
                    f"Reason  : <b>{reason}</b>\n"
                    f"Status  : <b>{status}</b> — market likely closed\n"
                    f"Will execute at next market open.\n"
                    f"Unrealized PnL: <b>${pnl_usd:.2f} ({pnl_pct*100:.1f}%)</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
                )
        else:
            remaining = MAX_HOLDING_DAYS - days_held
            print(f"    -> holding — {remaining} days remaining")
            still_open.append({
                "symbol":    symbol,
                "pnl_pct":   pnl_pct,
                "pnl_usd":   pnl_usd,
                "days_held": days_held,
                "remaining": remaining,
            })

    # send status notification for positions still genuinely open (not pending close)
    if still_open:
        lines = [f"<b>🌙 Evening Check — {len(still_open)} open position(s)</b>", "━━━━━━━━━━━━━━━"]
        for p in still_open:
            sign  = "+" if p["pnl_usd"] >= 0 else ""
            emoji = "🟢" if p["pnl_usd"] >= 0 else "🔴"
            lines.append(
                f"{emoji} <b>{p['symbol']}</b> — {sign}${p['pnl_usd']:.2f} "
                f"({sign}{p['pnl_pct']*100:.1f}%)\n"
                f"   held {p['days_held']}d — closes in {p['remaining']}d"
            )
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>")
        notify("\n".join(lines))

    print(f"\n  {closed} positions filled — {pending} pending")


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
    check_positions(client)

    print("\nDone.")


if __name__ == "__main__":
    run_position_manager()