import sqlite3
import feedparser
from urllib.parse import quote
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

DB_PATH = "delhi_aqi.db"


def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def sync_news():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT zone_id FROM zones")
    zones = cursor.fetchall()
    if not zones:
        print("No zones in DB yet. Run fetch_sensors.py first!")
        return

    query = quote(
        '("Delhi" OR "NCR") '
        '("air quality" OR "AQI" OR "smog" OR "stubble burning" '
        'OR "particulate matter" OR "air pollution" OR "PM2.5")'
    )
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    feed = feedparser.parse(url)
    entries = feed.entries

    inserted = 0
    for entry in entries:
        title = entry.get("title", "")
        summary_raw = entry.get("summary", "")
        link = entry.get("link", entry.get("id", ""))
        pub_date_str = entry.get("published", entry.get("updated", ""))

        try:
            dt = parsedate_to_datetime(pub_date_str)
            dt_utc = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            dt_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        clean_summary = clean_html(summary_raw)
        full_text = f"{title}. {clean_summary}"

        # FIX: no fake per-zone assignment. Delhi AQI news is almost always
        # citywide ("Delhi's AQI hits X"), not neighborhood-specific, so we
        # store NULL here and treat every mention as applying to ALL zones.
        # build_alignment.py has been updated to reflect this deliberately
        # instead of accidentally (it previously ignored zone matching anyway).
        # If you later want real per-zone geocoding, this is the field to
        # populate with nearest-neighbor lat/long matching against a
        # location mentioned in the article text.
        assigned_zone_id = None

        cursor.execute("""
            INSERT OR IGNORE INTO text_mentions 
            (published_at, title, clean_text, source_url, assigned_zone_id)
            VALUES (?, ?, ?, ?, ?)
        """, (dt_utc, title, full_text, link, assigned_zone_id))

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()
    print(f"News sync complete: Inserted {inserted} new articles (treated as citywide).")


if __name__ == "__main__":
    sync_news()