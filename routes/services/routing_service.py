import logging
import hashlib

from django.core.cache import cache
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import requests

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 15
TIMEOUT = (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)
HEADERS = {"User-Agent": "FuelRouteOptimizer/1.0 (assessment project)"}
GEOCODE_CACHE_TIMEOUT = 24 * 60 * 60
ROUTE_CACHE_TIMEOUT = 6 * 60 * 60


class UpstreamServiceError(RuntimeError):
    """A required third-party service returned an unusable response."""


class UpstreamTimeoutError(UpstreamServiceError):
    pass


class UpstreamRateLimitError(UpstreamServiceError):
    pass


class LocationNotFoundError(ValueError):
    pass


class OutsideUSLocationError(ValueError):
    pass


_SESSION = None


def _build_session() -> Session:
    # Retry only transient upstream failures. POST requests are not used here.
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    session = Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def _session() -> Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = _build_session()
    return _SESSION


def _request_json(url, *, params=None, headers=None):
    session = _session()
    try:
        response = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
    except requests.Timeout as exc:
        raise UpstreamTimeoutError("Upstream service timed out.") from exc
    except requests.RequestException as exc:
        raise UpstreamServiceError("Upstream service connection failed.") from exc

    if response.status_code == 429:
        raise UpstreamRateLimitError("Upstream service rate limit reached.")
    if response.status_code >= 500:
        raise UpstreamServiceError("Upstream service failed.")
    if response.status_code >= 400:
        raise UpstreamServiceError("Upstream service rejected the request.")

    try:
        return response.json()
    except ValueError as exc:
        raise UpstreamServiceError("Upstream service returned invalid JSON.") from exc


def geocode_address(location_string):
    normalized = " ".join(str(location_string).strip().casefold().split())
    if not normalized:
        raise LocationNotFoundError("Location cannot be empty.")
    cache_key = "geocode:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _request_json(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": location_string,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "countrycodes": "us",
        },
        headers=HEADERS,
    )

    if not data:
        raise LocationNotFoundError(f"Could not find a U.S. location for: {location_string}")

    result = data[0]
    address = result.get("address") or {}
    if address.get("country_code", "").lower() != "us":
        raise OutsideUSLocationError("Origin and destination must be located in the United States.")

    try:
        coordinates = (float(result["lon"]), float(result["lat"]))
        cache.set(cache_key, coordinates, GEOCODE_CACHE_TIMEOUT)
        return coordinates
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamServiceError("Geocoding service returned invalid coordinates.") from exc


def get_osrm_route(origin_str, destination_str):
    start_lon, start_lat = geocode_address(origin_str)
    end_lon, end_lat = geocode_address(destination_str)

    route_key_material = f"{start_lon:.6f},{start_lat:.6f}:{end_lon:.6f},{end_lat:.6f}"
    route_cache_key = "route:" + hashlib.sha256(route_key_material.encode("utf-8")).hexdigest()
    cached_route = cache.get(route_cache_key)
    if cached_route is not None:
        return cached_route

    if (start_lon, start_lat) == (end_lon, end_lat):
        raise ValueError("Origin and destination resolve to the same location.")

    data = _request_json(
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}",
        params={"overview": "simplified", "geometries": "geojson"},
        headers=HEADERS,
    )

    if data.get("code") != "Ok" or not data.get("routes"):
        raise UpstreamServiceError("Routing provider could not calculate a route.")

    try:
        route = data["routes"][0]
        geometry = route["geometry"]["coordinates"]
        route_result = {
            "distance_miles": float(route["distance"]) * 0.000621371,
            "duration_hours": float(route["duration"]) / 3600,
            "geometry": geometry,
        }
        cache.set(route_cache_key, route_result, ROUTE_CACHE_TIMEOUT)
        return route_result
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise UpstreamServiceError("Routing provider returned an invalid route.") from exc
