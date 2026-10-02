# Spotter Fuel Route API

Django REST API for calculating a driving route and selecting cost-effective fuel
stops from the supplied OPIS fuel-price dataset.

## Stack

- Django 6.1.1
- Django REST Framework
- OSRM for driving routes
- OpenStreetMap Nominatim for start/end geocoding
- US Census Geocoder for one-time station preprocessing
- Pandas for CSV preprocessing
- Shapely for route/station spatial calculations

## Architecture

POST request
-> geocode start/end
-> one OSRM route request
-> filter locally against preprocessed fuel stations
-> project candidate stations onto route
-> optimize fuel stops
-> calculate gallons/cost
-> JSON response

The route result is cached, so repeated requests for the same endpoints do not
need another OSRM request.

## Important assumptions

1. Vehicle range: 500 miles.
2. Fuel efficiency: 10 MPG.
3. Effective tank capacity: 50 gallons.
4. Vehicle starts with a full tank. The returned fuel cost represents fuel
   purchased during the trip; the initial tank contents are not charged.
5. A station is considered on-route if it is within 25 miles of the route.
6. Fuel selection uses a greedy strategy: when a cheaper reachable station is
   available, buy enough to reach it; otherwise buy enough to maximize useful
   range / reach the destination.
7. The supplied CSV has no coordinates in the provided schema, so a one-time
   preprocessing step creates a coordinate-enriched JSON file.

## Setup

Python 3.13+ is recommended.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and replace the Nominatim user-agent with an identifiable value.

## Add the supplied CSV

Put the company's CSV here:

```text
data/fuel_prices.csv
```

## Preprocess stations

First try the US Census batch geocoder:

```bash
python scripts/preprocess_stations.py --input data/fuel_prices.csv
```

Because many OPIS records use highway exits/intersections rather than normal
street addresses, some rows may not match the Census geocoder.

For unmatched rows, you can optionally run the Nominatim fallback:

```bash
python scripts/preprocess_stations.py \
  --input data/fuel_prices.csv \
  --fallback-nominatim
```

This fallback is intentionally a one-time preprocessing operation, not part of
the API request path.

## Run

```bash
python manage.py runserver
```

## API

### POST

```text
http://127.0.0.1:8000/api/v1/route/optimize/
```

### Request

```json
{
  "start": "New York, NY",
  "finish": "Chicago, IL"
}
```

### Response shape

```json
{
  "start": {},
  "finish": {},
  "route": {
    "distance_miles": 790.4,
    "duration_minutes": 760.0,
    "geometry": {
      "type": "LineString",
      "coordinates": []
    }
  },
  "fuel": {
    "mpg": 10,
    "max_range_miles": 500,
    "initial_fuel_gallons": 50,
    "total_gallons_consumed": 79.04,
    "total_cost": 251.37
  },
  "fuel_stops": [],
  "assumptions": {}
}
```

## Tests

```bash
python manage.py test tests
```

## API efficiency

The application makes one routing request per uncached origin/destination pair.
Fuel-station calculations are performed locally against the preprocessed
dataset. This avoids making thousands of routing API calls.

## External service notes

OSRM route responses provide distance, duration, and GeoJSON route geometry.

Nominatim's public service is rate-limited and should not be used for bulk
station geocoding in the request path. Station preprocessing therefore uses the
US Census batch geocoder first, with a slow Nominatim fallback only for
unmatched records.

For a production deployment, replace public shared services with a provider or
self-hosted routing/geocoding infrastructure appropriate for expected traffic.
