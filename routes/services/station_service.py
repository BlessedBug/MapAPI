from math import radians, cos, sin, asin, sqrt

from routes.models import FuelStation

EARTH_RADIUS_MILES = 3958.7613


def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(a))


def get_stations_in_corridor(geometry_coords, corridor_miles=15.0):

    if not geometry_coords:
        return FuelStation.objects.none()
    lons = [coord[0] for coord in geometry_coords]
    lats = [coord[1] for coord in geometry_coords]
    mean_lat = sum(lats) / len(lats)
    lat_pad = corridor_miles / 69.0
    lon_pad = corridor_miles / max(1.0, 69.172 * abs(cos(radians(mean_lat))))
    return (
        FuelStation.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__range=(min(lats) - lat_pad, max(lats) + lat_pad),
            longitude__range=(min(lons) - lon_pad, max(lons) + lon_pad),
        )
        .only("id", "truckstop_id", "name", "city", "state", "retail_price", "latitude", "longitude")
    )
