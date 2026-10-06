"""Cheap-first cascade: rules, then (only if needed) the LLM, always ending in a validated FoodRequest."""
from __future__ import annotations

import re

from foodbot.concierge.intent import FoodRequest
from foodbot.concierge.llm import GroqClient, default_client
from foodbot.concierge.rules import CUISINE_WORDS, DISH_MAP, interpret_rules

_TOGETHER = re.compile(r"\b(?:and|with|plus|mattu|aur|saath)\b|\+")


def normalise_llm(req: FoodRequest, text: str) -> FoodRequest:
    """Deterministic clean-up of an LLM reading: catalogue vocabulary for dishes, 'together' detection."""
    mapped = []
    for phrase in req.dishes:
        words = [DISH_MAP.get(w, w) for w in phrase.split()]
        out = " ".join(w for w in words if w)
        if out:
            mapped.append(out)
    req.dishes = list(dict.fromkeys(mapped))
    if len(req.dishes) >= 2 and _TOGETHER.search(text.lower()) and " or " not in f" {text.lower()} ":
        req.combine = True
    if req.cuisine:                       # a cuisine the customer never mentioned would silently hide most of the menu
        words = {w for w, key in CUISINE_WORDS if key == req.cuisine} | {req.cuisine}
        if not any(w in text.lower() for w in words):
            req.cuisine = None
    if "tiffin" in req.dishes and not req.slot:
        req.slot = "breakfast"
    return req.clean()


def merge(llm: FoodRequest, rules: FoodRequest) -> FoodRequest:
    """Prefer the LLM's reading but keep numbers and constraints the rules extracted reliably when it left them blank."""
    if not llm.budget and rules.budget:
        llm.budget, llm.budget_scope = rules.budget, rules.budget_scope
    if llm.servings == 1 and rules.servings > 1:
        llm.servings = rules.servings
    if llm.quantity == 1 and rules.quantity > 1:
        llm.quantity = rules.quantity
    for field in ("exclude", "tags"):
        merged = list(dict.fromkeys(getattr(llm, field) + getattr(rules, field)))
        setattr(llm, field, merged)
    llm.diet = llm.diet or rules.diet
    if not llm.groups and rules.groups:
        llm.groups = rules.groups
    if llm.sort == "relevance":
        llm.sort = rules.sort
    llm.spice = llm.spice or rules.spice
    llm.slot = llm.slot or rules.slot
    return llm.clean()


async def understand(text: str, *, llm: GroqClient | None = None, allow_llm: bool = True) -> FoodRequest:
    """Rules first. The LLM is consulted only when the rules found nothing to search for."""
    rules = interpret_rules(text)
    if rules.intent != "order" or rules.has_target:
        return rules
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
