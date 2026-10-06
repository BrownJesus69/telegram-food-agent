from math import radians, sin, cos, sqrt, asin


EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * c


def is_within_radius(user_lat: float, user_lon: float, restaurant_lat: float, restaurant_lon: float, radius_km: float) -> bool:
    return haversine_km(user_lat, user_lon, restaurant_lat, restaurant_lon) <= radius_km