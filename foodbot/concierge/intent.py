"""The structured request the concierge works with.

Both interpreters (rules and LLM) produce a `FoodRequest`. Nothing the LLM says reaches the catalogue except
through this schema: every field is an enum, a bounded number or a short list of vocabulary words, and
`FoodRequest.clean()` coerces or drops anything else. That is the "LLM proposes, code disposes" boundary.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

INTENTS = ("order", "menu", "address", "cart", "greeting", "other")
SLOTS = ("breakfast", "lunch", "snack", "dinner", "latenight")
DIETS = ("veg", "egg", "nonveg")
SPICES = ("mild", "medium", "hot")
SORTS = ("relevance", "cheapest", "fastest", "top_rated", "nearest")
SCOPES = ("item", "total", "per_person")
LANGS = ("en", "hi", "kn", "mixed")
# allergen names match the catalogue's `allergens` column; onion-garlic maps to the Jain-friendly tag
EXCLUDES = ("dairy", "gluten", "nuts", "peanut", "egg", "fish", "soy", "sesame", "onion-garlic")
TAGS = ("sweet", "healthy", "light", "high-protein", "comfort", "street-food", "festive", "kids-fav", "vegan", "bestseller")
CUISINES = (
    "south indian", "north indian", "chinese", "italian", "continental", "arabian", "mughlai", "kerala", "coastal",
    "andhra", "hyderabadi", "tibetan", "asian", "bengali", "gujarati", "street food", "cafe", "bakery", "dessert",
    "biryani", "pizza", "burger", "healthy",
)

_DIET_ALIASES = {"non_veg": "nonveg", "non-veg": "nonveg", "non veg": "nonveg", "vegetarian": "veg", "eggetarian": "egg"}


@dataclass
class Group:
    diet: str
    count: int


@dataclass
class FoodRequest:
    intent: str = "order"
    dishes: list[str] = field(default_factory=list)
    cuisine: str | None = None
    slot: str | None = None
    diet: str | None = None
    exclude: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    spice: str | None = None
    budget: int | None = None
    budget_scope: str = "item"
    servings: int = 1
    quantity: int = 1
    groups: list[Group] = field(default_factory=list)
    sort: str = "relevance"
    combine: bool = False            # dishes are meant to be ordered together (e.g. "dosa and filter coffee")
    restaurant: str | None = None
    language: str | None = None
    cautions: list[str] = field(default_factory=list)      # constraints the customer stated that we cannot enforce (set by the rules, never by a model)
    raw: str = ""
    source: str = "rules"

    # ------------------------------------------------------------------ helpers
    @property
    def has_target(self) -> bool:
        """Did we learn *what* the customer wants (as opposed to only how)?"""
        return bool(self.dishes or self.cuisine or self.tags or self.slot or self.groups)

    def clean(self) -> FoodRequest:
        """Coerce every field into its allowed vocabulary; drop what doesn't fit. Idempotent."""
        self.intent = self.intent if self.intent in INTENTS else "order"
        self.dishes = _dedupe([_short(d) for d in self.dishes if _short(d)])[:4]
        self.cuisine = _pick(self.cuisine, CUISINES)
        self.slot = _pick(self.slot, SLOTS)
        diet = _DIET_ALIASES.get(_text(self.diet), _text(self.diet))
        self.diet = diet if diet in DIETS else None
        self.exclude = [e for e in _dedupe(_lower(self.exclude)) if e in EXCLUDES]
        if self.diet == "egg" and "egg" in self.exclude:        # "no egg" is an allergy, not "egg only": the allergy wins
            self.diet = None
        self.tags = [t for t in _dedupe(_lower(self.tags)) if t in TAGS]
        spice = _text(self.spice)
        self.spice = spice if spice in SPICES else None
        self.budget = _bounded(self.budget, 20, 20_000)
        self.budget_scope = self.budget_scope if self.budget_scope in SCOPES else "item"
        self.servings = _bounded(self.servings, 1, 20) or 1
        self.quantity = _bounded(self.quantity, 1, 10) or 1
        groups = []
        for g in self.groups if isinstance(self.groups, (list, tuple)) else []:
            d = g.diet if isinstance(g, Group) else g.get("diet") if isinstance(g, dict) else None
            c = g.count if isinstance(g, Group) else g.get("count") if isinstance(g, dict) else None
            d = _DIET_ALIASES.get(_text(d), _text(d))
            c = _bounded(c, 1, 20)
            if d in DIETS and c:
                groups.append(Group(d, c))
        self.groups = groups if len({g.diet for g in groups}) >= 2 else []      # a "group" needs two diets to mean anything
        if self.groups:
            self.servings = max(self.servings, sum(g.count for g in self.groups))
        self.sort = self.sort if self.sort in SORTS else "relevance"
        self.combine = bool(self.combine) and len(self.dishes) >= 2
        self.restaurant = _short(self.restaurant) or None
        self.cautions = [c for c in _dedupe(_lower(self.cautions)) if re.fullmatch(r"[a-z0-9][a-z0-9 \-]{1,29}", c)][:3]
        self.language = self.language if self.language in LANGS else None
        if self.budget and self.servings > 1 and self.budget_scope == "item":
            self.budget_scope = "total"
        return self

    def describe(self) -> str:
        """Human-readable echo of what we understood, shown to the customer so they can verify it."""
        bits = []
        if self.dishes:
            bits.append((" + " if self.combine else ", ").join(self.dishes))
        if self.cuisine and not any(self.cuisine in d for d in self.dishes):
            bits.append(self.cuisine.title())
        if self.groups:
            bits.append(" + ".join(f"{g.count} {'non-veg' if g.diet == 'nonveg' else g.diet}" for g in self.groups))
        elif self.diet:
            bits.append({"veg": "veg", "egg": "egg", "nonveg": "non-veg"}[self.diet])
        if self.slot:
            bits.append({"latenight": "late night"}.get(self.slot, self.slot))
        bits += self.tags
        if self.spice:
            bits.append(f"{self.spice} spice")
        if self.servings > 1:
            bits.append(f"for {self.servings}")
        elif self.quantity > 1:
            bits.append(f"×{self.quantity}")
        if self.budget:
            scope = {"item": "per item", "total": "total", "per_person": "per person"}[self.budget_scope]
            bits.append(f"under ₹{self.budget} {scope}")
        if self.exclude:
            bits.append("no " + "/".join(self.exclude))
        if self.sort != "relevance":
            bits.append({"cheapest": "cheapest first", "fastest": "fastest first", "top_rated": "top rated", "nearest": "nearest"}[self.sort])
        return " · ".join(bits) or "anything good"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


