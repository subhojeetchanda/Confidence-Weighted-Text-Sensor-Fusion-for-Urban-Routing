import sqlite3
import pandas as pd
import numpy as np
import joblib
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
import optuna

from train_baselines import load_and_prepare_data

def train_phase3_gating():
    print("--- PHASE 3: Training Gating Model ---")
    df = load_and_prepare_data()

    sensor_features = ["hour", "dayofweek", "pm25_lag1", "pm25_lag2", "pm25_rolling_3h", "pm25_rate_of_change"]
    target = "pm25_value"

    cutoff_time = df["datetime"].quantile(0.8)
    train_df = df[df["datetime"] <= cutoff_time].reset_index(drop=True)
    test_df = df[df["datetime"] > cutoff_time].reset_index(drop=True)

    vectorizer = joblib.load("tfidf_vectorizer.pkl")
    train_tfidf = vectorizer.transform(train_df["concat_text"]).toarray()
    test_tfidf = vectorizer.transform(test_df["concat_text"]).toarray()

    tfidf_cols = [f"tfidf_{i}" for i in range(train_tfidf.shape[1])]
    train_df = pd.concat([train_df, pd.DataFrame(train_tfidf, columns=tfidf_cols)], axis=1)
    test_df = pd.concat([test_df, pd.DataFrame(test_tfidf, columns=tfidf_cols)], axis=1)

    text_features = ["has_text", "recency_hours"] + tfidf_cols

    model_a = joblib.load("model_baseline_a.pkl")
    model_b = joblib.load("model_baseline_b.pkl")

    train_df["pred_sensor"] = model_a.predict(train_df[sensor_features])
    train_df["pred_text"] = model_b.predict(train_df[text_features])

    test_df["pred_sensor"] = model_a.predict(test_df[sensor_features])
    test_df["pred_text"] = model_b.predict(test_df[text_features])

    train_df["disagreement_score"] = np.abs(train_df["pred_sensor"] - train_df["pred_text"])
    test_df["disagreement_score"] = np.abs(test_df["pred_sensor"] - test_df["pred_text"])

    gating_features = ["pred_sensor", "pred_text", "disagreement_score", "recency_hours"]

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 20, 200),
            "max_depth": trial.suggest_int("max_depth", 2, 6),
            "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.2, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "random_state": 42
        }
        
        # Split train_df further into train/val for Optuna to avoid overfitting
        val_cutoff = train_df["datetime"].quantile(0.8)
        opt_train = train_df[train_df["datetime"] <= val_cutoff]
        opt_val = train_df[train_df["datetime"] > val_cutoff]
        
        model = XGBRegressor(**params)
        model.fit(opt_train[gating_features], opt_train[target])
        
        preds = model.predict(opt_val[gating_features])
        rmse = np.sqrt(mean_squared_error(opt_val[target], preds))
        return rmse

    # Disable optuna logs to avoid spamming the console
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    print("Running Optuna tuning for the gating model (20 trials)...")
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=20)
    
    print("Best hyperparameters:", study.best_params)

    best_params = study.best_params
    best_params["random_state"] = 42
    gating_model = XGBRegressor(**best_params)
    gating_model.fit(train_df[gating_features], train_df[target])

    final_preds = gating_model.predict(test_df[gating_features])
    
    rmse = np.sqrt(mean_squared_error(test_df[target], final_preds))
    mae = mean_absolute_error(test_df[target], final_preds)
    
    print("== Gating Model (Phase 3) ==")
    print(f"   RMSE: {rmse:.3f} µg/m³")
    print(f"   MAE : {mae:.3f} µg/m³\n")
    
    test_df["pred_gating"] = final_preds
    
    model_naive = joblib.load("model_naive_fusion.pkl")
    naive_features = sensor_features + text_features
    test_df["pred_naive_fusion"] = model_naive.predict(test_df[naive_features])
    
    naive_rmse = np.sqrt(mean_squared_error(test_df[target], test_df["pred_naive_fusion"]))
    naive_mae = mean_absolute_error(test_df[target], test_df["pred_naive_fusion"])
    
    print("== Naive Fusion (Baseline C) ==")
    print(f"   RMSE: {naive_rmse:.3f} µg/m³")
    print(f"   MAE : {naive_mae:.3f} µg/m³\n")

    test_df.to_csv("phase3_test_predictions.csv", index=False)
    joblib.dump(gating_model, "model_gating.pkl")
    
    print("Phase 3 complete! Trained gating model saved to model_gating.pkl.")
    print("Predictions saved to phase3_test_predictions.csv.")

if __name__ == "__main__":
    train_phase3_gating()
