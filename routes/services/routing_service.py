import requests

def geocode_address(location_string):
    url = f"https://nominatim.openstreetmap.org/search?q={location_string}&format=json&limit=1"
    headers = {'User-Agent': 'FuelRouteOptimizer/1.0'}
    response = requests.get(url, headers=headers).json()
    
    if not response:
        raise ValueError(f"Could not find coordinates for: {location_string}")
        
    return float(response[0]['lon']), float(response[0]['lat'])

def get_osrm_route(origin_str, destination_str):
    start_lon, start_lat = geocode_address(origin_str)
    end_lon, end_lat = geocode_address(destination_str)

    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=simplified&geometries=geojson"
    response = requests.get(osrm_url).json()
    
    if response.get('code') != 'Ok':
        raise ValueError("Failed to calculate route via OSRM.")
        
    route = response['routes'][0]
    
    return {
        "distance_miles": route['distance'] * 0.000621371,
        "duration_hours": route['duration'] / 3600,
        "geometry": route['geometry']['coordinates']
    }