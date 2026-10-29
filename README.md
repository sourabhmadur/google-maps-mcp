# google-maps-mcp

A Python MCP server that gives Claude (or any MCP client) Google Maps: place search, place details, geocoding, directions, travel times, and your current location.

It can answer questions like *"what's a good ramen place near me?"*, *"how long is the drive to the airport?"*, or *"what's the address at this lat/lng?"*.

## Tools

| Tool | What it does | Google API |
| --- | --- | --- |
| `get_my_location` | Your best-known current lat/lng. It tries macOS CoreLocation first, then Google IP geolocation, then a default you configure. | Geolocation API |
| `search_nearby` | Places near a point, filtered by type (`restaurant`, `cafe`, `bar`, ...), with optional `open_now` and `min_rating`. Results are ranked by popularity or distance. | Places API (New) |
| `search_text` | Free-text place search, e.g. "vegan brunch in Mission". | Places API (New) |
| `get_place_details` | Hours, phone, website, reviews, price level, and amenities for a `place_id`. | Places API (New) |
| `geocode` | Turns an address into lat/lng plus structured address components. | Geocoding API |
| `reverse_geocode` | Turns a lat/lng into a readable address. | Geocoding API |
| `get_directions` | Turn-by-turn directions for driving, walking, bicycling, or transit, with optional alternative routes. | Directions API |
| `get_distance_matrix` | Travel time and distance for every origin/destination pair. | Distance Matrix API |

Any location argument (`location`, `origin`) is optional and takes `"lat,lng"`. If you leave it out, the server detects your current location.

## Example

*This is an illustrative example of how Claude uses the tools. It is not a recorded transcript.*

> **You:** Find a well-rated cafe I can walk to that's open now, and tell me how long the walk is.
>
> **Claude:** *(calls `get_my_location`, then `search_nearby` with `query_types=["cafe"]`, `open_now=true`, `min_rating=4.3`, `rank_by="distance"`, then `get_directions` with `mode="walking"` to the top result)*
> The closest match is *[cafe name]*, rated 4.6. It's about a 7-minute walk: head north on ... Do you want its hours or recent reviews?

## Requirements

- Python 3.10+
- A Google Maps Platform API key. Billing must be enabled on the Cloud project, and Google charges per request beyond any free usage. In the [Cloud Console](https://console.cloud.google.com/google/maps-apis), enable these APIs:
  - **Places API (New)**: `search_nearby`, `search_text`, `get_place_details`
  - **Geocoding API**: `geocode`, `reverse_geocode`
  - **Directions API**: `get_directions`
  - **Distance Matrix API**: `get_distance_matrix`
  - **Geolocation API**: IP-based fallback for `get_my_location`

  Restrict the key to these APIs.
- Optional (macOS): `brew install corelocationcli` gives a more precise location. macOS asks for Location Services permission the first time it runs.

## Install

```sh
git clone https://github.com/sourabhmadur/google-maps-mcp.git
cd google-maps-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # then set GOOGLE_MAPS_API_KEY
```

Environment variables (in `.env`, or passed in through the client config):

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | yes | Google Maps Platform key |
| `GOOGLE_MAPS_DEFAULT_LOCATION` | no | Fallback `"lat,lng"` used when location can't be detected |
| `GOOGLE_MAPS_DISABLE_CORELOCATION` | no | Set to `1` to skip CoreLocation |

## Connect to Claude

**Claude Code**

```sh
claude mcp add google-maps -e GOOGLE_MAPS_API_KEY=your_key_here \
  -- /absolute/path/to/google-maps-mcp/.venv/bin/google-maps-mcp
```

**Claude Desktop**: add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "/absolute/path/to/google-maps-mcp/.venv/bin/google-maps-mcp",
      "env": { "GOOGLE_MAPS_API_KEY": "your_key_here" }
    }
  }
}
```

## Sanity check

This lists the registered tools. It makes no API calls.

```sh
python -c "import asyncio; from google_maps_mcp.server import mcp; print([t.name for t in asyncio.run(mcp.list_tools())])"
```

You should see all eight tool names.

## Works well with

[ticketmaster-mcp](https://github.com/sourabhmadur/ticketmaster-mcp): pass the coordinates from `get_my_location` to its `search_events` to find events near you.
