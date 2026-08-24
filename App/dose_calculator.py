import sqlite3
import pandas as pd
import numpy as np
import joblib
from math import radians, cos, sin, asin, sqrt

DB_PATH = "../Dataset/delhi_aqi.db"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

class DoseCalculator:
    def __init__(self):
        # Load zones
        conn = sqlite3.connect(DB_PATH)
        self.zones = pd.read_sql_query("SELECT zone_id, latitude, longitude FROM zones", conn)
        conn.close()
        
    def find_nearest_zone(self, lat, lng):
        min_dist = float('inf')
        nearest_zone = None
        for _, row in self.zones.iterrows():
            dist = haversine(lat, lng, row['latitude'], row['longitude'])
            if dist < min_dist:
                min_dist = dist
                nearest_zone = int(row['zone_id'])
        return nearest_zone
    
    def get_concentration(self, zone_id):
        # Get the most recent PM2.5 value for this zone to act as the current concentration
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT pm25_value FROM alignment_table WHERE zone_id = {zone_id} ORDER BY timestamp_hour DESC LIMIT 1", conn)
        conn.close()
        
        if len(df) > 0:
            return float(df.iloc[0]['pm25_value'])
        else:
            return 50.0 + (zone_id * 5) % 100 # Fallback

    def calculate_dose(self, distance_m, duration_s, concentration, activity="walking"):
        # activity_multiplier: walking = 1.0, biking = 2.0 (breathing volume)
        multiplier = 2.0 if activity == "biking" else 1.0
        time_hours = duration_s / 3600.0
        dose = concentration * time_hours * multiplier
        return dose
