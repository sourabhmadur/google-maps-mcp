# google-maps-mcp

An MCP server that gives Claude (or any MCP client) access to Google Maps so it
can answer location-aware questions like *"what's a good ramen place near me?"*,
*"how long to drive to the airport?"*, or *"what's the address of this lat/lng?"*.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_my_location` | Returns your best-known current lat/lng (CoreLocation → Google IP geolocation → env default). |
| `search_nearby` | Places API (New) Nearby Search by type (restaurant, cafe, tourist_attraction, etc.). |
| `search_text` | Places API (New) free-form text search ("vegan brunch in Mission"). |
| `get_place_details` | Hours, phone, website, reviews, amenities for a specific place_id. |
| `geocode` | Address → lat/lng + structured components. |
| `reverse_geocode` | lat/lng → human-readable address. |
| `get_directions` | Turn-by-turn directions, driving/walking/bicycling/transit. |
| `get_distance_matrix` | Travel time and distance for every origin/destination pair. |

Any tool that needs a location accepts an optional `location="lat,lng"` (or
`origin=`) override. If omitted, the server auto-detects your location.

## Setup

### 1. Get a Google Maps Platform API key

In the [Google Cloud Console](https://console.cloud.google.com/google/maps-apis):

1. Create a project (or pick one) and enable billing.
2. Enable these APIs:
   - **Places API (New)** — for `search_nearby`, `search_text`, `get_place_details`
   - **Geocoding API** — for `geocode`, `reverse_geocode`
   - **Directions API** — for `get_directions`
   - **Distance Matrix API** — for `get_distance_matrix`
   - **Geolocation API** — for IP-based current location fallback
3. Create an API key under *APIs & Services → Credentials*. Restrict it to those
   APIs.

### 2. (Optional, macOS) Install CoreLocationCLI for real GPS-ish location

```sh
brew install corelocationcli
```

The first run will prompt you to grant Location Services permission to the
terminal. Without this, the server falls back to IP-based geolocation.

### 3. Install the server

```sh
cd google_maps_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# edit .env and paste your API key
```

### 4. Register with Claude Code

Add it to Claude Code's MCP config (`~/.claude.json` or via the CLI):

```sh
claude mcp add google-maps \
  --command "/absolute/path/to/google_maps_mcp/.venv/bin/google-maps-mcp" \
  --env GOOGLE_MAPS_API_KEY=your_key_here
```

Or, run from anywhere with `uv`:

```sh
claude mcp add google-maps \
  --command "uv" \
  --args "run" "--directory" "/absolute/path/to/google_maps_mcp" "google-maps-mcp" \
  --env GOOGLE_MAPS_API_KEY=your_key_here
```

### 5. (Optional) Set a default fallback location

If neither CoreLocation nor the Geolocation API can determine your location,
the server reads `GOOGLE_MAPS_DEFAULT_LOCATION`:

```sh
# in .env
GOOGLE_MAPS_DEFAULT_LOCATION=37.7749,-122.4194
```

## Quick sanity check

```sh
source .venv/bin/activate
python -c "from google_maps_mcp.server import mcp; print([t.name for t in mcp._tool_manager.list_tools()])"
```

You should see all eight tool names.

## Example prompts

- *"Find me a highly-rated cafe within walking distance."*
- *"What's open right now near me for late-night food?"*
- *"How long to drive to SFO with current traffic?"*
- *"Give me the hours and phone number for [place name]."*
- *"What's the address for 37.7749,-122.4194?"*
