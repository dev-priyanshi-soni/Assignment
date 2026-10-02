"""
Preprocess the supplied OPIS CSV into data/geocoded_stations.json.

Usage:
    python scripts/preprocess_stations.py --input data/fuel_prices.csv

The script first tries the US Census batch geocoder. Because some OPIS
addresses are highway exits/intersections rather than standard street
addresses, unmatched rows can optionally be geocoded using Nominatim.

Nominatim is deliberately used only as a one-time preprocessing fallback,
not on normal API requests.
"""

import argparse
import csv
import io
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests


CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def normalize_columns(df):
    mapping = {}
    for col in df.columns:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(col).lower()).strip()
        mapping[col] = normalized
    df = df.rename(columns=mapping)

    required = {
        "opis truckstop id": "truckstop_id",
        "truckstop name": "name",
        "address": "address",
        "city": "city",
        "state": "state",
        "retail price": "price",
    }
    for source, target in required.items():
        if source not in df.columns:
            raise ValueError(f"Missing required CSV column: {source}")
        df = df.rename(columns={source: target})

    return df

def census_batch(records):
    # Census requires: Unique ID, Street address, City, State, ZIP.
    rows = []
    for i, r in enumerate(records, start=1):
        rows.append([
            str(i),
            str(r["address"]),
            str(r["city"]),
            str(r["state"]),
            "",
        ])

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)

    response = requests.post(
        CENSUS_URL,
        files={"addressFile": ("stations.csv", buf.getvalue())},
        data={"benchmark": "Public_AR_Current"},
        timeout=120,
    )
    response.raise_for_status()

    parsed = []
    for line in response.text.splitlines():
        if not line.strip():
            continue
        cols = next(csv.reader([line]))
        parsed.append(cols)

    result = {}
    for cols in parsed:
        idx = int(cols[0]) - 1
        if len(cols) >= 6 and cols[2] == "Match":
            lon, lat = map(float, cols[5].split(","))
            result[idx] = (lat, lon)
    return result

def nominatim_geocode(record, user_agent):
    query = f'{record["address"]}, {record["city"]}, {record["state"]}, USA'
    response = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
        headers={"User-Agent": user_agent},
        timeout=20,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        # City/state fallback is intentionally weaker but gives a useful
        # approximate point when a highway-exit address cannot be resolved.
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": f'{record["city"]}, {record["state"]}, USA',
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "us",
            },
            headers={"User-Agent": user_agent},
            timeout=20,
        )
        response.raise_for_status()
        results = response.json()

    if not results:
        return None

    return float(results[0]["lat"]), float(results[0]["lon"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/geocoded_stations.json")
    parser.add_argument("--fallback-nominatim", action="store_true")
    args = parser.parse_args()

    user_agent = os.getenv(
        "NOMINATIM_USER_AGENT",
        "spotter-fuel-route-preprocessor/1.0 (test@gmail.com)",
    )

    df = pd.read_csv(args.input)
    df = normalize_columns(df)

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price", "city", "state", "address"])
    df = df[df["price"] > 0]

    # Remove exact duplicates while retaining legitimate same-ID rows with
    # different prices as separate observations.
    df = df.drop_duplicates(
        subset=["truckstop_id", "name", "address", "city", "state", "price"]
    )

    records = df.to_dict("records")

    print(f"Preparing {len(records)} station records...")
    coords = census_batch(records)
    print(f"Census matched {len(coords)}/{len(records)} records.")

    if args.fallback_nominatim:
        # Respect Nominatim public-service rate limit: <= 1 request/sec.
        for i, record in enumerate(records):
            if i in coords:
                continue
            print(f"Nominatim fallback {i+1}/{len(records)}: {record['name']}")
            point = nominatim_geocode(record, user_agent)
            if point:
                coords[i] = point
            time.sleep(1.05)

    output = []
    for i, record in enumerate(records):
        if i not in coords:
            continue
        lat, lon = coords[i]
        output.append({
            "truckstop_id": str(record["truckstop_id"]),
            "name": str(record["name"]).strip(),
            "address": str(record["address"]).strip(),
            "city": str(record["city"]).strip(),
            "state": str(record["state"]).strip(),
            "price": round(float(record["price"]), 4),
            "latitude": lat,
            "longitude": lon,
        })

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(output)} geocoded stations to {args.output}")
    print(f"Skipped {len(records) - len(output)} stations without coordinates.")

if __name__ == "__main__":
    main()
