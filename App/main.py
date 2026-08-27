from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from dose_calculator import DoseCalculator
from routing import get_routes
import math

app = FastAPI(title="Urban Routing with AQI")

app.mount("/static", StaticFiles(directory="static"), name="static")

dose_calc = DoseCalculator()

class RouteRequest(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    activity: str = "walking"

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/api/geocode")
def geocode(q: str):
    import requests
    from routing import ORS_API_KEY
    if not ORS_API_KEY:
        return {"features": [{"properties": {"label": "Mock Location (Add ORS API Key)"}, "geometry": {"coordinates": [77.2090, 28.6139]}}]}
        
    url = "https://api.openrouteservice.org/geocode/autocomplete"
    params = {
        "api_key": ORS_API_KEY,
        "text": q,
        "boundary.rect.min_lon": 76.8,
        "boundary.rect.max_lon": 77.5,
        "boundary.rect.min_lat": 28.4,
        "boundary.rect.max_lat": 28.9
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "features" not in data:
            print("ORS Geocode Error:", data)
            # Fallback mock data if API key fails or rate-limits on Railway
            if "dtu" in q.lower():
                return {"features": [{"properties": {"label": "Delhi Technological University, Delhi (Fallback)"}, "geometry": {"coordinates": [77.114162, 28.749501]}}]}
            elif "igi" in q.lower():
                return {"features": [{"properties": {"label": "IGI Airport, Delhi (Fallback)"}, "geometry": {"coordinates": [77.0867, 28.556463]}}]}
            return {"features": []}
        return data
    except Exception as e:
        print("Geocode Exception:", e)
        return {"features": []}

@app.post("/api/routes")
def calculate_routes(req: RouteRequest):
    profile = "foot-walking" if req.activity == "walking" else "cycling-regular"
    routes_geojson = get_routes(req.start_lat, req.start_lng, req.end_lat, req.end_lng, profile)
    
    response_routes = []
    
    for feature in routes_geojson.get("features", []):
        coords = feature["geometry"]["coordinates"]
        props = feature["properties"]
        
        total_dose = 0
        total_dist = props["summary"]["distance"]
        total_dur = props["summary"]["duration"]
        
        segment_results = []
        
        for i in range(len(coords) - 1):
            pt1 = coords[i]
            pt2 = coords[i+1]
            lng1, lat1 = pt1[0], pt1[1]
            lng2, lat2 = pt2[0], pt2[1]
            elev1 = pt1[2] if len(pt1) > 2 else 0.0
            elev2 = pt2[2] if len(pt2) > 2 else 0.0
            
            mid_lat = (lat1 + lat2) / 2
            mid_lng = (lng1 + lng2) / 2
            
            zone_id = dose_calc.find_nearest_zone(mid_lat, mid_lng)
            concentration = dose_calc.get_concentration(zone_id)
            
            # Simple proportional distance/time for the segment
            seg_dist = total_dist / max(1, (len(coords)-1))
            seg_dur = total_dur / max(1, (len(coords)-1))
            
            gradient = (elev2 - elev1) / seg_dist if seg_dist > 0 else 0.0
            
            dose = dose_calc.calculate_dose(seg_dist, seg_dur, concentration, req.activity, gradient)
            total_dose += dose
            
            segment_results.append({
                "start": [lng1, lat1],
                "end": [lng2, lat2],
                "concentration": concentration,
                "dose": dose,
                "zone_id": zone_id
            })
            
        response_routes.append({
            "total_distance": total_dist,
            "total_duration": total_dur,
            "total_dose": total_dose,
            "segments": segment_results,
            "geometry": feature["geometry"]
        })
        
    return {"routes": response_routes}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
