# ============================================================
# PHASE 1 — DATA PIPELINE
# Signal Alpha Engine
# ============================================================

import yfinance as yf          # Pour télécharger les données boursières
import pandas as pd            # Pour manipuler les données en tableaux
import pandas_ta as ta         # Pour calculer les indicateurs techniques
import numpy as np             # Pour les calculs mathématiques
import os                      # Pour gérer les fichiers/dossiers

# ============================================================
# 1. LISTE DES ACTIFS À ANALYSER
# ============================================================

TICKERS = [
    # --- Mega-caps tech (très liquides, favoris des hedge funds) ---
    "AAPL",    # Apple
    "MSFT",    # Microsoft
    "NVDA",    # Nvidia — star absolue du moment
    "GOOGL",   # Google
    "META",    # Meta

    # --- Finance (bonne volatilité, sensibles aux taux) ---
    "JPM",     # JPMorgan
    "GS",      # Goldman Sachs

    # --- Matières premières ---
    "GC=F",    # Or (futures)
    "CL=F",    # Pétrole WTI (futures)

    # --- Crypto ---
    "BTC-USD", # Bitcoin

    # --- ETFs de référence ---
    "SPY",     # S&P 500
    "QQQ",     # Nasdaq
]

# Données macro — téléchargées séparément et mergées
MACRO_TICKERS = [
    "^VIX",       # Indice de peur du marché
    "^TNX",       # Taux d'intérêt US 10 ans
    "DX-Y.NYB",   # Dollar Index
]

# ============================================================
# 2. TÉLÉCHARGEMENT DES DONNÉES HISTORIQUES
# ============================================================

def telecharger_donnees(tickers, periode="5y"):
    """Télécharge les prix OHLCV pour chaque actif."""

    print(f"Téléchargement des données pour {len(tickers)} actifs...")

    tous_les_df = []

    for ticker in tickers:
        print(f"  → {ticker}")

        df = yf.download(ticker, period=periode, auto_adjust=True, progress=False)

        if df.empty:
            print(f"    ⚠ Pas de données pour {ticker}, on passe.")
            continue

        # Aplatir les colonnes multi-niveaux que yfinance crée parfois
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ajoute une colonne pour identifier l'actif
        df["ticker"] = ticker

        tous_les_df.append(df)

    data = pd.concat(tous_les_df)

    print(f"\n✓ {len(data)} lignes téléchargées au total.")
    return data

def telecharger_macro(periode="5y"):
    """Télécharge les données macro (VIX, taux, dollar)."""

    print("\nTéléchargement des données macro...")

    macro_df = pd.DataFrame()

    for ticker in MACRO_TICKERS:
        print(f"  → {ticker}")

        df = yf.download(ticker, period=periode, auto_adjust=True, progress=False)

        if df.empty:
            print(f"    ⚠ Pas de données pour {ticker}, on passe.")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # On ne garde que le prix de clôture renommé
        nom = ticker.replace("^", "").replace("-", "_").replace(".", "_")
        macro_df[nom] = df["Close"]

    print(f"✓ Données macro téléchargées : {list(macro_df.columns)}")
    return macro_df

# ============================================================
# 3. NETTOYAGE DES DONNÉES
# ============================================================

def nettoyer_donnees(data):
    """Supprime les valeurs manquantes et les anomalies."""

    print("\nNettoyage des données...")

    lignes_avant = len(data)

    # Supprime les lignes où le prix de clôture est manquant
    data = data.dropna(subset=["Close"])

    # Supprime les jours où le volume est nul (marché fermé, erreur)
    data = data[data["Volume"] > 0]

    # Supprime les prix négatifs ou nuls
    data = data[data["Close"] > 0]

    lignes_apres = len(data)
    print(f"✓ {lignes_avant - lignes_apres} lignes supprimées, {lignes_apres} lignes conservées.")

    return data

# ============================================================
# 4. CALCUL DES FEATURES (indicateurs techniques)
# ============================================================

