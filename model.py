import pandas as pd
import numpy as np
import lightgbm as lgb
import optuna
import shap
import joblib
from sklearn.metrics import accuracy_score, precision_score, roc_auc_score
import warnings
import os

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

FEATURES = [
    "momentum_5", "momentum_20", "momentum_60",
    "rsi_14",
    "macd", "macd_signal", "macd_hist",
    "bb_position",
    "atr_14_norm",
    "volume_ratio", "volume_trend",
    "price_vs_sma20", "price_vs_sma200",
    "dist_52w_high", "dist_52w_low",
    "vol_5", "vol_20", "vol_ratio",
    "day_of_week",
    "vix_level", "vix_change",
    "taux_change", "dollar_change",
    "ticker_code",
    "fear_greed",         # fear & greed index (0=extreme fear, 100=extreme greed)
    "fear_greed_change",  # variation sur 5 jours
]


def load_data(path="data/features.csv"):
    print("Loading data...")
    data = pd.read_csv(path, index_col=0, parse_dates=True)
    print(f"  {len(data)} rows loaded")
    return data


def prepare_data(data):
    print("\nPreparing data...")

    data["ticker_code"] = pd.Categorical(data["ticker"]).codes
    data["atr_14_norm"] = data["atr_14"] / data["Close"]
    data = data.dropna(subset=FEATURES + ["target"])

    X = data[FEATURES]
    y = data["target"]

    split = int(len(data) * 0.70)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    print(f"  train: {len(X_train)} rows — test: {len(X_test)} rows")
    print(f"  positive rate train: {y_train.mean()*100:.1f}% — test: {y_test.mean()*100:.1f}%")

    return X_train, X_test, y_train, y_test, data


def optimize(X_train, y_train, n_trials=50):
    print(f"\nOptimizing hyperparameters ({n_trials} trials)...")

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

        split_val = int(len(X_train) * 0.80)
        X_tr,  X_val = X_train.iloc[:split_val], X_train.iloc[split_val:]
        y_tr,  y_val = y_train.iloc[:split_val], y_train.iloc[split_val:]

        model = lgb.LGBMClassifier(**params)
        model.fit(X_tr, y_tr)
        return roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42)
    )
    study.optimize(objective, n_trials=n_trials)

    print(f"  best AUC: {study.best_value:.4f}")
    print(f"  best params: {study.best_params}")
    return study.best_params


def train_model(X_train, y_train, params):
    print("\nTraining final model...")
    params.update({"objective": "binary", "metric": "auc",
                   "verbosity": -1, "boosting_type": "gbdt"})
    model = lgb.LGBMClassifier(**params)
    model.fit(X_train, y_train)

    # save model to disk
    joblib.dump(model, "model.pkl")
    print("  model saved to model.pkl")
    return model


def evaluate(model, X_test, y_test):
    print("\nEvaluating model...")
    y_pred       = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    print(f"  accuracy  : {accuracy_score(y_test, y_pred)*100:.1f}%")
    print(f"  precision : {precision_score(y_test, y_pred, zero_division=0)*100:.1f}%")
    print(f"  AUC       : {roc_auc_score(y_test, y_pred_proba):.4f}")
    return y_pred_proba


def shap_analysis(model, X_test):
    print("\nSHAP analysis...")
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

    print(f"\n  {'feature':<20} {'importance':>10}")
    print(f"  {'-'*32}")
    for _, row in shap_df.iterrows():
        bar = "|" * int(row["importance"] * 100)
        print(f"  {row['feature']:<20} {row['importance']:>8.4f}  {bar}")

    return shap_df


def generate_signals(model, data, y_pred_proba, threshold=0.60):
    print("\nGenerating signals...")

    data_clean = data.dropna(subset=FEATURES + ["target"])
    split      = int(len(data_clean) * 0.70)
    test_data  = data_clean.iloc[split:].copy()

    test_data["signal_proba"] = y_pred_proba
    test_data["signal_achat"] = (test_data["signal_proba"] > threshold).astype(int)

    os.makedirs("data", exist_ok=True)
    test_data.to_csv("data/signals.csv")

    print(f"  {test_data['signal_achat'].sum()} buy signals out of {len(test_data)} days")
    return test_data


if __name__ == "__main__":
    print("Signal Alpha Engine — ML Model")
    print("=" * 40)

    data = load_data()
    X_train, X_test, y_train, y_test, data = prepare_data(data)

    # load existing model or train new one
    if os.path.exists("model.pkl"):
        print("\nLoading existing model from model.pkl...")
        model = joblib.load("model.pkl")
        print("  done")
    else:
        print("\nNo saved model — training from scratch...")
        best_params = optimize(X_train, y_train, n_trials=50)
        model       = train_model(X_train, y_train, best_params)

    y_pred_proba = evaluate(model, X_test, y_test)
    shap_df      = shap_analysis(model, X_test)
    signals      = generate_signals(model, data, y_pred_proba)

    print("\nDone. Signals ready for backtesting.")