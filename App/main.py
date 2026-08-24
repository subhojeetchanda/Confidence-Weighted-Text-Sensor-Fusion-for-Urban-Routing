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
            lng1, lat1 = coords[i]
            lng2, lat2 = coords[i+1]
            
            mid_lat = (lat1 + lat2) / 2
            mid_lng = (lng1 + lng2) / 2
            
            zone_id = dose_calc.find_nearest_zone(mid_lat, mid_lng)
            concentration = dose_calc.get_concentration(zone_id)
            
            # Simple proportional distance/time for the segment
            seg_dist = total_dist / max(1, (len(coords)-1))
            seg_dur = total_dur / max(1, (len(coords)-1))
            
            dose = dose_calc.calculate_dose(seg_dist, seg_dur, concentration, req.activity)
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
