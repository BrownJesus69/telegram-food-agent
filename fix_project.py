from pathlib import Path
import shutil
import textwrap

ROOT = Path(__file__).resolve().parent

search_py = ROOT / "services" / "search.py"
handlers_py = ROOT / "handlers.py"

if not search_py.exists():
    raise SystemExit("services/search.py not found")
if not handlers_py.exists():
    raise SystemExit("handlers.py not found")

shutil.copy2(search_py, search_py.with_suffix(".py.bak"))
shutil.copy2(handlers_py, handlers_py.with_name("handlers.py.bak_absolute"))

SEARCH_CODE = textwrap.dedent('''
from __future__ import annotations

from dataclasses import dataclass
from typing import List
import re

from services import catalogue
from services.distance import haversine_km
from services.eta import estimate_eta


GENERIC_ITEM_NAMES = {
    "veg meal",
    "chicken meal",
    "paneer starter",
    "soft drink",
    "dessert cup",
    "cappuccino",
    "cold coffee",
    "brownie",
    "fruit bowl",
    "lime soda",
    "filter coffee",
}

STOPWORDS = {
    "i", "am", "hungry", "want", "need", "would", "like", "to", "eat",
    "give", "me", "show", "find", "near", "nearby", "within", "under",
    "below", "less", "than", "rs", "rupees", "price", "budget", "please",
    "a", "an", "the", "and", "with", "for", "some"
}


@dataclass
class SearchResult:
    item: object
    restaurant: object
    distance_km: float
    eta_min: int
    eta_max: int
    score: float


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\\s]", " ", s)
    s = re.sub(r"\\s+", " ", s).strip()
    return s


def _tokens(s: str) -> list[str]:
    return [t for t in _norm(s).split() if t and t not in STOPWORDS and not t.isdigit()]


def _meaningful_query_tokens(query_text: str) -> list[str]:
    toks = _tokens(query_text)
    budget_words = {"under", "within", "below", "max"}
    return [t for t in toks if t not in budget_words]


def _is_generic_template_item(item_name: str, item_desc: str = "", category: str = "") -> bool:
    n = _norm(item_name)
    if n in GENERIC_ITEM_NAMES:
        return True

    generic_fragments = [
        "balanced vegetarian meal",
        "complete chicken meal",
        "chef special dessert",
        "chilled beverage",
        "freshly brewed cappuccino",
        "grilled veg sandwich",
        "creamy alfredo pasta",
        "classic chicken shawarma wrap",
        "chargrilled kebab platter",
    ]
    hay = " ".join([_norm(item_name), _norm(item_desc), _norm(category)])
    return any(g in hay for g in generic_fragments)


def _match_score(query_text: str, item) -> float:
    qnorm = _norm(query_text)
    inorm = _norm(getattr(item, "name", ""))
    desc = _norm(getattr(item, "description", ""))
    cat = _norm(getattr(item, "category", ""))

    qtoks = _meaningful_query_tokens(query_text)
    if not qtoks:
        return 0.0

    text_pool = " ".join([inorm, desc, cat]).strip()
    item_toks = set(_tokens(text_pool))

    overlap = sum(1 for t in qtoks if t in item_toks)
    if overlap == 0:
        return 0.0

    score = 0.0

    if qnorm == inorm:
        score += 120.0
    if qnorm and qnorm in inorm:
        score += 80.0

    for t in qtoks:
        if t == inorm:
            score += 60.0
        elif t in inorm:
            score += 25.0
        elif t in desc:
            score += 10.0
        elif t in cat:
            score += 6.0

    score += overlap * 20.0

    if len(qtoks) >= 2:
        consecutive = " ".join(qtoks)
        if consecutive in inorm:
            score += 40.0

    return score


def search_items(
    query_text: str,
    user_lat: float,
    user_lon: float,
    budget: int | None = None,
    limit: int = 5,
    max_distance_km: float = 6.0,
    veg_only: bool = False,
) -> List[SearchResult]:
    results: list[SearchResult] = []
    seen_pairs = set()

    qtoks = _meaningful_query_tokens(query_text)
    if not qtoks:
        return []

    for item in catalogue.ITEMS.values():
        rest = catalogue.RESTAURANTS.get(getattr(item, "restaurant_id", None))
        if not rest:
            continue

        if not getattr(item, "active", 1):
            continue
        if not getattr(item, "in_stock", 1):
            continue
        if not getattr(rest, "active", 1):
            continue
        if veg_only and not getattr(item, "veg", False):
            continue

        price = int(getattr(item, "price", 0) or 0)
        if budget is not None and price > budget:
            continue

        if _is_generic_template_item(
            getattr(item, "name", ""),
            getattr(item, "description", ""),
            getattr(item, "category", ""),
        ):
            continue

        score = _match_score(query_text, item)
        if score <= 0:
            continue

        dist = haversine_km(
            user_lat, user_lon,
            float(getattr(rest, "latitude")),
            float(getattr(rest, "longitude")),
        )
        if dist > max_distance_km:
            continue

        pair_key = (
            _norm(getattr(item, "name", "")),
            _norm(getattr(rest, "name", "")),
            round(dist, 2),
        )
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        eta_min, eta_max = estimate_eta(
            prep_minutes=int(getattr(rest, "prepminutes", 25) or 25),
            distance_km=dist,
        )

        rating = float(getattr(rest, "rating", 4.0) or 4.0)
        final_score = score + (rating * 3.0) - (dist * 2.5)

        results.append(
            SearchResult(
                item=item,
                restaurant=rest,
                distance_km=dist,
                eta_min=eta_min,
                eta_max=eta_max,
                score=final_score,
            )
        )

    results.sort(
        key=lambda r: (-r.score, r.distance_km, int(getattr(r.item, "price", 0) or 0))
    )
    return results[:limit]
''').strip() + "\n"

