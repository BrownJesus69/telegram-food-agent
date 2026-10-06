import csv
from dataclasses import dataclass
from pathlib import Path

import config


@dataclass(frozen=True)
class Restaurant:
    id: str
    name: str
    lat: float
    lon: float
    rating: float
    prep_min: int
    prep_max: int
    min_per_km: float
    delivery_fee: int
    radius_km: float
    is_open: bool
    category: str = ""
    cuisine: str = ""
    address: str = ""
    operator_chat_id: str = ""
    operator_mode: str = ""


@dataclass(frozen=True)
class Item:
    id: str
    restaurant_id: str
    name: str
    aliases: tuple[str, ...]
    description: str
    category: str
    price: int
    available: bool
    veg: bool
    prep_minutes: int = 0
    restaurant_name: str = ""


RESTAURANTS: dict[str, Restaurant] = {}
ITEMS: dict[str, Item] = {}
ITEMS_BY_RESTAURANT: dict[str, list[Item]] = {}


def _bool(v) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _clean(v) -> str:
    return str(v or "").strip()


def _to_int(v, default=0) -> int:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(v, default=0.0) -> float:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def _build_aliases(name: str, category: str, description: str) -> tuple[str, ...]:
    tokens = set()

    for raw in (name, category, description):
        text = _clean(raw).lower()
        if text:
            tokens.add(text)

    name_l = _clean(name).lower()

    if "shawarma" in name_l:
        tokens.update({"shawarma", "shawarma wrap", "wrap", "roll"})
    if "biryani" in name_l or "biriyani" in name_l:
        tokens.update({"biryani", "biriyani"})
    if "pizza" in name_l:
        tokens.add("pizza")
    if "burger" in name_l:
        tokens.add("burger")
    if "dosa" in name_l:
        tokens.add("dosa")
    if "fried rice" in name_l:
        tokens.add("fried rice")
    if "noodles" in name_l:
        tokens.add("noodles")
    if "coffee" in name_l or "cappuccino" in name_l:
        tokens.add("coffee")

    return tuple(sorted(tokens))


def load(data_dir=None):
    data_path = Path(data_dir or config.DATA_DIR)

    restaurants_file = data_path / "restaurants.csv"
    menu_file = data_path / "menu.csv"

    RESTAURANTS.clear()
    ITEMS.clear()
    ITEMS_BY_RESTAURANT.clear()

    with restaurants_file.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            restaurant_id = _clean(r.get("restaurant_id"))
            if not restaurant_id:
                continue

            prep = _to_int(r.get("prep_minutes"), 20)

            restaurant = Restaurant(
                id=restaurant_id,
                name=_clean(r.get("name")),
                lat=_to_float(r.get("latitude")),
                lon=_to_float(r.get("longitude")),
                rating=_to_float(r.get("catalogue_rating"), 4.0),
                prep_min=max(5, prep),
                prep_max=max(10, prep + 10),
                min_per_km=4.0,
                delivery_fee=_to_int(r.get("delivery_fee"), 30),
                radius_km=5.0,
                is_open=_bool(r.get("active")),
                category=_clean(r.get("category")),
                cuisine=_clean(r.get("cuisine")),
                address=_clean(r.get("address")),
                operator_chat_id=_clean(r.get("operator_chat_id")),
                operator_mode=_clean(r.get("operator_mode")),
            )

            RESTAURANTS[restaurant.id] = restaurant
            ITEMS_BY_RESTAURANT[restaurant.id] = []

    with menu_file.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            item_id = _clean(r.get("menu_item_id"))
            restaurant_id = _clean(r.get("restaurant_id"))

            if not item_id or not restaurant_id:
                continue

            if restaurant_id not in RESTAURANTS:
                raise ValueError(
                    f"menu item {item_id} has unknown restaurant {restaurant_id}"
                )

            item = Item(
                id=item_id,
                restaurant_id=restaurant_id,
                name=_clean(r.get("item_name")),
                aliases=_build_aliases(
                    r.get("item_name"),
                    r.get("category"),
                    r.get("item_description"),
                ),
                description=_clean(r.get("item_description")),
                category=_clean(r.get("category")),
                price=_to_int(r.get("price")),
                available=_bool(r.get("in_stock")) and _bool(r.get("active")),
                veg=_bool(r.get("veg")),
                prep_minutes=_to_int(r.get("prep_minutes"), 0),
                restaurant_name=_clean(r.get("restaurant_name")),
            )

            ITEMS[item.id] = item
            ITEMS_BY_RESTAURANT[item.restaurant_id].append(item)

    return len(RESTAURANTS), len(ITEMS)


def get_restaurant(restaurant_id: str) -> Restaurant | None:
    return RESTAURANTS.get(restaurant_id)


def get_item(item_id: str) -> Item | None:
    return ITEMS.get(item_id)


def get_items_for_restaurant(restaurant_id: str) -> list[Item]:
    return ITEMS_BY_RESTAURANT.get(restaurant_id, [])