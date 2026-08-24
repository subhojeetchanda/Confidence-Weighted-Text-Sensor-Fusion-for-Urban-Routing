let map = L.map('map').setView([28.6139, 77.2090], 12);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO'
}).addTo(map);

let routeLayers = [];

async function calculateRoutes() {
    const origin = document.getElementById('origin').value.split(',');
    const dest = document.getElementById('dest').value.split(',');
    const activity = document.getElementById('activity').value;
    
    document.getElementById('results').innerHTML = '<p>Calculating...</p>';
    
    routeLayers.forEach(l => map.removeLayer(l));
    routeLayers = [];
    
    const reqBody = {
        start_lat: parseFloat(origin[0]),
        start_lng: parseFloat(origin[1]),
        end_lat: parseFloat(dest[0]),
        end_lng: parseFloat(dest[1]),
        activity: activity
    };
    
    const res = await fetch('/api/routes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody)
    });
    
    const data = await res.json();
    let html = '';
    
    let minDoseIdx = 0;
    let minDurIdx = 0;
    
    data.routes.forEach((r, idx) => {
        if (r.total_dose < data.routes[minDoseIdx].total_dose) minDoseIdx = idx;
        if (r.total_duration < data.routes[minDurIdx].total_duration) minDurIdx = idx;
    });
    
    data.routes.forEach((route, idx) => {
        let badges = [];
        if (idx === minDoseIdx) badges.push('<span class="badge badge-lowest">Lowest Exposure</span>');
        if (idx === minDurIdx) badges.push('<span class="badge badge-fastest">Fastest</span>');
        
        html += `
            <div class="route-card">
                <h3>Route ${idx + 1} ${badges.join(' ')}</h3>
                <p>Time: ${Math.round(route.total_duration / 60)} mins</p>
                <p>Dist: ${(route.total_distance / 1000).toFixed(1)} km</p>
                <p>Total Dose: <b>${route.total_dose.toFixed(1)} µg</b></p>
            </div>
        `;
        
        route.segments.forEach(seg => {
            const c = Math.min(1, seg.concentration / 300); // 300 µg/m³ is very hazardous
            const r = Math.round(255 * c);
            const g = Math.round(255 * (1 - c));
            const color = `rgb(${r},${g},0)`;
            
            const polyline = L.polyline([
                [seg.start[1], seg.start[0]], 
                [seg.end[1], seg.end[0]]
            ], { color: color, weight: 6, opacity: 0.8 }).addTo(map);
            
            // Add tooltip with concentration
            polyline.bindTooltip(`Conc: ${seg.concentration.toFixed(1)} µg/m³<br>Dose: ${seg.dose.toFixed(1)} µg`);
            routeLayers.push(polyline);
        });
    });
    
    document.getElementById('results').innerHTML = html;
    
    if (routeLayers.length > 0) {
        const group = new L.featureGroup(routeLayers);
        map.fitBounds(group.getBounds(), {padding: [50, 50]});
    }
}