HANDLERS_PATCH = textwrap.dedent('''
from pathlib import Path
p = Path("handlers.py")
text = p.read_text(encoding="utf-8")

if "def result_text(r):" in text:
    start = text.find("def result_text(r):")
    markers = [
        pos for pos in [
            text.find("\\n@router", start + 1),
            text.find("\\nasync def ", start + 1),
            text.find("\\ndef ", start + 1),
        ] if pos != -1
    ]
    end = min(markers) if markers else len(text)
    new_func = """def result_text(r):
    it, rest = r.item, r.restaurant
    veg_label = "Veg" if getattr(it, "veg", False) else "Non-veg"
    return (
        f"{it.name} — {rest.name}\\n"
        f"Price: ₹{it.price}\\n"
        f"Rating: {float(getattr(rest, 'rating', 4.0)):.1f}\\n"
        f"Distance: {r.distance_km:.2f} km\\n"
        f"ETA: {r.eta_min}-{r.eta_max} min\\n"
        f"Category: {it.category}\\n"
        f"Type: {veg_label}"
    )

"""
    text = text[:start] + new_func + text[end:]

text = text.replace('r["item"].id', 'r.item.id')
text = text.replace('r["item"]', 'r.item')
text = text.replace('r["rest"]', 'r.restaurant')
text = text.replace('r["restaurant"]', 'r.restaurant')
text = text.replace('r["distance_km"]', 'r.distance_km')
text = text.replace('r["eta_min"]', 'r.eta_min')
text = text.replace('r["eta_max"]', 'r.eta_max')
text = text.replace('r["score"]', 'r.score')
text = text.replace('r.restaurantaurant', 'r.restaurant')
text = text.replace('it, rest = r.item, r.rest', 'it, rest = r.item, r.restaurant')
text = text.replace('it, rest = r.item, r.restaurantaurant', 'it, rest = r.item, r.restaurant')

p.write_text(text, encoding="utf-8", newline="\\n")
print("handlers.py patched")
''').strip() + "\n"

search_py.write_text(SEARCH_CODE, encoding="utf-8", newline="\n")

tmp_patch = ROOT / "_patch_handlers_once.py"
tmp_patch.write_text(HANDLERS_PATCH, encoding="utf-8", newline="\n")

print("=" * 80)
print("Patched services/search.py with strict non-generic search")
print("Now patching handlers.py")
print("=" * 80)

exec(compile(tmp_patch.read_text(encoding="utf-8"), str(tmp_patch), "exec"), {})

tmp_patch.unlink(missing_ok=True)

print("=" * 80)
print("ABSOLUTE FIX COMPLETE")
print("Backups created:")
print(" - services/search.py.bak")
print(" - handlers.py.bak_absolute")
print("=" * 80)
print("Next run:")
print("  python .\\\\app.py")