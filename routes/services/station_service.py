from routes.models import FuelStation
from math import radians, cos, sin, asin, sqrt

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 3956 
    return c * r

def get_stations_in_corridor(geometry_coords):
    lons = [coord[0] for coord in geometry_coords]
    lats = [coord[1] for coord in geometry_coords]
    
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    pad = 0.5 
    
    return FuelStation.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__range=(min_lat - pad, max_lat + pad),
        longitude__range=(min_lon - pad, max_lon + pad)
    )