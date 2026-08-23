import sqlite3
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_squared_error, mean_absolute_error
from xgboost import XGBRegressor
import joblib

DB_PATH = "../Dataset/delhi_aqi.db"


def load_and_prepare_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT zone_id, timestamp_hour, pm25_value, has_text, recency_hours, concat_text 
        FROM alignment_table 
        ORDER BY timestamp_hour ASC
    """, conn)
    conn.close()

    df["datetime"] = pd.to_datetime(df["timestamp_hour"].str.replace("Z", "", regex=False))

    df["hour"] = df["datetime"].dt.hour
    df["dayofweek"] = df["datetime"].dt.dayofweek

    # Sort by zone then time so lag/rolling calculations never cross zone boundaries.
    # NOTE: this ordering is ONLY for the feature engineering below. The train/test
    # split further down does NOT use this row order — see the fix there.
    df = df.sort_values(["zone_id", "datetime"]).reset_index(drop=True)

    df["pm25_lag1"] = df.groupby("zone_id")["pm25_value"].shift(1)
    df["pm25_lag2"] = df.groupby("zone_id")["pm25_value"].shift(2)

    # FIX: rolling average must be computed on the SHIFTED series (past values only).
    # The original computed rolling(3) directly on pm25_value, which includes the
    # current row in its own "3-hour average" — that's the model seeing the answer
    # baked into a feature. Shifting first means pm25_rolling_3h at hour t is the
    # average of hours t-1, t-2, t-3 only.
    df["pm25_rolling_3h"] = (
        df.groupby("zone_id")["pm25_lag1"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )

    df["pm25_rate_of_change"] = df["pm25_lag1"] - df["pm25_lag2"]

    df = df.dropna(subset=["pm25_lag1", "pm25_lag2", "pm25_rolling_3h", "pm25_rate_of_change"]).reset_index(drop=True)

    df["concat_text"] = df["concat_text"].fillna("")

    return df


def train_phase2_baselines():
    print("--- PHASE 2: Training Baseline Models ---")
    df = load_and_prepare_data()

    sensor_features = ["hour", "dayofweek", "pm25_lag1", "pm25_lag2", "pm25_rolling_3h", "pm25_rate_of_change"]
    target = "pm25_value"

    # FIX: split chronologically by an actual datetime cutoff, not by row position
    # in a zone-sorted dataframe. This guarantees "train" = all zone-hours before
    # the cutoff (across every zone) and "test" = all zone-hours after it — a real
    # time-based split, not an accidental zone-based one.
    cutoff_time = df["datetime"].quantile(0.8)
    train_df = df[df["datetime"] <= cutoff_time].reset_index(drop=True)
    test_df = df[df["datetime"] > cutoff_time].reset_index(drop=True)

    print(f"Chronological cutoff: {cutoff_time}")
    print(f"Dataset Split: {len(train_df)} Training samples | {len(test_df)} Test samples")
    print(f"Zones in train: {train_df['zone_id'].nunique()} | Zones in test: {test_df['zone_id'].nunique()}\n")

    # FIX: fit TF-IDF on TRAIN text only, then transform test with that same
    # fitted vectorizer. Fitting on the full dataset (including test rows) lets
    # test-set vocabulary influence the features test performance is measured on.
    vectorizer = TfidfVectorizer(max_features=50, stop_words="english")
    train_tfidf = vectorizer.fit_transform(train_df["concat_text"]).toarray()
    test_tfidf = vectorizer.transform(test_df["concat_text"]).toarray()

    tfidf_cols = [f"tfidf_{i}" for i in range(train_tfidf.shape[1])]
    train_df = pd.concat([train_df, pd.DataFrame(train_tfidf, columns=tfidf_cols)], axis=1)
    test_df = pd.concat([test_df, pd.DataFrame(test_tfidf, columns=tfidf_cols)], axis=1)

    text_features = ["has_text", "recency_hours"] + tfidf_cols
    naive_features = sensor_features + text_features

    # --- MODEL A: Sensor-Only ---
    model_a = XGBRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
    model_a.fit(train_df[sensor_features], train_df[target])
    pred_a = model_a.predict(test_df[sensor_features])

    # --- MODEL B: Text-Only ---
    # NOTE: expect this to perform noticeably worse than Model A. Your text
    # mentions are citywide (same headlines for every zone at a given hour, per
    # the earlier design decision), so this model is trying to predict different
    # zone-specific pm25 values from identical inputs across zones at the same
    # timestamp. A high error here isn't a bug — it's the expected, honest
    # consequence of text not being zone-specific, and it's worth discussing
    # directly in your results/limitations section.
    model_b = XGBRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
    model_b.fit(train_df[text_features], train_df[target])
    pred_b = model_b.predict(test_df[text_features])

    # --- MODEL C: Naive Fusion ---
    model_naive = XGBRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
    model_naive.fit(train_df[naive_features], train_df[target])
    pred_naive = model_naive.predict(test_df[naive_features])

    def eval_metrics(y_true, y_pred, name):
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = mean_absolute_error(y_true, y_pred)
        print(f"== {name} ==")
        print(f"   RMSE: {rmse:.3f} µg/m³")
        print(f"   MAE : {mae:.3f} µg/m³\n")

    print("--- MODEL PERFORMANCE COMPARISON ---")
    eval_metrics(test_df[target], pred_a, "Baseline A (Sensor-Only)")
    eval_metrics(test_df[target], pred_b, "Baseline B (Text-Only)")
    eval_metrics(test_df[target], pred_naive, "Naive Fusion (Concatenated)")

    test_df = test_df.copy()
    test_df["pred_sensor_only"] = pred_a
    test_df["pred_text_only"] = pred_b
    test_df["pred_naive_fusion"] = pred_naive
    test_df.to_csv("phase2_test_predictions.csv", index=False)

    joblib.dump(model_a, "model_baseline_a.pkl")
    joblib.dump(model_b, "model_baseline_b.pkl")
    joblib.dump(model_naive, "model_naive_fusion.pkl")
    joblib.dump(vectorizer, "tfidf_vectorizer.pkl")

    print("Phase 2 complete! Trained models saved to .pkl files.")
    print("Predictions saved to phase2_test_predictions.csv for Phase 3 gating.")


if __name__ == "__main__":
    train_phase2_baselines()