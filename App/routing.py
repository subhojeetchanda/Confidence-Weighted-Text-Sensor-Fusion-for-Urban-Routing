import os
import requests

ORS_API_KEY = os.environ.get("ORS_API_KEY", "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjMxZjVlN2RhNmE0MDRmMzhiMGQ1YmZhMDIwZmNhMjRjIiwiaCI6Im11cm11cjY0In0=")

def get_routes(start_lat, start_lng, end_lat, end_lng, profile="foot-walking"):
    if not ORS_API_KEY:
        return get_mock_routes(start_lat, start_lng, end_lat, end_lng)
        
    url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
    
    body = {
        "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
        "elevation": "true",
        "alternative_routes": {
            "target_count": 3
        }
    }
    
    headers = {
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, json=body, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"ORS API Error: {response.status_code} - {response.text}")
        return get_mock_routes(start_lat, start_lng, end_lat, end_lng)

def get_mock_routes(start_lat, start_lng, end_lat, end_lng):
    # Mock GeoJSON response for demonstration
    mid_lat = (start_lat + end_lat) / 2
    mid_lng = (start_lng + end_lng) / 2
    return {
        "features": [
            {
                "properties": {
                    "summary": {"distance": 2000, "duration": 1200},
                    "segments": [{"distance": 2000, "duration": 1200}]
                },
                "geometry": {
                    "coordinates": [[start_lng, start_lat], [mid_lng, start_lat], [end_lng, end_lat]]
                }
            },
            {
                "properties": {
                    "summary": {"distance": 2500, "duration": 1500},
                    "segments": [{"distance": 2500, "duration": 1500}]
                },
                "geometry": {
                    "coordinates": [[start_lng, start_lat], [start_lng, mid_lat], [end_lng, end_lat]]
                }
            }
        ]
    }
