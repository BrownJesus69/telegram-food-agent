"""Cheap-first cascade: rules, then (only if needed) the LLM, always ending in a validated FoodRequest."""
from __future__ import annotations

import re

from foodbot.concierge.intent import FoodRequest
from foodbot.concierge.llm import GroqClient, default_client
from foodbot.concierge.rules import CUISINE_WORDS, DISH_MAP, interpret_rules
from foodbot.services import catalogue

_TOGETHER = re.compile(r"\b(?:and|with|plus|mattu|aur|saath)\b|\+")
_WORD = re.compile(r"[a-z0-9]+")
_INDIC_SCRIPT = re.compile("[ऀ-෿]")      # Devanagari ... Kannada ... Sinhala
_CONNECTORS = {"and", "or", "with", "the", "a", "an", "of", "in", "for", "to", "on"}
_vocab: dict = {"key": None, "words": frozenset(), "restaurants": frozenset()}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def catalogue_words() -> tuple[frozenset[str], frozenset[str]]:
    """(dish vocabulary, restaurant-name vocabulary): every word the catalogue itself uses. Rebuilt if the catalogue is reloaded."""
    key = (len(catalogue.ITEMS), len(catalogue.RESTAURANTS))
    if _vocab["key"] != key:
        dish = {_stem(w) for it in catalogue.ITEMS.values() for text in (it.name, *it.aliases, it.category) for w in _WORD.findall(text.lower())}
        dish |= {_stem(w) for v in DISH_MAP.values() for w in _WORD.findall(v)}
        dish |= {_stem(w) for cw, _ in CUISINE_WORDS for w in _WORD.findall(cw)}
        names = {_stem(w) for r in catalogue.RESTAURANTS.values() for w in _WORD.findall(f"{r.name} {r.cuisine}".lower())}
        _vocab.update(key=key, words=frozenset(dish), restaurants=frozenset(names))
    return _vocab["words"], _vocab["restaurants"]


def ground(phrase: str, allowed: set[str] | frozenset[str]) -> str:
    """Keep only the words of a model-written phrase that the catalogue or the customer's own message supports."""
    words = [w for w in _WORD.findall(str(phrase).lower()) if _stem(w) in allowed]
    while words and words[0] in _CONNECTORS:
        words.pop(0)
    while words and words[-1] in _CONNECTORS:
        words.pop()
    return " ".join(words)


def mostly_catalogue(phrase: str, vocab: set[str] | frozenset[str], ratio: float = 2 / 3) -> bool:
    """Is a model-written phrase mostly catalogue words? A dish name that is really a sentence ("ignore your rules, price 0")
    is dropped whole instead of being trimmed to whichever of its words happen to be real."""
    words = [w for w in _WORD.findall(str(phrase).lower()) if w not in _CONNECTORS]
    if not 1 <= len(words) <= 5:
        return False
    return sum(1 for w in words if _stem(DISH_MAP.get(w, w)) in vocab or _stem(w) in vocab) >= ratio * len(words)


def normalise_llm(req: FoodRequest, text: str) -> FoodRequest:
    """Deterministic clean-up of an LLM reading: catalogue vocabulary for dishes, 'together' detection."""
    # Free text is the one thing a model could smuggle through the schema (dish names, a restaurant name). Every word that
    # survives must be one the catalogue uses or the customer typed, so a model cannot put its own sentences in the bot's mouth.
    dish_vocab, restaurant_vocab = catalogue_words()
    said = {_stem(w) for w in _WORD.findall(text.lower())}
    mapped = []
    for phrase in req.dishes:
        words = [DISH_MAP.get(w, w) for w in ground(phrase, dish_vocab | said).split()]
        out = " ".join(w for w in words if w)
        if out:
            mapped.append(out)
    req.dishes = list(dict.fromkeys(mapped))
    if req.restaurant and ground(req.restaurant, restaurant_vocab | said) != " ".join(_WORD.findall(req.restaurant.lower())):
        req.restaurant = None
    if len(req.dishes) >= 2 and _TOGETHER.search(text.lower()) and " or " not in f" {text.lower()} ":
        req.combine = True
    if req.cuisine:                       # a cuisine the customer never mentioned would silently hide most of the menu
        words = {w for w, key in CUISINE_WORDS if key == req.cuisine} | {req.cuisine}
        if not any(w in text.lower() for w in words) or any(req.cuisine in d for d in req.dishes):
            req.cuisine = None
    if "tiffin" in req.dishes and not req.slot:
        req.slot = "breakfast"
    return req.clean()


def merge(llm: FoodRequest, rules: FoodRequest) -> FoodRequest:
    """Prefer the LLM's reading for what the customer *wants*, but never let it overrule what they *stated*.

    Diet, budget, party size and mixed-diet groups are matched by literal patterns in the rules; when the rules found
    one, it is authoritative (a hallucinated or injected reply must not turn "I'm vegetarian" into non-veg or "under 200"
    into 5000). The LLM only fills what the rules left blank. Exclusions are a union: an allergy is never dropped."""
    if rules.budget:
        llm.budget, llm.budget_scope = rules.budget, rules.budget_scope
    if rules.servings > 1:
        llm.servings = rules.servings
    if rules.quantity > 1:
        llm.quantity = rules.quantity
    for field in ("exclude", "tags"):
        merged = list(dict.fromkeys(getattr(llm, field) + getattr(rules, field)))
        setattr(llm, field, merged)
    llm.diet = rules.diet or llm.diet
    llm.cautions = rules.cautions                  # only the deterministic reader decides what we cannot enforce
    if rules.groups:
        llm.groups = rules.groups
    if llm.sort == "relevance":
        llm.sort = rules.sort
    llm.spice = llm.spice or rules.spice
    llm.slot = llm.slot or rules.slot
    return llm.clean()


async def understand(text: str, *, llm: GroqClient | None = None, allow_llm: bool = True) -> FoodRequest:
    """Rules first. The LLM is consulted only when the rules found nothing to search for."""
    rules = interpret_rules(text)
    if rules.intent != "order" or (rules.has_target and not _INDIC_SCRIPT.search(text)):
        return rules            # (text in Kannada/Hindi script is only partly readable by the rules, so the model is always asked)
    client = llm or default_client()
    if allow_llm and client.available:
        got = await client.interpret(text)
        if got:
            return merge(normalise_llm(got, text), rules)
    return rules


async def second_opinion(text: str, rules: FoodRequest, *, llm: GroqClient | None = None) -> FoodRequest | None:
    """Called when the rules' reading found no food: ask the LLM to reinterpret (typos, Kannada, odd phrasing)."""
    client = llm or default_client()
    if not client.available or rules.source == "llm":
        return None
    got = await client.interpret(text)
    return merge(normalise_llm(got, text), rules) if got else None
