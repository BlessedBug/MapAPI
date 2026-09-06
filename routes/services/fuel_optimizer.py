from math import cos, radians, sqrt

from .station_service import get_stations_in_corridor, haversine

MAX_RANGE_MILES = 500.0
MPG = 10.0
TANK_CAPACITY_GALLONS = MAX_RANGE_MILES / MPG
DEFAULT_INITIAL_FUEL_GALLONS = 30.0
DEFAULT_ORIGIN_FUEL_PRICE = 3.0
EPSILON = 1e-9


def calculate_polyline_distances(geometry):
    distances = [0.0]
    for i in range(1, len(geometry)):
        lon1, lat1 = geometry[i - 1]
        lon2, lat2 = geometry[i]
        distances.append(distances[-1] + haversine(lon1, lat1, lon2, lat2))
    return distances


def _snap_stations(geometry):

    stations = get_stations_in_corridor(geometry, corridor_miles=15.0).iterator(chunk_size=500)
    route_distances = calculate_polyline_distances(geometry)
    if len(geometry) < 2:
        return []

    def nearest_on_segment(lon, lat, a_lon, a_lat, b_lon, b_lat):

        scale_x = 69.172 * cos(radians(lat))
        scale_y = 69.0
        ax, ay = (a_lon - lon) * scale_x, (a_lat - lat) * scale_y
        bx, by = (b_lon - lon) * scale_x, (b_lat - lat) * scale_y
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        t = 0.0 if denom == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / denom))
        px, py = ax + t * dx, ay + t * dy
        return sqrt(px * px + py * py), t

    snapped = []
    for station in stations:
        best_distance = float("inf")
        best_route_distance = None
        for i in range(1, len(geometry)):
            a_lon, a_lat = geometry[i - 1]
            b_lon, b_lat = geometry[i]
            distance, fraction = nearest_on_segment(
                station.longitude, station.latitude, a_lon, a_lat, b_lon, b_lat
            )
            if distance < best_distance:
                best_distance = distance
                segment_length = route_distances[i] - route_distances[i - 1]
                best_route_distance = route_distances[i - 1] + fraction * segment_length
        if best_distance <= 15.0:
            snapped.append({
                "station": station,
                "route_dist": best_route_distance,
                "distance_to_route_miles": best_distance,
            })
    snapped.sort(key=lambda item: item["route_dist"])
    return snapped

def _build_nodes(snapped, total_distance, origin_price):

    by_position = {}
    for item in snapped:
        position = min(max(float(item["route_dist"]), 0.0), total_distance)
        if not (EPSILON < position < total_distance - EPSILON):
            continue
        station = item["station"]

        price = float(station.get_effective_price()) if hasattr(station, "get_effective_price") else float(station.retail_price)
        existing = by_position.get(position)
        if existing is None or price < existing["price"]:
            by_position[position] = {
                "position": position,
                "price": price,
                "station": station,
                "is_destination": False,
            }

    station_nodes = [by_position[position] for position in sorted(by_position)]

    nodes = [{
        "position": 0.0,
        "price": origin_price,
        "station": None,
        "is_destination": False,
    }]
    nodes.extend(station_nodes)
    nodes.append({
        "position": total_distance,
        "price": float("-inf"),
        "station": None,
        "is_destination": True,
    })
    return nodes, origin_price


def _first_cheaper_reachable(nodes, index):
    current = nodes[index]
    for candidate_index in range(index + 1, len(nodes)):
        candidate = nodes[candidate_index]
        if candidate["position"] - current["position"] > MAX_RANGE_MILES + EPSILON:
            break
        if candidate["price"] < current["price"]:
            return candidate_index
    return None


def _farthest_reachable(nodes, index):
    current_position = nodes[index]["position"]
    farthest = None
    for candidate_index in range(index + 1, len(nodes)):
        if nodes[candidate_index]["position"] - current_position <= MAX_RANGE_MILES + EPSILON:
            farthest = candidate_index
        else:
            break
    return farthest


