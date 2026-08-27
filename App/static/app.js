let map = L.map('map', {zoomControl: false}).setView([28.6139, 77.2090], 12);
L.control.zoom({position: 'bottomleft'}).addTo(map);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
    maxZoom: 16
}).addTo(map);

// Map Layers
let sensorsLayer = L.layerGroup().addTo(map);
let newsLayer = L.layerGroup(); 
L.control.layers({}, {
    "Sensor Stations (Mock)": sensorsLayer,
    "News Alerts (Mock)": newsLayer
}, {position: 'topright'}).addTo(map);

// Custom Legend
const legend = L.control({position: 'bottomright'});
legend.onAdd = function () {
    const div = L.DomUtil.create('div', 'map-legend');
    div.innerHTML = `
        <div class="legend-item"><div class="legend-color l-green"></div><span>≤30</span></div>
        <div class="legend-item"><div class="legend-color l-amber"></div><span>31-90</span></div>
        <div class="legend-item"><div class="legend-color l-red"></div><span>>90</span></div>
    `;
    return div;
};
legend.addTo(map);

// Mock Sensor Data
const mockSensors = [
    {lat: 28.6315, lng: 77.2167, name: 'DPCC Mandir Marg', val: 180},
    {lat: 28.5670, lng: 77.2100, name: 'CPCB Safdarjung', val: 140},
    {lat: 28.6990, lng: 77.1450, name: 'DPCC Punjabi Bagh', val: 260},
    {lat: 28.5550, lng: 77.2600, name: 'DPCC Okhla', val: 320},
];
mockSensors.forEach(s => {
    let sensorIcon = L.divIcon({className: 'marker-origin', iconSize: [12, 12], iconAnchor: [6, 6]});
    L.marker([s.lat, s.lng], {icon: sensorIcon})
      .bindPopup(`<b>${s.name}</b><br>PM2.5: ${s.val} µg/m³`).addTo(sensorsLayer);
});

// Mock News Alerts
const mockNews = [
    {lat: 28.6139, lng: 77.2090, text: 'Construction dust spike expected near Parliament.'},
    {lat: 28.6500, lng: 77.2300, text: 'Local fires reported in Old Delhi.'},
];
let alertIcon = L.divIcon({ html: '<div style="font-size:20px;">⚠️</div>', className: 'alert-icon', iconSize: [24, 24] });
mockNews.forEach(n => {
    L.marker([n.lat, n.lng], {icon: alertIcon}).bindPopup(`<b>News Alert</b><br>${n.text}`).addTo(newsLayer);
});

let routeLayers = [];
let markers = [];
window.allRouteGroups = [];

function setupAutocomplete(inputId, dropdownId, latId, lngId) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    let timeout = null;
    
    input.addEventListener('input', function() {
        clearTimeout(timeout);
        const q = this.value;
        if(q.length < 3) {
            dropdown.style.display = 'none';
            return;
        }
        timeout = setTimeout(async () => {
            const res = await fetch('/api/geocode?q=' + encodeURIComponent(q));
            const data = await res.json();
            
            dropdown.innerHTML = '';
            if(data.features && data.features.length > 0) {
                data.features.forEach(f => {
                    const div = document.createElement('div');
                    div.className = 'autocomplete-item';
                    div.textContent = f.properties.label || f.properties.name;
                    div.onclick = () => {
                        input.value = div.textContent;
                        // ORS returns [lng, lat]
                        document.getElementById(latId).value = f.geometry.coordinates[1];
                        document.getElementById(lngId).value = f.geometry.coordinates[0];
                        dropdown.style.display = 'none';
                    };
                    dropdown.appendChild(div);
                });
                dropdown.style.display = 'block';
            } else {
                dropdown.style.display = 'none';
            }
        }, 300);
    });
    
    // Close dropdown on click outside
    document.addEventListener('click', (e) => {
        if(e.target !== input) dropdown.style.display = 'none';
    });
}

setupAutocomplete('origin-input', 'origin-dropdown', 'origin-lat', 'origin-lng');
setupAutocomplete('dest-input', 'dest-dropdown', 'dest-lat', 'dest-lng');

window.highlightRoute = function(activeIndex) {
    document.querySelectorAll('.route-card').forEach((card, i) => {
        if (i === activeIndex) {
            card.classList.add('active-card');
        } else {
            card.classList.remove('active-card');
        }
    });
    
    window.allRouteGroups.forEach((groupObj, i) => {
        if (i === activeIndex) {
            groupObj.casing.eachLayer(layer => {
                layer.setStyle({ opacity: 0.8, weight: 10 });
            });
            groupObj.path.eachLayer(layer => {
                layer.setStyle({ color: layer.options.originalColor, weight: 6, opacity: 1.0 });
            });
            groupObj.casing.bringToFront();
            groupObj.path.bringToFront();
        } else {
            groupObj.casing.eachLayer(layer => {
                layer.setStyle({ opacity: 0 });
            });
            groupObj.path.eachLayer(layer => {
                layer.setStyle({ color: '#94a3b8', weight: 4, opacity: 0.5 });
            });
        }
    });
};

window.toggleDrawer = function(idx) {
    const header = document.getElementById(`explain-header-${idx}`);
    const content = document.getElementById(`explain-content-${idx}`);
    if (header.classList.contains('open')) {
        header.classList.remove('open');
        content.classList.remove('open');
    } else {
        header.classList.add('open');
        content.classList.add('open');
    }
};

