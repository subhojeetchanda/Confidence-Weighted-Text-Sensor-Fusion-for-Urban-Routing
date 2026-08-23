import sqlite3
from datetime import datetime, timedelta

DB_PATH = "delhi_aqi.db"

# FIX: window is now backward-only (no peeking at news published after the
# sensor reading — that would be leakage a real deployed system could never
# have) and much tighter (48h instead of 7 days each direction). This is
# what actually gives has_text and recency_hours real, non-trivial variance
# instead of being 1 / near-0 for almost every row.
RECENCY_WINDOW_HOURS = 48

# Sentinel value used when no text mention falls inside the window at all.
# Set higher than the window itself so the model can clearly distinguish
# "no recent text" from "text right at the edge of the window."
NO_TEXT_RECENCY_SENTINEL = RECENCY_WINDOW_HOURS + 1.0


def get_aqi_category(pm25):
    """Standard CPCB / EPA PM2.5 AQI category thresholds."""
    if pm25 <= 30.0:
        return "Good"
    elif pm25 <= 60.0:
        return "Satisfactory"
    elif pm25 <= 90.0:
        return "Moderate"
    elif pm25 <= 120.0:
        return "Poor"
    elif pm25 <= 250.0:
        return "Very Poor"
    else:
        return "Severe"


def build_alignment():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT zone_id, timestamp, pm25_value FROM sensor_readings ORDER BY timestamp ASC")
    readings = cursor.fetchall()

    print(f"Aligning {len(readings)} zone-hour sensor observations...")

    for zone_id, ts_str, pm25 in readings:
        aqi_cat = get_aqi_category(pm25)

        try:
            ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        # FIX: only look backward from ts_dt, never forward.
        window_start_str = (ts_dt - timedelta(hours=RECENCY_WINDOW_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_end_str = ts_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # NOTE: deliberately not filtering by assigned_zone_id here, since
        # fetch_news.py now stores NULL for it — text mentions are treated
        # as a citywide signal shared by every zone (see fetch_news.py for
        # the reasoning). If you add real per-zone geocoding later, add
        # "AND (assigned_zone_id = ? OR assigned_zone_id IS NULL)" here.
        cursor.execute("""
            SELECT published_at, clean_text 
            FROM text_mentions 
            WHERE published_at > ? AND published_at <= ?
            ORDER BY published_at DESC
        """, (window_start_str, window_end_str))

        mentions = cursor.fetchall()

        if mentions:
            has_text = 1
            concat_text = " ".join([m[1] for m in mentions[:3]])

            latest_pub_str = mentions[0][0]
            latest_dt = datetime.fromisoformat(latest_pub_str.replace("Z", "+00:00"))
            recency_hours = round((ts_dt - latest_dt).total_seconds() / 3600.0, 2)
        else:
            has_text = 0
            concat_text = ""
            recency_hours = NO_TEXT_RECENCY_SENTINEL

        cursor.execute("""
            INSERT OR REPLACE INTO alignment_table 
            (zone_id, timestamp_hour, pm25_value, aqi_category, has_text, recency_hours, concat_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (zone_id, ts_str, pm25, aqi_cat, has_text, recency_hours, concat_text))

    conn.commit()

    cursor.execute("SELECT COUNT(*), SUM(has_text) FROM alignment_table")
    total, text_count = cursor.fetchone()
    text_count = text_count or 0
    print(f"Alignment table ready! Total zone-hours: {total} | Zone-hours with text mentions: {text_count}")
    print(f"(That should now be well under 100% — if it's still near 100%, your news table")
    print(f" may be too dense relative to the {RECENCY_WINDOW_HOURS}h window, which is worth checking.)")

    conn.close()


if __name__ == "__main__":
    build_alignment()