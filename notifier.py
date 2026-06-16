import asyncio
from telegram import Bot
from datetime import datetime

# ============================================================
# TELEGRAM CONFIG
# ============================================================
TOKEN   = "8799557932:AAFCp3Xy_AFHSqL5-fGQhBPZA8J1BeNHhaU"
CHAT_ID = "5278385166"

bot = Bot(token=TOKEN)


async def send_message(text):
    """Send a message to Telegram."""
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")


def notify(text):
    """Wrapper to send message from sync code."""
    asyncio.run(send_message(text))


def notify_signal(ticker, proba, price, stop, target):
    """Notify when a buy signal is detected."""
    msg = (
        f"<b>⚡ Signal Alpha Engine</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>BUY SIGNAL</b> — {ticker}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Confidence  : <b>{proba*100:.1f}%</b>\n"
        f"Price       : <b>${price:.2f}</b>\n"
        f"Stop loss   : <b>${stop:.2f}</b>\n"
        f"Take profit : <b>${target:.2f}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
    )
    notify(msg)


def notify_order(ticker, qty, price, order_id):
    """Notify when an order is placed."""
    msg = (
        f"<b>✅ Order Placed</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Ticker  : <b>{ticker}</b>\n"
        f"Qty     : <b>{qty} shares</b>\n"
        f"Price   : <b>${price:.2f}</b>\n"
        f"Total   : <b>${qty*price:.2f}</b>\n"
        f"ID      : <code>{order_id}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
    )
    notify(msg)


def notify_no_signals():
    """Notify when no signals today."""
    msg = (
        f"<b>⚡ Signal Alpha Engine</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>No signals today</b>\n"
        f"Market conditions not favorable.\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
    )
    notify(msg)


def notify_daily_summary(nb_orders, capital):
    """Notify daily summary."""
    msg = (
        f"<b>📊 Daily Summary</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Orders placed : <b>{nb_orders}</b>\n"
        f"Buying power  : <b>${capital:,.2f}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
    )
    notify(msg)


if __name__ == "__main__":
    # test — send a message to verify everything works
    notify(
        "<b>⚡ Signal Alpha Engine</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "Bot connected successfully!\n"
        "You will receive trading alerts here.\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"
    )
    print("Test message sent — check Telegram!")