async function calculateRoutes() {
    const originLat = document.getElementById('origin-lat').value;
    const originLng = document.getElementById('origin-lng').value;
    const destLat = document.getElementById('dest-lat').value;
    const destLng = document.getElementById('dest-lng').value;
    const activity = document.getElementById('activity').value;
    
    document.getElementById('results').innerHTML = '<p>Calculating...</p>';
    
    window.allRouteGroups.forEach(g => {
        map.removeLayer(g.casing);
        map.removeLayer(g.path);
    });
    window.allRouteGroups = [];
    routeLayers = [];
    
    markers.forEach(m => map.removeLayer(m));
    markers = [];
    
    let originIcon = L.divIcon({className: 'marker-origin', iconSize: [16, 16], iconAnchor: [8, 8]});
    let destIcon = L.divIcon({className: 'marker-dest', iconSize: [16, 16], iconAnchor: [8, 8]});
    
    markers.push(L.marker([parseFloat(originLat), parseFloat(originLng)], {icon: originIcon}).addTo(map).bindPopup('Origin'));
    markers.push(L.marker([parseFloat(destLat), parseFloat(destLng)], {icon: destIcon}).addTo(map).bindPopup('Destination'));
    
    const reqBody = {
        start_lat: parseFloat(originLat),
        start_lng: parseFloat(originLng),
        end_lat: parseFloat(destLat),
        end_lng: parseFloat(destLng),
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
    
    let avoidedDose = 0;
    if (minDurIdx !== minDoseIdx) {
        avoidedDose = data.routes[minDurIdx].total_dose - data.routes[minDoseIdx].total_dose;
    }
    
    data.routes.forEach((route, idx) => {
        let badges = [];
        let isActive = idx === minDoseIdx;
        
        if (isActive) badges.push('<span class="badge badge-lowest">🌿 Lowest Exposure</span>');
        if (idx === minDurIdx) badges.push('<span class="badge badge-fastest">⚡️ Fastest</span>');
        
        let doseClass = 'dose-med';
        if (route.total_dose < 100) doseClass = 'dose-low';
        else if (route.total_dose > 250) doseClass = 'dose-high';
        
        let avoidedHtml = '';
        if (isActive && avoidedDose > 0) {
            avoidedHtml = `<div class="avoided-metric">🍃 You avoided ${avoidedDose.toFixed(1)} µg of PM2.5 exposure</div>`;
        }
        
        html += `
            <div class="route-card ${isActive ? 'active-card' : ''}" id="route-card-${idx}" onclick="highlightRoute(${idx})" onmouseenter="highlightRoute(${idx})">
                <div class="route-card-header">
                    <h3>Route ${idx + 1}</h3>
                    <div class="badge-container">${badges.join(' ')}</div>
                </div>
                <div class="route-metrics">
                    <span class="metric-primary ${doseClass}">${route.total_dose.toFixed(1)} µg</span>
                    <div class="metric-secondary">
                        <span>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                            ${Math.round(route.total_duration / 60)} mins
                        </span>
                        <span>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                            ${(route.total_distance / 1000).toFixed(1)} km
                        </span>
                    </div>
                    ${avoidedHtml}
                </div>
                
                <div class="explain-drawer" onclick="event.stopPropagation()">
                    <div class="explain-header" id="explain-header-${idx}" onclick="toggleDrawer(${idx})">
                        <span>Why this route? (Model Gating)</span>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div class="explain-content" id="explain-content-${idx}">
                        <div class="explain-item">
                            <span class="explain-icon">📡</span>
                            <span><b>Sensor:</b> ~${Math.round(route.segments[0].concentration)} µg/m³</span>
                        </div>
                        <div class="explain-item">
                            <span class="explain-icon">📰</span>
                            <span><b>Signal:</b> Mock text advisory active</span>
                        </div>
                        <div class="explain-item">
                            <span class="explain-icon">⚖️</span>
                            <span><b>Gate:</b> ${isActive ? 'Upweighted 1.35x' : 'Sensor Driven'}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        let segmentPolylines = [];
        let casingPolylines = [];
        
        route.segments.forEach(seg => {
            let color = '#10B981'; // Green (<= 30)
            if (seg.concentration > 90) color = '#EF4444'; // Red
            else if (seg.concentration > 30) color = '#F59E0B'; // Amber
            
            const weight = isActive ? 6 : 4;
            const opacity = isActive ? 1.0 : 0.5;
            const routeColor = isActive ? color : '#94a3b8';
            
            const latlngs = [
                [seg.start[1], seg.start[0]], 
                [seg.end[1], seg.end[0]]
            ];
            
            const casing = L.polyline(latlngs, {
                color: 'rgba(0,0,0,0.15)',
                weight: isActive ? 10 : 0,
                opacity: isActive ? 0.8 : 0,
                lineCap: 'round',
                lineJoin: 'round'
            });
            
            const polyline = L.polyline(latlngs, { 
                color: routeColor, 
                weight: weight, 
                opacity: opacity,
                lineCap: 'round',
                lineJoin: 'round',
                originalColor: color 
            });
            
            polyline.bindTooltip(`Conc: ${seg.concentration.toFixed(1)} µg/m³<br>Dose: ${seg.dose.toFixed(1)} µg`, {
                sticky: true,
                direction: 'top',
                className: 'custom-tooltip'
            });
            
            segmentPolylines.push(polyline);
            casingPolylines.push(casing);
            routeLayers.push(polyline);
            routeLayers.push(casing);
        });
        
        const pathGroup = L.featureGroup(segmentPolylines).addTo(map);
        const casingGroup = L.featureGroup(casingPolylines).addTo(map);
        casingGroup.bringToBack();
        
        window.allRouteGroups.push({ path: pathGroup, casing: casingGroup });
        
        pathGroup.on('mouseover', () => highlightRoute(idx));
    });
    
    document.getElementById('results').innerHTML = html;
    
    if (routeLayers.length > 0) {
        const group = new L.featureGroup(routeLayers);
        map.fitBounds(group.getBounds(), {padding: [50, 50]});
    }
}
