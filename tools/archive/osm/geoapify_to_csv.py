import csv
import os
import time
import requests

API_KEY = os.getenv("GEOAPIFY_API_KEY", "YOUR_GEOAPIFY_API_KEY")

SEARCH_POINTS = [
    (12.9716, 77.5946),
    (12.9352, 77.6245),
    (12.9279, 77.6271),
    (13.0358, 77.5970),
    (12.9081, 77.6476),
    (12.9854, 77.7066),
]

RADIUS_METERS = 4000
LIMIT = 200
CATEGORIES = ",".join([
    "catering.restaurant",
    "catering.fast_food",
    "catering.cafe",
])
OUTFILE = "restaurants.csv"

def s(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v).strip()

def fetch_places(lat, lon):
    url = "https://api.geoapify.com/v2/places"
    params = {
        "categories": CATEGORIES,
        "filter": f"circle:{lon},{lat},{RADIUS_METERS}",
        "bias": f"proximity:{lon},{lat}",
        "limit": LIMIT,
        "apiKey": API_KEY,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def normalize_feature(feature):
    props = feature.get("properties", {})
    return {
        "restaurant_id": s(props.get("place_id") or props.get("osm_id")),
        "name": s(props.get("name")),
        "latitude": s(props.get("lat")),
        "longitude": s(props.get("lon")),
        "category": s(props.get("categories")),
        "subcategory": s(props.get("subcategory")),
        "formatted": s(props.get("formatted")),
        "street": s(props.get("street")),
        "city": s(props.get("city")),
        "state": s(props.get("state")),
        "postcode": s(props.get("postcode")),
        "phone": s(props.get("phone")),
        "website": s(props.get("website")),
        "opening_hours": s(props.get("opening_hours")),
        "source": "geoapify",
    }

def main():
    seen = {}
    for lat, lon in SEARCH_POINTS:
        data = fetch_places(lat, lon)
        for feature in data.get("features", []):
            row = normalize_feature(feature)
            if not row["name"]:
                continue
            key = (row["name"].lower(), row["latitude"], row["longitude"])
            if key not in seen:
                seen[key] = row
        time.sleep(1)

    rows = list(seen.values())
    rows.sort(key=lambda x: x["name"].lower())

    with open(OUTFILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "restaurant_id", "name", "latitude", "longitude",
                "category", "subcategory", "formatted", "street",
                "city", "state", "postcode", "phone", "website",
                "opening_hours", "source"
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTFILE}")

if __name__ == "__main__":
    main()