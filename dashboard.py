import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import pandas as pd
import requests
import os
from datetime import datetime

COLORS = {
    "bg":         "#0d1117",
    "card":       "#161b22",
    "border":     "#30363d",
    "text":       "#e6edf3",
    "text_muted": "#8b949e",
    "green":      "#3fb950",
    "red":        "#f85149",
    "blue":       "#58a6ff",
    "yellow":     "#d29922",
    "purple":     "#bc8cff",
}

EXCLUDED = ["BTC-USD"]


def card_style(extra={}):
    base = {
        "backgroundColor": COLORS["card"],
        "border":          f"1px solid {COLORS['border']}",
        "borderRadius":    "8px",
        "padding":         "20px",
    }
    return {**base, **extra}


def load_trades():
    try:
        return pd.read_csv("data/trades.csv", parse_dates=["date_entree", "date_sortie"])
    except:
        return pd.DataFrame()


def load_signals():
    try:
        return pd.read_csv("data/signals.csv", index_col=0, parse_dates=True)
    except:
        return pd.DataFrame()


def load_metrics():
    try:
        return pd.read_csv("data/metrics.csv").iloc[0].to_dict()
    except:
        return {}


def load_fear_greed():
    try:
        r    = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = r.json()["data"][0]
        return int(data["value"]), data["value_classification"]
    except:
        return None, None


def get_latest_signals(signals):
    if signals.empty:
        return pd.DataFrame()
    latest = signals.groupby("ticker").last().reset_index()
    latest = latest[~latest["ticker"].isin(EXCLUDED)]
    return latest[["ticker", "signal_proba", "signal_achat", "Close"]].sort_values(
        "signal_proba", ascending=False
    )


app = dash.Dash(
    __name__,
    title="Signal Alpha Engine",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)

