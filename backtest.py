# ============================================================
# PHASE 3 — BACKTESTING
# Signal Alpha Engine
# ============================================================

import pandas as pd
import numpy as np
import os

# ============================================================
# 1. CHARGEMENT DES SIGNAUX
# ============================================================

def charger_signaux(chemin="data/signaux.csv"):
    """Charge les signaux générés par le modèle ML."""

    print("Chargement des signaux...")
    data = pd.read_csv(chemin, index_col=0, parse_dates=True)
    print(f"✓ {len(data)} lignes chargées.")
    return data

# ============================================================
# 2. SIMULATION DES TRADES
# On rejoue chaque signal comme si on avait vraiment tradé
# ============================================================

def simuler_trades(data, capital_initial=10000, seuil_signal=0.60,
                   stop_loss=0.02, take_profit=0.05, horizon=5):
    """
    Simule les trades sur la période de test.

    Règles :
    - On achète quand signal_proba > seuil (60%)
    - On vend après 'horizon' jours (5 jours)
    - Stop-loss à -2% (coupe la perte si ça baisse trop)
    - Take-profit à +5% (prend le gain si ça monte fort)
    - Frais de 0.1% par trade (réaliste pour un broker en ligne)
    - On risque max 10% du capital par trade
    """

    print(f"\nSimulation des trades...")
    print(f"  Capital initial : {capital_initial}$")
    print(f"  Seuil signal    : {seuil_signal*100}%")
    print(f"  Stop-loss       : -{stop_loss*100}%")
    print(f"  Take-profit     : +{take_profit*100}%")
    print(f"  Horizon         : {horizon} jours")
    print(f"  Frais           : 0.1% par trade")

    trades      = []       # Liste de tous les trades effectués
    capital     = capital_initial
    capital_max = capital  # Pour calculer le drawdown

    # On trie par date pour rejouer dans l'ordre chronologique
    data = data.sort_index()

    # On groupe par ticker pour traiter chaque actif séparément
    for ticker in data["ticker"].unique():

        df = data[data["ticker"] == ticker].copy()
        df = df.sort_index()

        for i in range(len(df) - horizon):

            ligne = df.iloc[i]

            # On ne trade que si le signal est positif
            if ligne["signal_achat"] != 1:
                continue

            prix_entree = ligne["Close"]

            # Taille de position : max 10% du capital par trade
            montant     = capital * 0.10
            nb_actions  = montant / prix_entree

            # Frais d'achat
            frais_achat = montant * 0.001

            # On regarde ce qui se passe dans les jours suivants
            prix_sortie   = None
            raison_sortie = "horizon"
            jour_sortie   = horizon

            for j in range(1, horizon + 1):
                prix_j    = df.iloc[i + j]["Close"]
                rendement = (prix_j - prix_entree) / prix_entree

                # Stop-loss déclenché
                if rendement <= -stop_loss:
                    prix_sortie   = prix_j
                    raison_sortie = "stop_loss"
                    jour_sortie   = j
                    break

                # Take-profit déclenché
                if rendement >= take_profit:
                    prix_sortie   = prix_j
                    raison_sortie = "take_profit"
                    jour_sortie   = j
                    break

            # Si ni stop ni take-profit : on vend au bout de horizon jours
            if prix_sortie is None:
                prix_sortie = df.iloc[i + horizon]["Close"]

            # Calcul du PnL (profit and loss)
            frais_vente = (nb_actions * prix_sortie) * 0.001
            pnl         = (nb_actions * prix_sortie) - (nb_actions * prix_entree) - frais_achat - frais_vente
            rendement   = pnl / montant

            # Met à jour le capital
            capital += pnl
            capital_max = max(capital_max, capital)

            trades.append({
                "date_entree":  df.index[i],
                "date_sortie":  df.index[i + jour_sortie],
                "ticker":       ticker,
                "prix_entree":  round(prix_entree, 2),
                "prix_sortie":  round(prix_sortie, 2),
                "montant":      round(montant, 2),
                "pnl":          round(pnl, 2),
                "rendement":    round(rendement * 100, 2),
                "raison":       raison_sortie,
                "capital":      round(capital, 2),
            })

    trades_df = pd.DataFrame(trades)
    print(f"✓ {len(trades_df)} trades simulés.")
    return trades_df, capital

