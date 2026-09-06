from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .serializers import RouteRequestSerializer
from .services.routing_service import get_osrm_route
from .services.fuel_optimizer import optimize_fuel_stops
from .models import FuelStation

class RouteOptimizationView(APIView):
    def get(self, request):
        # Query all unique city/state combinations from the imported CSV
        locations = FuelStation.objects.values_list('city', 'state').distinct().order_by('state', 'city')
        datalist_options = "".join([f'<option value="{loc[0]}, {loc[1]}">\n' for loc in locations])

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Fuel Route Optimizer</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <style>
                body { font-family: sans-serif; margin: 20px; background-color: #f4f6f9;}
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .controls { margin-bottom: 20px; display: flex; align-items: flex-end; gap: 15px; flex-wrap: wrap; }
                .input-group { display: flex; flex-direction: column; }
                .input-group label { font-size: 12px; font-weight: bold; color: #555; margin-bottom: 5px; text-transform: uppercase; }
                input { padding: 10px; width: 240px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
                button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; height: 39px;}
                button:hover { background: #0056b3; }
                
                /* Dashboard Summary Boxes */
                .dashboard { display: flex; gap: 15px; margin-top: 20px; flex-wrap: wrap; }
                .stat-box { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; flex: 1; min-width: 160px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
                .stat-box h4 { margin: 0 0 10px 0; color: #6c757d; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
                .stat-box p { margin: 0; font-size: 22px; font-weight: bold; color: #343a40; }
                .stat-box .route-text { font-size: 14px; color: #007bff; }
                
                #map { height: 500px; width: 100%; border-radius: 8px; border: 1px solid #ccc; margin-top: 15px; }
                pre { background: #f8f9fa; padding: 15px; border-radius: 5px; max-height: 200px; overflow: auto; border: 1px solid #eee; margin-top: 20px;}
                
                .fuel-marker { display: flex; align-items: center; justify-content: center; color: white; border-radius: 50%; font-weight: bold; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5); }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Fuel Route Optimizer</h2>
                
                <datalist id="us_cities">
                    DATALIST_PLACEHOLDER
                </datalist>

                <div class="controls">
                    <div class="input-group">
                        <label for="origin">Starting Location</label>
                        <input type="text" id="origin" list="us_cities" value="Chicago, IL" placeholder="Search Origin...">
                    </div>
                    <div class="input-group">
                        <label for="destination">Destination</label>
                        <input type="text" id="destination" list="us_cities" value="Dallas, TX" placeholder="Search Destination...">
                    </div>
                    <button onclick="calculate()">Find Route & Fuel Stops</button>
                    <span id="loading" style="display:none; font-weight: bold; color: #007bff;">Calculating route...</span>
                </div>
                
                <div id="map"></div>

                <!-- Dashboard Summary UI -->
                <div id="dashboard" class="dashboard" style="display: none;">
                    <div class="stat-box">
                        <h4>Route</h4>
                        <p id="sumRoute" class="route-text">---</p>
                    </div>
                    <div class="stat-box">
                        <h4>Total Distance</h4>
                        <p id="sumDistance">---</p>
                    </div>
                    <div class="stat-box">
                        <h4>Fuel Needed</h4>
                        <p id="sumFuel">---</p>
                    </div>
                    <div class="stat-box">
                        <h4>Total Fuel Cost</h4>
                        <p id="sumCost">---</p>
                    </div>
                    <div class="stat-box">
                        <h4>Vehicle Economy</h4>
                        <p id="sumMPG">---</p>
                    </div>
                </div>

                <h4 style="margin-top: 30px; color: #666;">Raw API JSON Response</h4>
                <pre id="result">Awaiting route calculation...</pre>
            </div>

            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script>
                const map = L.map('map').setView([39.8283, -98.5795], 4);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors'
                }).addTo(map);

                let routeLayer = null;
                let mapMarkers = [];

                function getBearing(lat1, lon1, lat2, lon2) {
                    const rad = Math.PI / 180;
                    const dLon = (lon2 - lon1) * rad;
                    lat1 = lat1 * rad;
                    lat2 = lat2 * rad;
                    const y = Math.sin(dLon) * Math.cos(lat2);
                    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
                    let brng = Math.atan2(y, x) * (180 / Math.PI);
                    return (brng + 360) % 360;
                }

                const destIcon = L.divIcon({
                    className: 'custom-icon',
                    html: `<svg style="filter: drop-shadow(0px 3px 3px rgba(0,0,0,0.4));" width="28" height="40" viewBox="0 0 384 512" xmlns="http://www.w3.org/2000/svg">
                             <path fill="#EA4335" d="M384 192c0 87.4-117 243-168.3 307.2c-12.3 15.3-35.1 15.3-47.4 0C117 435 0 279.4 0 192C0 86 86 0 192 0S384 86 384 192z"/>
                             <circle cx="192" cy="192" r="70" fill="white"/>
                           </svg>`,
                    iconSize: [28, 40],
                    iconAnchor: [14, 40],
                    popupAnchor: [0, -40]
                });

                function createFuelIcon() {
                    return L.divIcon({
                        className: 'custom-icon',
                        html: `<div class="fuel-marker" style="background:#ff9800; width:20px; height:20px; font-size:10px;">⛽</div>`,
                        iconSize: [20, 20],
                        iconAnchor: [10, 10],
                        popupAnchor: [0, -10]
                    });
                }

                async function calculate() {
                    const origin = document.getElementById('origin').value;
                    const destination = document.getElementById('destination').value;
                    const loading = document.getElementById('loading');
                    const result = document.getElementById('result');
                    const dashboard = document.getElementById('dashboard');

                    loading.style.display = 'inline';
                    dashboard.style.display = 'none';
                    result.textContent = 'Processing...';

                    if (routeLayer) map.removeLayer(routeLayer);
                    mapMarkers.forEach(marker => map.removeLayer(marker));
                    mapMarkers = [];

                    try {
                        const response = await fetch('/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ origin, destination })
                        });
                        const data = await response.json();
                        result.textContent = JSON.stringify(data, null, 2);

                        if (response.ok && data.route && data.route.geometry) {
                            // Populate Dashboard
                            dashboard.style.display = 'flex';
                            document.getElementById('sumRoute').innerHTML = `<b>${data.origin}</b><br>➔<br><b>${data.destination}</b>`;
                            document.getElementById('sumDistance').textContent = `${data.route.distance_miles} mi`;
                            document.getElementById('sumFuel').textContent = `${data.fuel.gallons_used} gal`;
                            document.getElementById('sumCost').textContent = `$${data.fuel.estimated_cost}`;
                            document.getElementById('sumMPG').textContent = `${data.vehicle.fuel_economy_mpg} MPG`;

                            // Map Drawing
                            const latLngs = data.route.geometry.map(coord => [coord[1], coord[0]]);
                            routeLayer = L.polyline(latLngs, { color: '#0066cc', weight: 5, opacity: 0.85 }).addTo(map);
                            map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });

                            const pt1 = latLngs[0];
                            const pt2 = latLngs.length > 5 ? latLngs[5] : latLngs[latLngs.length - 1];
                            const bearing = getBearing(pt1[0], pt1[1], pt2[0], pt2[1]);

                            const startIcon = L.divIcon({
                                className: 'custom-icon',
                                html: `<svg style="filter: drop-shadow(0px 3px 3px rgba(0,0,0,0.4)); transform: rotate(${bearing}deg);" width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
                                         <path d="M16 2 L28 28 L16 22 L4 28 Z" fill="#4285F4" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>
                                       </svg>`,
                                iconSize: [32, 32],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            });

                            const startMarker = L.marker(latLngs[0], { icon: startIcon })
                                .bindPopup(`<b>Start Location:</b><br>${data.origin}`)
                                .addTo(map);
                            mapMarkers.push(startMarker);

                            const endMarker = L.marker(latLngs[latLngs.length - 1], { icon: destIcon })
                                .bindPopup(`<b>Destination:</b><br>${data.destination}`)
                                .addTo(map);
                            mapMarkers.push(endMarker);

                            data.stops.forEach((stop, index) => {
                                const fuelMarker = L.marker([stop.latitude, stop.longitude], { icon: createFuelIcon() })
                                    .bindPopup(`<b>Stop #${index + 1}: ${stop.name}</b><br>${stop.city}, ${stop.state}<br><b>Price:</b> $${stop.retail_price}/gal<br><b>Refuel:</b> ${stop.gallons} gal ($${stop.estimated_cost})<br><b>Distance:</b> ${stop.distance_from_start_miles} miles from start`)
                                    .addTo(map);
                                mapMarkers.push(fuelMarker);
                            });
                        }
                    } catch (err) {
                        result.textContent = 'Error connecting to API.';
                    } finally {
                        loading.style.display = 'none';
                    }
                }
            </script>
        </body>
        </html>
        """
        html = html.replace("DATALIST_PLACEHOLDER", datalist_options)
        return HttpResponse(html)

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            origin = serializer.validated_data['origin']
            destination = serializer.validated_data['destination']
            
            route_data = get_osrm_route(origin, destination)
            fuel_plan = optimize_fuel_stops(route_data)
            
            response_data = {
                "origin": origin,
                "destination": destination,
                "route": {
                    "distance_miles": round(route_data['distance_miles'], 2),
                    "duration_hours": round(route_data['duration_hours'], 2),
                    "geometry": route_data['geometry']
                },
                "vehicle": {
                    "max_range_miles": 500,
                    "fuel_economy_mpg": 10
                },
                "fuel": {
                    "gallons_used": fuel_plan['total_gallons'],
                    "estimated_cost": fuel_plan['total_cost']
                },
                "stops": fuel_plan['stops']
            }
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)