import pandas as pd
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GEO_FILE = BASE_DIR / "restaurants.csv"
OSM_FILE = BASE_DIR / "restaurants_overpass.csv"
OUT_FILE = BASE_DIR / "restaurants_clean.csv"


def getcol(df, name, default=''):
    return df[name] if name in df.columns else default


def norm_name(s: str) -> str:
    suffixes = ['restaurant','resto','hotel','cafe','kitchen','kitchens','foods','fast food','mess','diner']
    s = str(s).lower().strip()
    s = re.sub(r'[^a-z0-9\\s&-]', ' ', s)
    s = re.sub(r'\\b(the|and)\\b', ' ', s)
    for suf in suffixes:
        s = re.sub(rf'\\b{suf}\\b', ' ', s)
    s = re.sub(r'\\s+', ' ', s).strip()
    return s


def normalize_geo(df):
    return pd.DataFrame({
        'restaurant_id': getcol(df,'restaurant_id'),
        'name': getcol(df,'name'),
        'latitude': pd.to_numeric(getcol(df,'latitude'), errors='coerce'),
        'longitude': pd.to_numeric(getcol(df,'longitude'), errors='coerce'),
        'category': getcol(df,'category'),
        'cuisine': getcol(df,'subcategory'),
        'address': getcol(df,'formatted'),
        'phone': getcol(df,'phone'),
        'website': getcol(df,'website'),
        'opening_hours': getcol(df,'opening_hours'),
        'source': 'geoapify'
    })


def normalize_osm(df):
    address = (
        getcol(df,'housenumber').fillna('').astype(str).str.strip() + ' ' +
        getcol(df,'street').fillna('').astype(str).str.strip() + ' ' +
        getcol(df,'city').fillna('').astype(str).str.strip() + ' ' +
        getcol(df,'postcode').fillna('').astype(str).str.strip()
    ).str.replace(r'\\s+', ' ', regex=True).str.strip()
    return pd.DataFrame({
        'restaurant_id': getcol(df,'restaurant_id'),
        'name': getcol(df,'name'),
        'latitude': pd.to_numeric(getcol(df,'latitude'), errors='coerce'),
        'longitude': pd.to_numeric(getcol(df,'longitude'), errors='coerce'),
        'category': getcol(df,'category'),
        'cuisine': getcol(df,'cuisine'),
        'address': address,
        'phone': getcol(df,'phone'),
        'website': getcol(df,'website'),
        'opening_hours': getcol(df,'opening_hours'),
        'source': 'openstreetmap_overpass'
    })


def main():
    geo = pd.read_csv(GEO_FILE)
    osm = pd.read_csv(OSM_FILE)

    geo_n = normalize_geo(geo)
    osm_n = normalize_osm(osm)
    all_df = pd.concat([geo_n, osm_n], ignore_index=True)

    for col in ['name','category','cuisine','address','phone','website','opening_hours']:
        all_df[col] = all_df[col].fillna('').astype(str).str.strip()

    bad_names = {'nan','none','null','unknown','restaurant','cafe','fast food','food court','canteen'}
    all_df = all_df[(all_df['name'] != '') & (~all_df['name'].str.lower().isin(bad_names))]
    all_df = all_df.dropna(subset=['latitude','longitude'])
    all_df = all_df[(all_df['latitude'].between(12.7,13.2)) & (all_df['longitude'].between(77.3,78.0))]

    all_df['norm_name'] = all_df['name'].map(norm_name)
    all_df = all_df[all_df['norm_name'] != '']

    priority = {'geoapify': 0, 'openstreetmap_overpass': 1}
    all_df['priority'] = all_df['source'].map(priority).fillna(9)
    all_df['completeness'] = all_df[['address','phone','website','opening_hours','cuisine']].astype(str).apply(
        lambda r: sum(1 for v in r if v.strip() and v.strip().lower() != 'nan'), axis=1
    )

    all_df['lat_r'] = all_df['latitude'].round(4)
    all_df['lon_r'] = all_df['longitude'].round(4)
    all_df = all_df.sort_values(
        ['norm_name','lat_r','lon_r','priority','completeness'],
        ascending=[True, True, True, True, False]
    )

    clean = all_df.drop_duplicates(subset=['norm_name','lat_r','lon_r'], keep='first').copy()

    clean['catalogue_rating'] = 4.0
    clean['prep_minutes'] = 25
    clean['delivery_fee'] = 30
    clean['operator_chat_id'] = ''
    clean['operator_mode'] = 'PRIVATE'
    clean['active'] = 1

    final_cols = [
        'restaurant_id','name','latitude','longitude','category','cuisine','address',
        'phone','website','opening_hours','source','catalogue_rating','prep_minutes',
        'delivery_fee','operator_chat_id','operator_mode','active'
    ]

    clean = clean[final_cols].sort_values('name')
    clean.to_csv(OUT_FILE, index=False)
    print(f"Wrote {len(clean)} rows to {OUT_FILE}")


if __name__ == '__main__':
    main()
