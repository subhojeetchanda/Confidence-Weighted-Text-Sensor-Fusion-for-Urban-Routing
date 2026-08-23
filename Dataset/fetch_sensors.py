import requests
import sqlite3
from datetime import datetime, timedelta

API_KEY = "d0be21c422199539a94e2537f212fbfdfd6de05007117daf3fe4a89ea736b83e"
HEADERS = {"X-API-Key": API_KEY}
DB_PATH = "delhi_aqi.db"

def sync_sensors():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Step A: Discover active stations around Delhi
    loc_params = {
        "coordinates": "28.6139,77.2090",
        "radius": 25000,
        "parameters_id": 2, # PM2.5 ID
        "limit": 50
    }
    loc_req = requests.get("https://api.openaq.org/v3/locations", headers=HEADERS, params=loc_params)
    stations = loc_req.json().get("results", [])

    print(f"Found {len(stations)} potential stations near Delhi.")

    date_to = datetime.utcnow()
    date_from = date_to - timedelta(days=7)
    meas_params = {
        "datetime_from": date_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datetime_to": date_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 100
    }

    for station in stations:
        loc_id = station["id"]
        name = station["name"]
        coords = station.get("coordinates", {})
        lat = coords.get("latitude")
        lon = coords.get("longitude")

        if not lat or not lon:
            continue

        # Register Zone in SQLite
        cursor.execute("""
            INSERT OR IGNORE INTO zones (openaq_location_id, name, latitude, longitude)
            VALUES (?, ?, ?, ?)
        """, (loc_id, name, lat, lon))
        
        cursor.execute("SELECT zone_id FROM zones WHERE openaq_location_id = ?", (loc_id,))
        zone_id = cursor.fetchone()[0]

        # Fetch PM2.5 Sensor ID
        sen_req = requests.get(f"https://api.openaq.org/v3/locations/{loc_id}/sensors", headers=HEADERS)
        sensors = sen_req.json().get("results", [])
        
        pm25_sensor_id = None
        for sensor in sensors:
            if sensor.get("parameter", {}).get("id") == 2:
                pm25_sensor_id = sensor["id"]
                break

        if not pm25_sensor_id:
            continue

        # Download hourly readings
        meas_req = requests.get(
            f"https://api.openaq.org/v3/sensors/{pm25_sensor_id}/hours",
            headers=HEADERS,
            params=meas_params
        )
        measurements = meas_req.json().get("results", [])

        inserted = 0
        for m in measurements:
            timestamp = m["period"]["datetimeFrom"]["utc"]
            val = m["value"]
            if val is not None and val >= 0:
                cursor.execute("""
                    INSERT OR IGNORE INTO sensor_readings (zone_id, timestamp, pm25_value, sensor_id)
                    VALUES (?, ?, ?, ?)
                """, (zone_id, timestamp, val, pm25_sensor_id))
                if cursor.rowcount > 0:
                    inserted += 1

        if inserted > 0:
            print(f"Station [{name}] (Zone {zone_id}): Inserted {inserted} hourly PM2.5 readings.")

    conn.commit()
    conn.close()
    print("Sensor sync complete.")

if __name__ == "__main__":
    sync_sensors()