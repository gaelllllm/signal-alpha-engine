# ============================================================
# PHASE 2 — MODÈLE ML & GÉNÉRATION DE SIGNAUX
# Signal Alpha Engine
# ============================================================

import pandas as pd                              # Manipulation des données
import numpy as np                               # Calculs mathématiques
import lightgbm as lgb                           # Modèle ML (utilisé par les hedge funds)
import optuna                                    # Optimisation automatique des paramètres
import shap                                      # Explication des décisions du modèle
from sklearn.metrics import (
    accuracy_score,                              # % de bonnes prédictions
    precision_score,                             # % de vrais positifs
    roc_auc_score                                # Score global du modèle
)
import warnings
import os
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ============================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================

def charger_donnees(chemin="data/donnees_features.csv"):
    """Charge le CSV généré par la Phase 1."""

    print("Chargement des données...")
    data = pd.read_csv(chemin, index_col=0, parse_dates=True)
    print(f"✓ {len(data)} lignes chargées.")
    return data

# ============================================================
# 2. FEATURES — ce que le modèle va analyser
# ============================================================

FEATURES = [
    "momentum_5",
    "momentum_20",
    "momentum_60",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_position",
    "atr_14_norm",
    "volume_ratio",
    "price_vs_sma20",
    "price_vs_sma200",
    "ticker_code",
    "dist_52w_high",   # Nouveau
    "dist_52w_low",    # Nouveau
    "vol_5",           # Nouveau
    "vol_20",          # Nouveau
    "vol_ratio",       # Nouveau
    "day_of_week",     # Nouveau
    "volume_trend",    # Nouveau
    "vix_level",       # Nouveau
    "vix_change",      # Nouveau
    "taux_change",     # Nouveau
    "dollar_change",   # Nouveau
]

# ============================================================
# 3. PRÉPARATION DES DONNÉES
# ============================================================

def preparer_donnees(data):
    """Sépare les features (X) et le target (y), puis fait le split temporel."""

    print("\nPréparation des données...")

    # Convertit le ticker en nombre (AAPL=0, MSFT=1, etc.)
    # Le modèle ne comprend que les chiffres, pas les textes
    data["ticker_code"] = pd.Categorical(data["ticker"]).codes

    # Normalise l'ATR par le prix — sinon BTC (60 000$) écrase AAPL (180$)
    data["atr_14_norm"] = data["atr_14"] / data["Close"]

    # Supprime les lignes avec des valeurs manquantes
    data = data.dropna(subset=FEATURES + ["target"])

    # X = ce que le modèle voit (les indicateurs)
    X = data[FEATURES]

    # y = ce que le modèle doit prédire (0 ou 1)
    y = data["target"]

    # --- SPLIT TEMPOREL ---
    # 70% des données pour apprendre, 30% pour tester
    # On ne mélange jamais passé et futur en finance
    split = int(len(data) * 0.70)

    X_train = X.iloc[:split]
    X_test  = X.iloc[split:]
    y_train = y.iloc[:split]
    y_test  = y.iloc[split:]

    print(f"✓ Entraînement : {len(X_train)} lignes")
    print(f"✓ Test         : {len(X_test)} lignes")
    print(f"✓ % hausses dans train : {y_train.mean()*100:.1f}%")
    print(f"✓ % hausses dans test  : {y_test.mean()*100:.1f}%")

    return X_train, X_test, y_train, y_test, data

# ============================================================
# 4. OPTIMISATION DES HYPERPARAMÈTRES AVEC OPTUNA
# Optuna teste 50 combinaisons et garde la meilleure
# ============================================================

def optimiser_modele(X_train, y_train, n_trials=50):
    """Trouve les meilleurs paramètres du modèle via Optuna."""

    print(f"\nOptimisation des hyperparamètres ({n_trials} essais)...")
    print("(C'est normal si ça prend 1-2 minutes)")

    def objective(trial):
        params = {
            "objective":         "binary",
            "metric":            "auc",
            "verbosity":         -1,
            "boosting_type":     "gbdt",
            "num_leaves":        trial.suggest_int("num_leaves", 20, 150),
            "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators":      trial.suggest_int("n_estimators", 100, 1000),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha":         trial.suggest_float("reg_alpha", 1e-8, 1.0, log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda", 1e-8, 1.0, log=True),
        }

        # Validation croisée temporelle — évite l'overfitting
        split_val = int(len(X_train) * 0.80)
        X_tr  = X_train.iloc[:split_val]
        X_val = X_train.iloc[split_val:]
        y_tr  = y_train.iloc[:split_val]
        y_val = y_train.iloc[split_val:]

        model = lgb.LGBMClassifier(**params)
        model.fit(X_tr, y_tr)

        # On évalue sur la validation, pas sur le train — évite la triche
        score = roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])
        return score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    print(f"✓ Meilleur score AUC (validation) : {study.best_value:.4f}")
    print(f"✓ Meilleurs paramètres : {study.best_params}")

    return study.best_params