app.layout = html.Div([

    # header
    html.Div([
        html.Div([
            html.H1("⚡ Signal Alpha Engine",
                style={"color": COLORS["text"], "margin": "0",
                       "fontSize": "24px", "fontWeight": "600"}),
            html.P("Quantitative Trading Dashboard",
                style={"color": COLORS["text_muted"], "margin": "4px 0 0 0",
                       "fontSize": "13px"}),
        ]),
        html.Div([
            html.P(id="last-update",
                style={"color": COLORS["text_muted"], "fontSize": "12px",
                       "margin": "0 16px 0 0", "alignSelf": "center"}),
            html.Button("🔄 Refresh signals", id="refresh-btn",
                style={
                    "backgroundColor": COLORS["blue"],
                    "color":           "#0d1117",
                    "border":          "none",
                    "borderRadius":    "6px",
                    "padding":         "8px 16px",
                    "cursor":          "pointer",
                    "fontWeight":      "600",
                    "fontSize":        "13px",
                }),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={
        "backgroundColor": COLORS["card"],
        "borderBottom":    f"1px solid {COLORS['border']}",
        "padding":         "16px 24px",
        "display":         "flex",
        "justifyContent":  "space-between",
        "alignItems":      "center",
    }),

    # main content
    html.Div([

        # 5 metric cards
        html.Div(id="metric-cards", style={
            "display":             "grid",
            "gridTemplateColumns": "repeat(5, 1fr)",
            "gap":                 "16px",
            "marginBottom":        "24px",
        }),

        # signals with date
        html.Div([
            html.Div([
                html.H2("📡 Today's signals",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0"}),
                html.P(datetime.now().strftime("%A %d %B %Y"),
                    style={"color": COLORS["text_muted"], "fontSize": "12px",
                           "margin": "0"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "marginBottom": "16px"}),
            html.Div(id="signals-table"),
        ], style=card_style({"marginBottom": "24px"})),

        # top charts
        html.Div([
            html.Div([
                html.H2("💰 Equity curve",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="equity-curve",
                    config={"displayModeBar": False},
                    style={"height": "300px"}),
            ], style=card_style()),

            html.Div([
                html.H2("📊 PnL by asset",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="perf-by-asset",
                    config={"displayModeBar": False},
                    style={"height": "300px"}),
            ], style=card_style()),

        ], style={
            "display":             "grid",
            "gridTemplateColumns": "1fr 1fr",
            "gap":                 "16px",
            "marginBottom":        "24px",
        }),

        # bottom charts
        html.Div([
            html.Div([
                html.H2("📈 Return distribution",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="returns-hist",
                    config={"displayModeBar": False},
                    style={"height": "250px"}),
            ], style=card_style()),

            html.Div([
                html.H2("🎯 Exit reasons",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="exits-pie",
                    config={"displayModeBar": False},
                    style={"height": "250px"}),
            ], style=card_style()),

        ], style={
            "display":             "grid",
            "gridTemplateColumns": "1fr 1fr",
            "gap":                 "16px",
            "marginBottom":        "24px",
        }),

        # recent trades
        html.Div([
            html.H2("📋 Recent trades",
                style={"color": COLORS["text"], "fontSize": "16px",
                       "fontWeight": "600", "margin": "0 0 16px 0"}),
            html.Div(id="trades-table"),
        ], style=card_style()),

    ], style={"padding": "24px", "maxWidth": "1400px", "margin": "0 auto"}),

    dcc.Interval(id="interval", interval=60*1000, n_intervals=0),

], style={
    "backgroundColor": COLORS["bg"],
    "minHeight":       "100vh",
    "fontFamily":      "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
})


@app.callback(
    Output("metric-cards",  "children"),
    Output("signals-table", "children"),
    Output("equity-curve",  "figure"),
    Output("perf-by-asset", "figure"),
    Output("returns-hist",  "figure"),
    Output("exits-pie",     "figure"),
    Output("trades-table",  "children"),
    Output("last-update",   "children"),
    Input("interval",       "n_intervals"),
    Input("refresh-btn",    "n_clicks"),
)
def update(n_intervals, n_clicks):
    trades  = load_trades()
    signals = load_signals()
    metrics = load_metrics()
    now     = datetime.now().strftime("%d/%m/%Y %H:%M")

    # metric cards
    def metric_card(label, value, color, sub=""):
        return html.Div([
            html.P(label, style={"color": COLORS["text_muted"], "fontSize": "12px",
                                 "margin": "0 0 8px 0", "textTransform": "uppercase",
                                 "letterSpacing": "0.5px"}),
            html.H2(value, style={"color": color, "fontSize": "26px",
                                  "fontWeight": "700", "margin": "0"}),
            html.P(sub, style={"color": COLORS["text_muted"], "fontSize": "11px",
                               "margin": "4px 0 0 0"}),
        ], style=card_style())

    if metrics:
        nb_trades    = int(metrics.get('nb_trades', 0))
        total_return = metrics.get('rendement_total', 0)

        # calculate exact period from trades
        if not trades.empty:
            start      = pd.to_datetime(trades["date_entree"].min())
            end        = pd.to_datetime(trades["date_entree"].max())
            years      = (end - start).days / 365.25
            annual_return = total_return / years if years > 0 else 0
            start_date = start.strftime("%b %Y")
        else:
            annual_return = 0
            start_date    = ""

        # fear & greed
        fg_value, fg_label = load_fear_greed()
        fg_color = (COLORS["green"]  if fg_value and fg_value > 60
               else COLORS["red"]    if fg_value and fg_value < 40
               else COLORS["yellow"])

        cards = [
            metric_card("Total return",
                f"+{total_return:.1f}%",
                COLORS["green"], f"since {start_date}"),
            metric_card("Annual return",
                f"+{annual_return:.1f}%",
                COLORS["green"], "annualized"),
            metric_card("Sharpe ratio",
                f"{metrics.get('sharpe', 0):.2f}",
                COLORS["blue"], ">1.5 = good"),
            metric_card("Win rate",
                f"{metrics.get('win_rate', 0):.1f}%",
                COLORS["purple"], f"{nb_trades} trades"),
            metric_card("Fear & Greed",
                f"{fg_value}/100" if fg_value else "N/A",
                fg_color, fg_label or ""),
        ]
    else:
        cards = [html.P("No metrics available",
                        style={"color": COLORS["text_muted"]})]

    # signals table
    latest = get_latest_signals(signals)
    if not latest.empty:
        rows = []
        for _, row in latest.iterrows():
            buy   = row["signal_achat"] == 1
            color = COLORS["green"] if buy else COLORS["text_muted"]
            label = "✅ BUY" if buy else "⏸ WAIT"
            proba = row["signal_proba"]

            bar = html.Div([
                html.Div(style={
                    "width":           f"{proba*100:.0f}%",
                    "height":          "6px",
                    "backgroundColor": COLORS["green"] if buy else COLORS["border"],
                    "borderRadius":    "3px",
                }),
            ], style={"width": "100px", "backgroundColor": COLORS["border"],
                      "borderRadius": "3px", "height": "6px"})

            rows.append(html.Div([
                html.Span(row["ticker"],
                    style={"color": COLORS["text"], "fontWeight": "600",
                           "width": "100px", "display": "inline-block", "fontSize": "14px"}),
                html.Span(label,
                    style={"color": color, "width": "100px", "display": "inline-block",
                           "fontSize": "13px", "fontWeight": "600"}),
                html.Span(f"{proba*100:.1f}%",
                    style={"color": color, "width": "60px",
                           "display": "inline-block", "fontSize": "13px"}),
                bar,
                html.Span(f"${row['Close']:.2f}",
                    style={"color": COLORS["text_muted"], "fontSize": "13px",
                           "marginLeft": "20px"}),
            ], style={"display": "flex", "alignItems": "center", "padding": "10px 0",
                      "borderBottom": f"1px solid {COLORS['border']}", "gap": "16px"}))

        signals_html = html.Div(rows)
    else:
        signals_html = html.P("No signals — run data_pipeline.py and model.py",
                              style={"color": COLORS["text_muted"]})

    # equity curve
    if not trades.empty:
        sorted_trades = trades.sort_values("date_entree").reset_index(drop=True)
        capital = 10000
        curve   = [capital]
        for _, t in sorted_trades.iterrows():
            capital += t["pnl"]
            curve.append(round(capital, 2))
        dates = [sorted_trades["date_entree"].iloc[0]] + list(sorted_trades["date_entree"])

        y_min = min(curve) * 0.98
        y_max = max(curve) * 1.02

        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=dates, y=curve, mode="lines",
            line={"color": COLORS["blue"], "width": 2},
            fill="tozeroy", fillcolor="rgba(88, 166, 255, 0.08)",
        ))
        fig_equity.add_hline(
            y=10000, line_dash="dash",
            line_color=COLORS["text_muted"], opacity=0.5,
            annotation_text="initial capital",
            annotation_font_color=COLORS["text_muted"],
        )
        fig_equity.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"],
            font={"color": COLORS["text"], "size": 11},
            margin={"t": 10, "b": 30, "l": 60, "r": 20},
            xaxis={"gridcolor": COLORS["border"]},
            yaxis={"gridcolor": COLORS["border"], "tickprefix": "$",
                   "range": [y_min, y_max]},
            showlegend=False, hovermode="x unified",
        )
    else:
        fig_equity = go.Figure()
        fig_equity.update_layout(paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"])

    # pnl by asset
    if not trades.empty:
        perf = trades.groupby("ticker").agg(
            pnl_total=("pnl", "sum")
        ).reset_index().sort_values("pnl_total", ascending=True)

        fig_perf = go.Figure(go.Bar(
            x=perf["pnl_total"], y=perf["ticker"], orientation="h",
            marker_color=[COLORS["green"] if x > 0 else COLORS["red"]
                         for x in perf["pnl_total"]],
            text=[f"+${x:.0f}" if x > 0 else f"-${abs(x):.0f}"
                 for x in perf["pnl_total"]],
            textposition="outside",
        ))
        fig_perf.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"],
            font={"color": COLORS["text"], "size": 11},
            margin={"t": 10, "b": 30, "l": 80, "r": 60},
            xaxis={"gridcolor": COLORS["border"], "tickprefix": "$"},
            yaxis={"gridcolor": COLORS["border"]},
            showlegend=False,
        )
    else:
        fig_perf = go.Figure()
        fig_perf.update_layout(paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"])

    # return distribution
    if not trades.empty:
        fig_hist = go.Figure(go.Histogram(
            x=trades["rendement"], nbinsx=30,
            marker={"color": COLORS["blue"], "opacity": 0.8},
        ))
        fig_hist.add_vline(x=0, line_color=COLORS["red"], line_dash="dash", opacity=0.7)
        fig_hist.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"],
            font={"color": COLORS["text"], "size": 11},
            margin={"t": 10, "b": 30, "l": 50, "r": 20},
            xaxis={"gridcolor": COLORS["border"], "ticksuffix": "%"},
            yaxis={"gridcolor": COLORS["border"]},
            showlegend=False, bargap=0.1,
        )
    else:
        fig_hist = go.Figure()
        fig_hist.update_layout(paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"])

    # exit pie
    if not trades.empty:
        exits = trades["raison"].value_counts()
        fig_pie = go.Figure(go.Pie(
            labels=exits.index, values=exits.values, hole=0.5,
            marker={"colors": [COLORS["blue"], COLORS["red"], COLORS["green"]]},
            textfont={"color": COLORS["text"]},
        ))
        fig_pie.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"],
            font={"color": COLORS["text"], "size": 11},
            margin={"t": 10, "b": 10, "l": 20, "r": 20},
            legend={"font": {"color": COLORS["text"]}},
        )
    else:
        fig_pie = go.Figure()
        fig_pie.update_layout(paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["card"])

    # recent trades
    if not trades.empty:
        recent = trades.sort_values("date_entree", ascending=False).head(10)

        headers = ["Date", "Ticker", "Entry", "Exit", "PnL", "Return", "Reason"]
        widths  = ["100px", "80px", "80px", "80px", "80px", "90px", "auto"]

        header_row = html.Div([
            html.Span(h, style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "width": w, "display": "inline-block",
                                "textTransform": "uppercase"})
            for h, w in zip(headers, widths)
        ], style={"padding": "8px 0", "borderBottom": f"1px solid {COLORS['border']}"})

        exit_colors = {
            "take_profit": COLORS["green"],
            "stop_loss":   COLORS["red"],
            "horizon":     COLORS["text_muted"],
        }

        trade_rows = [header_row]
        for _, t in recent.iterrows():
            pos   = t["pnl"] > 0
            color = COLORS["green"] if pos else COLORS["red"]
            sign  = "+" if pos else ""

            trade_rows.append(html.Div([
                html.Span(str(t["date_entree"])[:10],
                    style={"color": COLORS["text_muted"], "fontSize": "13px",
                           "width": "100px", "display": "inline-block"}),
                html.Span(t["ticker"],
                    style={"color": COLORS["text"], "fontWeight": "600",
                           "fontSize": "13px", "width": "80px", "display": "inline-block"}),
                html.Span(f"${t['prix_entree']:.2f}",
                    style={"color": COLORS["text"], "fontSize": "13px",
                           "width": "80px", "display": "inline-block"}),
                html.Span(f"${t['prix_sortie']:.2f}",
                    style={"color": COLORS["text"], "fontSize": "13px",
                           "width": "80px", "display": "inline-block"}),
                html.Span(f"{sign}{t['pnl']:.2f}$",
                    style={"color": color, "fontWeight": "600", "fontSize": "13px",
                           "width": "80px", "display": "inline-block"}),
                html.Span(f"{sign}{t['rendement']:.1f}%",
                    style={"color": color, "fontSize": "13px",
                           "width": "90px", "display": "inline-block"}),
                html.Span(t["raison"],
                    style={"color": exit_colors.get(t["raison"], COLORS["text_muted"]),
                           "fontSize": "12px"}),
            ], style={"padding": "10px 0",
                      "borderBottom": f"1px solid {COLORS['border']}"}))

        trades_html = html.Div(trade_rows)
    else:
        trades_html = html.P("No trades available",
                             style={"color": COLORS["text_muted"]})

    return (cards, signals_html, fig_equity, fig_perf,
            fig_hist, fig_pie, trades_html,
            f"Last update: {now}")


if __name__ == "__main__":
    print("Signal Alpha Engine — Dashboard")
    print("=" * 40)
    print("  running on http://localhost:8050\n")
    app.run(debug=True, port=8050, use_reloader=False)