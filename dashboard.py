# ============================================================
# PHASE 4 — DASHBOARD
# Signal Alpha Engine
# ============================================================

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import pandas as pd
import os
from datetime import datetime

# ============================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================

def charger_trades():
    try:
        return pd.read_csv("data/trades.csv", parse_dates=["date_entree", "date_sortie"])
    except:
        return pd.DataFrame()

def charger_signaux():
    try:
        df = pd.read_csv("data/signaux.csv", index_col=0, parse_dates=True)
        return df
    except:
        return pd.DataFrame()

def charger_metriques():
    try:
        return pd.read_csv("data/metriques.csv").iloc[0].to_dict()
    except:
        return {}

def get_signaux_aujourdhui(signaux):
    if signaux.empty:
        return pd.DataFrame()
    derniers = signaux.groupby("ticker").last().reset_index()
    derniers = derniers[["ticker", "signal_proba", "signal_achat", "Close"]].copy()
    derniers = derniers.sort_values("signal_proba", ascending=False)
    return derniers

# ============================================================
# 2. INITIALISATION
# ============================================================

app = dash.Dash(
    __name__,
    title="Signal Alpha Engine",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)

# ============================================================
# 3. COULEURS
# ============================================================

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

def card_style(extra={}):
    base = {
        "backgroundColor": COLORS["card"],
        "border":          f"1px solid {COLORS['border']}",
        "borderRadius":    "8px",
        "padding":         "20px",
    }
    return {**base, **extra}

# ============================================================
# 4. LAYOUT
# ============================================================

