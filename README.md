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

## Key Application Features (Latest Updates)

- 🌍 **Elevation-Aware Dose Calculation**: Parses 3D coordinates (Z-axis) from OpenRouteService. Modifies the physiological `activity_multiplier` based on gradient slope, accurately simulating heavier breathing volume when biking or walking uphill.
- 🍃 **Gamified "Exposure Avoided" UI**: Automatically calculates the difference in PM2.5 dose between the fastest route and the lowest exposure route, injecting a vibrant green badge to positively reinforce healthy routing choices.
- 🗺️ **Dynamic Heatmap Polylines**: Renders multi-segment map polylines dynamically colored based on local PM2.5 concentrations (🟢 ≤30, 🟡 31-90, 🔴 >90).
- 💎 **World-Class Glassmorphic UI**: Production-grade aesthetic inspired by top-tier mobility apps (Uber, Apple Maps). Features frosted-glass sidebars (`backdrop-filter`), segmented pill controls, custom SVG glowing markers, and buttery-smooth JavaScript accordions for explainability.

---

## Project Structure

* **`/Dataset`**: Data engineering pipeline.
  * `fetch_sensors.py` & `openAQ.py`: Scripts to pull historical and live PM2.5 readings.
  * `fetch_news.py` & `news.py`: Scrapes and geocodes RSS feeds for municipal advisories.
  * `build_alignment.py`: Merges asynchronous sensor series and sparse text events into zone-hour buckets (`delhi_aqi.db`).
* **`/Model`**: Machine Learning pipeline.
  * `train_baselines.py`: Trains the isolated Sensor Model, Text Model, and the Naive Fusion Baseline.
  * `train_gating_model.py`: Uses Optuna to tune and train the novel Gating meta-learner.
  * `evaluate_models.py`: Runs a time-based rolling 5-fold cross-validation.
* **`/App`**: Full-stack application.
  * `main.py`: FastAPI backend.
  * `dose_calculator.py`: Executes real-time predictions and maps coordinates to zones using the Haversine formula, adjusted by elevation gradient.
  * `routing.py`: Interfaces with the OpenRouteService API for fetching candidate routes.
  * `/static`: Vanilla HTML/CSS/JS frontend utilizing Leaflet.js for interactive mapping.

---

## Setup & Running the Application

The application is containerized with Docker for seamless execution, removing the need to manually install heavy ML dependencies just to run the web UI.

**1. Clone the repository:**
```bash
git clone https://github.com/subhojeetchanda/Confidence-Weighted-Text-Sensor-Fusion-for-Urban-Routing.git
cd Confidence-Weighted-Text-Sensor-Fusion-for-Urban-Routing/cap-project
```

**2. Set your OpenRouteService API Key:**
Get a free key from [OpenRouteService](https://openrouteservice.org/).
```bash
export ORS_API_KEY="your_api_key_here"
```

**3. Build and run using Docker Compose:**
```bash
docker compose up --build
```
*(To run in the background, append the `-d` flag: `docker compose up -d --build`)*

**4. Open the App:**
Navigate to [http://localhost:8000](http://localhost:8000) in your web browser. Type an origin and destination (autocomplete via Nominatim/ORS), toggle your mode of transport, and discover your healthiest route!

---

## ☁️ Cloud Deployment (Railway)

Since this project is fully Dockerized, deploying it online is incredibly simple and takes less than two minutes using [Railway](https://railway.app/):

1. **Connect GitHub:** Create a new project on Railway and select "Deploy from GitHub repo".
2. **Select Repo:** Choose your `Confidence-Weighted-Text-Sensor-Fusion-for-Urban-Routing` repository.
3. **Set the Root Directory:** Before hitting deploy, edit the settings and set the Root Directory to `/cap-project` (this is where the Dockerfile lives).
4. **Add Environment Variable:** Add a variable named `ORS_API_KEY` and paste your OpenRouteService API key (without quotes).
5. **Deploy:** Click deploy! Railway will automatically detect the Dockerfile, build the image, and assign a dynamic `PORT`. 
6. **Generate Domain:** Go to the Networking tab and click "Generate Domain" to get your live public `.up.railway.app` URL.
