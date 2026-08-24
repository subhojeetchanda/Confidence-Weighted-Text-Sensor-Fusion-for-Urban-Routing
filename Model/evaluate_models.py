import sqlite3
import pandas as pd
import numpy as np
import time
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor
from scipy.stats import wilcoxon

from train_baselines import load_and_prepare_data

def evaluate_phase4():
    print("--- PHASE 4: Evaluation and Ablation ---")
    df = load_and_prepare_data()

    # Re-sort by datetime globally for time-based rolling cross-validation
    df = df.sort_values("datetime").reset_index(drop=True)

    sensor_features = ["hour", "dayofweek", "pm25_lag1", "pm25_lag2", "pm25_rolling_3h", "pm25_rate_of_change"]
    target = "pm25_value"
    
    # Generate 5 time-based folds
    tscv = TimeSeriesSplit(n_splits=5)
    
    results = {
        "Sensor": [],
        "Text": [],
        "Naive": [],
        "Gated": [],
        "Ablation": []
    }
    
    # Use best parameters found in Phase 3
    gating_params = {'n_estimators': 146, 'max_depth': 2, 'learning_rate': 0.035, 'subsample': 0.93, 'colsample_bytree': 0.82, 'random_state': 42}
    
    fold = 1
    # Variables to store the last fold's models for latency testing
    last_naive_model = None
    last_gated_model = None
    last_sensor_model = None
    last_text_model = None
    last_test_df = None
    last_gating_features = None
    last_naive_features = None

    for train_index, test_index in tscv.split(df):
        print(f"\n--- Fold {fold} ---")
        train_df = df.iloc[train_index].copy()
        test_df = df.iloc[test_index].copy()
        
        # TF-IDF on this fold
        try:
            vectorizer = TfidfVectorizer(max_features=50, stop_words="english")
            train_tfidf = vectorizer.fit_transform(train_df["concat_text"]).toarray()
            test_tfidf = vectorizer.transform(test_df["concat_text"]).toarray()
        except ValueError:
            # Fallback if no valid text in this fold (empty vocabulary)
            train_tfidf = np.zeros((len(train_df), 50))
            test_tfidf = np.zeros((len(test_df), 50))
        
        tfidf_cols = [f"tfidf_{i}" for i in range(train_tfidf.shape[1])]
        train_df[tfidf_cols] = train_tfidf
        test_df[tfidf_cols] = test_tfidf
        
        text_features = ["has_text", "recency_hours"] + tfidf_cols
        naive_features = sensor_features + text_features
        
        # Model A: Sensor-only
        model_a = XGBRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
        model_a.fit(train_df[sensor_features], train_df[target])
        pred_a_test = model_a.predict(test_df[sensor_features])
        pred_a_train = model_a.predict(train_df[sensor_features])
        
        # Model B: Text-only
        model_b = XGBRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
        model_b.fit(train_df[text_features], train_df[target])
        pred_b_test = model_b.predict(test_df[text_features])
        pred_b_train = model_b.predict(train_df[text_features])
        
        # Model C: Naive Fusion
        model_naive = XGBRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
        model_naive.fit(train_df[naive_features], train_df[target])
        pred_naive_test = model_naive.predict(test_df[naive_features])
        
        # Gating Model
        train_df["disagreement_score"] = np.abs(pred_a_train - pred_b_train)
        test_df["disagreement_score"] = np.abs(pred_a_test - pred_b_test)
        
        train_df["pred_sensor"] = pred_a_train
        train_df["pred_text"] = pred_b_train
        test_df["pred_sensor"] = pred_a_test
        test_df["pred_text"] = pred_b_test
        
        gating_features = ["pred_sensor", "pred_text", "disagreement_score", "recency_hours"]
        model_gating = XGBRegressor(**gating_params)
        model_gating.fit(train_df[gating_features], train_df[target])
        pred_gated_test = model_gating.predict(test_df[gating_features])
        
        # Ablation Model (No disagreement score)
        ablation_features = ["pred_sensor", "pred_text", "recency_hours"]
        model_ablation = XGBRegressor(**gating_params)
        model_ablation.fit(train_df[ablation_features], train_df[target])
        pred_ablation_test = model_ablation.predict(test_df[ablation_features])
        
        # Metrics
        results["Sensor"].append(np.sqrt(mean_squared_error(test_df[target], pred_a_test)))
        results["Text"].append(np.sqrt(mean_squared_error(test_df[target], pred_b_test)))
        results["Naive"].append(np.sqrt(mean_squared_error(test_df[target], pred_naive_test)))
        results["Gated"].append(np.sqrt(mean_squared_error(test_df[target], pred_gated_test)))
        results["Ablation"].append(np.sqrt(mean_squared_error(test_df[target], pred_ablation_test)))
        
        print(f"Sensor RMSE:   {results['Sensor'][-1]:.3f}")
        print(f"Text RMSE:     {results['Text'][-1]:.3f}")
        print(f"Naive RMSE:    {results['Naive'][-1]:.3f}")
        print(f"Gated RMSE:    {results['Gated'][-1]:.3f}")
        print(f"Ablation RMSE: {results['Ablation'][-1]:.3f}")
        
        if fold == 5:
            last_naive_model = model_naive
            last_gated_model = model_gating
            last_sensor_model = model_a
            last_text_model = model_b
            last_test_df = test_df
            last_gating_features = gating_features
            last_naive_features = naive_features
            
        fold += 1

    print("\n--- Summary across 5 Folds ---")
    for k, v in results.items():
        print(f"{k:8s} Mean RMSE: {np.mean(v):.3f} (std: {np.std(v):.3f})")
        
    print("\n--- Wilcoxon Signed-Rank Test ---")
    # Paired Wilcoxon test comparing gated fusion vs. naive fusion on the 5 folds' RMSE metrics
    try:
        w_stat, p_val = wilcoxon(results["Naive"], results["Gated"])
        print(f"Naive vs Gated across 5 folds: W-statistic={w_stat}, p-value={p_val:.4f}")
        if p_val < 0.05:
            print("Significant difference between Naive and Gated fusion metrics (p < 0.05)!")
        else:
            print("No significant difference across the 5 fold metrics (common for N=5, p > 0.05).")
    except Exception as e:
        print("Could not run Wilcoxon test:", str(e))

    print("\n--- Inference Latency Test (on fold 5 test set) ---")
    n_samples = len(last_test_df)
    
    # Measure latency for naive
    start_time = time.time()
    _ = last_naive_model.predict(last_test_df[last_naive_features])
    naive_time = (time.time() - start_time) * 1000 # in ms
    
    # Measure latency for gated
    start_time = time.time()
    pred_s = last_sensor_model.predict(last_test_df[sensor_features])
    pred_t = last_text_model.predict(last_test_df[text_features])
    dis_score = np.abs(pred_s - pred_t)
    
    g_input = pd.DataFrame({
        "pred_sensor": pred_s,
        "pred_text": pred_t,
        "disagreement_score": dis_score,
        "recency_hours": last_test_df["recency_hours"].values
    })
    _ = last_gated_model.predict(g_input)
    gated_time = (time.time() - start_time) * 1000
    
    print(f"Rows predicted: {n_samples}")
    print(f"Naive Fusion Latency: {naive_time:.2f} ms")
    print(f"Gated Fusion Latency: {gated_time:.2f} ms")
    print(f"Difference: {gated_time - naive_time:.2f} ms")

if __name__ == "__main__":
    evaluate_phase4()
