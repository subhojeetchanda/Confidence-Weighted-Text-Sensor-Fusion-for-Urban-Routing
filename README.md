# Confidence-Weighted Text-Sensor Fusion for Urban Routing

This project builds a multimodal fusion pipeline to improve short-horizon PM2.5 air quality predictions, applied specifically to an urban route re-ranking system. 

## In Plain Terms
Think of it like this: your phone's map app tells you the fastest way to walk somewhere, but it has no idea if one route takes you past a construction site kicking up dust, or through an area with wildfire smoke drifting in. This project builds a smarter version that actually thinks about air quality.

It combines two kinds of information:
- **Sensor readings** — actual air quality measurements from monitoring stations around the city (like a thermometer, but for pollution).
- **Text mentions** — news articles and city advisories that might say "smoke advisory in effect" before the sensors even catch the spike, because sensors are only in a few spots but news can mention things happening anywhere.

The clever part: instead of just dumping both types of information into one model and hoping it figures things out, this project builds a system that specifically asks: *"Does this news mention agree or disagree with what the sensors are saying right now?"* 

When they disagree, that's the interesting case — it usually means something is changing that the sensors haven't caught yet. When they agree, the text isn't telling you anything new, so it gets less weight.

Finally, instead of just saying "this area is unhealthy," the system calculates something much more useful: **how much bad air you'd actually breathe in** if you walked (or biked) a specific route. A fast 10-minute walk through a bad zone can result in less total exposure than a slow 25-minute walk through a moderately polluted one!

---

## Technical Overview & The Gating Mechanism

Traditional routing applications give you the fastest path, but lack real-time environmental context. This system intelligently fuses hard sensor time-series data with unstructured text to predict localized air quality anomalies.

Instead of naively concatenating sensor data and text vectors, this project employs a **Confidence-Weighted Fusion (Meta-Learner)**. 

1. A **Sensor Model** (XGBoost) predicts the PM2.5 based on continuous tabular features (rolling averages, rate-of-change, lag, time-of-day).
2. A **Text Model** predicts PM2.5 based on sparse, irregularly-timed unstructured text (advisories/news) using TF-IDF (or MiniLM) embeddings.
3. A **Gating Model** dynamically weighs the two opinions by evaluating their *Disagreement Score* and the *recency* of the text. Instead of static concatenation, the meta-learner dynamically learns to trust the text more when it diverges from established sensor trends.

Finally, a **Dose Layer** calculates human exposure based on the predicted concentration: 
`dose = concentration * time_in_segment * activity_multiplier`

---

## Project Structure

* **`/Dataset`**: Data engineering pipeline.
  * `fetch_sensors.py` & `openAQ.py`: Scripts to pull historical and live PM2.5 readings.
  * `fetch_news.py` & `news.py`: Scrapes and geocodes RSS feeds for municipal advisories.
  * `build_alignment.py`: Merges asynchronous sensor series and sparse text events into zone-hour buckets (`delhi_aqi.db`).
* **`/Model`**: Machine Learning pipeline.
  * `train_baselines.py`: Trains the isolated Sensor Model, Text Model, and the Naive Fusion Baseline.
  * `train_gating_model.py`: Uses Optuna to tune and train the novel Gating meta-learner.
  * `evaluate_models.py`: Runs a time-based rolling 5-fold cross-validation, performing Wilcoxon signed-rank tests and inference latency comparisons.
* **`/App`**: Full-stack application.
  * `main.py`: FastAPI backend.
  * `dose_calculator.py`: Executes real-time predictions and maps coordinates to zones using the Haversine formula.
  * `routing.py`: Interfaces with the OpenRouteService API for fetching candidate routes.
  * `/static`: Vanilla HTML/CSS/JS frontend utilizing Leaflet.js for interactive mapping.

---

## Setup & Installation

**1. Clone the repository and navigate to the folder:**
```bash
git clone https://github.com/subhojeetchanda/Confidence-Weighted-Text-Sensor-Fusion-for-Urban-Routing.git
cd Confidence-Weighted-Text-Sensor-Fusion-for-Urban-Routing
```

**2. Install Dependencies:**
```bash
pip install pandas numpy scikit-learn xgboost optuna scipy fastapi uvicorn openrouteservice
```

*(Note: Ensure you have `sqlite3` available, though it comes pre-installed with most Python distributions).*

---

## Running the Application

To run the interactive map UI and test the dose calculation engine:

1. **Start the Backend**:
   ```bash
   cd App
   python main.py
   ```
2. **Open the App**:
   Navigate to [http://localhost:8000](http://localhost:8000) in your web browser. Enter an origin and destination coordinate pair in Delhi, select your activity (Walking/Biking), and the map will render routes dynamically color-coded by the predicted PM2.5 exposure dose.
