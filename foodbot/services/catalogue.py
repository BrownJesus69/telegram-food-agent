"""In-memory catalogue loaded from seed_data/restaurants.csv and seed_data/menu.csv.

The catalogue is synthetic (see tools/catalogue_gen). Everything the bot can sell is in here;
nothing outside it can ever be ordered.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from foodbot import config

IST = timezone(timedelta(hours=5, minutes=30))   # India has no DST, a fixed offset is exact
MEAL_SLOTS = ("breakfast", "lunch", "snack", "dinner", "latenight")

_SLOT_BOUNDS = (          # (slot, start minute, end minute) over the 24h clock, in IST
    ("breakfast", 6 * 60, 11 * 60),
    ("lunch", 11 * 60, 15 * 60 + 30),
    ("snack", 15 * 60 + 30, 18 * 60 + 30),
    ("dinner", 18 * 60 + 30, 23 * 60),
)


def now_ist() -> datetime:
    return datetime.now(IST)


def current_slot(now: datetime | None = None) -> str:
    """Which meal slot is it right now in Bengaluru?"""
    now = (now or now_ist()).astimezone(IST)
    m = now.hour * 60 + now.minute
    for slot, a, b in _SLOT_BOUNDS:
        if a <= m < b:
            return slot
    return "latenight"


def _minutes(hhmm: str, default: int) -> int:
    try:
        h, m = hhmm.strip().split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return default


@dataclass(frozen=True)
class Restaurant:
    id: str
    name: str
    lat: float
    lon: float
    rating: float
    prep_min: int
    prep_max: int
    delivery_fee: int
    radius_km: float
    active: bool
    category: str = ""
    cuisine: str = ""
    address: str = ""
    locality: str = ""
    price_level: int = 2
    rating_count: int = 0
    min_order: int = 0
    open_from: int = 0                 # minutes after midnight
    open_to: int = 24 * 60             # may exceed 1440 when the place closes after midnight
    tags: tuple[str, ...] = ()
    operator_chat_id: str = ""
    operator_mode: str = ""

    @property
    def pure_veg(self) -> bool:
        return "pure-veg" in self.tags

    def open_at(self, now: datetime | None = None) -> bool:
        if not self.active:
            return False
        now = (now or now_ist()).astimezone(IST)
        m = now.hour * 60 + now.minute
        return any(self.open_from <= m + shift < self.open_to for shift in (0, 24 * 60))

    @property
    def hours_label(self) -> str:
        def fmt(x: int) -> str:
            x %= 24 * 60
            h, mi = divmod(x, 60)
            suffix = "am" if h < 12 else "pm"
            return f"{(h % 12) or 12}:{mi:02d} {suffix}"
        return f"{fmt(self.open_from)} – {fmt(self.open_to)}"

    # kept for callers written against the pre-restructure API
    @property
    def is_open(self) -> bool:
        return self.open_at()

    @property
    def lat_lon(self) -> tuple[float, float]:
        return self.lat, self.lon


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
    diet: str = "veg"                  # veg | egg | nonveg
    spice: int = 0                     # 0 mild .. 3 very hot
    slots: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    allergens: tuple[str, ...] = ()
    calories: int = 0
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


def _pipe(v) -> tuple[str, ...]:
    return tuple(x.strip() for x in _clean(v).split("|") if x.strip())


def _build_aliases(name: str, aliases: tuple[str, ...]) -> tuple[str, ...]:
    tokens = {_clean(name).lower()}
    tokens.update(a.lower() for a in aliases)
    return tuple(sorted(tokens))


def load(data_dir=None):
    data_path = Path(data_dir or config.DATA_DIR)
    restaurants_file = data_path / "restaurants.csv"
    menu_file = data_path / "menu.csv"

    RESTAURANTS.clear()
    ITEMS.clear()
    ITEMS_BY_RESTAURANT.clear()

    with restaurants_file.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rid = _clean(r.get("restaurant_id"))
            if not rid:
                continue
            prep = max(5, _to_int(r.get("prep_minutes"), 20))
            open_from = _minutes(r.get("open_from", ""), 0)
            open_to = _minutes(r.get("open_to", ""), 24 * 60)
            if open_to <= open_from:
                open_to += 24 * 60
            RESTAURANTS[rid] = Restaurant(
                id=rid,
                name=_clean(r.get("name")),
                lat=_to_float(r.get("latitude")),
                lon=_to_float(r.get("longitude")),
                rating=_to_float(r.get("catalogue_rating"), 4.0),
                prep_min=prep,
                prep_max=prep + 10,
                delivery_fee=_to_int(r.get("delivery_fee"), 30),
                radius_km=_to_float(r.get("radius_km"), 5.0) or 5.0,
                active=_bool(r.get("active")),
                category=_clean(r.get("category")),
                cuisine=_clean(r.get("cuisine")),
                address=_clean(r.get("address")),
                locality=_clean(r.get("locality")),
                price_level=_to_int(r.get("price_level"), 2),
                rating_count=_to_int(r.get("rating_count")),
                min_order=_to_int(r.get("min_order")),
                open_from=open_from,
                open_to=open_to,
                tags=_pipe(r.get("tags")),
                operator_chat_id=_clean(r.get("operator_chat_id")),
                operator_mode=_clean(r.get("operator_mode")),
            )
            ITEMS_BY_RESTAURANT[rid] = []

    with menu_file.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            item_id = _clean(r.get("menu_item_id"))
            rid = _clean(r.get("restaurant_id"))
            if not item_id or not rid:
                continue
            if rid not in RESTAURANTS:
                raise ValueError(f"menu item {item_id} has unknown restaurant {rid}")
            diet = _clean(r.get("diet")) or ("veg" if _bool(r.get("veg")) else "nonveg")
            item = Item(
                id=item_id,
                restaurant_id=rid,
                name=_clean(r.get("item_name")),
                aliases=_build_aliases(r.get("item_name"), _pipe(r.get("aliases"))),
                description=_clean(r.get("item_description")),
                category=_clean(r.get("category")),
                price=_to_int(r.get("price")),
                available=_bool(r.get("in_stock")) and _bool(r.get("active")),
                veg=diet == "veg",
                diet=diet,
                spice=_to_int(r.get("spice")),
                slots=_pipe(r.get("meal_slots")),
                tags=_pipe(r.get("tags")),
                allergens=_pipe(r.get("allergens")),
                calories=_to_int(r.get("calories")),
                prep_minutes=_to_int(r.get("prep_minutes")),
                restaurant_name=_clean(r.get("restaurant_name")),
            )
            ITEMS[item.id] = item
            ITEMS_BY_RESTAURANT[rid].append(item)

    return len(RESTAURANTS), len(ITEMS)


def localities() -> dict[str, tuple[float, float, int]]:
    """Neighbourhood -> (centre lat, centre lon, restaurant count), derived from the loaded catalogue."""
    acc: dict[str, list[float]] = {}
    for r in RESTAURANTS.values():
        if r.locality:
            a = acc.setdefault(r.locality, [0.0, 0.0, 0])
            a[0] += r.lat
            a[1] += r.lon
            a[2] += 1
    return {k: (v[0] / v[2], v[1] / v[2], int(v[2])) for k, v in acc.items()}


def get_restaurant(restaurant_id: str) -> Restaurant | None:
    return RESTAURANTS.get(restaurant_id)


def get_item(item_id: str) -> Item | None:
    return ITEMS.get(item_id)


def get_items_for_restaurant(restaurant_id: str) -> list[Item]:
    return ITEMS_BY_RESTAURANT.get(restaurant_id, [])
