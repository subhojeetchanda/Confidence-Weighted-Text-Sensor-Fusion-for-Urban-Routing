# import feedparser
# from urllib.parse import quote

# def check_delhi_news():
#     print("--- Checking Google News for Delhi Air Quality Alerts ---")
    
#     # FIX: Tightened query that strictly pairs terms with air quality keywords
#     query = quote('("Delhi" OR "NCR") ("air quality" OR "AQI" OR "smog" OR "stubble burning" OR "particulate matter" OR "pollution")')
    
#     url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    
#     feed = feedparser.parse(url)
#     entries = feed.entries
    
#     print(f"Found {len(entries)} relevant news entries.\n")
    
#     if len(entries) > 0:
#         print("Sample Text Mentions (First 5):")
#         for i, entry in enumerate(entries[:5]):
#             title = entry.get('title', 'No Title')
#             published = entry.get('published', entry.get('updated', 'No Date'))
            
#             summary = entry.get('summary', '')[:120].replace('\n', ' ')
            
#             print(f"{i+1}. [{published}] {title}")
#             print(f"   Summary Snippet: {summary}...\n")
#     else:
#         print("Warning: The feed returned zero entries.")

# if __name__ == "__main__":
#     check_delhi_news()


import feedparser
from urllib.parse import quote

def check_delhi_news():
    print("--- Checking Google News for Delhi Air Quality Alerts ---")

    # FIX: dropped bare "pollution" (was matching Yamuna/river/noise/plastic
    # pollution stories with zero connection to air quality). Every term now
    # is either air-quality-specific on its own, or "pollution" is paired
    # with "air" so it can't match unrelated pollution stories.
    query = quote(
        '("Delhi" OR "NCR") '
        '("air quality" OR "AQI" OR "smog" OR "stubble burning" '
        'OR "particulate matter" OR "air pollution" OR "PM2.5")'
    )

    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    feed = feedparser.parse(url)
    entries = feed.entries

    print(f"Found {len(entries)} relevant news entries.\n")

    if len(entries) > 0:
        print("Sample Text Mentions (First 5):")
        for i, entry in enumerate(entries[:5]):
            title = entry.get('title', 'No Title')
            published = entry.get('published', entry.get('updated', 'No Date'))

            summary = entry.get('summary', '')[:120].replace('\n', ' ')

            print(f"{i+1}. [{published}] {title}")
            print(f"   Summary Snippet: {summary}...\n")

        # NEW: quick self-check — how many of the results actually contain
        # an air-quality keyword in the title itself (not just wherever
        # Google's fuzzy matching decided was relevant). This is a rougher
        # but more honest signal than the raw entry count above.
        strict_terms = [
            "air quality", "aqi", "smog", "stubble burning",
            "particulate matter", "air pollution", "pm2.5",
        ]
        strict_hits = sum(
            1 for e in entries
            if any(term in e.get("title", "").lower() for term in strict_terms)
        )
        print(f"Titles containing an air-quality term: {strict_hits} / {len(entries)}")
        if strict_hits < len(entries) * 0.3:
            print("Note: low hit rate. This may be seasonal (monsoon = low AQI news volume)")
            print("rather than a query problem — worth rechecking during pollution season (Oct-Feb).")
    else:
        print("Warning: The feed returned zero entries.")


if __name__ == "__main__":
    check_delhi_news()