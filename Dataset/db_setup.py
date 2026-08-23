import sqlite3

DB_PATH = "delhi_aqi.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Monitoring Station Zones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS zones (
        zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        openaq_location_id INTEGER UNIQUE NOT NULL
    )
    """)

    # 2. Hourly Sensor Measurements
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        pm25_value REAL NOT NULL,
        sensor_id INTEGER NOT NULL,
        UNIQUE(zone_id, timestamp),
        FOREIGN KEY(zone_id) REFERENCES zones(zone_id)
    )
    """)

    # 3. Text Mentions (News / Advisories)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS text_mentions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        published_at TEXT NOT NULL,
        title TEXT NOT NULL,
        clean_text TEXT NOT NULL,
        source_url TEXT UNIQUE NOT NULL,
        assigned_zone_id INTEGER,
        FOREIGN KEY(assigned_zone_id) REFERENCES zones(zone_id)
    )
    """)

    # 4. Geotemporal Alignment Table (Training Data)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alignment_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_id INTEGER NOT NULL,
        timestamp_hour TEXT NOT NULL,
        pm25_value REAL NOT NULL,
        aqi_category TEXT NOT NULL,
        has_text INTEGER DEFAULT 0,
        recency_hours REAL DEFAULT 24.0,
        concat_text TEXT DEFAULT '',
        UNIQUE(zone_id, timestamp_hour),
        FOREIGN KEY(zone_id) REFERENCES zones(zone_id)
    )
    """)

    conn.commit()
    conn.close()
    print("SQLite schema initialized successfully in delhi_aqi.db")

if __name__ == "__main__":
    init_db()