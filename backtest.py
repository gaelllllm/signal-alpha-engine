import pandas as pd
import numpy as np
import os


def load_signals(path="data/signals.csv"):
    print("Loading signals...")
    data = pd.read_csv(path, index_col=0, parse_dates=True)
    print(f"  {len(data)} rows loaded")
    return data


def run_backtest(data, capital=10000, threshold=0.60,
                 stop_loss=0.02, take_profit=0.05, horizon=5):

    print(f"\nRunning backtest...")
    print(f"  capital: ${capital} | threshold: {threshold*100}%")
    print(f"  stop loss: -{stop_loss*100}% | take profit: +{take_profit*100}% (4% from day 4)")
    print(f"  horizon: {horizon} days | fees: 0.1% per trade")

    trades  = []
    current = capital
    data    = data.sort_index()

    for ticker in data["ticker"].unique():
        if ticker == "BTC-USD":
            continue
        df = data[data["ticker"] == ticker].copy().sort_index()

        for i in range(len(df) - horizon):
            row = df.iloc[i]

            if row["signal_achat"] != 1:
                continue

            entry_price = row["Close"]
            size        = current * 0.10
            shares      = size / entry_price
            fee_entry   = size * 0.001

            exit_price  = None
            exit_reason = "horizon"
            exit_day    = horizon

            for j in range(1, horizon + 1):
                price_j = df.iloc[i + j]["Close"]
                ret_j   = (price_j - entry_price) / entry_price

                # dynamic take profit — lower to 4% from day 4
                tp = take_profit if j < 4 else 0.04

                if ret_j <= -stop_loss:
                    exit_price  = price_j
                    exit_reason = "stop_loss"
                    exit_day    = j
                    break

                if ret_j >= tp:
                    exit_price  = price_j
                    exit_reason = "take_profit"
                    exit_day    = j
                    break

            if exit_price is None:
                exit_price = df.iloc[i + horizon]["Close"]

            fee_exit = (shares * exit_price) * 0.001
            pnl      = (shares * exit_price) - (shares * entry_price) - fee_entry - fee_exit
            ret      = pnl / size

            current += pnl

            trades.append({
                "date_entree":  df.index[i],
                "date_sortie":  df.index[i + exit_day],
                "ticker":       ticker,
                "prix_entree":  round(entry_price, 2),
                "prix_sortie":  round(exit_price, 2),
                "montant":      round(size, 2),
                "pnl":          round(pnl, 2),
                "rendement":    round(ret * 100, 2),
                "raison":       exit_reason,
                "capital":      round(current, 2),
            })

    trades_df = pd.DataFrame(trades)
    print(f"  {len(trades_df)} trades simulated")
    return trades_df, current


def compute_metrics(trades_df, initial_capital=10000):
    print("\nComputing performance metrics...")

    if trades_df.empty:
        print("  no trades found")
        return {}

    winners = trades_df[trades_df["pnl"] > 0]
    losers  = trades_df[trades_df["pnl"] <= 0]
    n       = len(trades_df)

    win_rate      = len(winners) / n * 100
    avg_win       = winners["pnl"].mean() if len(winners) > 0 else 0
    avg_loss      = losers["pnl"].mean()  if len(losers)  > 0 else 0
    profit_factor = winners["pnl"].sum() / abs(losers["pnl"].sum()) if len(losers) > 0 else 0

    final_capital = trades_df["capital"].iloc[-1]
    total_return  = (final_capital - initial_capital) / initial_capital * 100

    rets   = trades_df["rendement"] / 100
    sharpe = (rets.mean() / rets.std()) * np.sqrt(252)

    curve    = trades_df["capital"]
    drawdown = (curve - curve.cummax()) / curve.cummax() * 100
    max_dd   = drawdown.min()

    annual_ret = total_return / (n / 252)
    calmar     = abs(annual_ret / max_dd) if max_dd != 0 else 0

    print(f"\n  {'='*44}")
    print(f"  PERFORMANCE REPORT — SIGNAL ALPHA ENGINE")
    print(f"  {'='*44}")
    print(f"  trades        : {n}")
    print(f"  win rate      : {win_rate:.1f}%")
    print(f"  avg win       : +${avg_win:.2f}")
    print(f"  avg loss      : ${avg_loss:.2f}")
    print(f"  profit factor : {profit_factor:.2f}")
    print(f"  {'='*44}")
    print(f"  initial capital : ${initial_capital}")
    print(f"  final capital   : ${final_capital:.2f}")
    print(f"  total return    : {total_return:+.1f}%")
    print(f"  {'='*44}")
    print(f"  sharpe ratio  : {sharpe:.2f}")
    print(f"  max drawdown  : {max_dd:.1f}%")
    print(f"  calmar ratio  : {calmar:.2f}")
    print(f"  {'='*44}")

    print("\n  exit breakdown:")
    for reason, count in trades_df["raison"].value_counts().items():
        print(f"  {reason:<15} {count} ({count/n*100:.1f}%)")

    print("\n  top 3 trades:")
    for _, r in trades_df.nlargest(3, "pnl").iterrows():
        print(f"  {r['ticker']:<10} {str(r['date_entree'])[:10]}  +${r['pnl']:.2f}  ({r['rendement']:+.1f}%)")

    print("\n  worst 3 trades:")
    for _, r in trades_df.nsmallest(3, "pnl").iterrows():
        print(f"  {r['ticker']:<10} {str(r['date_entree'])[:10]}  ${r['pnl']:.2f}  ({r['rendement']:+.1f}%)")

    return {
        "nb_trades":       n,
        "win_rate":        win_rate,
        "profit_factor":   profit_factor,
        "rendement_total": total_return,
        "sharpe":          sharpe,
        "max_drawdown":    max_dd,
        "calmar":          calmar,
    }


def performance_by_asset(trades_df):
    print(f"\n  {'ticker':<10} {'trades':>6} {'win%':>6} {'pnl':>10} {'avg':>10}")
    print(f"  {'-'*46}")
    for ticker in trades_df["ticker"].unique():
        t = trades_df[trades_df["ticker"] == ticker]
        print(f"  {ticker:<10} {len(t):>6} {(t['pnl']>0).mean()*100:>5.1f}% "
              f"{t['pnl'].sum():>+9.2f}$ {t['pnl'].mean():>+9.2f}$")


def save_results(trades_df, metrics):
    os.makedirs("data", exist_ok=True)
    trades_df.to_csv("data/trades.csv", index=False)
    pd.DataFrame([metrics]).to_csv("data/metrics.csv", index=False)
    print("\n  trades saved to data/trades.csv")
    print("  metrics saved to data/metrics.csv")


if __name__ == "__main__":
    print("Signal Alpha Engine — Backtesting")
    print("=" * 40)

    data = load_signals()

    trades_df, final_capital = run_backtest(
        data,
        capital     = 10000,
        threshold   = 0.60,
        stop_loss   = 0.02,
        take_profit = 0.05,
        horizon     = 5
    )

    metrics = compute_metrics(trades_df, initial_capital=10000)
    performance_by_asset(trades_df)

    if metrics:
        save_results(trades_df, metrics)

    print("\nDone.")