# ============================================================
# 3. CALCUL DES MÉTRIQUES PROFESSIONNELLES
# Ce sont exactement les métriques regardées par les hedge funds
# ============================================================

def calculer_metriques(trades_df, capital_initial=10000):
    """Calcule toutes les métriques de performance."""

    print("\nCalcul des métriques de performance...")

    if len(trades_df) == 0:
        print("⚠ Aucun trade effectué.")
        return

    # --- MÉTRIQUES DE BASE ---
    nb_trades      = len(trades_df)
    trades_gagnants = trades_df[trades_df["pnl"] > 0]
    trades_perdants = trades_df[trades_df["pnl"] <= 0]

    win_rate       = len(trades_gagnants) / nb_trades * 100
    gain_moyen     = trades_gagnants["pnl"].mean() if len(trades_gagnants) > 0 else 0
    perte_moyenne  = trades_perdants["pnl"].mean() if len(trades_perdants) > 0 else 0

    # Profit factor : combien on gagne pour 1$ perdu
    # > 1.5 = bon, > 2.0 = excellent
    total_gains   = trades_gagnants["pnl"].sum() if len(trades_gagnants) > 0 else 0
    total_pertes  = abs(trades_perdants["pnl"].sum()) if len(trades_perdants) > 0 else 1
    profit_factor = total_gains / total_pertes

    # --- RENDEMENT TOTAL ---
    capital_final  = trades_df["capital"].iloc[-1]
    rendement_total = (capital_final - capital_initial) / capital_initial * 100

    # --- SHARPE RATIO ---
    # Mesure le rendement ajusté au risque
    # > 1.0 = acceptable, > 1.5 = bon, > 2.0 = excellent
    rendements_journaliers = trades_df["rendement"] / 100
    sharpe = (rendements_journaliers.mean() / rendements_journaliers.std()) * np.sqrt(252)

    # --- MAX DRAWDOWN ---
    # La pire perte depuis un pic — mesure le risque réel
    capital_curve  = trades_df["capital"]
    rolling_max    = capital_curve.cummax()
    drawdown       = (capital_curve - rolling_max) / rolling_max * 100
    max_drawdown   = drawdown.min()

    # --- CALMAR RATIO ---
    # Rendement annuel / Max drawdown — mesure l'efficacité du risque
    # > 1.0 = bon
    rendement_annuel = rendement_total / (nb_trades / 252)
    calmar = abs(rendement_annuel / max_drawdown) if max_drawdown != 0 else 0

    # --- AFFICHAGE ---
    print(f"\n{'='*50}")
    print(f"  RAPPORT DE PERFORMANCE — SIGNAL ALPHA ENGINE")
    print(f"{'='*50}")
    print(f"\n  📊 STATISTIQUES DES TRADES")
    print(f"  Nombre de trades      : {nb_trades}")
    print(f"  Win rate              : {win_rate:.1f}%  (% de trades gagnants)")
    print(f"  Gain moyen            : +{gain_moyen:.2f}$")
    print(f"  Perte moyenne         : {perte_moyenne:.2f}$")
    print(f"  Profit factor         : {profit_factor:.2f}  (>1.5 = bon)")

    print(f"\n  💰 PERFORMANCE FINANCIÈRE")
    print(f"  Capital initial       : {capital_initial}$")
    print(f"  Capital final         : {capital_final:.2f}$")
    print(f"  Rendement total       : {rendement_total:+.1f}%")

    print(f"\n  ⚖️  MÉTRIQUES DE RISQUE")
    print(f"  Sharpe ratio          : {sharpe:.2f}  (>1.5 = bon)")
    print(f"  Max drawdown          : {max_drawdown:.1f}%  (pire perte depuis un pic)")
    print(f"  Calmar ratio          : {calmar:.2f}  (>1.0 = bon)")

    print(f"\n  🎯 RÉPARTITION DES SORTIES")
    for raison, count in trades_df["raison"].value_counts().items():
        pct = count / nb_trades * 100
        print(f"  {raison:<15} : {count} trades ({pct:.1f}%)")

    print(f"\n  🏆 MEILLEURS TRADES")
    top3 = trades_df.nlargest(3, "pnl")[["ticker","date_entree","pnl","rendement","raison"]]
    for _, row in top3.iterrows():
        print(f"  {row['ticker']:<10} {str(row['date_entree'])[:10]}  +{row['pnl']:.2f}$  ({row['rendement']:+.1f}%)")

    print(f"\n  💀 PIRES TRADES")
    bot3 = trades_df.nsmallest(3, "pnl")[["ticker","date_entree","pnl","rendement","raison"]]
    for _, row in bot3.iterrows():
        print(f"  {row['ticker']:<10} {str(row['date_entree'])[:10]}  {row['pnl']:.2f}$  ({row['rendement']:+.1f}%)")

    print(f"{'='*50}")

    return {
        "nb_trades":       nb_trades,
        "win_rate":        win_rate,
        "profit_factor":   profit_factor,
        "rendement_total": rendement_total,
        "sharpe":          sharpe,
        "max_drawdown":    max_drawdown,
        "calmar":          calmar,
    }

