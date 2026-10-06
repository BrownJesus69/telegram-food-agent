import csv
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTFILE = BASE_DIR / "restaurants_overpass.csv"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

HEADERS = {
    "User-Agent": "TelegramFoodAgent/1.0 (student project; contact: local-dev)",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Split Bengaluru into smaller boxes:
# (south, west, north, east)
BBOXES = [
    (12.84, 77.50, 12.91, 77.60),
    (12.84, 77.60, 12.91, 77.70),
    (12.84, 77.70, 12.91, 77.80),

    (12.91, 77.50, 12.98, 77.60),
    (12.91, 77.60, 12.98, 77.70),
    (12.91, 77.70, 12.98, 77.80),

    (12.98, 77.50, 13.05, 77.60),
    (12.98, 77.60, 13.05, 77.70),
    (12.98, 77.70, 13.05, 77.80),

    (13.05, 77.50, 13.12, 77.60),
    (13.05, 77.60, 13.12, 77.70),
    (13.05, 77.70, 13.12, 77.80),
]

def s(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v).strip()

def build_query(south, west, north, east):
    return f"""
[out:json][timeout:60];
(
  node["amenity"="restaurant"]({south},{west},{north},{east});
  way["amenity"="restaurant"]({south},{west},{north},{east});
  relation["amenity"="restaurant"]({south},{west},{north},{east});

  node["amenity"="fast_food"]({south},{west},{north},{east});
  way["amenity"="fast_food"]({south},{west},{north},{east});
  relation["amenity"="fast_food"]({south},{west},{north},{east});

  node["amenity"="cafe"]({south},{west},{north},{east});
  way["amenity"="cafe"]({south},{west},{north},{east});
  relation["amenity"="cafe"]({south},{west},{north},{east});
);
out center tags;
""".strip()

def get_lat_lon(el):
    if "lat" in el and "lon" in el:
        return s(el["lat"]), s(el["lon"])
    center = el.get("center", {})
    return s(center.get("lat")), s(center.get("lon"))

def normalize(el):
    tags = el.get("tags", {})
    lat, lon = get_lat_lon(el)
    return {
        "restaurant_id": f'osm:{s(el.get("type"))}:{s(el.get("id"))}',
        "name": s(tags.get("name")),
        "latitude": lat,
        "longitude": lon,
        "category": s(tags.get("amenity")),
        "cuisine": s(tags.get("cuisine")),
        "street": s(tags.get("addr:street")),
        "housenumber": s(tags.get("addr:housenumber")),
        "city": s(tags.get("addr:city")),
        "postcode": s(tags.get("addr:postcode")),
        "phone": s(tags.get("phone") or tags.get("contact:phone")),
        "website": s(tags.get("website") or tags.get("contact:website")),
        "opening_hours": s(tags.get("opening_hours")),
        "source": "openstreetmap_overpass",
    }

def fetch_overpass(query):
    last_error = None
    for url in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(
                url,
                data={"data": query},
                headers=HEADERS,
                timeout=90,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_error = e
            time.sleep(2)
    raise last_error

def main():
    seen = {}

    for i, bbox in enumerate(BBOXES, start=1):
        south, west, north, east = bbox
        print(f"[{i}/{len(BBOXES)}] Fetching bbox {bbox}...")
        query = build_query(south, west, north, east)

        try:
            data = fetch_overpass(query)
        except Exception as e:
            print(f"Skipping bbox {bbox}: {e}")
            continue

        for el in data.get("elements", []):
            row = normalize(el)
            if not row["name"]:
                continue
            key = (row["name"].lower(), row["latitude"], row["longitude"])
            if key not in seen:
                seen[key] = row

        time.sleep(3)

    rows = list(seen.values())
    rows.sort(key=lambda x: x["name"].lower())

    with OUTFILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "restaurant_id", "name", "latitude", "longitude",
                "category", "cuisine", "street", "housenumber",
                "city", "postcode", "phone", "website",
                "opening_hours", "source"
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTFILE}")

if __name__ == "__main__":
    main()