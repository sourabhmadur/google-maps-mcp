"""Best-effort current-location detection.

Resolution order:
1. macOS CoreLocation (via the `CoreLocationCLI` binary if installed).
2. Google Maps Geolocation API (IP/Wi-Fi based, ~city-level accuracy).
3. The GOOGLE_MAPS_DEFAULT_LOCATION env var, if set.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass

import httpx


@dataclass
class Location:
    lat: float
    lng: float
    source: str
    accuracy_m: float | None = None

    def as_dict(self) -> dict:
        out = {"lat": self.lat, "lng": self.lng, "source": self.source}
        if self.accuracy_m is not None:
            out["accuracy_m"] = self.accuracy_m
        return out


class LocationError(RuntimeError):
    pass


def _try_corelocation(timeout_s: float = 8.0) -> Location | None:
    if platform.system() != "Darwin":
        return None
    if os.environ.get("GOOGLE_MAPS_DISABLE_CORELOCATION"):
        return None
    binary = shutil.which("CoreLocationCLI")
    if not binary:
        return None
    try:
        result = subprocess.run(
            [binary, "-once", "true", "-format", "%latitude %longitude"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    if len(parts) < 2:
        return None
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except ValueError:
        return None
    return Location(lat=lat, lng=lng, source="corelocation")


def _try_google_geolocation(api_key: str, client: httpx.Client) -> Location | None:
    url = "https://www.googleapis.com/geolocation/v1/geolocate"
    try:
        resp = client.post(
            url,
            params={"key": api_key},
            json={"considerIp": True},
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    data = resp.json()
    loc = data.get("location")
    if not loc:
        return None
    return Location(
        lat=float(loc["lat"]),
        lng=float(loc["lng"]),
        source="google_geolocation_ip",
        accuracy_m=data.get("accuracy"),
    )


def _try_default(env_value: str | None) -> Location | None:
    if not env_value:
        return None
    try:
        lat_s, lng_s = env_value.split(",", 1)
        return Location(
            lat=float(lat_s.strip()),
            lng=float(lng_s.strip()),
            source="env_default",
        )
    except ValueError:
        return None


def get_current_location(api_key: str, client: httpx.Client) -> Location:
    """Return the user's best-known current location, or raise LocationError."""
    for fn in (
        lambda: _try_corelocation(),
        lambda: _try_google_geolocation(api_key, client),
        lambda: _try_default(os.environ.get("GOOGLE_MAPS_DEFAULT_LOCATION")),
    ):
        loc = fn()
        if loc is not None:
            return loc
    raise LocationError(
        "Could not determine current location. Install CoreLocationCLI "
        "(`brew install corelocationcli`), enable Google Geolocation API, "
        "or set GOOGLE_MAPS_DEFAULT_LOCATION."
    )