# ------------------------------------------------------------------------------ utils
def _short(s) -> str:
    if isinstance(s, (list, tuple, dict, set)):          # a container is never a dish or restaurant name
        return ""
    return re.sub(r"\s+", " ", str(s or "")).lower()[:60].strip()


def _text(value) -> str:
    """A lower-cased string, or '' for anything that is not text (a list or number from a hostile reply)."""
    return value.strip().lower() if isinstance(value, str) else ""


def _lower(xs) -> list[str]:
    if not isinstance(xs, (list, tuple)):
        return []
    return [str(x).strip().lower() for x in xs if str(x).strip()]


def _dedupe(xs):
    return list(dict.fromkeys(xs))


def _pick(value, allowed):
    v = _short(value)
    return v if v in allowed else None


def _bounded(value, lo, hi):
    try:
        n = int(float(value))
    except (TypeError, ValueError, OverflowError):          # None, "abc", a list, NaN, infinity
        return None
    return max(lo, min(hi, n)) if n else None


def from_dict(data: dict, *, raw: str = "", source: str = "llm") -> FoodRequest:
    """Build a request from untrusted JSON (e.g. an LLM reply). Unknown keys are ignored, bad values dropped."""
    data = data if isinstance(data, dict) else {}
    raw_groups = data.get("groups")
    groups = [Group(g.get("diet", ""), g.get("count", 0)) for g in (raw_groups if isinstance(raw_groups, (list, tuple)) else []) if isinstance(g, dict)]
    dishes = data.get("dishes")
    if isinstance(dishes, str):
        dishes = [dishes]
    req = FoodRequest(
        intent=str(data.get("intent") or "order"),
        dishes=list(dishes or []) if isinstance(dishes, (list, tuple)) else [],
        cuisine=data.get("cuisine"), slot=data.get("slot"), diet=data.get("diet"),
        exclude=list(data.get("exclude") or []) if isinstance(data.get("exclude"), (list, tuple)) else [],
        tags=list(data.get("tags") or []) if isinstance(data.get("tags"), (list, tuple)) else [],
        spice=data.get("spice"), budget=data.get("budget"), budget_scope=str(data.get("budget_scope") or "item"),
        servings=data.get("servings") or 1, quantity=data.get("quantity") or 1, groups=groups,
        sort=str(data.get("sort") or "relevance"), combine=bool(data.get("combine")), restaurant=data.get("restaurant"), language=data.get("language"),
        raw=raw, source=source,
    ).clean()
    if req.intent == "other" and req.has_target:         # "kuch meetha chahiye" is an order, whatever label the model chose
        req.intent = "order"
    return req