def optimize_fuel_stops(
    route_data,
    *,
    origin_fuel_price=DEFAULT_ORIGIN_FUEL_PRICE,
    initial_fuel_gallons=DEFAULT_INITIAL_FUEL_GALLONS,
):
    geometry = route_data["geometry"]
    total_distance = float(route_data["distance_miles"])
    if total_distance < 0:
        raise ValueError("Route distance cannot be negative.")
    origin_fuel_price = float(origin_fuel_price)
    initial_fuel_gallons = float(initial_fuel_gallons)
    if origin_fuel_price < 0:
        raise ValueError("Origin fuel price cannot be negative.")
    if not 0.0 <= initial_fuel_gallons <= TANK_CAPACITY_GALLONS:
        raise ValueError("Initial fuel must be between 0 and 50 gallons.")
    if total_distance <= EPSILON:
        return {
            "stops": [],
            "total_gallons": 0.0,
            "total_cost": 0.0,
            "initial_fuel_cost": 0.0,
            "origin_fuel_price": round(origin_fuel_price, 3),
            "initial_fuel_gallons": round(initial_fuel_gallons, 2),
            "initial_fuel_used_gallons": 0.0,
            "gallons_purchased": 0.0,
            "effective_station_price_policy": "latest_source_row",
        }

    total_gallons_used = total_distance / MPG

    initial_fuel_used = min(initial_fuel_gallons, total_gallons_used)
    initial_fuel_cost = initial_fuel_used * origin_fuel_price

    if initial_fuel_gallons * MPG + EPSILON >= total_distance:
        return {
            "stops": [],
            "total_gallons": round(total_gallons_used, 2),
            "total_cost": round(initial_fuel_cost, 2),
            "initial_fuel_cost": round(initial_fuel_cost, 2),
            "origin_fuel_price": round(origin_fuel_price, 3),
            "initial_fuel_gallons": round(initial_fuel_gallons, 2),
            "initial_fuel_used_gallons": round(initial_fuel_used, 2),
            "gallons_purchased": 0.0,
            "effective_station_price_policy": "latest_source_row",
        }

    snapped = _snap_stations(geometry) if geometry else []
    nodes, _ = _build_nodes(snapped, total_distance, origin_fuel_price)

    fuel = initial_fuel_gallons
    total_cost = initial_fuel_cost
    total_purchased = 0.0
    purchases = []
    current_index = 0

    while current_index < len(nodes) - 1:
        cheaper_index = _first_cheaper_reachable(nodes, current_index)
        farthest_index = _farthest_reachable(nodes, current_index)
        if farthest_index is None:
            raise ValueError("No fuel station plan can satisfy the 500-mile maximum range constraint.")

        current = nodes[current_index]
        if cheaper_index is not None:
            next_index = cheaper_index
        else:
            next_index = farthest_index

        required_distance = (
            nodes[next_index]["position"] - current["position"]
        )
        required_fuel = required_distance / MPG

        buy = max(0.0, required_fuel - fuel)
        if buy > EPSILON:
            cost = buy * current["price"]
            total_cost += cost
            purchases.append({"node": current, "gallons": buy, "cost": cost})
            fuel += buy
            total_purchased += buy

        leg_distance = nodes[next_index]["position"] - current["position"]
        consumed = leg_distance / MPG
        if fuel + EPSILON < consumed:
            raise ValueError("Fuel plan became infeasible under the 500-mile constraint.")
        fuel = max(0.0, fuel - consumed)
        current_index = next_index

    stops = []
    for purchase in purchases:
        station = purchase["node"]["station"]
        if station is None:
            continue
        stops.append({
            "truckstop_id": station.truckstop_id,
            "name": station.name,
            "city": station.city,
            "state": station.state,
            "retail_price": float(purchase["node"]["price"]),
        "effective_price_policy": "latest_source_row",
            "latitude": station.latitude,
            "longitude": station.longitude,
            "distance_from_start_miles": round(purchase["node"]["position"], 2),
            "gallons": round(purchase["gallons"], 2),
            "estimated_cost": round(purchase["cost"], 2),
        })

    return {
        "stops": stops,
        "total_gallons": round(total_gallons_used, 2),
        "total_cost": round(total_cost, 2),
        "initial_fuel_cost": round(initial_fuel_cost, 2),
        "origin_fuel_price": round(origin_fuel_price, 3),
        "initial_fuel_gallons": round(initial_fuel_gallons, 2),
        "initial_fuel_used_gallons": round(initial_fuel_used, 2),
        "gallons_purchased": round(total_purchased, 2),
        "effective_station_price_policy": "latest_source_row",
    }
