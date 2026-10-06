from services.catalogue import load
from services.search import search_items, format_result

load()

user_lat = 12.9716
user_lon = 77.5946

results = search_items("I am hungry, I want shawarma under 200", user_lat, user_lon, limit=5)

print(f"results: {len(results)}")
for i, r in enumerate(results, start=1):
    print(f"\n--- Result {i} ---")
    print(format_result(r))