def calculer_features(data, macro_df):
    """Calcule les indicateurs techniques pour chaque actif."""

    print("\nCalcul des features...")

    resultats = []

    for ticker in data["ticker"].unique():

        df = data[data["ticker"] == ticker].copy()
        df = df.sort_index()

        # --- MOMENTUM (force de la tendance) ---
        df["momentum_5"]   = df["Close"].pct_change(5)
        df["momentum_20"]  = df["Close"].pct_change(20)
        df["momentum_60"]  = df["Close"].pct_change(60)

        # --- RSI ---
        df["rsi_14"] = ta.rsi(df["Close"], length=14)

        # --- MACD ---
        macd = ta.macd(df["Close"])
        if macd is not None:
            df["macd"]        = macd["MACD_12_26_9"]
            df["macd_signal"] = macd["MACDs_12_26_9"]
            df["macd_hist"]   = macd["MACDh_12_26_9"]

        # --- BOLLINGER BANDS ---
        bb = ta.bbands(df["Close"], length=20)
        if bb is not None:
            df["bb_upper"]    = bb["BBU_20_2.0_2.0"]
            df["bb_lower"]    = bb["BBL_20_2.0_2.0"]
            df["bb_position"] = (df["Close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        # --- ATR ---
        df["atr_14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        # --- VOLUME ---
        df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

        # --- MOYENNES MOBILES ---
        df["sma_20"]  = ta.sma(df["Close"], length=20)
        df["sma_50"]  = ta.sma(df["Close"], length=50)
        df["sma_200"] = ta.sma(df["Close"], length=200)
        df["price_vs_sma20"]  = df["Close"] / df["sma_20"]
        df["price_vs_sma200"] = df["Close"] / df["sma_200"]

        # --- NOUVELLES FEATURES ---

        # Distance au plus haut et plus bas sur 52 semaines (252 jours de trading)
        # Proche du plus haut = momentum fort, proche du plus bas = possible rebond
        df["dist_52w_high"] = df["Close"] / df["High"].rolling(252).max()
        df["dist_52w_low"]  = df["Close"] / df["Low"].rolling(252).min()

        # Volatilité réalisée sur 5 et 20 jours
        # Mesure l'amplitude des mouvements récents
        df["vol_5"]  = df["Close"].pct_change().rolling(5).std()
        df["vol_20"] = df["Close"].pct_change().rolling(20).std()

        # Ratio volatilité court/long — spike = signal potentiel
        df["vol_ratio"] = df["vol_5"] / df["vol_20"]

        # Jour de la semaine (0=lundi, 4=vendredi)
        # Les lundis et vendredis ont des patterns différents
        df["day_of_week"] = df.index.dayofweek

        # Tendance du volume — volume qui monte = confirmation du mouvement
        df["volume_trend"] = df["Volume"].rolling(5).mean() / df["Volume"].rolling(20).mean()

        # --- DONNÉES MACRO (mergées par date) ---
        if not macro_df.empty:
            # Merge sur l'index de date — forward fill pour les jours sans cotation
            df = df.join(macro_df, how="left")
            df = df.ffill()

            # VIX : variation sur 5 jours (est-ce que la peur monte ?)
            if "VIX" in df.columns:
                df["vix_change"] = df["VIX"].pct_change(5)
                df["vix_level"]  = df["VIX"]  # Niveau absolu du VIX

            # Taux 10 ans : variation (hausse des taux = mauvais pour les actions)
            if "TNX" in df.columns:
                df["taux_change"] = df["TNX"].pct_change(5)

            # Dollar Index : variation (dollar fort = mauvais pour les matières premières)
            if "DX_Y_NYB" in df.columns:
                df["dollar_change"] = df["DX_Y_NYB"].pct_change(5)

        resultats.append(df)

    data_enrichie = pd.concat(resultats)

    nb_features = len([c for c in data_enrichie.columns
                      if c not in ["Open","High","Low","Close","Volume","ticker"]])
    print(f"✓ {nb_features} features calculées.")
    return data_enrichie

# ============================================================
# 5. CRÉATION DE LA VARIABLE CIBLE (TARGET)
# ============================================================

def creer_target(data, horizon=5, seuil=0.02):
    """
    Crée la variable cible binaire :
    1 = le prix monte de plus de 2% dans les 5 prochains jours
    0 = sinon
    """

    print("\nCréation de la variable cible...")

    resultats = []

    for ticker in data["ticker"].unique():
        df = data[data["ticker"] == ticker].copy()
        df = df.sort_index()

        # Prix dans 'horizon' jours
        df["prix_futur"] = df["Close"].shift(-horizon)

        # Rendement futur en pourcentage
        df["rendement_futur"] = (df["prix_futur"] - df["Close"]) / df["Close"]

        # Target : 1 si hausse > seuil, 0 sinon
        df["target"] = (df["rendement_futur"] > seuil).astype(int)

        resultats.append(df)

    data_finale = pd.concat(resultats)

    # Supprime les dernières lignes (futur inconnu)
    data_finale = data_finale.dropna(subset=["target"])

    pct_hausse = data_finale["target"].mean() * 100
    print(f"✓ Target créée : {pct_hausse:.1f}% de signaux positifs (hausses > {seuil*100}%)")

    return data_finale

# ============================================================
# 6. SAUVEGARDE
# ============================================================

def sauvegarder(data, nom_fichier="data/donnees_features.csv"):
    """Sauvegarde les données dans un fichier CSV."""

    os.makedirs("data", exist_ok=True)
    data.to_csv(nom_fichier)
    print(f"\n✓ Données sauvegardées dans '{nom_fichier}'")
    print(f"  Taille : {data.shape[0]} lignes × {data.shape[1]} colonnes")

# ============================================================
# 7. PROGRAMME PRINCIPAL
# ============================================================

if __name__ == "__main__":

    print("=" * 50)
    print("  SIGNAL ALPHA ENGINE — Phase 1 : Data Pipeline")
    print("=" * 50)

    # Étape 1 : téléchargement des actifs
    data = telecharger_donnees(TICKERS)

    # Étape 2 : téléchargement des données macro
    macro_df = telecharger_macro()

    # Étape 3 : nettoyage
    data = nettoyer_donnees(data)

    # Étape 4 : calcul des features + macro
    data = calculer_features(data, macro_df)

    # Étape 5 : création du target
    data = creer_target(data)

    # Étape 6 : sauvegarde
    sauvegarder(data)

    print("\n🎉 Phase 1 terminée ! Fichier prêt pour le modèle ML.")