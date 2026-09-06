from math import radians, cos, sin, asin, sqrt
from .station_service import get_stations_in_corridor, haversine

def calculate_polyline_distances(geometry):
    distances = [0.0]
    for i in range(1, len(geometry)):
        lon1, lat1 = geometry[i - 1]
        lon2, lat2 = geometry[i]
        distances.append(distances[-1] + haversine(lon1, lat1, lon2, lat2))
    return distances

def optimize_fuel_stops(route_data):
    geometry = route_data['geometry']
    total_distance = route_data['distance_miles']
    max_range = 500.0
    mpg = 10.0

    if total_distance <= max_range:
        return {
            "stops": [],
            "total_gallons": round(total_distance / mpg, 2),
            "total_cost": 0.0
        }

    stations = list(get_stations_in_corridor(geometry))
    route_distances = calculate_polyline_distances(geometry)

    # Subsample route points if geometry is dense to eliminate math lag
    step = max(1, len(geometry) // 300)
    sampled_indices = list(range(0, len(geometry), step))
    if sampled_indices[-1] != len(geometry) - 1:
        sampled_indices.append(len(geometry) - 1)

    sampled_points = [(geometry[i][0], geometry[i][1], route_distances[i]) for i in sampled_indices]

    station_snaps = []
    # 15 miles converted roughly to degree threshold squared (~0.25 deg)
    degree_thresh_sq = (15.0 / 60.0) ** 2

    for station in stations:
        st_lon = station.longitude
        st_lat = station.latitude
        
        best_d = float('inf')
        best_route_dist = 0.0

        for lon, lat, r_dist in sampled_points:
            d_sq = (lon - st_lon) ** 2 + (lat - st_lat) ** 2
            if d_sq < degree_thresh_sq:
                exact_d = haversine(lon, lat, st_lon, st_lat)
                if exact_d < best_d:
                    best_d = exact_d
                    best_route_dist = r_dist

        if best_d <= 15.0:
            station_snaps.append({
                "station": station,
                "route_dist": best_route_dist
            })

    station_snaps.sort(key=lambda x: x['route_dist'])

    stops = []
    current_pos = 0.0
    total_cost = 0.0

    while current_pos + max_range < total_distance:
        farthest_reachable = current_pos + max_range
        reachable = [s for s in station_snaps if current_pos < s['route_dist'] <= farthest_reachable]

        if not reachable:
            raise ValueError("No fuel stations found within 500-mile range to continue route.")

        best_stop = min(reachable, key=lambda s: float(s['station'].retail_price))

        leg_distance = best_stop['route_dist'] - current_pos
        gallons = leg_distance / mpg
        cost = gallons * float(best_stop['station'].retail_price)

        stops.append({
            "truckstop_id": best_stop['station'].truckstop_id,
            "name": best_stop['station'].name,
            "city": best_stop['station'].city,
            "state": best_stop['station'].state,
            "retail_price": float(best_stop['station'].retail_price),
            "latitude": best_stop['station'].latitude,
            "longitude": best_stop['station'].longitude,
            "distance_from_start_miles": round(best_stop['route_dist'], 2),
            "gallons": round(gallons, 2),
            "estimated_cost": round(cost, 2)
        })

        total_cost += cost
        current_pos = best_stop['route_dist']

    return {
        "stops": stops,
        "total_gallons": round(total_distance / mpg, 2),
        "total_cost": round(total_cost, 2)
    }