# ============================================================
# 5. ENTRAÎNEMENT DU MODÈLE FINAL
# ============================================================

def entrainer_modele(X_train, y_train, params):
    """Entraîne le modèle LightGBM avec les meilleurs paramètres."""

    print("\nEntraînement du modèle final...")

    params["objective"]     = "binary"
    params["metric"]        = "auc"
    params["verbosity"]     = -1
    params["boosting_type"] = "gbdt"

    model = lgb.LGBMClassifier(**params)
    model.fit(X_train, y_train)

    print("✓ Modèle entraîné.")
    return model

# ============================================================
# 6. ÉVALUATION DES PERFORMANCES
# ============================================================

def evaluer_modele(model, X_test, y_test):
    """Calcule les métriques de performance sur les données de test."""

    print("\nÉvaluation du modèle...")

    y_pred       = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    accuracy  = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    auc       = roc_auc_score(y_test, y_pred_proba)

    print(f"\n{'='*40}")
    print(f"  RÉSULTATS DU MODÈLE")
    print(f"{'='*40}")
    print(f"  Accuracy  : {accuracy*100:.1f}%  (% de bonnes prédictions)")
    print(f"  Precision : {precision*100:.1f}%  (% de vrais signaux d'achat)")
    print(f"  AUC Score : {auc:.4f}  (0.5=nul, 1.0=parfait)")
    print(f"{'='*40}")

    return y_pred_proba

# ============================================================
# 7. ANALYSE SHAP — POURQUOI LE MODÈLE DÉCIDE AINSI ?
# ============================================================

def analyser_shap(model, X_test):
    """Calcule et affiche l'importance des features via SHAP."""

    print("\nCalcul des valeurs SHAP...")

    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)

    if isinstance(shap_values, list):
        importance = np.abs(shap_values[1]).mean(axis=0)
    else:
        importance = np.abs(shap_values).mean(axis=0)

    shap_df = pd.DataFrame({
        "feature":    FEATURES,
        "importance": importance
    }).sort_values("importance", ascending=False)

    print("\n  TOP FEATURES (ce qui influence le plus les décisions) :")
    print(f"  {'Feature':<20} {'Importance':>10}")
    print(f"  {'-'*32}")
    for _, row in shap_df.iterrows():
        bar = "█" * int(row["importance"] * 100)
        print(f"  {row['feature']:<20} {row['importance']:>8.4f}  {bar}")

    return shap_df

# ============================================================
# 8. GÉNÉRATION DES SIGNAUX
# ============================================================

def generer_signaux(model, data, y_pred_proba):
    """Ajoute les signaux du modèle aux données de test."""

    print("\nGénération des signaux...")

    data_clean = data.dropna(subset=FEATURES + ["target"])
    split      = int(len(data_clean) * 0.70)
    data_test  = data_clean.iloc[split:].copy()

    # Probabilité de hausse prédite par le modèle
    data_test["signal_proba"] = y_pred_proba

    # Signal binaire : on achète si probabilité > 60%
    data_test["signal_achat"] = (data_test["signal_proba"] > 0.55).astype(int)

    os.makedirs("data", exist_ok=True)
    data_test.to_csv("data/signaux.csv")

    nb_signaux = data_test["signal_achat"].sum()
    print(f"✓ {nb_signaux} signaux d'achat générés sur {len(data_test)} jours de test.")
    print(f"✓ Signaux sauvegardés dans 'data/signaux.csv'")

    return data_test

# ============================================================
# 9. PROGRAMME PRINCIPAL
# ============================================================

if __name__ == "__main__":

    print("=" * 50)
    print("  SIGNAL ALPHA ENGINE — Phase 2 : Modèle ML")
    print("=" * 50)

    # Étape 1 : chargement
    data = charger_donnees()

    # Étape 2 : préparation
    X_train, X_test, y_train, y_test, data = preparer_donnees(data)

    # Étape 3 : optimisation
    meilleurs_params = optimiser_modele(X_train, y_train, n_trials=50)

    # Étape 4 : entraînement
    model = entrainer_modele(X_train, y_train, meilleurs_params)

    # Étape 5 : évaluation
    y_pred_proba = evaluer_modele(model, X_test, y_test)

    # Étape 6 : SHAP
    shap_df = analyser_shap(model, X_test)

    # Étape 7 : signaux
    signaux = generer_signaux(model, data, y_pred_proba)

    print("\n🎉 Phase 2 terminée ! Signaux prêts pour le backtesting.")