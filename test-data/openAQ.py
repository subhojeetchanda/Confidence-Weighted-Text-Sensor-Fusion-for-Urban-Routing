import requests
from datetime import datetime, timedelta

API_KEY = "d0be21c422199539a94e2537f212fbfdfd6de05007117daf3fe4a89ea736b83e"
HEADERS = {"X-API-Key": API_KEY}

def fetch_hourly_data():
    print("1. Searching for active stations in Delhi...")
    loc_params = {
        "coordinates": "28.6139,77.2090",
        "radius": 25000,
        "parameters_id": 2, # PM2.5
        "limit": 20
    }
    loc_req = requests.get("https://api.openaq.org/v3/locations", headers=HEADERS, params=loc_params)
    stations = loc_req.json().get("results", [])

    date_to = datetime.utcnow()
    date_from = date_to - timedelta(days=7)
    
    meas_params = {
        "datetime_from": date_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datetime_to": date_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 24
    }

    active_station_found = False

    for station in stations:
        location_id = station["id"]
        station_name = station["name"]
        
        # Get sensor ID for PM2.5
        sen_req = requests.get(f"https://api.openaq.org/v3/locations/{location_id}/sensors", headers=HEADERS)
        sensors = sen_req.json().get("results", [])
        
        pm25_sensor_id = None
        for sensor in sensors:
            if sensor.get("parameter", {}).get("id") == 2:
                pm25_sensor_id = sensor["id"]
                break
                
        if not pm25_sensor_id:
            continue

        # Fetch measurements
        meas_req = requests.get(f"https://api.openaq.org/v3/sensors/{pm25_sensor_id}/hours", headers=HEADERS, params=meas_params)
        measurements = meas_req.json().get("results", [])
        
        if len(measurements) > 0:
            # FIX: Sort measurements in descending order by timestamp so the newest comes first
            measurements.sort(key=lambda x: x["period"]["datetimeFrom"]["utc"], reverse=True)
            
            print(f"-> Active Station Found: {station_name} (Location ID: {location_id})")
            print(f"-> PM2.5 Sensor ID: {pm25_sensor_id}")
            print(f"-> Success! Downloaded {len(measurements)} hourly readings.\n")
            print("Most recent 5 hourly readings:")
            for m in measurements[:5]:
                timestamp = m["period"]["datetimeFrom"]["utc"]
                value = m["value"]
                print(f"   Time: {timestamp} | PM2.5: {value} µg/m³")
            active_station_found = True
            break

    if not active_station_found:
        print("No stations in Delhi returned hourly measurements for the past 7 days.")

if __name__ == "__main__":
    fetch_hourly_data()