app.layout = html.Div([

    # --- HEADER ---
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
            html.Button("🔄 Actualiser les signaux",
                id="refresh-btn",
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

    # --- CONTENU ---
    html.Div([

        # Métriques
        html.Div(id="metriques-cards", style={
            "display":             "grid",
            "gridTemplateColumns": "repeat(4, 1fr)",
            "gap":                 "16px",
            "marginBottom":        "24px",
        }),

        # Signaux
        html.Div([
            html.H2("📡 Signaux du jour",
                style={"color": COLORS["text"], "fontSize": "16px",
                       "fontWeight": "600", "margin": "0 0 16px 0"}),
            html.Div(id="signaux-table"),
        ], style=card_style({"marginBottom": "24px"})),

        # Graphiques haut
        html.Div([
            html.Div([
                html.H2("💰 Courbe d'équité",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="equity-curve",
                    config={"displayModeBar": False},
                    style={"height": "300px"}),
            ], style=card_style()),

            html.Div([
                html.H2("📊 Performance par actif",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="perf-par-actif",
                    config={"displayModeBar": False},
                    style={"height": "300px"}),
            ], style=card_style()),

        ], style={
            "display":             "grid",
            "gridTemplateColumns": "1fr 1fr",
            "gap":                 "16px",
            "marginBottom":        "24px",
        }),

        # Graphiques bas
        html.Div([
            html.Div([
                html.H2("📈 Distribution des rendements",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="rendements-hist",
                    config={"displayModeBar": False},
                    style={"height": "250px"}),
            ], style=card_style()),

            html.Div([
                html.H2("🎯 Raisons de sortie",
                    style={"color": COLORS["text"], "fontSize": "16px",
                           "fontWeight": "600", "margin": "0 0 16px 0"}),
                dcc.Graph(id="sorties-pie",
                    config={"displayModeBar": False},
                    style={"height": "250px"}),
            ], style=card_style()),

        ], style={
            "display":             "grid",
            "gridTemplateColumns": "1fr 1fr",
            "gap":                 "16px",
            "marginBottom":        "24px",
        }),

        # Derniers trades
        html.Div([
            html.H2("📋 Derniers trades",
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

# ============================================================
# 5. CALLBACKS
# ============================================================

@app.callback(
    Output("metriques-cards",  "children"),
    Output("signaux-table",    "children"),
    Output("equity-curve",     "figure"),
    Output("perf-par-actif",   "figure"),
    Output("rendements-hist",  "figure"),
    Output("sorties-pie",      "figure"),
    Output("trades-table",     "children"),
    Output("last-update",      "children"),
    Input("interval",          "n_intervals"),
    Input("refresh-btn",       "n_clicks"),
)
def update_dashboard(n_intervals, n_clicks):

    trades  = charger_trades()
    signaux = charger_signaux()
    metrics = charger_metriques()
    now     = datetime.now().strftime("%d/%m/%Y %H:%M")

    # --------------------------------------------------------
    # MÉTRIQUES CARDS
    # --------------------------------------------------------
    def metric_card(titre, valeur, couleur, sous_titre=""):
        return html.Div([
            html.P(titre,
                style={"color": COLORS["text_muted"], "fontSize": "12px",
                       "margin": "0 0 8px 0", "textTransform": "uppercase",
                       "letterSpacing": "0.5px"}),
            html.H2(valeur,
                style={"color": couleur, "fontSize": "28px",
                       "fontWeight": "700", "margin": "0"}),
            html.P(sous_titre,
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "margin": "4px 0 0 0"}),
        ], style=card_style())

    if metrics:
        cards = [
            metric_card("Rendement total",
                f"+{metrics.get('rendement_total', 0):.1f}%",
                COLORS["green"], "Sur la période de test"),
            metric_card("Sharpe ratio",
                f"{metrics.get('sharpe', 0):.2f}",
                COLORS["blue"], ">1.5 = bon"),
            metric_card("Win rate",
                f"{metrics.get('win_rate', 0):.1f}%",
                COLORS["purple"], f"{int(metrics.get('nb_trades', 0))} trades"),
            metric_card("Max drawdown",
                f"{metrics.get('max_drawdown', 0):.1f}%",
                COLORS["red"], "Pire perte depuis un pic"),
        ]
    else:
        cards = [html.P("Aucune métrique disponible",
            style={"color": COLORS["text_muted"]})]

    # --------------------------------------------------------
    # SIGNAUX DU JOUR
    # --------------------------------------------------------
    signaux_jour = get_signaux_aujourdhui(signaux)

    if not signaux_jour.empty:
        rows = []
        for _, row in signaux_jour.iterrows():
            achat   = row["signal_achat"] == 1
            couleur = COLORS["green"] if achat else COLORS["text_muted"]
            emoji   = "✅ ACHETER" if achat else "⏸ ATTENDRE"
            proba   = row["signal_proba"]

            barre = html.Div([
                html.Div(style={
                    "width":           f"{proba*100:.0f}%",
                    "height":          "6px",
                    "backgroundColor": COLORS["green"] if achat else COLORS["border"],
                    "borderRadius":    "3px",
                }),
            ], style={
                "width":           "100px",
                "backgroundColor": COLORS["border"],
                "borderRadius":    "3px",
                "height":          "6px",
            })

            rows.append(html.Div([
                html.Span(row["ticker"],
                    style={"color": COLORS["text"], "fontWeight": "600",
                           "width": "100px", "display": "inline-block",
                           "fontSize": "14px"}),
                html.Span(emoji,
                    style={"color": couleur, "width": "130px",
                           "display": "inline-block", "fontSize": "13px",
                           "fontWeight": "600"}),
                html.Span(f"{proba*100:.1f}%",
                    style={"color": couleur, "width": "60px",
                           "display": "inline-block", "fontSize": "13px"}),
                barre,
                html.Span(f"${row['Close']:.2f}",
                    style={"color": COLORS["text_muted"], "fontSize": "13px",
                           "marginLeft": "20px"}),
            ], style={
                "display":      "flex",
                "alignItems":   "center",
                "padding":      "10px 0",
                "borderBottom": f"1px solid {COLORS['border']}",
                "gap":          "16px",
            }))

        signaux_html = html.Div(rows)
    else:
        signaux_html = html.P("Aucun signal disponible",
            style={"color": COLORS["text_muted"]})

    # --------------------------------------------------------
    # COURBE D'ÉQUITÉ — corrigée
    # --------------------------------------------------------
    if not trades.empty:
        # Trie tous les trades par date pour une courbe continue
        trades_sorted = trades.sort_values("date_entree").reset_index(drop=True)

        # Recalcule la courbe de capital dans l'ordre chronologique
        capital = 10000
        courbe  = [capital]
        for _, t in trades_sorted.iterrows():
            capital += t["pnl"]
            courbe.append(round(capital, 2))

        dates = [trades_sorted["date_entree"].iloc[0]] + list(trades_sorted["date_entree"])

        fig_equity = go.Figure()

        fig_equity.add_trace(go.Scatter(
            x         = dates,
            y         = courbe,
            mode      = "lines",
            name      = "Capital",
            line      = {"color": COLORS["blue"], "width": 2},
            fill      = "tozeroy",
            fillcolor = "rgba(88, 166, 255, 0.08)",
        ))

        fig_equity.add_hline(
            y                     = 10000,
            line_dash             = "dash",
            line_color            = COLORS["text_muted"],
            opacity               = 0.5,
            annotation_text       = "Capital initial",
            annotation_font_color = COLORS["text_muted"],
        )

        fig_equity.update_layout(
            paper_bgcolor = COLORS["card"],
            plot_bgcolor  = COLORS["card"],
            font          = {"color": COLORS["text"], "size": 11},
            margin        = {"t": 10, "b": 30, "l": 60, "r": 20},
            xaxis         = {"gridcolor": COLORS["border"], "showgrid": True},
            yaxis         = {"gridcolor": COLORS["border"], "showgrid": True,
                            "tickprefix": "$"},
            showlegend    = False,
            hovermode     = "x unified",
        )
    else:
        fig_equity = go.Figure()
        fig_equity.update_layout(
            paper_bgcolor = COLORS["card"],
            plot_bgcolor  = COLORS["card"],
        )

    # --------------------------------------------------------
    # PERFORMANCE PAR ACTIF
    # --------------------------------------------------------
    if not trades.empty:
        perf = trades.groupby("ticker").agg(
            pnl_total = ("pnl", "sum"),
            nb_trades = ("pnl", "count"),
            win_rate  = ("pnl", lambda x: (x > 0).mean() * 100)
        ).reset_index().sort_values("pnl_total", ascending=True)

        colors_bar = [COLORS["green"] if x > 0 else COLORS["red"]
                     for x in perf["pnl_total"]]

        fig_perf = go.Figure(go.Bar(
            x            = perf["pnl_total"],
            y            = perf["ticker"],
            orientation  = "h",
            marker_color = colors_bar,
            text         = [f"+${x:.0f}" if x > 0 else f"-${abs(x):.0f}"
                           for x in perf["pnl_total"]],
            textposition = "outside",
        ))

        fig_perf.update_layout(
            paper_bgcolor = COLORS["card"],
            plot_bgcolor  = COLORS["card"],
            font          = {"color": COLORS["text"], "size": 11},
            margin        = {"t": 10, "b": 30, "l": 80, "r": 60},
            xaxis         = {"gridcolor": COLORS["border"], "showgrid": True,
                            "tickprefix": "$"},
            yaxis         = {"gridcolor": COLORS["border"]},
            showlegend    = False,
        )
    else:
        fig_perf = go.Figure()
        fig_perf.update_layout(paper_bgcolor=COLORS["card"],
                               plot_bgcolor=COLORS["card"])

    # --------------------------------------------------------
    # HISTOGRAMME DES RENDEMENTS
    # --------------------------------------------------------
    if not trades.empty:
        fig_hist = go.Figure(go.Histogram(
            x        = trades["rendement"],
            nbinsx   = 30,
            marker   = {"color": COLORS["blue"], "opacity": 0.8},
        ))

        fig_hist.add_vline(x=0, line_color=COLORS["red"],
                          line_dash="dash", opacity=0.7)

        fig_hist.update_layout(
            paper_bgcolor = COLORS["card"],
            plot_bgcolor  = COLORS["card"],
            font          = {"color": COLORS["text"], "size": 11},
            margin        = {"t": 10, "b": 30, "l": 50, "r": 20},
            xaxis         = {"gridcolor": COLORS["border"],
                            "ticksuffix": "%"},
            yaxis         = {"gridcolor": COLORS["border"]},
            showlegend    = False,
            bargap        = 0.1,
        )
    else:
        fig_hist = go.Figure()
        fig_hist.update_layout(paper_bgcolor=COLORS["card"],
                               plot_bgcolor=COLORS["card"])

    # --------------------------------------------------------
    # PIE CHART
    # --------------------------------------------------------
    if not trades.empty:
        sorties = trades["raison"].value_counts()

        fig_pie = go.Figure(go.Pie(
            labels   = sorties.index,
            values   = sorties.values,
            hole     = 0.5,
            marker   = {"colors": [COLORS["blue"],
                                   COLORS["red"],
                                   COLORS["green"]]},
            textfont = {"color": COLORS["text"]},
        ))

        fig_pie.update_layout(
            paper_bgcolor = COLORS["card"],
            plot_bgcolor  = COLORS["card"],
            font          = {"color": COLORS["text"], "size": 11},
            margin        = {"t": 10, "b": 10, "l": 20, "r": 20},
            legend        = {"font": {"color": COLORS["text"]}},
            showlegend    = True,
        )
    else:
        fig_pie = go.Figure()
        fig_pie.update_layout(paper_bgcolor=COLORS["card"],
                              plot_bgcolor=COLORS["card"])

    # --------------------------------------------------------
    # DERNIERS TRADES
    # --------------------------------------------------------
    if not trades.empty:
        # Trie par date pour afficher les plus récents en premier
        derniers = trades.sort_values("date_entree", ascending=False).head(10)

        header = html.Div([
            html.Span("Date",
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "width": "100px", "display": "inline-block",
                       "textTransform": "uppercase"}),
            html.Span("Ticker",
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "width": "80px", "display": "inline-block",
                       "textTransform": "uppercase"}),
            html.Span("Entrée",
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "width": "80px", "display": "inline-block",
                       "textTransform": "uppercase"}),
            html.Span("Sortie",
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "width": "80px", "display": "inline-block",
                       "textTransform": "uppercase"}),
            html.Span("PnL",
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "width": "80px", "display": "inline-block",
                       "textTransform": "uppercase"}),
            html.Span("Rendement",
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "width": "90px", "display": "inline-block",
                       "textTransform": "uppercase"}),
            html.Span("Raison",
                style={"color": COLORS["text_muted"], "fontSize": "11px",
                       "textTransform": "uppercase"}),
        ], style={
            "padding":      "8px 0",
            "borderBottom": f"1px solid {COLORS['border']}",
        })

        rows = [header]
        for _, t in derniers.iterrows():
            positif = t["pnl"] > 0
            couleur = COLORS["green"] if positif else COLORS["red"]

            raison_colors = {
                "take_profit": COLORS["green"],
                "stop_loss":   COLORS["red"],
                "horizon":     COLORS["text_muted"],
            }

            rows.append(html.Div([
                html.Span(str(t["date_entree"])[:10],
                    style={"color": COLORS["text_muted"], "fontSize": "13px",
                           "width": "100px", "display": "inline-block"}),
                html.Span(t["ticker"],
                    style={"color": COLORS["text"], "fontSize": "13px",
                           "fontWeight": "600", "width": "80px",
                           "display": "inline-block"}),
                html.Span(f"${t['prix_entree']:.2f}",
                    style={"color": COLORS["text"], "fontSize": "13px",
                           "width": "80px", "display": "inline-block"}),
                html.Span(f"${t['prix_sortie']:.2f}",
                    style={"color": COLORS["text"], "fontSize": "13px",
                           "width": "80px", "display": "inline-block"}),
                html.Span(f"{'+'if positif else ''}{t['pnl']:.2f}$",
                    style={"color": couleur, "fontSize": "13px",
                           "fontWeight": "600", "width": "80px",
                           "display": "inline-block"}),
                html.Span(f"{'+'if positif else ''}{t['rendement']:.1f}%",
                    style={"color": couleur, "fontSize": "13px",
                           "width": "90px", "display": "inline-block"}),
                html.Span(t["raison"],
                    style={"color": raison_colors.get(t["raison"],
                           COLORS["text_muted"]),
                           "fontSize": "12px"}),
            ], style={
                "padding":      "10px 0",
                "borderBottom": f"1px solid {COLORS['border']}",
            }))

        trades_html = html.Div(rows)
    else:
        trades_html = html.P("Aucun trade disponible",
            style={"color": COLORS["text_muted"]})

    return (cards, signaux_html, fig_equity, fig_perf,
            fig_hist, fig_pie, trades_html,
            f"Dernière mise à jour : {now}")

# ============================================================
# 6. LANCEMENT
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  SIGNAL ALPHA ENGINE — Dashboard")
    print("=" * 50)
    print("\n✓ Dashboard disponible sur : http://localhost:8050")
    print("  Ouvre ce lien dans ton navigateur\n")

    app.run(debug=True, port=8050, use_reloader=False)