# ============================================================
# 4. PERFORMANCE PAR ACTIF
# ============================================================

def performance_par_actif(trades_df):
    """Affiche les résultats trade par trade pour chaque actif."""

    print("\n  📈 PERFORMANCE PAR ACTIF")
    print(f"  {'Ticker':<10} {'Trades':>6} {'Win%':>6} {'PnL total':>10} {'Moy/trade':>10}")
    print(f"  {'-'*46}")

    for ticker in trades_df["ticker"].unique():
        t        = trades_df[trades_df["ticker"] == ticker]
        win_rate = (t["pnl"] > 0).mean() * 100
        pnl_total = t["pnl"].sum()
        pnl_moy   = t["pnl"].mean()
        print(f"  {ticker:<10} {len(t):>6} {win_rate:>5.1f}% {pnl_total:>+9.2f}$ {pnl_moy:>+9.2f}$")

# ============================================================
# 5. SAUVEGARDE
# ============================================================

def sauvegarder_resultats(trades_df, metriques):
    """Sauvegarde les trades et les métriques."""

    os.makedirs("data", exist_ok=True)

    # Sauvegarde tous les trades
    trades_df.to_csv("data/trades.csv", index=False)

    # Sauvegarde les métriques
    pd.DataFrame([metriques]).to_csv("data/metriques.csv", index=False)

    print(f"\n✓ Trades sauvegardés dans 'data/trades.csv'")
    print(f"✓ Métriques sauvegardées dans 'data/metriques.csv'")

# ============================================================
# 6. PROGRAMME PRINCIPAL
# ============================================================

if __name__ == "__main__":

    print("=" * 50)
    print("  SIGNAL ALPHA ENGINE — Phase 3 : Backtesting")
    print("=" * 50)

    # Étape 1 : chargement des signaux
    data = charger_signaux()

    # Étape 2 : simulation des trades
    trades_df, capital_final = simuler_trades(
        data,
        capital_initial = 10000,  # On part avec 10 000$
        seuil_signal    = 0.55,   # Seuil d'achat à 60%
        stop_loss       = 0.02,   # Stop-loss à -2%
        take_profit     = 0.05,   # Take-profit à +5%
        horizon         = 5       # On garde 5 jours max
    )

    # Étape 3 : métriques de performance
    metriques = calculer_metriques(trades_df, capital_initial=10000)

    # Étape 4 : performance par actif
    performance_par_actif(trades_df)

    # Étape 5 : sauvegarde
    if metriques:
        sauvegarder_resultats(trades_df, metriques)

    print("\n🎉 Phase 3 terminée ! Backtesting complet.")