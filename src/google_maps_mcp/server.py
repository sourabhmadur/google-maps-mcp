"""Google Maps MCP server.

Exposes tools for the user's current location, Places API (New) nearby/text
search and details, Geocoding, Directions, and Distance Matrix.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .location import LocationError, get_current_location

# Look for .env in CWD first, then walk up from this package toward the repo root.
load_dotenv()
for parent in Path(__file__).resolve().parents:
    env_path = parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
        break

PLACES_BASE = "https://places.googleapis.com/v1"
MAPS_BASE = "https://maps.googleapis.com/maps/api"

_DEFAULT_SEARCH_FIELDS = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.rating,"
    "places.userRatingCount,"
    "places.priceLevel,"
    "places.primaryType,"
    "places.types,"
    "places.businessStatus,"
    "places.currentOpeningHours.openNow,"
    "places.googleMapsUri"
)

_DETAILS_FIELDS = (
    "id,displayName,formattedAddress,internationalPhoneNumber,nationalPhoneNumber,"
    "websiteUri,location,rating,userRatingCount,priceLevel,primaryType,types,"
    "businessStatus,currentOpeningHours,regularOpeningHours,reviews,googleMapsUri,"
    "editorialSummary,allowsDogs,reservable,servesBreakfast,servesLunch,"
    "servesDinner,servesVegetarianFood,outdoorSeating"
)


def _api_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_MAPS_API_KEY is not set. Copy .env.example to .env "
            "and add your Google Maps API key."
        )
    return key


def _http() -> httpx.Client:
    return httpx.Client(timeout=20.0)


def _resolve_location(
    location: str | None, client: httpx.Client
) -> tuple[float, float]:
    """Accept 'lat,lng' or None; if None, use current-location detection."""
    if location:
        try:
            lat_s, lng_s = location.split(",", 1)
            return float(lat_s.strip()), float(lng_s.strip())
        except ValueError as e:
            raise ValueError(
                f"location must be 'lat,lng' (got {location!r})"
            ) from e
    loc = get_current_location(_api_key(), client)
    return loc.lat, loc.lng


mcp = FastMCP("google-maps")


@mcp.tool()
def get_my_location() -> dict[str, Any]:
    """Return the user's best-known current location.

    Tries macOS CoreLocation first (if CoreLocationCLI is installed), then
    Google's IP-based Geolocation API, then GOOGLE_MAPS_DEFAULT_LOCATION.
    Returns lat, lng, source (which method was used), and optional accuracy_m.
    """
    with _http() as client:
        try:
            loc = get_current_location(_api_key(), client)
        except LocationError as e:
            return {"error": str(e)}
    return loc.as_dict()


@mcp.tool()
def search_nearby(
    query_types: list[str] | None = None,
    location: str | None = None,
    radius_m: int = 1500,
    rank_by: str = "popularity",
    open_now: bool = False,
    min_rating: float | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Search for places near a location using Places API (New) Nearby Search.

    Args:
        query_types: Place types to include, e.g. ["restaurant"], ["cafe"],
            ["tourist_attraction"], ["bar", "night_club"]. See Google's
            "Place Types (New) - Table A" for the full list. Defaults to
            ["restaurant"] if omitted.
        location: "lat,lng" string. If omitted, uses the detected current
            location.
        radius_m: Search radius in meters (max 50000).
        rank_by: "popularity" (default) or "distance". When "distance",
            radius_m is ignored.
        open_now: If True, only return places currently open.
        min_rating: Optional minimum average rating (1.0 - 5.0).
        max_results: Up to 20 results (Places API hard cap).
    """
    types = query_types or ["restaurant"]
    body: dict[str, Any] = {
        "includedTypes": types,
        "maxResultCount": max(1, min(max_results, 20)),
    }
    if rank_by == "distance":
        body["rankPreference"] = "DISTANCE"
    else:
        body["rankPreference"] = "POPULARITY"

    with _http() as client:
        lat, lng = _resolve_location(location, client)
        body["locationRestriction"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(min(max(radius_m, 1), 50000)),
            }
        }
        resp = client.post(
            f"{PLACES_BASE}/places:searchNearby",
            headers={
                "X-Goog-Api-Key": _api_key(),
                "X-Goog-FieldMask": _DEFAULT_SEARCH_FIELDS,
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code >= 400:
            return {"error": resp.text, "status_code": resp.status_code}
        data = resp.json()

    places = data.get("places", [])
    if open_now:
        places = [
            p for p in places
            if p.get("currentOpeningHours", {}).get("openNow") is True
        ]
    if min_rating is not None:
        places = [p for p in places if (p.get("rating") or 0) >= min_rating]
    return {"origin": {"lat": lat, "lng": lng}, "results": places}


@mcp.tool()
def search_text(
    query: str,
    location: str | None = None,
    radius_m: int = 5000,
    open_now: bool = False,
    min_rating: float | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Free-form text search ("ramen near me", "vegan brunch in Mission").

    Args:
        query: Natural-language query.
        location: "lat,lng" to bias results. If omitted, uses current location.
        radius_m: Bias radius in meters (max 50000).
        open_now: If True, only return places currently open.
        min_rating: Optional minimum average rating.
        max_results: Up to 20 results.
    """
    body: dict[str, Any] = {
        "textQuery": query,
        "maxResultCount": max(1, min(max_results, 20)),
    }
    if open_now:
        body["openNow"] = True
    if min_rating is not None:
        body["minRating"] = float(min_rating)

    with _http() as client:
        lat, lng = _resolve_location(location, client)
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(min(max(radius_m, 1), 50000)),
            }
        }
        resp = client.post(
            f"{PLACES_BASE}/places:searchText",
            headers={
                "X-Goog-Api-Key": _api_key(),
                "X-Goog-FieldMask": _DEFAULT_SEARCH_FIELDS,
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code >= 400:
            return {"error": resp.text, "status_code": resp.status_code}
        return {
            "origin": {"lat": lat, "lng": lng},
            "results": resp.json().get("places", []),
        }


@mcp.tool()
def get_place_details(place_id: str) -> dict[str, Any]:
    """Fetch rich details for a place by its Places API id.

    Includes hours, phone, website, reviews, and amenities.
    """
    with _http() as client:
        resp = client.get(
            f"{PLACES_BASE}/places/{place_id}",
            headers={
                "X-Goog-Api-Key": _api_key(),
                "X-Goog-FieldMask": _DETAILS_FIELDS,
            },
        )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


@mcp.tool()
def geocode(address: str) -> dict[str, Any]:
    """Convert an address or place name into lat/lng + structured components."""
    with _http() as client:
        resp = client.get(
            f"{MAPS_BASE}/geocode/json",
            params={"address": address, "key": _api_key()},
        )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    data = resp.json()
    if data.get("status") != "OK":
        return {"error": data.get("status"), "message": data.get("error_message")}
    return {"results": data.get("results", [])}


@mcp.tool()
def reverse_geocode(location: str | None = None) -> dict[str, Any]:
    """Convert a lat/lng to a human-readable address.

    Args:
        location: "lat,lng" string. If omitted, uses the detected current
            location.
    """
    with _http() as client:
        lat, lng = _resolve_location(location, client)
        resp = client.get(
            f"{MAPS_BASE}/geocode/json",
            params={"latlng": f"{lat},{lng}", "key": _api_key()},
        )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    data = resp.json()
    if data.get("status") != "OK":
        return {"error": data.get("status"), "message": data.get("error_message")}
    return {"location": {"lat": lat, "lng": lng}, "results": data.get("results", [])}


@mcp.tool()
def get_directions(
    destination: str,
    origin: str | None = None,
    mode: str = "driving",
    departure_time: str = "now",
    alternatives: bool = False,
) -> dict[str, Any]:
    """Get turn-by-turn directions between two places.

    Args:
        destination: Address, place name, or "lat,lng".
        origin: Address, place name, or "lat,lng". If omitted, uses the
            detected current location.
        mode: "driving" (default), "walking", "bicycling", or "transit".
        departure_time: "now" or a Unix timestamp string (driving/transit only).
        alternatives: If True, return multiple route options.
    """
    with _http() as client:
        if origin is None:
            lat, lng = _resolve_location(None, client)
            origin = f"{lat},{lng}"
        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "alternatives": "true" if alternatives else "false",
            "key": _api_key(),
        }
        if mode in ("driving", "transit"):
            params["departure_time"] = departure_time
        resp = client.get(f"{MAPS_BASE}/directions/json", params=params)
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    data = resp.json()
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        return {"error": data.get("status"), "message": data.get("error_message")}

    routes_out = []
    for route in data.get("routes", []):
        leg = route.get("legs", [{}])[0]
        routes_out.append({
            "summary": route.get("summary"),
            "distance": leg.get("distance", {}).get("text"),
            "duration": leg.get("duration", {}).get("text"),
            "duration_in_traffic": leg.get("duration_in_traffic", {}).get("text"),
            "start_address": leg.get("start_address"),
            "end_address": leg.get("end_address"),
            "steps": [
                {
                    "instruction": s.get("html_instructions"),
                    "distance": s.get("distance", {}).get("text"),
                    "duration": s.get("duration", {}).get("text"),
                    "travel_mode": s.get("travel_mode"),
                }
                for s in leg.get("steps", [])
            ],
        })
    return {"origin": origin, "destination": destination, "mode": mode, "routes": routes_out}


@mcp.tool()
def get_distance_matrix(
    destinations: list[str],
    origins: list[str] | None = None,
    mode: str = "driving",
    departure_time: str = "now",
) -> dict[str, Any]:
    """Compute travel time and distance for every origin/destination pair.

    Args:
        destinations: List of addresses, place names, or "lat,lng" strings.
        origins: Same; if omitted, the current location is used as the sole origin.
        mode: "driving", "walking", "bicycling", or "transit".
        departure_time: "now" or a Unix timestamp string.
    """
    with _http() as client:
        if not origins:
            lat, lng = _resolve_location(None, client)
            origins = [f"{lat},{lng}"]
        params = {
            "origins": "|".join(origins),
            "destinations": "|".join(destinations),
            "mode": mode,
            "key": _api_key(),
        }
        if mode in ("driving", "transit"):
            params["departure_time"] = departure_time
        resp = client.get(f"{MAPS_BASE}/distancematrix/json", params=params)
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    data = resp.json()
    if data.get("status") != "OK":
        return {"error": data.get("status"), "message": data.get("error_message")}

    matrix = []
    for i, row in enumerate(data.get("rows", [])):
        for j, cell in enumerate(row.get("elements", [])):
            matrix.append({
                "origin": data["origin_addresses"][i],
                "destination": data["destination_addresses"][j],
                "status": cell.get("status"),
                "distance": cell.get("distance", {}).get("text"),
                "duration": cell.get("duration", {}).get("text"),
                "duration_in_traffic": cell.get("duration_in_traffic", {}).get("text"),
            })
    return {"mode": mode, "pairs": matrix}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
